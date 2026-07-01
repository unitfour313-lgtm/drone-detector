"""Multi-object tracking module."""

import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict
import numpy as np
from scipy.spatial.distance import cdist
from scipy.optimize import linear_sum_assignment

logger = logging.getLogger(__name__)

class Tracker:
    """Simple Kalman filter-based object."""
    
    def __init__(self, track_id: int, initial_bbox: List[float], initial_class: str, max_age: int = 30):
        """Initialize tracker.
        
        Args:
            track_id: Unique track ID
            initial_bbox: Initial bounding box [x1, y1, x2, y2]
            initial_class: Object class name
            max_age: Maximum frames without detection before track is deleted
        """
        self.track_id = track_id
        self.class_name = initial_class
        self.bbox = np.array(initial_bbox)
        self.center = self._bbox_to_center(initial_bbox)
        self.velocity = np.array([0.0, 0.0])
        self.age = 0
        self.time_since_update = 0
        self.max_age = max_age
        self.hits = 1
        self.history = [self.bbox.copy()]
    
    def _bbox_to_center(self, bbox: List[float]) -> np.ndarray:
        """Convert bbox to center point."""
        x1, y1, x2, y2 = bbox
        return np.array([(x1 + x2) / 2, (y1 + y2) / 2])
    
    def predict(self):
        """Predict next position using Kalman filter."""
        self.age += 1
        self.time_since_update += 1
        self.center = self.center + self.velocity
    
    def update(self, detection: Dict[str, Any]):
        """Update track with new detection.
        
        Args:
            detection: Detection dict with 'bbox' and 'class_name'
        """
        self.time_since_update = 0
        self.hits += 1
        
        new_bbox = np.array(detection['bbox'])
        new_center = self._bbox_to_center(detection['bbox'])
        
        # Update velocity estimate
        self.velocity = 0.7 * self.velocity + 0.3 * (new_center - self.center)
        
        self.center = new_center
        self.bbox = new_bbox
        self.history.append(self.bbox.copy())
        
        # Keep only recent history
        if len(self.history) > 50:
            self.history = self.history[-50:]
    
    def is_active(self) -> bool:
        """Check if track is still active."""
        return self.time_since_update < self.max_age
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'track_id': self.track_id,
            'class_name': self.class_name,
            'bbox': self.bbox.tolist(),
            'center': self.center.tolist(),
            'age': self.age,
            'hits': self.hits,
            'confidence': min(1.0, self.hits / 10.0)  # Confidence based on hit count
        }


class ObjectTracker:
    """Multi-object tracker using Kalman filtering and Hungarian algorithm."""
    
    def __init__(self, max_age: int = 30, max_distance: float = 50.0):
        """Initialize tracker.
        
        Args:
            max_age: Maximum frames without detection before track is deleted
            max_distance: Maximum distance for associating detections to tracks
        """
        self.max_age = max_age
        self.max_distance = max_distance
        self.tracks: Dict[int, Tracker] = {}
        self.next_track_id = 1
        self.frame_count = 0
    
    def update(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Update tracks with new detections.
        
        Args:
            detections: List of detection dicts
            
        Returns:
            List of active tracked objects
        """
        self.frame_count += 1
        
        # Predict new positions for existing tracks
        for track in self.tracks.values():
            track.predict()
        
        # Associate detections to tracks
        matched_indices, unmatched_detections, unmatched_tracks = self._match_detections(detections)
        
        # Update matched tracks
        for track_idx, det_idx in matched_indices:
            self.tracks[track_idx].update(detections[det_idx])
        
        # Create new tracks for unmatched detections
        for det_idx in unmatched_detections:
            detection = detections[det_idx]
            self.tracks[self.next_track_id] = Tracker(
                track_id=self.next_track_id,
                initial_bbox=detection['bbox'],
                initial_class=detection['class_name'],
                max_age=self.max_age
            )
            self.next_track_id += 1
        
        # Remove inactive tracks
        inactive_tracks = [track_id for track_id, track in self.tracks.items() if not track.is_active()]
        for track_id in inactive_tracks:
            del self.tracks[track_id]
        
        # Return active tracks
        active_tracks = [track.to_dict() for track in self.tracks.values()]
        return active_tracks
    
    def _match_detections(self, detections: List[Dict[str, Any]]):
        """Match detections to existing tracks using Hungarian algorithm.
        
        Returns:
            (matched_indices, unmatched_detections, unmatched_tracks)
        """
        if not self.tracks or not detections:
            return [], list(range(len(detections))), list(self.tracks.keys())
        
        # Get track centers
        track_ids = list(self.tracks.keys())
        track_centers = np.array([self.tracks[tid].center for tid in track_ids])
        
        # Get detection centers
        det_centers = np.array([self._get_det_center(det) for det in detections])
        
        # Compute distance matrix
        distances = cdist(track_centers, det_centers, metric='euclidean')
        
        # Apply Hungarian algorithm
        track_indices, det_indices = linear_sum_assignment(distances)
        
        # Filter matches by maximum distance
        matched_indices = []
        for t_idx, d_idx in zip(track_indices, det_indices):
            if distances[t_idx, d_idx] <= self.max_distance:
                matched_indices.append((track_ids[t_idx], d_idx))
        
        # Find unmatched detections and tracks
        matched_det_indices = set(d_idx for _, d_idx in matched_indices)
        matched_track_indices = set(track_ids[t_idx] for t_idx, _ in zip(track_indices, det_indices) if distances[t_idx, d_idx] <= self.max_distance for d_idx in [det_indices[list(track_indices).index(t_idx)]])
        
        unmatched_detections = [i for i in range(len(detections)) if i not in matched_det_indices]
        unmatched_tracks = [tid for tid in track_ids if tid not in matched_track_indices]
        
        return matched_indices, unmatched_detections, unmatched_tracks
    
    @staticmethod
    def _get_det_center(detection: Dict[str, Any]) -> np.ndarray:
        """Get center from detection dict."""
        x1, y1, x2, y2 = detection['bbox']
        return np.array([(x1 + x2) / 2, (y1 + y2) / 2])
    
    def get_active_tracks(self) -> List[Dict[str, Any]]:
        """Get all active tracks."""
        return [track.to_dict() for track in self.tracks.values() if track.is_active()]
    
    def get_track_history(self, track_id: int) -> Optional[List[List[float]]]:
        """Get history for specific track."""
        if track_id in self.tracks:
            return self.tracks[track_id].history
        return None
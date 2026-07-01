"""YOLO-based drone detection module."""

import logging
from typing import List, Dict, Any, Optional

import cv2
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)

class DroneDetector:
    """Drone detection using YOLOv8."""
    
    # Thermal-specific object classes
    THERMAL_CLASSES = {
        'drone': 0,
        'aircraft': 1,
        'bird': 2,
        'helicopter': 3,
    }
    
    def __init__(
        self,
        model_name: str = "yolov8m",
        confidence_threshold: float = 0.5,
        target_classes: Optional[List[str]] = None
    ):
        """Initialize detector.
        
        Args:
            model_name: YOLO model size (nano, small, medium, large, xlarge)
            confidence_threshold: Detection confidence threshold
            target_classes: Classes to detect (None = all)
        """
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.target_classes = target_classes or ['drone', 'aircraft']
        
        try:
            logger.info(f"Loading YOLO model: {model_name}")
            self.model = YOLO(f"{model_name}.pt")
            self.model.to('cpu')  # Use CPU, GPU support can be added
            logger.info("✓ YOLO model loaded")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
    
    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect objects in frame.
        
        Args:
            frame: Input frame (BGR format)
            
        Returns:
            List of detections with format:
            [
                {
                    'class_name': str,
                    'confidence': float,
                    'bbox': [x_min, y_min, x_max, y_max],
                    'center': (x, y),
                    'area': float
                },
                ...
            ]
        """
        try:
            # Run inference
            results = self.model(frame, conf=self.confidence_threshold, verbose=False)
            
            detections = []
            
            if results and len(results) > 0:
                result = results[0]
                
                if result.boxes is not None:
                    for box in result.boxes:
                        # Extract box coordinates
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = float(box.conf[0].cpu().numpy())
                        cls_id = int(box.cls[0].cpu().numpy())
                        
                        # Get class name
                        class_name = result.names[cls_id]
                        
                        # Filter by target classes if specified
                        if self.target_classes and class_name.lower() not in self.target_classes:
                            continue
                        
                        # Calculate additional properties
                        center_x = (x1 + x2) / 2
                        center_y = (y1 + y2) / 2
                        area = (x2 - x1) * (y2 - y1)
                        
                        detection = {
                            'class_name': class_name,
                            'confidence': conf,
                            'bbox': [float(x1), float(y1), float(x2), float(y2)],
                            'center': (float(center_x), float(center_y)),
                            'area': float(area),
                            'class_id': cls_id
                        }
                        detections.append(detection)
            
            return detections
            
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []
    
    def detect_with_visualization(
        self,
        frame: np.ndarray,
        detections: Optional[List[Dict[str, Any]]] = None
    ) -> np.ndarray:
        """Detect objects and return frame with visualizations.
        
        Args:
            frame: Input frame
            detections: Pre-computed detections (optional)
            
        Returns:
            Frame with bounding boxes and labels
        """
        if detections is None:
            detections = self.detect(frame)
        
        vis_frame = frame.copy()
        
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            conf = det['confidence']
            class_name = det['class_name']
            
            # Draw bounding box
            color = (0, 255, 0) if conf > 0.7 else (0, 165, 255)
            cv2.rectangle(vis_frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"{class_name} {conf:.2f}"
            cv2.putText(
                vis_frame,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2
            )
        
        return vis_frame
    
    def update_confidence_threshold(self, new_threshold: float):
        """Update confidence threshold.
        
        Args:
            new_threshold: New confidence threshold (0-1)
        """
        if 0 <= new_threshold <= 1:
            self.confidence_threshold = new_threshold
            logger.info(f"Confidence threshold updated to {new_threshold}")
        else:
            logger.warning(f"Invalid threshold value: {new_threshold}")
    
    def set_target_classes(self, classes: List[str]):
        """Set target detection classes.
        
        Args:
            classes: List of class names to detect
        """
        self.target_classes = classes
        logger.info(f"Target classes updated to {classes}")


class ThermalEnhancer:
    """Enhance thermal images for better detection."""
    
    @staticmethod
    def apply_histogram_equalization(frame: np.ndarray) -> np.ndarray:
        """Apply histogram equalization."""
        # Convert to LAB color space
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Equalize L channel
        l = cv2.equalizeHist(l)
        
        # Merge and convert back
        lab = cv2.merge([l, a, b])
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        return result
    
    @staticmethod
    def apply_clahe(frame: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
        """Apply Contrast Limited Adaptive Histogram Equalization."""
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        l = clahe.apply(l)
        
        lab = cv2.merge([l, a, b])
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        return result
    
    @staticmethod
    def apply_bilateral_filter(frame: np.ndarray, d: int = 9) -> np.ndarray:
        """Apply bilateral filtering to reduce noise."""
        return cv2.bilateralFilter(frame, d, 75, 75)
    
    @staticmethod
    def denoise(frame: np.ndarray) -> np.ndarray:
        """Apply denoising."""
        return cv2.fastNlMeansDenoisingColored(frame, None, h=10, hForColorComponents=10, templateWindowSize=7, searchWindowSize=21)
    
    @staticmethod
    def preprocess_thermal(frame: np.ndarray) -> np.ndarray:
        """Complete preprocessing pipeline for thermal images."""
        # Denoise
        frame = ThermalEnhancer.denoise(frame)
        
        # Apply CLAHE
        frame = ThermalEnhancer.apply_clahe(frame)
        
        # Apply bilateral filter
        frame = ThermalEnhancer.apply_bilateral_filter(frame)
        
        return frame
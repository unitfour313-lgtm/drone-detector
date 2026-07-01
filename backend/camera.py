"""Uniview thermal camera interface."""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any

import cv2
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

class UniviewCamera:
    """Interface for Uniview thermal camera via RTSP."""
    
    def __init__(self, config_path: str = "config/camera_config.yaml"):
        """Initialize camera connection.
        
        Args:
            config_path: Path to camera configuration file
        """
        self.config = self._load_config(config_path)
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_connected = False
        self.width = 0
        self.height = 0
        self.fps = 0
        self.last_frame_time: Optional[datetime] = None
        self._frame_buffer = None
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load camera configuration."""
        import yaml
        
        default_config = {
            'ip': '192.168.1.100',
            'port': 554,
            'username': 'admin',
            'password': 'password',
            'rtsp_path': '/stream',
            'timeout': 10,
        }
        
        if Path(config_path).exists():
            with open(config_path) as f:
                config = yaml.safe_load(f)
                if config and 'camera' in config:
                    default_config.update(config['camera'])
        
        return default_config
    
    def _build_rtsp_url(self) -> str:
        """Build RTSP URL from configuration."""
        username = self.config.get('username')
        password = self.config.get('password')
        ip = self.config.get('ip')
        port = self.config.get('port')
        path = self.config.get('rtsp_path')
        
        if username and password:
            return f"rtsp://{username}:{password}@{ip}:{port}{path}"
        else:
            return f"rtsp://{ip}:{port}{path}"
    
    async def connect(self) -> bool:
        """Connect to camera."""
        try:
            rtsp_url = self._build_rtsp_url()
            logger.info(f"Connecting to camera: {rtsp_url}")
            
            self.cap = cv2.VideoCapture(rtsp_url)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Try to read a frame to verify connection
            ret, frame = self.cap.read()
            if not ret:
                logger.error("Failed to read frame from camera")
                self.cap.release()
                self.cap = None
                return False
            
            self.is_connected = True
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(f"✓ Connected to camera: {self.width}x{self.height} @ {self.fps} FPS")
            return True
            
        except Exception as e:
            logger.error(f"Camera connection error: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from camera."""
        if self.cap:
            self.cap.release()
            self.cap = None
        self.is_connected = False
        logger.info("Camera disconnected")
    
    async def get_frame(self) -> Optional[np.ndarray]:
        """Get current frame from camera."""
        if not self.is_connected or not self.cap:
            return None
        
        try:
            ret, frame = self.cap.read()
            if ret:
                self.last_frame_time = datetime.utcnow()
                self._frame_buffer = frame
                return frame
            else:
                logger.warning("Failed to read frame")
                # Try to reconnect
                await self.connect()
                return None
        except Exception as e:
            logger.error(f"Error reading frame: {e}")
            return None
    
    async def get_mjpeg_frame(self) -> bytes:
        """Get frame as MJPEG bytes."""
        frame = await self.get_frame()
        if frame is None:
            return b''
        
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            return (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n'
                b'Content-Length: ' + str(len(buffer)).encode() + b'\r\n\r\n'
                + buffer.tobytes() + b'\r\n'
            )
        return b''
    
    async def ptz_control(
        self,
        pan: Optional[float] = None,
        tilt: Optional[float] = None,
        zoom: Optional[float] = None
    ):
        """Control pan, tilt, zoom.
        
        Args:
            pan: -1 (left) to 1 (right)
            tilt: -1 (down) to 1 (up)
            zoom: -1 (zoom out) to 1 (zoom in)
        """
        if not self.is_connected:
            logger.warning("Camera not connected")
            return
        
        try:
            # PTZ control implementation would go here
            # This depends on camera's specific API
            logger.info(f"PTZ control: pan={pan}, tilt={tilt}, zoom={zoom}")
        except Exception as e:
            logger.error(f"PTZ control error: {e}")
    
    async def take_snapshot(self, filepath: str):
        """Save a snapshot."""
        frame = self._frame_buffer
        if frame is not None:
            cv2.imwrite(filepath, frame)
            logger.info(f"Snapshot saved to {filepath}")


class MockCamera:
    """Mock camera for testing without hardware."""
    
    def __init__(self):
        """Initialize mock camera."""
        self.is_connected = True
        self.width = 640
        self.height = 480
        self.fps = 30
        self.last_frame_time = datetime.utcnow()
        self.frame_count = 0
    
    async def connect(self) -> bool:
        """Connect to mock camera."""
        return True
    
    async def disconnect(self):
        """Disconnect from mock camera."""
        pass
    
    async def get_frame(self) -> np.ndarray:
        """Get synthetic frame."""
        # Create a simple thermal-like image
        frame = np.random.randint(50, 200, (self.height, self.width, 3), dtype=np.uint8)
        
        # Add some synthetic hot spots
        for _ in range(3):
            x = np.random.randint(100, self.width - 100)
            y = np.random.randint(100, self.height - 100)
            cv2.circle(frame, (x, y), 30, (200, 150, 50), -1)
        
        self.frame_count += 1
        self.last_frame_time = datetime.utcnow()
        return frame
    
    async def get_mjpeg_frame(self) -> bytes:
        """Get synthetic frame as MJPEG."""
        frame = await self.get_frame()
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            return (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n'
                b'Content-Length: ' + str(len(buffer)).encode() + b'\r\n\r\n'
                + buffer.tobytes() + b'\r\n'
            )
        return b''
    
    async def ptz_control(
        self,
        pan: Optional[float] = None,
        tilt: Optional[float] = None,
        zoom: Optional[float] = None
    ):
        """Mock PTZ control."""
        logger.info(f"[MOCK] PTZ: pan={pan}, tilt={tilt}, zoom={zoom}")
    
    async def take_snapshot(self, filepath: str):
        """Save mock snapshot."""
        frame = await self.get_frame()
        cv2.imwrite(filepath, frame)
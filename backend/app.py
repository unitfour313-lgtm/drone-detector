"""FastAPI application for drone detection system."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from camera import UniviewCamera
from detector import DroneDetector
from tracker import ObjectTracker
from database import Database, Detection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Pydantic Models
# ============================================================================

class DetectionResult(BaseModel):
    """Detection result model."""
    id: int
    timestamp: datetime
    object_type: str
    confidence: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    track_id: Optional[int] = None

class CameraStatus(BaseModel):
    """Camera status model."""
    connected: bool
    ip: str
    resolution: str
    fps: float
    last_frame_time: Optional[datetime] = None

class PTZCommand(BaseModel):
    """Pan-Tilt-Zoom command."""
    pan: Optional[float] = None  # -1 to 1
    tilt: Optional[float] = None  # -1 to 1
    zoom: Optional[float] = None  # -1 to 1

class AlertConfig(BaseModel):
    """Alert configuration."""
    enabled: bool
    confidence_threshold: float
    email_recipients: Optional[List[str]] = None
    webhook_url: Optional[str] = None

class StatsResponse(BaseModel):
    """Statistics response."""
    total_detections: int
    detections_today: int
    unique_tracks: int
    average_confidence: float
    detection_frequency: str  # detections per hour

# ============================================================================
# Global State
# ============================================================================

camera: Optional[UniviewCamera] = None
detector: Optional[DroneDetector] = None
tracker: Optional[ObjectTracker] = None
db: Optional[Database] = None
detection_task: Optional[asyncio.Task] = None
active_websockets: set = set()

# ============================================================================
# Lifespan Management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    global camera, detector, tracker, db, detection_task
    
    logger.info("Starting drone detection system...")
    
    # Initialize components
    try:
        db = Database()
        await db.init()
        logger.info("✓ Database initialized")
        
        camera = UniviewCamera()
        if await camera.connect():
            logger.info("✓ Camera connected")
        else:
            logger.warning("⚠ Camera connection failed - will retry")
        
        detector = DroneDetector(model_name="yolov8m")
        logger.info("✓ YOLO detector loaded")
        
        tracker = ObjectTracker(max_age=30)
        logger.info("✓ Object tracker initialized")
        
        # Start detection task
        detection_task = asyncio.create_task(detection_loop())
        logger.info("✓ Detection loop started")
        
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise
    
    yield
    
    # Cleanup
    logger.info("Shutting down drone detection system...")
    if detection_task:
        detection_task.cancel()
    if camera:
        await camera.disconnect()
    if db:
        await db.close()
    logger.info("✓ Shutdown complete")

# ============================================================================
# Detection Loop
# ============================================================================

async def detection_loop():
    """Main detection loop - runs continuously."""
    frame_count = 0
    
    while True:
        try:
            if not camera or not camera.is_connected:
                await asyncio.sleep(1)
                continue
            
            # Capture frame
            frame = await camera.get_frame()
            if frame is None:
                await asyncio.sleep(0.033)  # ~30 FPS
                continue
            
            # Run detection
            detections = detector.detect(frame)
            
            # Update tracker
            tracked_objects = tracker.update(detections)
            
            # Save detections to database
            for obj in tracked_objects:
                detection_db = Detection(
                    timestamp=datetime.utcnow(),
                    object_type=obj['class_name'],
                    confidence=obj['confidence'],
                    x_min=obj['bbox'][0],
                    y_min=obj['bbox'][1],
                    x_max=obj['bbox'][2],
                    y_max=obj['bbox'][3],
                    track_id=obj['track_id']
                )
                await db.add_detection(detection_db)
            
            # Broadcast to WebSocket clients
            await broadcast_detections(tracked_objects)
            
            frame_count += 1
            if frame_count % 100 == 0:
                logger.info(f"Processed {frame_count} frames")
            
            await asyncio.sleep(0.033)  # ~30 FPS
            
        except asyncio.CancelledError:
            logger.info("Detection loop cancelled")
            break
        except Exception as e:
            logger.error(f"Detection loop error: {e}")
            await asyncio.sleep(1)

async def broadcast_detections(detections):
    """Broadcast detections to all WebSocket clients."""
    if not active_websockets:
        return
    
    message = {
        "type": "detections",
        "timestamp": datetime.utcnow().isoformat(),
        "detections": [
            {
                "class": d['class_name'],
                "confidence": float(d['confidence']),
                "bbox": [float(x) for x in d['bbox']],
                "track_id": d['track_id']
            }
            for d in detections
        ]
    }
    
    disconnected = set()
    for ws in active_websockets:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.add(ws)
    
    active_websockets.difference_update(disconnected)

# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Drone Detection API",
    description="Real-time drone detection using thermal imaging",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Health & Status Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "camera_connected": camera.is_connected if camera else False,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/camera/status", response_model=CameraStatus)
async def get_camera_status():
    """Get camera connection status."""
    if not camera:
        raise HTTPException(status_code=503, detail="Camera not initialized")
    
    return CameraStatus(
        connected=camera.is_connected,
        ip=camera.config.get('ip', 'unknown'),
        resolution=f"{camera.width}x{camera.height}" if camera.width else "unknown",
        fps=camera.fps,
        last_frame_time=camera.last_frame_time
    )

# ============================================================================
# Detection Endpoints
# ============================================================================

@app.get("/api/detections", response_model=List[DetectionResult])
async def get_detections(
    limit: int = Query(100, ge=1, le=1000),
    hours: int = Query(24, ge=1, le=168)
):
    """Get recent detections."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    since = datetime.utcnow() - timedelta(hours=hours)
    detections = await db.get_detections(since=since, limit=limit)
    
    return [
        DetectionResult(
            id=d.id,
            timestamp=d.timestamp,
            object_type=d.object_type,
            confidence=d.confidence,
            x_min=d.x_min,
            y_min=d.y_min,
            x_max=d.x_max,
            y_max=d.y_max,
            track_id=d.track_id
        )
        for d in detections
    ]

@app.get("/api/detections/{detection_id}", response_model=DetectionResult)
async def get_detection(detection_id: int):
    """Get specific detection by ID."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    detection = await db.get_detection(detection_id)
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    
    return DetectionResult(
        id=detection.id,
        timestamp=detection.timestamp,
        object_type=detection.object_type,
        confidence=detection.confidence,
        x_min=detection.x_min,
        y_min=detection.y_min,
        x_max=detection.x_max,
        y_max=detection.y_max,
        track_id=detection.track_id
    )

# ============================================================================
# Camera Control Endpoints
# ============================================================================

@app.post("/api/camera/ptz")
async def control_ptz(command: PTZCommand):
    """Control camera pan/tilt/zoom."""
    if not camera or not camera.is_connected:
        raise HTTPException(status_code=503, detail="Camera not available")
    
    await camera.ptz_control(
        pan=command.pan,
        tilt=command.tilt,
        zoom=command.zoom
    )
    
    return {"status": "success", "message": "PTZ command sent"}

@app.get("/api/camera/stream")
async def stream_camera():
    """Stream MJPEG from camera."""
    if not camera or not camera.is_connected:
        raise HTTPException(status_code=503, detail="Camera not available")
    
    async def generate():
        while True:
            frame = await camera.get_mjpeg_frame()
            yield frame
    
    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# ============================================================================
# Analytics Endpoints
# ============================================================================

@app.get("/api/stats/today", response_model=StatsResponse)
async def get_stats_today():
    """Get today's detection statistics."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    detections = await db.get_detections(since=today)
    
    if not detections:
        return StatsResponse(
            total_detections=0,
            detections_today=0,
            unique_tracks=0,
            average_confidence=0.0,
            detection_frequency="0/hour"
        )
    
    unique_tracks = len(set(d.track_id for d in detections if d.track_id))
    avg_confidence = sum(d.confidence for d in detections) / len(detections)
    
    return StatsResponse(
        total_detections=len(detections),
        detections_today=len(detections),
        unique_tracks=unique_tracks,
        average_confidence=avg_confidence,
        detection_frequency=f"{len(detections)/24:.1f}/hour"
    )

# ============================================================================
# WebSocket Endpoint
# ============================================================================

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time detection stream."""
    await websocket.accept()
    active_websockets.add(websocket)
    
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        active_websockets.discard(websocket)

# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Drone Detection API",
        "version": "1.0.0",
        "docs": "/docs",
        "api_prefix": "/api"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
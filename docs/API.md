# Drone Detection API Reference

## Base URL

```
http://localhost:8000
```

## Authentication

Currently, no authentication is required. For production, add API keys or OAuth2.

## Endpoints

### Health Check

#### GET /health

Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "camera_connected": true,
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

### Detections

#### GET /api/detections

Get recent detections with optional filtering.

**Query Parameters:**
- `limit` (int, default: 100, max: 1000): Number of results
- `hours` (int, default: 24, max: 168): Hours to look back

**Response:**
```json
[
  {
    "id": 1,
    "timestamp": "2024-01-15T10:30:00.000Z",
    "object_type": "drone",
    "confidence": 0.95,
    "x_min": 100.5,
    "y_min": 200.3,
    "x_max": 250.7,
    "y_max": 350.2,
    "track_id": 1
  }
]
```

**Example:**
```bash
curl http://localhost:8000/api/detections?limit=50&hours=12
```

---

#### GET /api/detections/{id}

Get specific detection by ID.

**Path Parameters:**
- `id` (int): Detection ID

**Response:**
```json
{
  "id": 1,
  "timestamp": "2024-01-15T10:30:00.000Z",
  "object_type": "drone",
  "confidence": 0.95,
  "x_min": 100.5,
  "y_min": 200.3,
  "x_max": 250.7,
  "y_max": 350.2,
  "track_id": 1
}
```

**Example:**
```bash
curl http://localhost:8000/api/detections/1
```

---

### Camera Status

#### GET /api/camera/status

Get current camera connection status.

**Response:**
```json
{
  "connected": true,
  "ip": "192.168.1.100",
  "resolution": "640x480",
  "fps": 30.0,
  "last_frame_time": "2024-01-15T10:30:00.000Z"
}
```

**Example:**
```bash
curl http://localhost:8000/api/camera/status
```

---

### Pan-Tilt-Zoom Control

#### POST /api/camera/ptz

Control camera pan, tilt, zoom.

**Request Body:**
```json
{
  "pan": 0.5,
  "tilt": -0.3,
  "zoom": 0.2
}
```

**Parameters:**
- `pan` (float, -1 to 1): Pan direction (-1=left, 1=right)
- `tilt` (float, -1 to 1): Tilt direction (-1=down, 1=up)
- `zoom` (float, -1 to 1): Zoom (-1=out, 1=in)

**Response:**
```json
{
  "status": "success",
  "message": "PTZ command sent"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/camera/ptz \
  -H "Content-Type: application/json" \
  -d '{"pan": 0.5, "tilt": -0.3, "zoom": 0.2}'
```

---

### Camera Stream

#### GET /api/camera/stream

Get live MJPEG stream from camera.

**Response:**
MJPEG video stream

**Example:**
```bash
curl http://localhost:8000/api/camera/stream > stream.mjpeg
```

---

### Statistics

#### GET /api/stats/today

Get today's detection statistics.

**Response:**
```json
{
  "total_detections": 42,
  "detections_today": 42,
  "unique_tracks": 8,
  "average_confidence": 0.87,
  "detection_frequency": "1.75/hour"
}
```

**Example:**
```bash
curl http://localhost:8000/api/stats/today
```

---

### WebSocket Real-time Stream

#### WebSocket /ws/stream

Connect to real-time detection stream.

**Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/stream');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Detections:', data.detections);
};

ws.send('ping');
```

**Message Format:**
```json
{
  "type": "detections",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "detections": [
    {
      "class": "drone",
      "confidence": 0.95,
      "bbox": [100.5, 200.3, 250.7, 350.2],
      "track_id": 1
    }
  ]
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid parameter"
}
```

### 404 Not Found
```json
{
  "detail": "Detection not found"
}
```

### 503 Service Unavailable
```json
{
  "detail": "Camera not available"
}
```

---

## Response Codes

| Code | Meaning |
|------|----------|
| 200 | Success |
| 400 | Bad Request |
| 404 | Not Found |
| 503 | Service Unavailable |

---

## Rate Limiting

Currently unlimited. Implement rate limiting in production.

---

## Testing with curl

```bash
# Health check
curl http://localhost:8000/health

# Get camera status
curl http://localhost:8000/api/camera/status

# Get recent detections
curl http://localhost:8000/api/detections?limit=10&hours=1

# Get today's stats
curl http://localhost:8000/api/stats/today

# Control PTZ
curl -X POST http://localhost:8000/api/camera/ptz \
  -H "Content-Type: application/json" \
  -d '{"pan": 0.5}'
```

---

## Integration with Antigravity IDE

See `ANTIGRAVITY_SETUP.md` for dashboard integration instructions.
# Drone Aircraft Detector - Thermal Camera System

Real-time drone detection system using IP thermal cameras (Uniview), with Python backend processing and Antigravity IDE dashboard integration.

## 📋 Project Overview

This system detects and tracks drones/aircraft using thermal imaging from Uniview cameras, processes detection data through a Python backend, and visualizes results in an Antigravity IDE dashboard.

### Architecture

```
Uniview Thermal Camera (RTSP)
    ↓
Python Backend (OpenCV + YOLO)
    ↓
REST API (Detection Data)
    ↓
Antigravity IDE Dashboard
    ↓
Alerts & Logging
```

## 🛠 Tech Stack

- **Camera**: Uniview TIC7626EL thermal camera (RTSP streaming)
- **Backend**: Python 3.9+
  - OpenCV (video processing)
  - YOLOv8 (object detection)
  - FastAPI (REST API)
  - PostgreSQL (detection logging)
- **Frontend**: Antigravity IDE (visual dashboard)
- **Deployment**: Docker

## 📁 Project Structure

```
drone-detector/
├── backend/                 # Python microservice
│   ├── app.py              # FastAPI application
│   ├── camera.py           # Uniview camera integration
│   ├── detector.py         # YOLO detection logic
│   ├── tracker.py          # Multi-object tracking
│   ├── database.py         # PostgreSQL models
│   ├── requirements.txt    # Python dependencies
│   └── Dockerfile          # Docker configuration
├── antigravity/            # Antigravity IDE files
│   └── dashboard.yml       # Dashboard configuration
├── config/                 # Configuration files
│   └── camera_config.yaml  # Camera settings
├── docker-compose.yml      # Multi-container setup
└── docs/                   # Documentation
    └── API.md              # API reference
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Uniview camera on network
- Antigravity IDE account

### Setup

1. **Clone repository**
   ```bash
   git clone https://github.com/unitfour313-lgtm/drone-detector.git
   cd drone-detector
   ```

2. **Configure camera**
   ```bash
   cp config/camera_config.example.yaml config/camera_config.yaml
   # Edit with your camera IP, credentials, RTSP port
   ```

3. **Start services**
   ```bash
   docker-compose up -d
   ```

4. **Connect Antigravity IDE**
   - API endpoint: `http://localhost:8000`
   - See `docs/API.md` for endpoints

## 📡 API Endpoints

### Detection Results
- `GET /api/detections` - List recent detections
- `GET /api/detections/{id}` - Get detection details
- `POST /api/detections` - Manual detection log
- `WebSocket /ws/stream` - Real-time detection stream

### Camera Control
- `GET /api/camera/status` - Camera connection status
- `POST /api/camera/ptz` - Pan/Tilt/Zoom control
- `GET /api/camera/stream` - MJPEG stream

### Analytics
- `GET /api/stats/today` - Daily detection stats
- `GET /api/stats/hourly` - Hourly breakdown
- `GET /api/alerts` - Alert history

## 🔧 Configuration

Edit `config/camera_config.yaml`:

```yaml
camera:
  ip: "192.168.1.100"
  port: 554
  username: "admin"
  password: "password"
  rtsp_path: "/stream"

detection:
  model: "yolov8m"
  confidence_threshold: 0.5
  target_classes: ["aircraft", "drone"]

database:
  host: "postgres"
  port: 5432
  name: "drone_detection"
  user: "detector"
  password: "secure_password"
```

## 📊 Features

- ✅ Real-time thermal image streaming
- ✅ YOLO-based drone detection
- ✅ Multi-object tracking (Kalman filter)
- ✅ Detection logging & history
- ✅ REST API for external integration
- ✅ WebSocket for live updates
- ✅ Camera PTZ control
- ✅ Alert system (email/SMS/webhook)
- ✅ Web dashboard (Antigravity IDE)

## 🔄 Detection Pipeline

1. **Capture** - RTSP stream from Uniview camera
2. **Preprocess** - Thermal image enhancement
3. **Detect** - YOLO inference on frame
4. **Track** - Kalman filter tracking across frames
5. **Log** - Store detection in PostgreSQL
6. **Alert** - Trigger alerts if configured
7. **Stream** - Send to Antigravity IDE via WebSocket/API

## 📚 Documentation

- [API Reference](docs/API.md)
- [Camera Setup Guide](docs/CAMERA_SETUP.md)
- [Antigravity Integration](docs/ANTIGRAVITY_SETUP.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

## 🤝 Contributing

Contributions welcome! Please submit PRs for:
- Additional detection models
- Improved tracking algorithms
- UI enhancements
- Documentation

## 📝 License

MIT License - see LICENSE file

## 📞 Support

Issues & feature requests: GitHub Issues
Questions: Discussions tab

---

**Status**: 🚧 In Development
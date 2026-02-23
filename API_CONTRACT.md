# Flask API Contract

REST and SSE endpoints for the Raspberry Pi sensor dashboard.

## Base URL

`http://localhost:5000`

## Health & Status

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "sources": 7,
  "sensors": 6
}
```

## Sensor Data

### GET /api/sensors

Get all current sensor readings.

**Response:**
```json
{
  "sensor.bme280": {
    "temperature": 22.5,
    "humidity": 45.0,
    "pressure": 1013.2,
    "timestamp": "2026-02-12T03:45:12.123456",
    "source_id": "sensor.bme280"
  },
  "sensor.tsl25911": {
    "lux": 350.5,
    "infrared": 120,
    "visible": 230,
    "timestamp": "2026-02-12T03:45:11.987654",
    "source_id": "sensor.tsl25911"
  },
  "camera.feed": {
    "motion_detected": false,
    "motion_level": 0.8,
    "frame_jpeg": "<bytes>",
    "timestamp": "2026-02-12T03:45:13.456789",
    "source_id": "camera.feed"
  },
  "system.stats": {
    "cpu_temp": 52.3,
    "ram_percent": 35.2,
    "disk_percent": 42.1,
    "uptime": 86400,
    "timestamp": "2026-02-12T03:45:10.123456",
    "source_id": "system.stats"
  }
}
```

### GET /api/sensors/:source_id

Get specific sensor reading.

**Parameters:**
- `source_id` (path) - Source identifier (e.g., `sensor.bme280`, `camera.feed`)

**Response:**
```json
{
  "temperature": 22.5,
  "humidity": 45.0,
  "pressure": 1013.2,
  "timestamp": "2026-02-12T03:45:12.123456",
  "source_id": "sensor.bme280"
}
```

**Error Response (404):**
```json
{
  "error": "Sensor not found"
}
```

### GET /api/sensors/:source_id/history

Get sensor history for graphing.

**Parameters:**
- `source_id` (path) - Source identifier
- `limit` (query, optional) - Max history points (default: 100)

**Response:**
```json
{
  "source_id": "sensor.bme280",
  "count": 50,
  "data": [
    {
      "timestamp": 1707709512.123,
      "data": {
        "temperature": 22.3,
        "humidity": 44.8,
        "pressure": 1013.1
      }
    },
    {
      "timestamp": 1707709514.456,
      "data": {
        "temperature": 22.5,
        "humidity": 45.0,
        "pressure": 1013.2
      }
    }
  ]
}
```

## Situation Report

### GET /api/situation

Get structured sensor context for LLM chat.

**Response:**
```json
{
  "timestamp": "2026-02-12T03:45:15.123456",
  "environment": {
    "temperature": 22.5,
    "humidity": 45.0,
    "pressure": 1013.2,
    "light_level": 350.5,
    "uv_index": 2.3,
    "air_quality_voc": 28500
  },
  "motion": {},
  "camera": {
    "motion_detected": false,
    "motion_level": 0.8,
    "has_frame": true,
    "scene_description": "A well-lit room with a desk and computer monitor. Natural light coming from the left side."
  },
  "system": {
    "cpu_temp": 52.3,
    "ram_percent": 35.2,
    "disk_percent": 42.1,
    "uptime_seconds": 86400
  },
  "network": {
    "ping_ms": 12.5,
    "ip_address": "192.168.1.100",
    "throughput_mbps": 45.2
  },
  "weather": {
    "temperature": 18.5,
    "windspeed": 5.2,
    "winddirection": 180,
    "weathercode": 0,
    "is_day": 1,
    "time": "2026-02-12T03:00"
  }
}
```

## Camera

### GET /api/camera/frame

Get latest camera frame as JPEG.

**Response:**
- Content-Type: `image/jpeg`
- Body: JPEG binary data

**Error Response (404):**
```json
{
  "error": "No camera frame available"
}
```

### GET /api/camera/status

Get camera motion detection status.

**Response:**
```json
{
  "has_frame": true,
  "motion_detected": false
}
```

## Chat

### POST /api/chat

Send chat message with sensor context to VPS LLM API.

**Request:**
```json
{
  "message": "What's the current temperature?"
}
```

**Response:**
```json
{
  "response": "The current indoor temperature is 22.5°C with 45% humidity. It's comfortable.",
  "context": {
    "timestamp": "2026-02-12T03:45:15.123456",
    "environment": { ... },
    "camera": { ... },
    "system": { ... }
  }
}
```

**Error Response (400):**
```json
{
  "error": "Missing message field"
}
```

**Error Response (500):**
```json
{
  "error": "Failed to reach chat API: Connection timeout",
  "context": { ... }
}
```

## Vision Analysis

### POST /api/vision/analyze

Proxy vision analysis request to VPS.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `image` file (JPEG/PNG)

**Response:**
```json
{
  "description": "A modern office desk with a laptop, monitor, and potted plant. Natural lighting from a nearby window.",
  "provider": "xai"
}
```

**Error Response (400):**
```json
{
  "error": "No image file provided"
}
```

**Error Response (500):**
```json
{
  "error": "Failed to reach vision API: Connection timeout"
}
```

## Server-Sent Events

### GET /stream

Real-time sensor updates via SSE.

**Connection:**
```
GET /stream HTTP/1.1
Accept: text/event-stream
```

**Event Types:**

#### sensor_update
Sent when any sensor reading changes.

```
event: sensor_update
data: {"source_id": "sensor.bme280", "temperature": 22.5, "humidity": 45.0, "pressure": 1013.2, "timestamp": "2026-02-12T03:45:12.123456"}

event: sensor_update
data: {"source_id": "camera.feed", "motion_detected": false, "motion_level": 0.8, "timestamp": "2026-02-12T03:45:13.456789"}
```

#### camera_motion
Sent when camera detects motion.

```
event: camera_motion
data: {"motion_detected": true, "level": 5.2}
```

**Update Frequency:** 2Hz (every 500ms)

**Client Example (JavaScript):**
```javascript
const eventSource = new EventSource('/stream');

eventSource.addEventListener('sensor_update', (event) => {
  const data = JSON.parse(event.data);
  console.log(`Sensor ${data.source_id} updated:`, data);
});

eventSource.addEventListener('camera_motion', (event) => {
  const data = JSON.parse(event.data);
  console.log('Motion detected:', data.level);
});

eventSource.onerror = (error) => {
  console.error('SSE connection error:', error);
};
```

## VPS API Endpoints (External)

These endpoints are hosted on the VPS and called by the Flask app:

### POST https://dr.eamer.dev/pivision/api/chat

LLM chat endpoint with sensor context.

**Request:**
```json
{
  "message": "What's the air quality like?",
  "context": {
    "timestamp": "2026-02-12T03:45:15.123456",
    "environment": {
      "temperature": 22.5,
      "air_quality_voc": 28500
    },
    "camera": {
      "scene_description": "..."
    }
  }
}
```

**Response:**
```json
{
  "response": "The air quality is good. The VOC reading of 28,500 is in the normal range."
}
```

### POST https://dr.eamer.dev/pivision/api/analyze

Vision analysis endpoint (scene description).

**Request:**
- Content-Type: `multipart/form-data`
- Body: `image` file (JPEG/PNG)

**Response:**
```json
{
  "description": "A modern office desk with a laptop and monitor.",
  "provider": "xai"
}
```

## Static Files

### GET /

Serve main dashboard HTML page.

**Response:**
- Content-Type: `text/html`
- Body: `static/index.html`

### GET /<path>

Serve static assets (JS, CSS, images).

**Examples:**
- `/app.js`
- `/styles.css`
- `/favicon.ico`

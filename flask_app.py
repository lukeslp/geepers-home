#!/usr/bin/env python3
"""Flask web interface for Raspberry Pi sensor dashboard.

Serves a single-page web UI for an 800x480 touchscreen in kiosk mode.
Uses SSE for real-time sensor updates and REST for chat interactions.

Architecture:
- Starts all DataSource threads from dashboard.yaml
- Subscribes to EventBus to collect latest sensor readings
- Serves SSE stream at /stream for real-time updates
- Provides /api/chat endpoint for LLM interaction
- Serves static files for the web frontend
- Camera feed JPEG served at /api/camera/frame

No database, no auth. Local-only dashboard.
"""

import json
import logging
import os
import sys
import time
import threading
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import yaml
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.event_bus import EventBus
from core.registry import get_source_class

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)  # Allow CORS for local dev

# Configuration
CONFIG_FILE = Path(__file__).parent / "dashboard.yaml"
VPS_CHAT_ENDPOINT = "https://dr.eamer.dev/pivision/api/chat"
VPS_VISION_ENDPOINT = "https://dr.eamer.dev/pivision/api/analyze"

# Global state
class DashboardState:
    """Thread-safe global state container."""
    def __init__(self):
        self.lock = threading.Lock()
        self.sensor_data: Dict[str, Dict[str, Any]] = {}  # source_id -> latest data
        self.sensor_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.sources = []
        self.event_bus = None
        self.camera_jpeg: Optional[bytes] = None
        self.motion_detected = False

    def update_sensor(self, source_id: str, data: Dict[str, Any]):
        """Update sensor data from EventBus callback."""
        with self.lock:
            self.sensor_data[source_id] = {
                **data,
                'timestamp': datetime.now().isoformat(),
                'source_id': source_id
            }
            # Store history for graphing
            self.sensor_history[source_id].append({
                'timestamp': time.time(),
                'data': data
            })

            # Update camera JPEG if camera data
            if source_id == "camera.feed" and data.get('frame_jpeg'):
                self.camera_jpeg = data['frame_jpeg']
                self.motion_detected = data.get('motion_detected', False)

    def get_all_sensors(self) -> Dict[str, Dict[str, Any]]:
        """Get all current sensor readings."""
        with self.lock:
            return dict(self.sensor_data)

    def get_sensor(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Get specific sensor reading."""
        with self.lock:
            return self.sensor_data.get(source_id)

    def get_history(self, source_id: str, limit: int = 100) -> list:
        """Get sensor history."""
        with self.lock:
            history = list(self.sensor_history.get(source_id, []))
            return history[-limit:]

    def get_situation_report(self) -> Dict[str, Any]:
        """Build structured sensor context for LLM chat."""
        with self.lock:
            report = {
                'timestamp': datetime.now().isoformat(),
                'environment': {},
                'motion': {},
                'camera': {},
                'system': {},
                'network': {},
                'weather': {}
            }

            # Group sensors by category
            for source_id, data in self.sensor_data.items():
                if source_id.startswith('sensor.'):
                    # Environment sensors
                    if 'temperature' in data:
                        report['environment']['temperature'] = data['temperature']
                    if 'humidity' in data:
                        report['environment']['humidity'] = data['humidity']
                    if 'pressure' in data:
                        report['environment']['pressure'] = data['pressure']
                    if 'lux' in data:
                        report['environment']['light_level'] = data['lux']
                    if 'uvi' in data:
                        report['environment']['uv_index'] = data['uvi']
                    if 'voc_raw' in data:
                        report['environment']['air_quality_voc'] = data['voc_raw']

                elif source_id == 'camera.feed':
                    report['camera'] = {
                        'motion_detected': data.get('motion_detected', False),
                        'motion_level': data.get('motion_level', 0),
                        'has_frame': bool(data.get('frame_jpeg'))
                    }

                elif source_id == 'camera.vision':
                    report['camera']['scene_description'] = data.get('description', 'No description available')

                elif source_id == 'system.stats':
                    report['system'] = {
                        'cpu_temp': data.get('cpu_temp'),
                        'ram_percent': data.get('ram_percent'),
                        'disk_percent': data.get('disk_percent'),
                        'uptime_seconds': data.get('uptime')
                    }

                elif source_id == 'net.health':
                    report['network'] = {
                        'ping_ms': data.get('ping'),
                        'ip_address': data.get('ip'),
                        'throughput_mbps': data.get('throughput')
                    }

                elif source_id == 'api.weather':
                    report['weather'] = data

            return report

state = DashboardState()


# Mock EventBus for Flask (no tkinter root needed)
class FlaskEventBus:
    """EventBus adapter for Flask (no tkinter dependency)."""
    def __init__(self):
        self._subscribers: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()

    def publish(self, topic: str, payload: Any):
        """Publish data from background threads."""
        with self._lock:
            for callback in self._subscribers.get(topic, []):
                try:
                    callback(payload)
                except Exception as exc:
                    logger.error(f"EventBus callback error [{topic}]: {exc}")

    def subscribe(self, topic: str, callback):
        """Subscribe to a topic."""
        with self._lock:
            self._subscribers[topic].append(callback)

    def unsubscribe(self, topic: str, callback):
        """Unsubscribe from a topic."""
        with self._lock:
            if topic in self._subscribers:
                self._subscribers[topic] = [
                    cb for cb in self._subscribers[topic] if cb is not callback
                ]


def load_config() -> dict:
    """Load dashboard.yaml configuration."""
    if not CONFIG_FILE.exists():
        logger.error(f"Config file not found: {CONFIG_FILE}")
        return {'sources': []}

    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def start_data_sources():
    """Initialize and start all data sources from config."""
    config = load_config()
    bus = FlaskEventBus()
    state.event_bus = bus

    for source_config in config.get('sources', []):
        source_id = source_config['id']
        source_type = source_config['type']

        # Get source class from registry
        source_class = get_source_class(source_type)
        if not source_class:
            logger.warning(f"Unknown source type: {source_type} for {source_id}")
            continue

        try:
            # Create source instance
            source = source_class(source_id, bus, source_config)

            # Subscribe to its topic
            bus.subscribe(source_id, lambda data, sid=source_id: state.update_sensor(sid, data))

            # Start background thread
            source.start()
            state.sources.append(source)
            logger.info(f"Started source: {source_id} ({source_type})")

        except Exception as exc:
            logger.error(f"Failed to start source {source_id}: {exc}")

    logger.info(f"Started {len(state.sources)} data sources")


# Routes

@app.route('/')
def index():
    """Serve main dashboard page."""
    return send_from_directory('static', 'index.html')


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'sources': len(state.sources),
        'sensors': len(state.get_all_sensors())
    })


@app.route('/api/sensors')
def get_sensors():
    """Get all current sensor readings."""
    return jsonify(state.get_all_sensors())


@app.route('/api/sensors/<source_id>')
def get_sensor(source_id: str):
    """Get specific sensor reading."""
    data = state.get_sensor(source_id)
    if data is None:
        return jsonify({'error': 'Sensor not found'}), 404
    return jsonify(data)


@app.route('/api/sensors/<source_id>/history')
def get_sensor_history(source_id: str):
    """Get sensor history for graphing."""
    limit = int(request.args.get('limit', 100))
    history = state.get_history(source_id, limit)
    return jsonify({
        'source_id': source_id,
        'count': len(history),
        'data': history
    })


@app.route('/api/situation')
def get_situation():
    """Get structured situation report for LLM context."""
    return jsonify(state.get_situation_report())


@app.route('/api/camera/frame')
def get_camera_frame():
    """Serve latest camera frame as JPEG."""
    if state.camera_jpeg is None:
        return jsonify({'error': 'No camera frame available'}), 404

    return Response(state.camera_jpeg, mimetype='image/jpeg')


@app.route('/api/camera/status')
def get_camera_status():
    """Get camera motion detection status."""
    return jsonify({
        'has_frame': state.camera_jpeg is not None,
        'motion_detected': state.motion_detected
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat request with sensor context.

    Expects JSON: {'message': 'user message'}
    Returns JSON: {'response': 'LLM response', 'context': {...}}
    """
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'Missing message field'}), 400

    user_message = data['message']

    # Build situation report
    situation = state.get_situation_report()

    # Send to VPS chat API
    try:
        response = requests.post(
            VPS_CHAT_ENDPOINT,
            json={
                'message': user_message,
                'context': situation
            },
            timeout=30
        )
        response.raise_for_status()

        result = response.json()
        return jsonify({
            'response': result.get('response', 'No response from LLM'),
            'context': situation
        })

    except requests.RequestException as exc:
        logger.error(f"Chat API error: {exc}")
        return jsonify({
            'error': f'Failed to reach chat API: {str(exc)}',
            'context': situation
        }), 500


@app.route('/stream')
def stream():
    """Server-Sent Events stream for real-time sensor updates.

    Format:
        event: sensor_update
        data: {"source_id": "sensor.bme280", "temperature": 22.5, ...}

        event: camera_motion
        data: {"motion_detected": true, "level": 5.2}
    """
    def event_stream():
        """Generator for SSE events."""
        last_sent = {}

        while True:
            # Get current sensor data
            sensors = state.get_all_sensors()

            # Send updates for changed sensors
            for source_id, data in sensors.items():
                # Only send if data changed
                if last_sent.get(source_id) != data:
                    yield f"event: sensor_update\n"
                    yield f"data: {json.dumps(data)}\n\n"
                    last_sent[source_id] = data

            # Send camera motion events
            camera_data = state.get_sensor('camera.feed')
            if camera_data and camera_data.get('motion_detected'):
                yield f"event: camera_motion\n"
                yield f"data: {json.dumps({'motion_detected': True, 'level': camera_data.get('motion_level', 0)})}\n\n"

            time.sleep(0.5)  # 2Hz update rate

    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/api/vision/analyze', methods=['POST'])
def analyze_vision():
    """Proxy vision analysis request to VPS.

    Accepts multipart/form-data with 'image' file.
    Returns JSON: {'description': '...', 'provider': 'xai'}
    """
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    image_file = request.files['image']

    try:
        # Forward to VPS vision API
        files = {'image': (image_file.filename, image_file.stream, image_file.mimetype)}
        response = requests.post(VPS_VISION_ENDPOINT, files=files, timeout=30)
        response.raise_for_status()

        return jsonify(response.json())

    except requests.RequestException as exc:
        logger.error(f"Vision API error: {exc}")
        return jsonify({'error': f'Failed to reach vision API: {str(exc)}'}), 500


# Startup

def main():
    """Start Flask app with data sources."""
    logger.info("Starting Raspberry Pi Sensor Dashboard (Flask)")

    # Start all data sources
    start_data_sources()

    # Run Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True
    )


if __name__ == '__main__':
    main()

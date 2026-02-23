#!/usr/bin/env python3
"""Geepers — Web dashboard mode.

Replaces tkinter with a Flask web server for the 800x480 touchscreen.
Serves a conversational sensor dashboard with SSE for real-time data
and a chat interface backed by the VPS LLM gateway.

Usage:
    python3 web_app.py              # Normal mode
    python3 web_app.py --demo       # Simulated sensor data
    python3 web_app.py --port 5000  # Custom port
"""

__version__ = "4.1.0"

import argparse
import io
import json
import logging
import os
import sys
import time

import yaml

# Ensure project root on path
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, Response, jsonify, render_template, request, send_from_directory

from core.web_event_bus import WebEventBus
from core.alerts import AlertManager
from core.data_store import DataStore
from core.registry import SOURCE_REGISTRY

# Import sources to trigger @register_source decorators
import sources  # noqa: F401

logger = logging.getLogger(__name__)

# ─── Globals ───
bus = WebEventBus()
data_store = DataStore()
alert_manager = None  # Initialized from config in main()
active_sources = []
demo_mode = False


def create_app(config_path="dashboard.yaml"):
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder="web/templates",
        static_folder="web/static",
    )

    # ─── Routes: UI ───

    @app.route("/")
    def index():
        return render_template("index.html")

    # ─── Routes: Sensor SSE stream ───

    @app.route("/api/sensors/stream")
    def sensor_stream():
        """SSE endpoint streaming real-time sensor data."""
        def generate():
            for topic, payload in bus.sse_stream():
                if topic == "keepalive":
                    yield ": keepalive\n\n"
                    continue

                # Determine event type
                if topic == "alert":
                    event_type = "alert"
                elif "camera.vision" in topic:
                    event_type = "vision"
                elif "camera.feed" in topic:
                    # Don't stream raw camera frames over SSE
                    continue
                elif "weather" in topic:
                    event_type = "weather"
                elif "voice" in topic:
                    event_type = "voice"
                elif "news" in topic:
                    event_type = "news"
                else:
                    event_type = "sensor"

                try:
                    # Clean payload for JSON (remove PIL Image objects)
                    clean = _clean_payload(topic, payload)
                    if clean:
                        yield f"event: {event_type}\ndata: {json.dumps(clean)}\n\n"
                except Exception as exc:
                    logger.debug("SSE serialize error for %s: %s", topic, exc)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # ─── Routes: Camera frame ───

    @app.route("/api/camera/frame")
    def camera_frame():
        """Serve latest camera JPEG."""
        from sources.camera_source import CameraSource
        jpeg = CameraSource.latest_jpeg
        if jpeg:
            return Response(jpeg, mimetype="image/jpeg")
        # Return a 1x1 transparent pixel as placeholder
        return Response(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00'
            b'\x01\x00\x00\x05\x00\x01\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82',
            mimetype="image/png",
        )

    # ─── Routes: Sensor snapshot ───

    @app.route("/api/sensors")
    def sensor_snapshot():
        """Return latest readings for all sensors."""
        all_data = bus.get_latest()
        result = {}
        for topic, payload in all_data.items():
            clean = _clean_payload(topic, payload)
            if clean:
                result[topic] = clean
        return jsonify(result)

    # ─── Routes: Chat (proxy to api-gateway LLM) ───

    @app.route("/api/chat", methods=["POST"])
    def chat():
        """Accept user message + sensor context, proxy to api-gateway /v1/llm/chat."""
        import requests as http_requests

        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"error": "message required"}), 400

        user_msg = data["message"]
        sensor_ctx = data.get("sensor_context", {})
        camera_scene = data.get("camera_scene", "")
        history = data.get("history", [])

        # Build system prompt with sensor context
        system_prompt = _build_system_prompt(sensor_ctx, camera_scene)

        # Convert history + new message into messages array
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history[-10:]:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        messages.append({"role": "user", "content": user_msg})

        # Call the api-gateway
        gateway_url = os.environ.get(
            "CHAT_ENDPOINT",
            "https://api.dr.eamer.dev/v1/llm/chat"
        )
        api_key = os.environ.get("DREAMER_API_KEY", "")

        gateway_payload = {
            "provider": data.get("provider", "anthropic"),
            "model": data.get("model", "claude-sonnet-4-5-20250929"),
            "messages": messages,
            "stream": True,
            "max_tokens": 2048,
            "temperature": 0.5,
        }

        def stream_response():
            try:
                resp = http_requests.post(
                    gateway_url,
                    json=gateway_payload,
                    stream=True,
                    timeout=60,
                    headers={
                        "Accept": "text/event-stream",
                        "X-API-Key": api_key,
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    for line in resp.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        if line.startswith("data: "):
                            payload = line[6:]
                            try:
                                chunk = json.loads(payload)
                                if chunk.get("done"):
                                    yield "data: [DONE]\n\n"
                                elif "content" in chunk:
                                    yield f"data: {json.dumps({'text': chunk['content']})}\n\n"
                            except json.JSONDecodeError:
                                pass
                else:
                    try:
                        result = resp.json()
                        text = result.get("error", f"Gateway returned {resp.status_code}")
                    except Exception:
                        text = f"Gateway returned {resp.status_code}"
                    yield f"data: {json.dumps({'text': text})}\n\n"
                    yield "data: [DONE]\n\n"
            except http_requests.ConnectionError:
                yield f"data: {json.dumps({'text': 'Cannot reach the assistant. Check your connection.'})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as exc:
                logger.error("Chat proxy error: %s", exc)
                yield f"data: {json.dumps({'text': f'Error: {exc}'})}\n\n"
                yield "data: [DONE]\n\n"

        return Response(
            stream_response(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ─── Routes: Sensor config (eliminates hardcoded SENSOR_MAP in JS) ───

    @app.route("/api/config")
    def sensor_config():
        """Return sensor metadata from dashboard.yaml so the frontend
        can build its SENSOR_MAP dynamically."""
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
        except Exception:
            return jsonify({"sensors": {}, "demo": demo_mode})

        sensors = {}
        for page in config.get("pages", []):
            for card in page.get("cards", []):
                if card.get("type") != "sensor":
                    continue
                field = card.get("field")
                if not field or field in sensors:
                    continue

                # Build threshold array: [[value, status], ...]
                raw_thresholds = card.get("thresholds", [])
                thresholds = []
                for t in raw_thresholds:
                    if isinstance(t, list) and len(t) >= 2:
                        thresholds.append([t[0], t[1]])

                entry = {
                    "label": card.get("label", field),
                    "unit": card.get("unit", ""),
                    "color": card.get("color", "#888"),
                    "format": card.get("format", "{}"),
                    "thresholds": thresholds,
                }
                if card.get("convert"):
                    entry["convert"] = card["convert"]
                sensors[field] = entry

        return jsonify({
            "sensors": sensors,
            "demo": demo_mode,
            "version": __version__,
        })

    # ─── Routes: View registry (multi-view kiosk) ───

    @app.route("/api/views")
    def views_config():
        """Return view definitions from dashboard.yaml for the frontend ViewManager."""
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
        except Exception:
            return jsonify({"views": []})
        views = config.get("views", [])
        return jsonify({"views": views})

    # ─── Routes: History (time-series from SQLite) ───

    @app.route("/api/history/<field>")
    def history(field):
        """Return time-series data for a sensor field.

        Query params:
            hours: float (default 24, max 720 = 30 days)
            points: int (default 300, max 1000)
        """
        hours = min(float(request.args.get("hours", 24)), 720)
        points = min(int(request.args.get("points", 300)), 1000)
        data = data_store.get_history(field, hours=hours, max_points=points)
        return jsonify({"field": field, "hours": hours, "data": data})

    @app.route("/api/history/summary")
    def history_summary():
        """Return 24h min/max/avg/current for all sensor fields."""
        hours = min(float(request.args.get("hours", 24)), 720)
        summary = data_store.get_summary(hours=hours)
        return jsonify({"hours": hours, "summary": summary})

    @app.route("/api/history/fields")
    def history_fields():
        """Return list of all fields with recorded data."""
        return jsonify({"fields": data_store.get_fields()})

    # ─── Routes: Alerts ───

    @app.route("/api/alerts")
    def active_alerts():
        """Return currently active (uncleared) alerts."""
        if alert_manager:
            return jsonify({"alerts": alert_manager.get_active_alerts()})
        return jsonify({"alerts": []})

    # ─── Routes: Demo toggle ───

    @app.route("/api/demo", methods=["POST"])
    def toggle_demo():
        """Toggle demo mode for all sources."""
        global demo_mode
        demo_mode = not demo_mode
        for src in active_sources:
            if hasattr(src, "set_demo"):
                src.set_demo(demo_mode)
        return jsonify({"demo": demo_mode})

    # ─── Routes: Voice input (browser MediaRecorder → VPS Whisper) ───

    @app.route("/api/voice", methods=["POST"])
    def voice_transcribe():
        """Accept audio from browser MediaRecorder, forward to VPS for STT.

        Browser captures webm/opus via getUserMedia + MediaRecorder,
        POSTs the blob here, we forward to VPS Whisper endpoint.
        """
        if "audio" not in request.files:
            return jsonify({"error": "No audio file provided"}), 400

        audio_file = request.files["audio"]
        bus.publish("voice.state", {"state": "processing"})

        try:
            import requests as http_requests
            vps_url = os.environ.get("VPS_URL", "https://api.dr.eamer.dev")

            api_key = os.environ.get("DREAMER_API_KEY", "")
            resp = http_requests.post(
                f"{vps_url}/v1/voice/transcribe",
                files={"audio": (
                    audio_file.filename or "recording.webm",
                    audio_file.stream,
                    audio_file.content_type or "audio/webm",
                )},
                headers={"X-API-Key": api_key} if api_key else {},
                timeout=30,
            )

            bus.publish("voice.state", {"state": "idle"})

            if resp.status_code == 200:
                result = resp.json()
                text = result.get("text", "").strip()
                if text:
                    return jsonify({"text": text})
                return jsonify({"error": "Could not understand audio"}), 400
            else:
                logger.warning("VPS transcription failed: %s", resp.status_code)
                return jsonify({"error": f"Transcription failed ({resp.status_code})"}), 502

        except Exception as exc:
            logger.error("Voice transcription error: %s", exc)
            bus.publish("voice.state", {"state": "error"})
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/voice/status")
    def voice_status():
        """Voice availability — browser-based, always available."""
        return jsonify({
            "state": "idle",
            "available": True,
            "method": "browser",
        })

    return app


def _wire_data_store(bus, store):
    """Subscribe to sensor topics on the event bus and record numeric values.

    Also runs alert checks on each incoming value.
    """
    global alert_manager

    # Load sensor field names from config so we know what to record
    _sensor_fields = set()
    try:
        with open("dashboard.yaml") as f:
            config = yaml.safe_load(f)
        for page in config.get("pages", []):
            for card in page.get("cards", []):
                if card.get("type") == "sensor" and card.get("field"):
                    _sensor_fields.add(card["field"])

        # Initialize alert manager from config
        alert_rules = config.get("alerts", [])
        if alert_rules:
            alert_manager = AlertManager(alert_rules)
            logger.info("AlertManager loaded with %d rules", len(alert_rules))
    except Exception:
        pass

    original_publish = bus.publish

    def recording_publish(topic, payload):
        """Wrap publish to also record sensor data and check alerts."""
        original_publish(topic, payload)

        # Only record sensor data, not camera/system/etc
        if not isinstance(payload, dict):
            return
        if "camera" in topic:
            return

        for field, value in payload.items():
            if field.startswith("_"):
                continue
            if not isinstance(value, (int, float)):
                continue
            # If we have a field list, only record known fields
            if _sensor_fields and field not in _sensor_fields:
                continue
            fval = float(value)
            store.record(field, fval)

            # Check alert rules
            if alert_manager:
                triggered = alert_manager.check(field, fval)
                for alert in triggered:
                    # Publish alert as a special event so SSE picks it up
                    original_publish("alert", alert)

    bus.publish = recording_publish
    logger.info("DataStore wired to event bus (tracking %d fields)", len(_sensor_fields))


def _build_system_prompt(sensor_ctx, camera_scene):
    """Build a system prompt that gives the LLM full context about everything available."""
    import datetime

    now = datetime.datetime.now()

    lines = [
        "You are Geepers, a smart general-purpose assistant running on a Raspberry Pi "
        "sensor station. You have live access to 23 physical sensors (temperature, humidity, "
        "air quality, UV, motion, sound, light, flame, soil moisture, magnetism, tilt, "
        "touch, barometric pressure, and more), a USB camera with vision analysis, "
        "indoor/outdoor weather data, news headlines, system health metrics, and "
        "conversation history.",
        "",
        "You can help with anything — general knowledge, questions about the environment, "
        "interpreting sensor data, comparing indoor vs outdoor conditions, commenting on "
        "what the camera sees, discussing news, giving advice, or just chatting. "
        "Be conversational, helpful, and concise (2-4 sentences unless the user wants detail). "
        "Use Fahrenheit for temperature. When sensor data is relevant to the question, "
        "reference specific readings. When it's not relevant, just answer normally.",
        "",
        f"Current time: {now.strftime('%I:%M %p')}, {now.strftime('%A %B %d, %Y')}",
    ]

    # Sensor readings
    sensor_fields = {k: v for k, v in (sensor_ctx or {}).items() if not k.startswith("_")}
    if sensor_fields:
        lines.append("")
        lines.append("Live sensor readings:")
        for field, info in sensor_fields.items():
            if isinstance(info, dict):
                val = info.get("value", "?")
                unit = info.get("unit", "")
                trend = info.get("trend", "")
                line = f"  {field}: {val}{unit}"
                if trend and trend != "unknown":
                    line += f" ({trend})"
                lines.append(line)
            else:
                lines.append(f"  {field}: {info}")
    else:
        lines.append("")
        lines.append("Sensor readings: (waiting for first data)")

    # Comfort score
    comfort = sensor_ctx.get("_comfort") if isinstance(sensor_ctx, dict) else None
    if comfort and isinstance(comfort, dict) and comfort.get("score"):
        lines.append(f"  Comfort score: {comfort['score']}/100 ({comfort.get('label', '')})")

    # Weather / outdoor conditions
    weather = sensor_ctx.get("_weather") if isinstance(sensor_ctx, dict) else None
    if weather and isinstance(weather, dict):
        lines.append("")
        lines.append("Outdoor conditions:")
        if weather.get("weather_desc"):
            lines.append(f"  Condition: {weather['weather_desc']}")
        if weather.get("outdoor_temp") is not None:
            temp_f = weather["outdoor_temp"] * 9 / 5 + 32
            lines.append(f"  Temperature: {temp_f:.0f}\u00b0F")
        if weather.get("feels_like") is not None:
            feels_f = weather["feels_like"] * 9 / 5 + 32
            lines.append(f"  Feels like: {feels_f:.0f}\u00b0F")
        if weather.get("outdoor_humidity") is not None:
            lines.append(f"  Humidity: {weather['outdoor_humidity']}%")
        if weather.get("wind_speed") is not None:
            lines.append(f"  Wind: {weather['wind_speed']} km/h")

    # System health
    system = sensor_ctx.get("_system") if isinstance(sensor_ctx, dict) else None
    if system and isinstance(system, dict):
        lines.append("")
        lines.append("Pi system health:")
        if system.get("cpu_temp") is not None:
            lines.append(f"  CPU temp: {system['cpu_temp']:.1f}\u00b0C")
        if system.get("ram_percent") is not None:
            lines.append(f"  RAM: {system['ram_percent']:.0f}%")
        if system.get("disk_percent") is not None:
            lines.append(f"  Disk: {system['disk_percent']:.0f}%")
        if system.get("load_1m") is not None:
            lines.append(f"  Load: {system['load_1m']:.2f}")
        if system.get("uptime"):
            lines.append(f"  Uptime: {system['uptime']}")

    # News headlines
    news = sensor_ctx.get("_news") if isinstance(sensor_ctx, dict) else None
    if news and isinstance(news, list) and len(news) > 0:
        lines.append("")
        lines.append("Recent news headlines:")
        for item in news[:5]:
            if isinstance(item, dict):
                lines.append(f"  - [{item.get('section', '')}] {item.get('title', '')}")
            elif isinstance(item, str):
                lines.append(f"  - {item}")

    # Active alerts
    alerts = sensor_ctx.get("_alerts") if isinstance(sensor_ctx, dict) else None
    if alerts and isinstance(alerts, list) and len(alerts) > 0:
        lines.append("")
        lines.append("Active alerts:")
        for a in alerts:
            if isinstance(a, dict):
                lines.append(f"  [{a.get('level', 'info').upper()}] {a.get('message', '')}")

    # Camera scene
    if camera_scene:
        lines.append("")
        lines.append(f"Camera currently sees: {camera_scene}")

    return "\n".join(lines)


def _clean_payload(topic, payload):
    """Remove non-serializable objects (PIL Images) from payload."""
    if not isinstance(payload, dict):
        return None
    clean = {}
    for k, v in payload.items():
        if k == "frame":  # PIL Image
            continue
        if isinstance(v, (str, int, float, bool, type(None))):
            clean[k] = v
        elif isinstance(v, (list, tuple)):
            clean[k] = v
        elif isinstance(v, dict):
            clean[k] = v
        # Skip anything else (bytes, PIL objects, etc.)
    if clean:
        clean["_topic"] = topic
        clean["_ts"] = time.time()
    return clean


def load_sources(config_path, demo=False):
    """Load data sources from YAML config."""
    global demo_mode
    demo_mode = demo

    with open(config_path) as f:
        config = yaml.safe_load(f)

    source_configs = config.get("sources", [])
    sources_started = []

    for src_cfg in source_configs:
        src_type = src_cfg.get("type")
        src_id = src_cfg.get("id")

        if src_type not in SOURCE_REGISTRY:
            logger.warning("Unknown source type: %s (for %s)", src_type, src_id)
            continue

        cls = SOURCE_REGISTRY[src_type]
        try:
            if demo:
                src_cfg["demo"] = True
            source = cls(src_id, bus, src_cfg)
            source.start()
            sources_started.append(source)
            logger.info("Started source: %s (%s)", src_id, src_type)
        except Exception as exc:
            logger.error("Failed to start source %s: %s", src_id, exc)

    return sources_started


def main():
    parser = argparse.ArgumentParser(description="Geepers Web Dashboard")
    parser.add_argument("--demo", action="store_true", help="Use simulated sensor data")
    parser.add_argument("--port", type=int, default=5000, help="Web server port")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--config", default="dashboard.yaml", help="Config file path")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info("Geepers Web v%s starting", __version__)

    # Start data store and wire it to the event bus
    data_store.start()
    _wire_data_store(bus, data_store)

    # Start data sources
    global active_sources
    active_sources = load_sources(args.config, demo=args.demo)
    logger.info("Started %d data sources", len(active_sources))

    # Create and run Flask app
    app = create_app(args.config)
    logger.info("Web dashboard at http://%s:%d", args.host, args.port)

    try:
        app.run(host=args.host, port=args.port, threaded=True, debug=False)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        for src in active_sources:
            src.close()
        data_store.stop()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()

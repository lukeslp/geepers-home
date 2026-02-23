"""Camera data source using ffmpeg.

Captures frames from a USB webcam via ffmpeg subprocess. Supports motion
detection via numpy frame differencing. No OpenCV needed -- just PIL,
numpy, and ffmpeg (all pre-installed on the Pi).

Stores latest frame as a class attribute so VisionSource can grab it
without needing its own camera access.

Config example:
    sources:
      - id: "camera.feed"
        type: "camera"
        device: "/dev/video0"
        width: 320
        height: 240
        fps: 2
        interval: 0.1
        motion_threshold: 3.0
        snapshot_interval: 300
"""

import io
import logging
import os
import subprocess
import time
from typing import Any, Dict, Optional

from core.data_source import DataSource
from core.registry import register_source

logger = logging.getLogger(__name__)

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


@register_source("camera")
class CameraSource(DataSource):
    """Captures frames from USB webcam via ffmpeg subprocess."""

    # Class-level frame storage for VisionSource to read
    latest_frame: Optional[Any] = None
    latest_jpeg: Optional[bytes] = None

    def __init__(self, source_id: str, bus, config: Dict):
        config.setdefault("interval", 0.1)
        super().__init__(source_id, bus, config)

        self._device = config.get("device", "/dev/video0")
        self._width = config.get("width", 320)
        self._height = config.get("height", 240)
        self._fps = config.get("fps", 2)
        self._motion_threshold = config.get("motion_threshold", 3.0)
        self._demo = config.get("demo", False)

        self._process = None
        self._prev_frame_array = None
        self._frame_size = self._width * self._height * 3  # RGB24

        # Snapshot settings
        self._snapshot_dir = config.get("snapshot_dir", "snapshots")
        self._snapshot_interval = config.get("snapshot_interval", 300)
        self._last_snapshot = 0
        self._last_restart = 0
        self._restart_backoff = 5.0  # seconds between restart attempts

    def _start_ffmpeg(self):
        """Start ffmpeg subprocess for frame capture."""
        # Check device exists
        if not os.path.exists(self._device):
            logger.warning("Camera device not found: %s", self._device)
            return False

        input_fmt = self.config.get("input_format", "")
        cmd = [
            "ffmpeg",
            "-f", "v4l2",
        ]
        if input_fmt:
            cmd += ["-input_format", input_fmt]
        cmd += [
            "-video_size", f"{self._width}x{self._height}",
            "-framerate", str(self._fps),
            "-i", self._device,
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-loglevel", "error",
            "-",
        ]
        try:
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            # Wait for ffmpeg to start producing data
            time.sleep(1.0)
            if self._process.poll() is not None:
                stderr = self._process.stderr.read().decode(errors="replace")
                logger.error("ffmpeg exited immediately: %s", stderr[:200])
                self._process = None
                return False
            logger.info("Camera ffmpeg started: %s %s @ %d fps",
                        self._device, f"{self._width}x{self._height}", self._fps)
            return True
        except FileNotFoundError:
            logger.error("ffmpeg not installed -- run 'sudo apt install ffmpeg'")
            return False
        except Exception as exc:
            logger.error("Failed to start ffmpeg: %s", exc)
            return False

    def _run(self):
        """Override base _run to skip sleep -- ffmpeg read is the rate limiter."""
        while not self._stop.is_set():
            try:
                data = self.fetch()
                if data is not None:
                    self.bus.publish(self.topic, data)
            except Exception as exc:
                logger.error("CameraSource fetch error: %s", exc)
                # Brief pause on error to avoid tight loop
                time.sleep(1.0)

    def fetch(self) -> Optional[Dict[str, Any]]:
        if not HAS_PIL:
            logger.error("PIL not available for camera source")
            return None

        # Demo mode: generate synthetic frames
        if self._demo:
            return self._generate_demo_frame()

        # Start ffmpeg if not running (with backoff to avoid device-busy loops)
        if self._process is None or self._process.poll() is not None:
            if self._process and self._process.poll() is not None:
                logger.warning("ffmpeg exited with code %d", self._process.returncode)
                self._process = None
            now = time.time()
            if now - self._last_restart < self._restart_backoff:
                time.sleep(self._restart_backoff - (now - self._last_restart))
                return None
            self._last_restart = now
            if not self._start_ffmpeg():
                time.sleep(self._restart_backoff)
                return None

        # Read one frame (blocks until data available)
        try:
            raw = self._process.stdout.read(self._frame_size)
            if len(raw) != self._frame_size:
                if len(raw) == 0 and self._process.poll() is not None:
                    logger.warning("ffmpeg exited, will restart")
                    self._process = None
                else:
                    logger.debug("Short read: %d/%d bytes, skipping frame",
                                 len(raw), self._frame_size)
                time.sleep(0.5)
                return None
        except Exception as exc:
            logger.error("Frame read error: %s", exc)
            self._process = None
            return None

        # Convert to PIL Image
        frame = Image.frombytes("RGB", (self._width, self._height), raw)

        # Store for VisionSource
        CameraSource.latest_frame = frame

        # Encode JPEG for VPS transmission
        buf = io.BytesIO()
        frame.save(buf, format="JPEG", quality=75)
        CameraSource.latest_jpeg = buf.getvalue()

        # Motion detection via numpy
        motion = False
        motion_pct = 0.0
        if HAS_NUMPY and self._prev_frame_array is not None:
            curr = np.frombuffer(raw, dtype=np.uint8).astype(np.int16)
            diff = np.abs(curr - self._prev_frame_array)
            motion_pct = float(np.mean(diff))
            motion = motion_pct > self._motion_threshold

        if HAS_NUMPY:
            self._prev_frame_array = np.frombuffer(raw, dtype=np.uint8).astype(np.int16)

        # Periodic snapshot
        now = time.time()
        if now - self._last_snapshot > self._snapshot_interval:
            self._save_snapshot(frame)
            self._last_snapshot = now

        return {
            "frame": frame,
            "motion": motion,
            "motion_pct": round(motion_pct, 1),
            "width": self._width,
            "height": self._height,
        }

    def _generate_demo_frame(self):
        """Generate a synthetic frame for demo mode."""
        if not HAS_NUMPY:
            # Solid color frame as fallback
            frame = Image.new("RGB", (self._width, self._height), "#1a3a5c")
            CameraSource.latest_frame = frame
            return {"frame": frame, "motion": False, "motion_pct": 0.0,
                    "width": self._width, "height": self._height}

        # Gradient + noise
        t = time.time()
        y_grad = np.linspace(20, 80, self._height, dtype=np.uint8)
        x_grad = np.linspace(40, 120, self._width, dtype=np.uint8)
        r = np.outer(y_grad, np.ones(self._width, dtype=np.uint8))
        g = np.outer(np.ones(self._height, dtype=np.uint8), x_grad)
        phase = int((t * 20) % 60)
        b = np.full((self._height, self._width), 60 + phase, dtype=np.uint8)
        rgb = np.stack([r, g, b], axis=-1)
        # Add a bit of noise
        noise = np.random.randint(0, 15, rgb.shape, dtype=np.uint8)
        rgb = np.clip(rgb.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        frame = Image.fromarray(rgb, "RGB")
        CameraSource.latest_frame = frame

        buf = io.BytesIO()
        frame.save(buf, format="JPEG", quality=75)
        CameraSource.latest_jpeg = buf.getvalue()

        time.sleep(0.5)  # simulate camera framerate in demo

        return {
            "frame": frame,
            "motion": False,
            "motion_pct": 0.0,
            "width": self._width,
            "height": self._height,
        }

    def _save_snapshot(self, frame):
        """Save a snapshot to disk."""
        os.makedirs(self._snapshot_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self._snapshot_dir, f"snap_{ts}.jpg")
        try:
            frame.save(path, format="JPEG", quality=85)
            logger.info("Snapshot saved: %s", path)
        except Exception as exc:
            logger.error("Snapshot save failed: %s", exc)

    def set_demo(self, demo: bool):
        """Toggle demo mode at runtime."""
        self._demo = demo
        if demo and self._process:
            self._process.terminate()
            self._process = None

    def close(self):
        """Kill ffmpeg and clean up."""
        super().close()
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        CameraSource.latest_frame = None
        CameraSource.latest_jpeg = None

# Camera Implementation Guide

**Project**: sensor-playground-mirror
**Target**: Phase 1 implementation (160x120 @ 5fps, 720p snapshots every 5 minutes)
**Date**: 2026-02-12

---

## Prerequisites

### Hardware
- Raspberry Pi 3B+ with heatsink installed
- Logitech Brio 100 USB webcam (or compatible MJPEG camera)
- 5V/2.5A power supply (camera adds ~0.5W draw)

### Software Dependencies
```bash
# Install v4l2 tools and Python bindings
sudo apt-get update
sudo apt-get install -y v4l-utils python3-opencv python3-pil python3-requests

# Or use pip in venv
source venv/bin/activate
pip install opencv-python Pillow requests numpy
```

### Verify Camera
```bash
# List video devices
v4l2-ctl --list-devices

# Check supported formats (should show MJPEG)
v4l2-ctl --device=/dev/video0 --list-formats-ext

# Test capture (should show video stream)
ffplay /dev/video0
```

---

## Implementation Steps

### Step 1: Add Camera Source

Create `sources/camera_source.py`:

```python
"""Camera data source -- USB webcam capture with MJPEG.

Publishes frames to EventBus at configured FPS.
Supports preview (low-res, continuous) and snapshot (high-res, periodic) modes.
"""

import logging
import cv2
import time
from typing import Any, Dict, Optional
from threading import Thread, Lock

from core.data_source import DataSource
from core.registry import register_source

logger = logging.getLogger(__name__)


@register_source("camera")
class CameraSource(DataSource):
    """USB camera with MJPEG preview and periodic snapshots."""

    def __init__(self, source_id: str, bus, config: Dict):
        # Preview runs at 5fps
        config.setdefault("interval", 0.2)  # 5fps = 200ms
        super().__init__(source_id, bus, config)

        self.device = config.get("device", "/dev/video0")
        self.preview_size = config.get("preview_size", (160, 120))
        self.snapshot_size = config.get("snapshot_size", (1280, 720))
        self.snapshot_interval = config.get("snapshot_interval", 300)  # 5 minutes

        self._cap = None
        self._lock = Lock()
        self._last_snapshot_time = 0
        self._init_camera()

    def _init_camera(self):
        """Initialize camera with MJPEG codec."""
        try:
            self._cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
            # Try MJPEG first (hardware-accelerated on most cameras)
            self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoCapture.fourcc('M', 'J', 'P', 'G'))
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.preview_size[0])
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.preview_size[1])
            self._cap.set(cv2.CAP_PROP_FPS, 5)

            if self._cap.isOpened():
                logger.info("Camera %s initialized at %dx%d", self.device, *self.preview_size)
            else:
                logger.error("Failed to open camera %s", self.device)
                self._cap = None
        except Exception as exc:
            logger.error("Camera init error: %s", exc)
            self._cap = None

    def fetch(self) -> Optional[Dict[str, Any]]:
        """Capture preview frame and optionally snapshot."""
        if self._cap is None or not self._cap.isOpened():
            return None

        with self._lock:
            ret, frame = self._cap.read()
            if not ret:
                logger.warning("Failed to read camera frame")
                return None

            # Convert BGR (OpenCV) to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            data = {
                "_source": self.source_id,
                "frame": frame_rgb,  # numpy array (H, W, 3)
                "width": frame_rgb.shape[1],
                "height": frame_rgb.shape[0],
                "timestamp": time.time(),
            }

            # Periodic snapshot at higher resolution
            now = time.time()
            if now - self._last_snapshot_time > self.snapshot_interval:
                snapshot = self._capture_snapshot()
                if snapshot is not None:
                    data["snapshot"] = snapshot
                    self._last_snapshot_time = now

            return data

    def _capture_snapshot(self) -> Optional[bytes]:
        """Capture high-res snapshot and return JPEG bytes."""
        try:
            # Temporarily switch resolution
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.snapshot_size[0])
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.snapshot_size[1])
            time.sleep(0.5)  # Let camera adjust

            ret, frame = self._cap.read()
            if not ret:
                return None

            # Encode as JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            logger.info("Captured %dx%d snapshot (%d KB)", *self.snapshot_size, len(buffer) // 1024)

            # Restore preview resolution
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.preview_size[0])
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.preview_size[1])

            return buffer.tobytes()

        except Exception as exc:
            logger.error("Snapshot error: %s", exc)
            return None

    def close(self):
        super().close()
        if self._cap:
            self._cap.release()
            logger.info("Camera released")
```

---

### Step 2: Add Camera Card

Create `cards/camera_card.py`:

```python
"""Camera preview card -- displays live video feed from USB camera.

Shows preview frame with timestamp and status.
Handles snapshot upload to VPS for LLM vision analysis.
"""

import logging
from tkinter import Label, Frame
from PIL import Image, ImageTk
import threading
import requests
from typing import Any, Dict, Optional

from cards.base import BaseCard
from core.registry import register_card

logger = logging.getLogger(__name__)


@register_card("camera")
class CameraCard(BaseCard):
    """Live camera preview with LLM vision analysis."""

    def __init__(self, parent, bus, config: Dict):
        super().__init__(parent, bus, config)

        self.vps_endpoint = config.get("vps_endpoint", "https://dr.eamer.dev/api/vision")
        self.upload_thread = None
        self.last_response = ""

        # Preview image label
        self.image_label = Label(
            self.container,
            bg=self.colors["card_bg"],
            width=250,
            height=180,
        )
        self.image_label.pack(pady=(0, 5))

        # Status label (timestamp + LLM response)
        self.status_label = Label(
            self.container,
            text="Waiting for camera...",
            font=("Helvetica", 9),
            fg=self.colors["text_dim"],
            bg=self.colors["card_bg"],
            wraplength=240,
            justify="left",
        )
        self.status_label.pack()

    def update_data(self, payload: Any):
        """Update preview frame and handle snapshots."""
        if payload is None:
            return

        # Update preview
        frame = payload.get("frame")
        if frame is not None:
            self._update_preview(frame)

        # Handle snapshot (upload to VPS in background)
        snapshot = payload.get("snapshot")
        if snapshot is not None:
            self._upload_snapshot_async(snapshot)

        # Update timestamp
        ts = payload.get("timestamp", 0)
        status = f"Last frame: {self._format_time(ts)}"
        if self.last_response:
            status += f"\n\n{self.last_response}"
        self.status_label.config(text=status)

    def _update_preview(self, frame):
        """Convert numpy frame to tkinter PhotoImage."""
        try:
            # frame is already RGB from camera source
            img = Image.fromarray(frame)
            img = img.resize((250, 180), Image.Resampling.BILINEAR)
            photo = ImageTk.PhotoImage(img)

            self.image_label.config(image=photo)
            self.image_label.image = photo  # Keep reference
        except Exception as exc:
            logger.error("Preview update error: %s", exc)

    def _upload_snapshot_async(self, jpeg_bytes: bytes):
        """Upload snapshot to VPS in background thread."""
        if self.upload_thread and self.upload_thread.is_alive():
            logger.debug("Upload already in progress, skipping")
            return

        self.upload_thread = threading.Thread(
            target=self._upload_snapshot,
            args=(jpeg_bytes,),
            daemon=True,
        )
        self.upload_thread.start()

    def _upload_snapshot(self, jpeg_bytes: bytes):
        """Upload snapshot and store LLM response."""
        try:
            files = {"image": ("snapshot.jpg", jpeg_bytes, "image/jpeg")}
            data = {"prompt": "What do you see in this image? Describe briefly."}

            logger.info("Uploading %d KB snapshot to VPS", len(jpeg_bytes) // 1024)
            response = requests.post(
                self.vps_endpoint,
                files=files,
                data=data,
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                self.last_response = result.get("description", "No response")
                logger.info("LLM response: %s", self.last_response[:100])
            else:
                logger.error("Upload failed: %d %s", response.status_code, response.text)
                self.last_response = f"Upload error: {response.status_code}"

        except requests.Timeout:
            logger.error("Upload timeout")
            self.last_response = "Upload timeout (VPS slow)"
        except Exception as exc:
            logger.error("Upload error: %s", exc)
            self.last_response = f"Upload error: {exc}"

    @staticmethod
    def _format_time(timestamp: float) -> str:
        """Format unix timestamp as HH:MM:SS."""
        from datetime import datetime
        return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
```

---

### Step 3: Update dashboard.yaml

Add to `dashboard.yaml`:

```yaml
pages:
  # ... existing pages ...

  - name: "Camera"
    cards:
      - type: "camera"
        source_id: "camera.preview"
        label: "Live Feed"
        vps_endpoint: "https://dr.eamer.dev/api/vision"
        color: "#42a5f5"

      - type: "system"
        source_id: "system.stats"
        label: "CPU Temp"
        metric: "cpu_temp"
        color: "#ff9800"

      - type: "system"
        source_id: "system.stats"
        label: "CPU Load"
        metric: "load_1m"
        color: "#ff5252"

sources:
  # ... existing sources ...

  - id: "camera.preview"
    type: "camera"
    device: "/dev/video0"
    preview_size: [160, 120]   # Low-res for continuous preview
    snapshot_size: [1280, 720]  # High-res for LLM analysis
    snapshot_interval: 300       # 5 minutes (300 seconds)
```

---

### Step 4: Add Thermal Monitoring

Update `cards/system_card.py` to add temperature color coding:

```python
# In SystemCard.update_data():
if self.metric == "cpu_temp":
    temp = value
    # Color-code by temperature
    if temp < 65:
        color = "#00d084"  # Green
    elif temp < 75:
        color = "#ffa726"  # Orange
    elif temp < 80:
        color = "#ff9100"  # Deep orange
    else:
        color = "#ff5252"  # Red (throttling!)
        label_text += " ⚠️"  # Warning icon

    self.value_label.config(fg=color)
```

---

### Step 5: Test & Monitor

```bash
# Run with camera enabled
python main.py --log-level DEBUG

# In another terminal, monitor temperature
watch -n 1 cat /sys/class/thermal/thermal_zone0/temp

# Check for throttling (should return 0x0)
vcgencmd get_throttled

# Monitor CPU frequency (should stay at 1400000)
watch -n 1 cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
```

**Expected behavior**:
- Preview updates at 5fps (200ms interval)
- CPU temp rises to 60-68°C over 5-10 minutes
- CPU stays at 1400MHz (no throttling)
- Snapshot captured every 5 minutes (1-2s burst)
- LLM response appears 2-5 seconds after snapshot

---

## Optimization Tips

### Reduce CPU Usage (If Needed)

1. **Lower preview resolution**:
   ```yaml
   preview_size: [128, 96]  # From 160x120
   ```

2. **Reduce preview FPS**:
   ```yaml
   interval: 0.4  # 2.5fps instead of 5fps
   ```

3. **Increase snapshot interval**:
   ```yaml
   snapshot_interval: 600  # 10 minutes instead of 5
   ```

### Improve Preview Quality (If Thermal Budget Allows)

After 24-hour test showing temps <65°C sustained:

```yaml
preview_size: [320, 240]  # From 160x120
# Expect +10% CPU, +5°C thermal
```

---

## Troubleshooting

### Camera Not Found

```bash
# Check device exists
ls -l /dev/video*

# Try different device number
v4l2-ctl --device=/dev/video1 --list-formats
```

Update `dashboard.yaml`:
```yaml
device: "/dev/video1"  # If video0 doesn't work
```

---

### Poor Frame Rate

Check if MJPEG is enabled:
```python
# In camera_source.py _init_camera():
fourcc = self._cap.get(cv2.CAP_PROP_FOURCC)
logger.info("Camera codec: %s", fourcc)
# Should print: Camera codec: MJPG
```

If codec is YUV or RAW, camera doesn't support MJPEG:
- Use lower resolution (128x96)
- Reduce FPS to 2-3

---

### VPS Upload Fails

Test endpoint manually:
```bash
curl -X POST https://dr.eamer.dev/api/vision \
  -F "image=@test.jpg" \
  -F "prompt=What do you see?"
```

If endpoint doesn't exist, set up Flask route on VPS:
```python
@app.route('/api/vision', methods=['POST'])
def vision_analysis():
    image = request.files['image']
    prompt = request.form.get('prompt', 'Describe this image.')

    # Call LLM vision API (OpenAI, Anthropic, etc.)
    response = llm_vision_api(image.read(), prompt)

    return jsonify({"description": response})
```

---

### High CPU Usage

Monitor CPU per-process:
```bash
top -p $(pgrep -f "python main.py")
```

If >70%, reduce preview resolution or FPS.

---

### Thermal Throttling

If `vcgencmd get_throttled` returns `0x50005`:
1. Check heatsink is properly attached
2. Add thermal paste if not present
3. Consider adding 5V fan
4. Reduce camera resolution/FPS

---

## Performance Validation Checklist

After implementation, verify these metrics:

- [ ] CPU usage stays <60% sustained
- [ ] CPU temp stays <70°C sustained
- [ ] No throttling after 1 hour (`vcgencmd get_throttled` = `0x0`)
- [ ] Preview updates smoothly (no stuttering)
- [ ] Snapshots captured successfully every 5 minutes
- [ ] LLM responses appear within 10 seconds
- [ ] No UI lag during snapshot capture
- [ ] RAM usage <250MB

If any fail, refer to troubleshooting section.

---

## Next Steps After Phase 1

Once Phase 1 is stable (24+ hours without throttling):

1. **Add motion detection** (Phase 2):
   - Create `sources/motion_source.py`
   - Subscribe to camera frames
   - Run frame differencing in background thread
   - Publish motion events to EventBus

2. **Add 5V fan** (if temps >65°C):
   - Connect to GPIO pin (PWM control)
   - Auto-adjust fan speed based on temp

3. **Upgrade preview resolution**:
   - Change `preview_size: [320, 240]`
   - Monitor temps for 24 hours

---

**Full performance analysis**: `/home/coolhand/geepers/reports/by-date/2026-02-12/perf-sensor-playground-camera.md`

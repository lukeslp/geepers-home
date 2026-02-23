"""Audio capture and playback for Raspberry Pi.

Handles USB microphone input and speaker/DAC output via PyAudio.
Records until silence is detected (energy-based VAD).
"""

import io
import logging
import wave

logger = logging.getLogger(__name__)

# Audio parameters
RATE = 16000        # 16kHz for speech
CHANNELS = 1        # Mono
CHUNK = 1024        # Frames per buffer
FORMAT_WIDTH = 2    # 16-bit (2 bytes)

# Silence detection
SILENCE_THRESHOLD = 500   # RMS energy threshold
SILENCE_DURATION = 1.5    # Seconds of silence to stop recording
MAX_RECORD_SECS = 15      # Hard cap on recording length


class AudioManager:
    """Manage audio capture and playback."""

    def __init__(self):
        import pyaudio
        self._pa = pyaudio.PyAudio()
        self._input_device = self._find_input_device()
        self._output_device = self._find_output_device()

        if self._input_device is None:
            raise RuntimeError("No USB microphone found")

        logger.info(
            "Audio: input=%s, output=%s",
            self._input_device,
            self._output_device,
        )

    def _find_input_device(self):
        """Find a USB audio input device."""
        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                name = info["name"].lower()
                # Prefer USB devices over built-in
                if "usb" in name or "mic" in name:
                    return i
        # Fallback to first input device
        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                return i
        return None

    def _find_output_device(self):
        """Find an audio output device."""
        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            if info["maxOutputChannels"] > 0:
                return i
        return None

    def record_until_silence(self):
        """Record audio until silence is detected. Returns WAV bytes."""
        import pyaudio
        import struct
        import math

        stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=self._input_device,
            frames_per_buffer=CHUNK,
        )

        frames = []
        silent_chunks = 0
        max_chunks = int(MAX_RECORD_SECS * RATE / CHUNK)
        silence_chunks_needed = int(SILENCE_DURATION * RATE / CHUNK)

        logger.debug("Recording started...")

        try:
            for _ in range(max_chunks):
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)

                # Calculate RMS energy
                samples = struct.unpack(f"<{CHUNK}h", data)
                rms = math.sqrt(sum(s * s for s in samples) / CHUNK)

                if rms < SILENCE_THRESHOLD:
                    silent_chunks += 1
                else:
                    silent_chunks = 0

                if silent_chunks >= silence_chunks_needed and len(frames) > 10:
                    break
        finally:
            stream.stop_stream()
            stream.close()

        if not frames:
            return None

        logger.debug("Recorded %d frames", len(frames))

        # Convert to WAV bytes
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(FORMAT_WIDTH)
            wf.setframerate(RATE)
            wf.writeframes(b"".join(frames))

        return buf.getvalue()

    def play(self, wav_bytes):
        """Play WAV audio bytes through the speaker."""
        import pyaudio

        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            stream = self._pa.open(
                format=self._pa.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                output_device_index=self._output_device,
            )
            data = wf.readframes(CHUNK)
            while data:
                stream.write(data)
                data = wf.readframes(CHUNK)
            stream.stop_stream()
            stream.close()

    def close(self):
        """Release PyAudio resources."""
        if self._pa:
            self._pa.terminate()
            self._pa = None

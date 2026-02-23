"""Wake word detection — runs locally on the Pi.

Supports two backends:
    1. Porcupine (Picovoice) — lightweight, accurate, needs API key
    2. openWakeWord — free, slightly heavier, good accuracy

Falls back gracefully: tries Porcupine first, then openWakeWord.
"""

import logging

logger = logging.getLogger(__name__)


class WakeWordDetector:
    """Detect wake word from microphone audio."""

    def __init__(self, wake_word="hey jarvis"):
        self.wake_word = wake_word
        self._backend = None
        self._impl = None

        self._init_backend()

    def _init_backend(self):
        """Try available wake word backends."""
        # Try Porcupine first (lighter on Pi)
        try:
            self._impl = _PorcupineBackend(self.wake_word)
            self._backend = "porcupine"
            logger.info("Wake word: using Porcupine (%s)", self.wake_word)
            return
        except Exception as exc:
            logger.debug("Porcupine not available: %s", exc)

        # Try openWakeWord
        try:
            self._impl = _OpenWakeWordBackend(self.wake_word)
            self._backend = "openwakeword"
            logger.info("Wake word: using openWakeWord (%s)", self.wake_word)
            return
        except Exception as exc:
            logger.debug("openWakeWord not available: %s", exc)

        raise RuntimeError(
            "No wake word backend available. "
            "Install pvporcupine or openwakeword."
        )

    def wait_for_wake_word(self):
        """Block until wake word is detected. Returns True on detection."""
        return self._impl.wait_for_wake_word()

    def close(self):
        if self._impl:
            self._impl.close()


class _PorcupineBackend:
    """Porcupine wake word detection."""

    def __init__(self, wake_word):
        import pvporcupine
        import pyaudio

        # Map friendly names to Porcupine built-in keywords
        keyword_map = {
            "hey jarvis": "jarvis",
            "jarvis": "jarvis",
            "alexa": "alexa",
            "ok google": "ok google",
            "hey siri": "hey siri",
            "computer": "computer",
            "hey computer": "computer",
        }
        kw = keyword_map.get(wake_word.lower(), "jarvis")

        self._porcupine = pvporcupine.create(keywords=[kw])
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            rate=self._porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self._porcupine.frame_length,
        )

    def wait_for_wake_word(self):
        import struct

        while True:
            pcm = self._stream.read(
                self._porcupine.frame_length, exception_on_overflow=False
            )
            pcm = struct.unpack_from(
                "h" * self._porcupine.frame_length, pcm
            )
            result = self._porcupine.process(pcm)
            if result >= 0:
                return True

    def close(self):
        if self._stream:
            self._stream.close()
        if self._pa:
            self._pa.terminate()
        if self._porcupine:
            self._porcupine.delete()


class _OpenWakeWordBackend:
    """openWakeWord detection."""

    def __init__(self, wake_word):
        import openwakeword
        import pyaudio

        openwakeword.utils.download_models()
        self._model = openwakeword.Model()
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            rate=16000,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=1280,
        )
        self._threshold = 0.5

    def wait_for_wake_word(self):
        import numpy as np

        while True:
            audio = self._stream.read(1280, exception_on_overflow=False)
            audio = np.frombuffer(audio, dtype=np.int16)
            prediction = self._model.predict(audio)
            for model_name, score in prediction.items():
                if score > self._threshold:
                    return True

    def close(self):
        if self._stream:
            self._stream.close()
        if self._pa:
            self._pa.terminate()

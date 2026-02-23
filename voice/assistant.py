"""Voice assistant — coordinates wake word, audio, and VPS communication.

Usage:
    assistant = VoiceAssistant(vps_url="https://dr.eamer.dev")
    assistant.start()       # Begin listening for wake word
    assistant.stop()        # Clean shutdown

State machine:
    IDLE → (wake word detected) → LISTENING → (silence/timeout) →
    PROCESSING → (VPS responds) → SPEAKING → (playback done) → IDLE
"""

import logging
import threading
from enum import Enum, auto

logger = logging.getLogger(__name__)


class State(Enum):
    IDLE = auto()        # Waiting for wake word
    LISTENING = auto()   # Recording user speech
    PROCESSING = auto()  # Waiting for VPS response
    SPEAKING = auto()    # Playing back TTS audio
    ERROR = auto()       # Recoverable error, will reset to IDLE


class VoiceAssistant:
    """Main voice assistant controller.

    Runs wake word detection in a background thread. When triggered,
    records audio, sends it to the VPS for STT + LLM + TTS, then
    plays the response.
    """

    def __init__(self, vps_url="https://dr.eamer.dev", on_state_change=None):
        self.vps_url = vps_url.rstrip("/")
        self.on_state_change = on_state_change
        self._state = State.IDLE
        self._running = False
        self._thread = None

        # These get initialized when hardware is available
        self._wake = None    # WakeWordDetector
        self._audio = None   # AudioManager
        self._client = None  # VPSClient

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        old = self._state
        self._state = new_state
        logger.info("Voice: %s → %s", old.name, new_state.name)
        if self.on_state_change:
            try:
                self.on_state_change(new_state)
            except Exception:
                pass

    def start(self):
        """Begin listening for the wake word."""
        if self._running:
            return

        if not self._init_hardware():
            logger.warning("Voice hardware not available — skipping start")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True
        )
        self._thread.start()
        logger.info("Voice assistant started")

    def stop(self):
        """Clean shutdown."""
        self._running = False
        if self._wake:
            self._wake.close()
        if self._audio:
            self._audio.close()
        logger.info("Voice assistant stopped")

    def _init_hardware(self):
        """Try to initialize audio hardware. Returns True on success."""
        try:
            from voice.audio import AudioManager
            self._audio = AudioManager()
        except Exception as exc:
            logger.warning("Audio init failed: %s", exc)
            return False

        try:
            from voice.wake import WakeWordDetector
            self._wake = WakeWordDetector()
        except Exception as exc:
            logger.warning("Wake word init failed: %s", exc)
            return False

        from voice.vps_client import VPSClient
        self._client = VPSClient(self.vps_url)

        return True

    def _listen_loop(self):
        """Main loop: wake word → record → process → speak → repeat."""
        while self._running:
            self.state = State.IDLE
            try:
                # Block until wake word detected
                if not self._wake.wait_for_wake_word():
                    continue

                # Record until silence
                self.state = State.LISTENING
                audio_data = self._audio.record_until_silence()
                if not audio_data:
                    continue

                # Send to VPS for STT → LLM → TTS
                self.state = State.PROCESSING
                response_audio = self._client.process(audio_data)
                if not response_audio:
                    self.state = State.ERROR
                    continue

                # Play response
                self.state = State.SPEAKING
                self._audio.play(response_audio)

            except Exception as exc:
                logger.error("Voice loop error: %s", exc)
                self.state = State.ERROR

    def get_status(self):
        """Return dict of current status for UI display."""
        return {
            "state": self._state.name.lower(),
            "running": self._running,
            "has_mic": self._audio is not None,
            "has_wake": self._wake is not None,
        }

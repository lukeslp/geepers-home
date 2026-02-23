"""VPS client — offloads STT, LLM, and TTS to dr.eamer.dev.

The Pi sends raw audio to the VPS endpoint, which returns:
    1. Transcription (STT)
    2. LLM response text
    3. TTS audio (WAV bytes)

All heavy computation happens on the VPS. The Pi just ships audio
back and forth.
"""

import json
import logging
from urllib import request, error

logger = logging.getLogger(__name__)

# VPS endpoints (to be created on dr.eamer.dev)
VOICE_ENDPOINT = "/api/voice/process"
HEALTH_ENDPOINT = "/api/voice/health"


class VPSClient:
    """Send audio to VPS, get spoken response back."""

    def __init__(self, vps_url="https://dr.eamer.dev"):
        self.vps_url = vps_url.rstrip("/")
        self._timeout = 30  # seconds — LLM can take a moment

    def process(self, audio_wav_bytes):
        """Send recorded audio to VPS, get TTS response audio back.

        Args:
            audio_wav_bytes: WAV file bytes from the microphone

        Returns:
            WAV bytes of the spoken response, or None on failure
        """
        url = f"{self.vps_url}{VOICE_ENDPOINT}"

        try:
            req = request.Request(
                url,
                data=audio_wav_bytes,
                headers={
                    "Content-Type": "audio/wav",
                    "Accept": "audio/wav",
                },
                method="POST",
            )
            with request.urlopen(req, timeout=self._timeout) as resp:
                if resp.status == 200:
                    return resp.read()
                logger.error("VPS returned status %d", resp.status)
                return None

        except error.URLError as exc:
            logger.error("VPS connection failed: %s", exc)
            return None
        except Exception as exc:
            logger.error("VPS request error: %s", exc)
            return None

    def transcribe(self, audio_wav_bytes):
        """Send audio for transcription only (no LLM/TTS).

        Returns:
            Transcription text, or None on failure
        """
        url = f"{self.vps_url}{VOICE_ENDPOINT}"

        try:
            req = request.Request(
                url,
                data=audio_wav_bytes,
                headers={
                    "Content-Type": "audio/wav",
                    "Accept": "application/json",
                },
                method="POST",
            )
            with request.urlopen(req, timeout=self._timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read())
                    return data.get("transcription")
                return None

        except Exception as exc:
            logger.error("Transcribe error: %s", exc)
            return None

    def health(self):
        """Check if the VPS voice endpoint is reachable."""
        url = f"{self.vps_url}{HEALTH_ENDPOINT}"
        try:
            req = request.Request(url, method="GET")
            with request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

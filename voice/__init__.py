"""Voice assistant module — wake word, audio capture, VPS offloading.

Local (Pi) responsibilities:
    - Wake word detection (Porcupine or openWakeWord)
    - Audio capture from USB microphone
    - Audio playback through speaker/DAC

Remote (VPS) responsibilities:
    - Speech-to-text (Whisper)
    - LLM inference (Claude, Grok, etc.)
    - Text-to-speech (ElevenLabs, Piper)

The Pi never runs heavy inference — it captures audio, detects the wake
word locally, then streams audio to the VPS for processing.
"""

from voice.assistant import VoiceAssistant

__all__ = ["VoiceAssistant"]

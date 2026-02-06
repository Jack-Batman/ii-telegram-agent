"""
Voice processing module for speech-to-text and text-to-speech.

Inspired by OpenClaw's TTS/STT integration. Supports:
- OpenAI Whisper for speech-to-text
- OpenAI TTS / Edge TTS for text-to-speech
- Telegram voice message handling
"""

from .processor import VoiceProcessor

__all__ = ["VoiceProcessor"]

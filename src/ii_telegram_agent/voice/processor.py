"""
Voice processor for STT and TTS operations.

Supports:
- OpenAI Whisper API for speech-to-text
- OpenAI TTS API for text-to-speech
- Edge TTS as a free fallback for text-to-speech
"""

import io
import tempfile
from pathlib import Path
from typing import Literal

import httpx
import structlog

logger = structlog.get_logger()


class VoiceProcessor:
    """Handles voice message transcription and synthesis."""

    def __init__(
        self,
        openai_api_key: str = "",
        tts_model: str = "tts-1",
        tts_voice: str = "nova",
        stt_model: str = "whisper-1",
        use_edge_tts_fallback: bool = True,
    ):
        self.openai_api_key = openai_api_key
        self.tts_model = tts_model
        self.tts_voice = tts_voice
        self.stt_model = stt_model
        self.use_edge_tts_fallback = use_edge_tts_fallback

    @property
    def stt_available(self) -> bool:
        """Check if speech-to-text is available."""
        return bool(self.openai_api_key)

    @property
    def tts_available(self) -> bool:
        """Check if text-to-speech is available."""
        return bool(self.openai_api_key) or self.use_edge_tts_fallback

    async def transcribe(
        self,
        audio_data: bytes,
        filename: str = "voice.ogg",
        language: str | None = None,
    ) -> str:
        """Transcribe audio to text using Whisper API.

        Args:
            audio_data: Raw audio bytes (OGG/MP3/WAV/etc.)
            filename: Original filename (helps with format detection)
            language: Optional language hint (ISO 639-1 code)

        Returns:
            Transcribed text
        """
        if not self.openai_api_key:
            raise RuntimeError("OpenAI API key required for speech-to-text")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {
                    "file": (filename, audio_data, "audio/ogg"),
                }
                data = {
                    "model": self.stt_model,
                }
                if language:
                    data["language"] = language

                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.openai_api_key}"},
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                result = response.json()

            text = result.get("text", "").strip()
            logger.info("Voice transcribed", length=len(text), language=language)
            return text

        except Exception as e:
            logger.error("Transcription failed", error=str(e))
            raise

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> bytes:
        """Convert text to speech audio.

        Tries OpenAI TTS first, falls back to Edge TTS if configured.

        Args:
            text: Text to synthesize
            voice: Voice name override
            speed: Playback speed (0.25 to 4.0)

        Returns:
            Audio bytes in OGG format
        """
        if self.openai_api_key:
            try:
                return await self._openai_tts(text, voice or self.tts_voice, speed)
            except Exception as e:
                logger.warning("OpenAI TTS failed, trying fallback", error=str(e))
                if self.use_edge_tts_fallback:
                    return await self._edge_tts(text, voice)
                raise
        elif self.use_edge_tts_fallback:
            return await self._edge_tts(text, voice)
        else:
            raise RuntimeError("No TTS provider available")

    async def _openai_tts(
        self,
        text: str,
        voice: str,
        speed: float = 1.0,
    ) -> bytes:
        """Synthesize using OpenAI TTS API."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.tts_model,
                    "input": text[:4096],  # API limit
                    "voice": voice,
                    "response_format": "opus",
                    "speed": speed,
                },
            )
            response.raise_for_status()

        logger.info("TTS synthesized via OpenAI", voice=voice, text_length=len(text))
        return response.content

    async def _edge_tts(
        self,
        text: str,
        voice: str | None = None,
    ) -> bytes:
        """Synthesize using Edge TTS (free, no API key needed)."""
        try:
            import edge_tts
        except ImportError:
            raise ImportError(
                "edge-tts not installed. Run: pip install edge-tts"
            )

        voice = voice or "en-US-AriaNeural"

        communicate = edge_tts.Communicate(text[:5000], voice)

        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        audio_data = audio_buffer.getvalue()
        logger.info("TTS synthesized via Edge TTS", voice=voice, text_length=len(text))
        return audio_data

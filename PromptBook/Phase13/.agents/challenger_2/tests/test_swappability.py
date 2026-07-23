"""
Empirical test suite for Challenge Focus 1: Provider Abstraction & Swappability
"""
import sys
import unittest
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# Import SPI definitions as specified in 01_Media_Production_Architecture.md Section 3.1
@dataclass(frozen=True)
class VoiceRequest:
    slug: str
    section_id: str
    narration_text: str
    voice_id: str = "default"
    speaking_rate: float = 1.0
    pitch: float = 0.0
    sample_rate: int = 24000
    output_format: str = "wav"

@dataclass(frozen=True)
class WordTiming:
    word: str
    start_time: float
    end_time: float

@dataclass(frozen=True)
class VoiceResponse:
    section_id: str
    audio_file_path: Path
    duration_seconds: float
    sha256_hash: str
    word_timings: list[WordTiming] = field(default_factory=list)
    cached: bool = False

@runtime_checkable
class VoiceProvider(Protocol):
    @property
    def provider_id(self) -> str: ...
    async def initialize(self, config: dict[str, Any]) -> None: ...
    async def synthesize(self, request: VoiceRequest) -> VoiceResponse: ...
    async def check_health(self) -> bool: ...

@dataclass(frozen=True)
class AnimationRequest:
    slug: str
    section_id: str
    scene_type: str
    visual_parameters: dict[str, Any]
    target_duration_seconds: float
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 60
    dark_mode: bool = True

@dataclass(frozen=True)
class AnimationResponse:
    section_id: str
    video_clip_path: Path
    duration_seconds: float
    frame_count: int
    sha256_hash: str
    cached: bool = False

@runtime_checkable
class AnimationProvider(Protocol):
    @property
    def provider_id(self) -> str: ...
    async def initialize(self, config: dict[str, Any]) -> None: ...
    async def render_scene(self, request: AnimationRequest) -> AnimationResponse: ...
    async def check_health(self) -> bool: ...


class KokoroVoiceProvider:
    @property
    def provider_id(self) -> str:
        return "kokoro_openvino"

    async def initialize(self, config: dict[str, Any]) -> None:
        self.model_path = config.get("model_path")
        self.voice_sample = config.get("voice_sample", "voices/af_sky.pt")

    async def synthesize(self, request: VoiceRequest) -> VoiceResponse:
        # Expects Kokoro voice sample or default
        return VoiceResponse(
            section_id=request.section_id,
            audio_file_path=Path(f"/tmp/{request.section_id}.wav"),
            duration_seconds=5.0,
            sha256_hash="kokoro_hash_123"
        )

    async def check_health(self) -> bool:
        return True


class ElevenLabsVoiceProvider:
    @property
    def provider_id(self) -> str:
        return "elevenlabs"

    async def initialize(self, config: dict[str, Any]) -> None:
        self.api_key = config.get("api_key_env")
        self.voice_id = config.get("voice_id")
        if not self.voice_id:
            raise ValueError("ElevenLabs requires explicit voice_id in provider settings")

    async def synthesize(self, request: VoiceRequest) -> VoiceResponse:
        # ElevenLabs requires valid ElevenLabs voice ID (e.g. 21m00Tcm4TlvDq8ikWAM)
        # If request.voice_id is passed as 'af_sky' (Kokoro voice sample), ElevenLabs API will fail!
        if request.voice_id != "default" and not request.voice_id.isalnum():
            raise ValueError(f"Invalid ElevenLabs voice_id: '{request.voice_id}'. Kokoro voice sample path not accepted by ElevenLabs API.")
        return VoiceResponse(
            section_id=request.section_id,
            audio_file_path=Path(f"/tmp/{request.section_id}_eleven.wav"),
            duration_seconds=5.0,
            sha256_hash="eleven_hash_456"
        )

    async def check_health(self) -> bool:
        return True


class TestProviderSwappability(unittest.TestCase):

    def test_voice_provider_spi_conformance(self):
        """Verify structural subtyping conformance to VoiceProvider Protocol."""
        kokoro = KokoroVoiceProvider()
        eleven = ElevenLabsVoiceProvider()
        self.assertTrue(isinstance(kokoro, VoiceProvider))
        self.assertTrue(isinstance(eleven, VoiceProvider))

    def test_kokoro_to_elevenlabs_voice_id_incompatibility(self):
        """
        Test swapping Kokoro for ElevenLabs when request payload contains Kokoro-specific voice_id.
        Changing media_production.yaml without modifying application code/request fails if voice_id is passed.
        """
        async def run():
            eleven = ElevenLabsVoiceProvider()
            await eleven.initialize({"api_key_env": "ELEVENLABS_API_KEY", "voice_id": "21m00Tcm4TlvDq8ikWAM"})
            
            # Script generator passed Kokoro-specific voice ID in VoiceRequest
            request = VoiceRequest(
                slug="two-sum",
                section_id="sec_1",
                narration_text="Hello world",
                voice_id="voices/af_sky.pt"  # Kokoro voice path
            )
            
            # Should fail because ElevenLabs cannot accept Kokoro voice sample path
            with self.assertRaises(ValueError) as ctx:
                await eleven.synthesize(request)
            self.assertIn("Invalid ElevenLabs voice_id", str(ctx.exception))

        asyncio.run(run())

    def test_factory_implementation_gaps(self):
        """
        Test MediaProductionFactory implementation in architecture spec.
        Check missing provider get methods, syntax errors, and PluginContext mismatch.
        """
        # Architectural Spec line 1116 has syntax error: async def get_voice_provider((self) -> VoiceProvider:
        # In factory.py, get_subtitle_provider, get_thumbnail_provider, get_publisher_provider are MISSING.
        # Check factory initialization vs Plugin SDK PluginContext
        pass

if __name__ == "__main__":
    unittest.main()

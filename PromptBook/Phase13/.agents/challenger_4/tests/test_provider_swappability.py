"""
Empirical test harness for Provider Swappability:
- media_production.yaml loading
- ProviderRegistry registration & retrieval for all 5 SPIs
- MediaProductionFactory instantiation and provider swappability
"""

import sys
import unittest
import asyncio
import tempfile
from pathlib import Path
from typing import Any
import yaml

# Extract or import components matching 01_Media_Production_Architecture.md Section 3
class MockVoiceProvider:
    def __init__(self):
        self.provider_id = "mock_voice"
        self.config = {}
        self.initialized = False

    async def initialize(self, config: dict[str, Any]) -> None:
        self.config = config
        self.initialized = True

    async def check_health(self) -> bool:
        return True

class MockElevenLabsVoiceProvider:
    def __init__(self):
        self.provider_id = "elevenlabs"
        self.config = {}
        self.initialized = False

    async def initialize(self, config: dict[str, Any]) -> None:
        self.config = config
        self.initialized = True

    async def check_health(self) -> bool:
        return True

class MockAnimationProvider:
    def __init__(self):
        self.provider_id = "mock_anim"
        self.config = {}
        self.initialized = False

    async def initialize(self, config: dict[str, Any]) -> None:
        self.config = config
        self.initialized = True

    async def check_health(self) -> bool:
        return True

class MockSubtitleProvider:
    def __init__(self):
        self.provider_id = "mock_sub"
        self.config = {}
        self.initialized = False

    async def initialize(self, config: dict[str, Any]) -> None:
        self.config = config
        self.initialized = True

    async def check_health(self) -> bool:
        return True

class MockThumbnailProvider:
    def __init__(self):
        self.provider_id = "mock_thumb"
        self.config = {}
        self.initialized = False

    async def initialize(self, config: dict[str, Any]) -> None:
        self.config = config
        self.initialized = True

    async def check_health(self) -> bool:
        return True

class MockPublisherProvider:
    def __init__(self):
        self.provider_id = "mock_pub"
        self.config = {}
        self.initialized = False

    async def initialize(self, config: dict[str, Any]) -> None:
        self.config = config
        self.initialized = True

    async def check_health(self) -> bool:
        return True


class ProviderRegistry:
    """Central registry mapping provider IDs to concrete implementations."""

    def __init__(self) -> None:
        self._voice_providers: dict[str, Any] = {}
        self._animation_providers: dict[str, Any] = {}
        self._subtitle_providers: dict[str, Any] = {}
        self._thumbnail_providers: dict[str, Any] = {}
        self._publisher_providers: dict[str, Any] = {}

    def register_voice(self, provider_id: str, cls: Any) -> None:
        self._voice_providers[provider_id] = cls

    def register_animation(self, provider_id: str, cls: Any) -> None:
        self._animation_providers[provider_id] = cls

    def register_subtitle(self, provider_id: str, cls: Any) -> None:
        self._subtitle_providers[provider_id] = cls

    def register_thumbnail(self, provider_id: str, cls: Any) -> None:
        self._thumbnail_providers[provider_id] = cls

    def register_publisher(self, provider_id: str, cls: Any) -> None:
        self._publisher_providers[provider_id] = cls

    def get_voice(self, provider_id: str) -> Any:
        return self._voice_providers.get(provider_id)

    def get_animation(self, provider_id: str) -> Any:
        return self._animation_providers.get(provider_id)

    def get_subtitle(self, provider_id: str) -> Any:
        return self._subtitle_providers.get(provider_id)

    def get_thumbnail(self, provider_id: str) -> Any:
        return self._thumbnail_providers.get(provider_id)

    def get_publisher(self, provider_id: str) -> Any:
        return self._publisher_providers.get(provider_id)


class MediaProductionFactory:
    """Factory instantiating and bootstrapping providers based on YAML configuration."""

    def __init__(self, registry: ProviderRegistry, config_path: str) -> None:
        self._registry = registry
        self._config = self._load_config(config_path)

    def _load_config(self, path: str) -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    async def get_voice_provider(self) -> Any:
        provider_id = self._config["providers"]["voice"]
        cls = self._registry.get_voice(provider_id)
        if not cls:
            raise KeyError(f"Voice provider '{provider_id}' not registered.")
        instance = cls()
        settings = self._config.get("provider_settings", {}).get(provider_id, {})
        await instance.initialize(settings)
        return instance

    async def get_animation_provider(self) -> Any:
        provider_id = self._config["providers"]["animation"]
        cls = self._registry.get_animation(provider_id)
        if not cls:
            raise KeyError(f"Animation provider '{provider_id}' not registered.")
        instance = cls()
        settings = self._config.get("provider_settings", {}).get(provider_id, {})
        await instance.initialize(settings)
        return instance

    async def get_subtitle_provider(self) -> Any:
        provider_id = self._config["providers"]["subtitle"]
        cls = self._registry.get_subtitle(provider_id)
        if not cls:
            raise KeyError(f"Subtitle provider '{provider_id}' not registered.")
        instance = cls()
        settings = self._config.get("provider_settings", {}).get(provider_id, {})
        await instance.initialize(settings)
        return instance

    async def get_thumbnail_provider(self) -> Any:
        provider_id = self._config["providers"]["thumbnail"]
        cls = self._registry.get_thumbnail(provider_id)
        if not cls:
            raise KeyError(f"Thumbnail provider '{provider_id}' not registered.")
        instance = cls()
        settings = self._config.get("provider_settings", {}).get(provider_id, {})
        await instance.initialize(settings)
        return instance

    async def get_publisher_provider(self) -> Any:
        provider_id = self._config["providers"]["publisher"]
        cls = self._registry.get_publisher(provider_id)
        if not cls:
            raise KeyError(f"Publisher provider '{provider_id}' not registered.")
        instance = cls()
        settings = self._config.get("provider_settings", {}).get(provider_id, {})
        await instance.initialize(settings)
        return instance


class TestProviderSwappability(unittest.TestCase):

    def setUp(self):
        self.registry = ProviderRegistry()
        self.registry.register_voice("kokoro_openvino", MockVoiceProvider)
        self.registry.register_voice("elevenlabs", MockElevenLabsVoiceProvider)
        self.registry.register_animation("manim", MockAnimationProvider)
        self.registry.register_subtitle("whisper_local", MockSubtitleProvider)
        self.registry.register_thumbnail("playwright_svg", MockThumbnailProvider)
        self.registry.register_publisher("youtube_api", MockPublisherProvider)

    def test_factory_instantiates_all_five_providers(self):
        yaml_content = """
version: "1.0"
providers:
  voice: "kokoro_openvino"
  animation: "manim"
  subtitle: "whisper_local"
  thumbnail: "playwright_svg"
  publisher: "youtube_api"
provider_settings:
  kokoro_openvino:
    device: "NPU"
"""
        with tempfile.NamedTemporaryFile("w+", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = f.name

        async def run_test():
            factory = MediaProductionFactory(self.registry, config_path)
            voice = await factory.get_voice_provider()
            anim = await factory.get_animation_provider()
            sub = await factory.get_subtitle_provider()
            thumb = await factory.get_thumbnail_provider()
            pub = await factory.get_publisher_provider()

            self.assertTrue(voice.initialized)
            self.assertEqual(voice.config.get("device"), "NPU")
            self.assertTrue(anim.initialized)
            self.assertTrue(sub.initialized)
            self.assertTrue(thumb.initialized)
            self.assertTrue(pub.initialized)

        asyncio.run(run_test())

    def test_provider_swap_via_yaml_only(self):
        yaml_content = """
version: "1.0"
providers:
  voice: "elevenlabs"
  animation: "manim"
  subtitle: "whisper_local"
  thumbnail: "playwright_svg"
  publisher: "youtube_api"
provider_settings:
  elevenlabs:
    voice_id: "21m00Tcm4TlvDq8ikWAM"
"""
        with tempfile.NamedTemporaryFile("w+", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = f.name

        async def run_test():
            factory = MediaProductionFactory(self.registry, config_path)
            voice = await factory.get_voice_provider()
            self.assertIsInstance(voice, MockElevenLabsVoiceProvider)
            self.assertEqual(voice.config.get("voice_id"), "21m00Tcm4TlvDq8ikWAM")

        asyncio.run(run_test())

    def test_unregistered_provider_raises_key_error(self):
        yaml_content = """
version: "1.0"
providers:
  voice: "unregistered_tts"
  animation: "manim"
  subtitle: "whisper_local"
  thumbnail: "playwright_svg"
  publisher: "youtube_api"
"""
        with tempfile.NamedTemporaryFile("w+", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = f.name

        async def run_test():
            factory = MediaProductionFactory(self.registry, config_path)
            with self.assertRaises(KeyError):
                await factory.get_voice_provider()

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()

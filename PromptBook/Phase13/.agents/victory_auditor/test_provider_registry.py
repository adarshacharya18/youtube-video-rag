import asyncio
import types
import sys

from run_full_code_tests import setup_environment, TARGET_FILE
import re

def test_spi_and_registry():
    setup_environment()

    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = re.findall(r"```python([\s\S]*?)```", content)
    
    global_env = {}

    src_mod = types.ModuleType('src')
    media_mod = types.ModuleType('src.media_production')
    spi_mod = types.ModuleType('src.media_production.spi')
    contracts_mod = types.ModuleType('src.media_production.spi.contracts')
    sys.modules['src'] = src_mod
    sys.modules['src.media_production'] = media_mod
    sys.modules['src.media_production.spi'] = spi_mod
    sys.modules['src.media_production.spi.contracts'] = contracts_mod

    # Exec block 3
    exec(compile(blocks[2], "<b3>", "exec"), global_env)
    for item in ["AnimationProvider", "PublisherProvider", "SubtitleProvider", "ThumbnailProvider", "VoiceProvider"]:
        setattr(contracts_mod, item, global_env[item])

    # Exec block 4
    exec(compile(blocks[3], "<b4>", "exec"), global_env)

    ProviderRegistry = global_env['ProviderRegistry']

    # Create dummy provider implementations conforming to protocols
    class DummyVoiceProvider:
        async def initialize(self, config): self.config = config
        async def synthesize_speech(self, text, voice_id, format): return b"AUDIO"
        async def list_voices(self): return ["v1"]

    class DummyAnimationProvider:
        async def initialize(self, config): self.config = config
        async def render_scene(self, script, options): return "out.mp4"

    class DummySubtitleProvider:
        async def initialize(self, config): self.config = config
        async def generate_subtitles(self, audio, format): return "1\n00:00 -> 00:01\nHi"

    class DummyThumbnailProvider:
        async def initialize(self, config): self.config = config
        async def generate_thumbnail(self, title, options): return b"PNG"

    class DummyPublisherProvider:
        async def initialize(self, config): self.config = config
        async def publish_video(self, file_path, metadata): return "https://youtu.be/123"

    import tempfile
    import yaml

    config_data = {
        "providers": {
            "voice": "kokoro_v1",
            "animation": "manim_v1",
            "subtitle": "whisper_v1",
            "thumbnail": "pillow_v1",
            "publisher": "youtube_v1",
        },
        "provider_settings": {
            "kokoro_v1": {"rate": 22050},
            "manim_v1": {"fps": 30},
            "whisper_v1": {"model": "base"},
            "pillow_v1": {"font": "sans"},
            "youtube_v1": {"privacy": "public"},
        }
    }

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp_yaml:
        yaml.dump(config_data, tmp_yaml)
        yaml_path = tmp_yaml.name

    try:
        registry = ProviderRegistry()
        registry.register_voice("kokoro_v1", DummyVoiceProvider)
        registry.register_animation("manim_v1", DummyAnimationProvider)
        registry.register_subtitle("whisper_v1", DummySubtitleProvider)
        registry.register_thumbnail("pillow_v1", DummyThumbnailProvider)
        registry.register_publisher("youtube_v1", DummyPublisherProvider)

        MediaProductionFactory = global_env['MediaProductionFactory']
        factory = MediaProductionFactory(registry, yaml_path)

        async def run_async_tests():
            voice = await factory.get_voice_provider()
            assert isinstance(voice, DummyVoiceProvider)
            assert voice.config == {"rate": 22050}

            anim = await factory.get_animation_provider()
            assert isinstance(anim, DummyAnimationProvider)
            assert anim.config == {"fps": 30}

            sub = await factory.get_subtitle_provider()
            assert isinstance(sub, DummySubtitleProvider)
            assert sub.config == {"model": "base"}

            thumb = await factory.get_thumbnail_provider()
            assert isinstance(thumb, DummyThumbnailProvider)
            assert thumb.config == {"font": "sans"}

            pub = await factory.get_publisher_provider()
            assert isinstance(pub, DummyPublisherProvider)
            assert pub.config == {"privacy": "public"}

            print("[PASS] ProviderRegistry & MediaProductionFactory dynamic bootstrapping verified.")

        asyncio.run(run_async_tests())
    finally:
        import os
        if os.path.exists(yaml_path):
            os.remove(yaml_path)

if __name__ == "__main__":
    test_spi_and_registry()

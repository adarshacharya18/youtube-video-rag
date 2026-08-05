"""
Re-export module for backward compatibility.
Exposes Voice Production components from src.core.media.voice.
"""

from src.core.media.voice import (
    AudioSegment,
    VoiceConfig,
    VoiceProviderProtocol,
    KokoroVoiceProvider,
    ManualVoiceProvider,
)

__all__ = [
    "AudioSegment",
    "VoiceConfig",
    "VoiceProviderProtocol",
    "KokoroVoiceProvider",
    "ManualVoiceProvider",
]

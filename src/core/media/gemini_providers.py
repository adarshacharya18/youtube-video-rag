"""
Gemini Media Providers (Phase 13 / Phase 14)

Provides GeminiVoiceProvider and GeminiVideoProvider using Google's new 
native `google-genai` SDK for Audio (TTS) and Video (Veo) generation capabilities.
"""

import hashlib
import logging
import os
import wave
from pathlib import Path
from typing import Optional

from src.core.exceptions import VoiceGenerationError, AnimationError
from src.core.media.voice import AudioSegment, VoiceProviderProtocol, _calculate_audio_duration, _compute_checksum

logger = logging.getLogger(__name__)

class GeminiVoiceProvider(VoiceProviderProtocol):
    """
    Concrete implementation of VoiceProviderProtocol using Gemini's native Audio Generation API.
    Requires google-genai package and GEMINI_API_KEY.
    """
    
    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        self._logger = logging.getLogger(__name__)
        self.model_name = model_name or os.getenv("GEMINI_AUDIO_MODEL", "gemini-2.5-flash")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._logger.info(f"Initialized Gemini Voice Provider with model: {self.model_name}")

    def generate_segment(self, text: str, voice_id: str, speed: float = 1.0, output_path: str = "") -> AudioSegment:
        try:
            from google import genai
        except ImportError:
            raise VoiceGenerationError("google-genai package is required for GeminiVoiceProvider. Please run `pip install google-genai`")
            
        if not output_path:
            output_path = f"gemini_voice_{hashlib.md5(text.encode()).hexdigest()[:8]}.wav"
            
        client = genai.Client(api_key=self.api_key)
        
        # Override Kokoro's default voice_id with a Gemini-compatible one
        if voice_id == "af_sky":
            voice_id = "achird"
        
        try:
            self._logger.info(f"Requesting audio generation from {self.model_name} for text length {len(text)} with voice {voice_id}")
            response = client.models.generate_content(
                model=self.model_name,
                contents=text,
                config={
                    "response_modalities": ["AUDIO"],
                    "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": voice_id}}}
                }
            )
            
            audio_data = None
            if hasattr(response, 'candidates') and response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        audio_data = part.inline_data.data
                        break
            
            if not audio_data:
                raise VoiceGenerationError("Gemini API did not return audio data in the response")
                
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2) # 16-bit PCM
                wf.setframerate(24000) # Standard Gemini TTS sample rate
                wf.writeframes(audio_data)
                
            duration = _calculate_audio_duration(str(path))
            if duration == 0.0:
                duration = max(len(text) / 15.0, 1.0) # Fallback duration heuristic
                
            return AudioSegment(
                file_path=str(path),
                duration_sec=duration,
                voice_id=voice_id,
                checksum=_compute_checksum(str(path))
            )
        except Exception as e:
            self._logger.error(f"Gemini API voice generation failed: {e}")
            raise VoiceGenerationError(f"Gemini voice generation failed: {e}") from e


class GeminiVideoProvider:
    """
    Provides video generation capabilities using Gemini's native Video Generation API (e.g., Veo 3.1).
    Requires google-genai package and GEMINI_API_KEY.
    """
    
    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        self._logger = logging.getLogger(__name__)
        self.model_name = model_name or os.getenv("GEMINI_VIDEO_MODEL", "veo-3.1")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._logger.info(f"Initialized Gemini Video Provider with model: {self.model_name}")

    def generate_video(self, prompt: str, output_path: str, duration: float = 5.0) -> str:
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise AnimationError("google-genai package is required for GeminiVideoProvider. Please run `pip install google-genai`")
            
        client = genai.Client(api_key=self.api_key)
        
        try:
            self._logger.info(f"Requesting video generation from {self.model_name} for prompt: {prompt}")
            # As per standard video generation endpoints in Gemini API
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    # Typically video generation might require specific configs or modalities
                    # We pass the prompt and let the video model generate the content
                }
            )
            
            video_data = None
            if hasattr(response, 'candidates') and response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        video_data = part.inline_data.data
                        break
            
            if not video_data:
                raise AnimationError("Gemini API did not return video data in the response")
                
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, "wb") as f:
                f.write(video_data)
                
            return str(path)
        except Exception as e:
            self._logger.error(f"Gemini API video generation failed: {e}")
            raise AnimationError(f"Gemini video generation failed: {e}") from e

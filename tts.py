"""
tts.py — Malayalam TTS using Sarvam Bulbul v3.
Free tier: ₹1000 credits on signup (~100+ videos worth).
API key from: https://dashboard.sarvam.ai
"""

import io
import base64
import logging
import requests
import os
from pydub import AudioSegment
from dotenv import load_dotenv 
from pydub.effects import speedup

logger = logging.getLogger(__name__)
load_dotenv()
SPEAKER_VOICES = {
    "SPEAKER_00": "aditya",    # male, story
    "SPEAKER_01": "gokul",    # male, clear
    "SPEAKER_02": "tanya",  # female, expressive
    "SPEAKER_03": "vijay",    # male, deep
}

ALL_VOICES = list(SPEAKER_VOICES.values())
print(ALL_VOICES)


class MalayalamTTS:
    def __init__(self):
        self.api_key = os.getenv("SARVAM_API_KEY") 
        self._speaker_index: dict[str, int] = {}
        self._next_index = 0
        logger.info("Sarvam Bulbul v3 TTS ready")

    def _get_voice(self, speaker_id: str) -> str:
        if speaker_id not in self._speaker_index:
            self._speaker_index[speaker_id] = self._next_index % len(ALL_VOICES)
            self._next_index += 1
        return ALL_VOICES[self._speaker_index[speaker_id]]

    def text_to_audio_segment(self, text: str, speaker_id: str = "SPEAKER_00") -> AudioSegment:
        if not text.strip():
            return AudioSegment.silent(duration=200)


        voice = self._get_voice(speaker_id).lower()

        try:
            response = requests.post(
                "https://api.sarvam.ai/text-to-speech",
                headers={
                    "api-subscription-key": self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "inputs": [text],            
                    "speaker": voice,
                    "target_language_code": "ml-IN", 
                    "model": "bulbul:v3",
                    "pace": 1.0
                },
                timeout=30,
            )
            
            if response.status_code != 200:
                logger.error(f"Sarvam API Error: {response.text}")
                
            response.raise_for_status()
            data = response.json()
            audio_bytes = base64.b64decode(data["audios"][0])
            return AudioSegment.from_wav(io.BytesIO(audio_bytes))

        except Exception as e:
            logger.error(f"Sarvam TTS failed for speaker {speaker_id}: {e}")
            return AudioSegment.silent(duration=500)

    def fit_audio_to_slot(self, audio: AudioSegment, slot_ms: int) -> AudioSegment:
        if slot_ms <= 0 or len(audio) <= slot_ms:
            return audio
            
        speed_ratio = min(len(audio) / slot_ms, 2.0)
        
        try:

            fitted_audio = speedup(audio, playback_speed=speed_ratio, chunk_size=50, crossfade=25)
            
            return fitted_audio[:slot_ms]
            
        except Exception as e:
            logger.warning(f"Pitch-preserving speedup failed, falling back to raw stretch: {e}")
            return audio._spawn(
                audio.raw_data,
                overrides={"frame_rate": int(audio.frame_rate * speed_ratio)},
            ).set_frame_rate(audio.frame_rate)
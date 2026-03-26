"""
tts.py — Malayalam TTS using gTTS (Google TTS Fallback).
Free, NO API KEY REQUIRED. Perfect for testing the pipeline.
"""

import io
import logging
import os
from pydub import AudioSegment
from gtts import gTTS

logger = logging.getLogger(__name__)

SPEAKER_VOICES = {
    "SPEAKER_00": "aditya",   
    "SPEAKER_01": "gokul",     
    "SPEAKER_02": "tanya",  
    "SPEAKER_03": "vijay",    
}

ALL_VOICES = list(SPEAKER_VOICES.values())
print("Loaded mock voices for compatibility.")

class MalayalamTTS:
    def __init__(self):
        self._speaker_index: dict[str, int] = {}
        self._next_index = 0
        logger.info("gTTS (Google Free TTS) fallback ready")

    def _get_voice(self, speaker_id: str) -> str:
        if speaker_id not in self._speaker_index:
            self._speaker_index[speaker_id] = self._next_index % len(ALL_VOICES)
            self._next_index += 1
        return ALL_VOICES[self._speaker_index[speaker_id]]

    def text_to_audio_segment(self, text: str, speaker_id: str = "SPEAKER_00") -> AudioSegment:
        if not text.strip():
            return AudioSegment.silent(duration=200)

        try:
            tts = gTTS(text=text, lang='ml')
            
            mp3_fp = io.BytesIO()
            tts.write_to_fp(mp3_fp)
            mp3_fp.seek(0)
            return AudioSegment.from_file(mp3_fp, format="mp3")

        except Exception as e:
            logger.error(f"gTTS failed for speaker {speaker_id}: {e}")
            return AudioSegment.silent(duration=500)

    def fit_audio_to_slot(self, audio: AudioSegment, slot_ms: int) -> AudioSegment:
        if slot_ms <= 0 or len(audio) <= slot_ms:
            return audio
        speed_ratio = min(len(audio) / slot_ms, 2.0)
        return audio._spawn(
            audio.raw_data,
            overrides={"frame_rate": int(audio.frame_rate * speed_ratio)},
        ).set_frame_rate(audio.frame_rate)
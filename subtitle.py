import whisper
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from indicnlp.transliterate.unicode_transliterate import UnicodeIndicTransliterator

# Load Whisper
whisper_model = whisper.load_model("base")

# Load IndicTrans2
model_name = "ai4bharat/indictrans2-en-indic-1B"

tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

model = AutoModelForSeq2SeqLM.from_pretrained(
    model_name,
    trust_remote_code=True
)

def format_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)

    return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"


def generate_subtitles(video_path):

    result = whisper_model.transcribe(video_path)

    segments = result["segments"]

    subtitles = []

    for seg in segments:

        english_text = seg["text"]

        input_text = f"eng_Latn mal_Mlym {english_text}"

        inputs = tokenizer(input_text, return_tensors="pt")

        outputs = model.generate(**inputs)

        translation = tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]

        translation = UnicodeIndicTransliterator.transliterate(
            translation,
            "hi",
            "ml"
        )

        subtitles.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": translation
        })

    return subtitles
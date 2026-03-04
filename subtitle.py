import os
import torch
import whisper
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from IndicTransToolkit import IndicProcessor  # <-- NEW IMPORT
from dotenv import load_dotenv

# 1. Load environment variables securely
load_dotenv()
hf_token = os.getenv("HF_TOKEN")

# 2. SPLIT DEVICES: Whisper to GPU (Small), IndicTrans2 to CPU (Massive)
whisper_device = "cuda" if torch.cuda.is_available() else "cpu"
translation_device = "cpu"  

print(f"Loading Whisper on: {whisper_device.upper()}")
whisper_model = whisper.load_model("base").to(whisper_device)

print(f"Loading IndicTrans2 on: {translation_device.upper()} (Slow, but safe from crashes)...")
model_name = "ai4bharat/indictrans2-en-indic-1B"

tokenizer = AutoTokenizer.from_pretrained(
    model_name, 
    trust_remote_code=True,
    token=hf_token
)

model = AutoModelForSeq2SeqLM.from_pretrained(
    model_name,
    trust_remote_code=True,
    token=hf_token
).to(translation_device)

# Initialize the official IndicProcessor
ip = IndicProcessor(inference=True)

def format_time(seconds):
    """Converts seconds into SRT time format (HH:MM:SS,mmm)"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"

def generate_subtitles(video_path):
    """Transcribes audio to English, then translates to Malayalam"""
    print(f"Transcribing audio for: {video_path}")
    
    # Whisper runs on GPU using stable 32-bit math
    result = whisper_model.transcribe(video_path, fp16=False)  
    segments = result["segments"]
    
    subtitles = []

    print("Translating to Malayalam... (This will take some time per sentence)")
    for seg in segments:
        english_text = seg["text"].strip()
        
        # 1. Let the official processor format the exact language tokens
        batch = ip.preprocess_batch(
            [english_text], 
            src_lang="eng_Latn", 
            tgt_lang="mal_Mlym"
        )
        
        # 2. Tokenize and safely pad the inputs
        inputs = tokenizer(
            batch, 
            truncation=True, 
            padding="longest",
            return_tensors="pt"
        ).to(translation_device)
        
        # 3. Generate Translation
        outputs = model.generate(**inputs)
        
        # 4. Decode to raw text
        raw_translation = tokenizer.batch_decode(outputs, skip_special_tokens=True)
        
        # 5. Post-process to clean up any leftover AI tokens into perfect Malayalam
        final_translation = ip.postprocess_batch(raw_translation, lang="mal_Mlym")[0]
        
        # 6. Save the segment
        subtitles.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": final_translation.strip()
        })
        
    return subtitles
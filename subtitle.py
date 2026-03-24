
import re
import time
import os
import torch
from faster_whisper import WhisperModel
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from IndicTransToolkit import IndicProcessor 
from dotenv import load_dotenv
from groq import Groq

# 1. Load environment variables
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=groq_api_key)

# 2. EXPLICIT DUAL-GPU SPLIT
whisper_device_index = 0       
translation_device = "cuda:1"  

print("Loading Faster-Whisper Offline on GPU 0...")
whisper_path = "/kaggle/input/models/aadithn/faster-whisper/pytorch/default/1/whisper-large-v3"
whisper_model = WhisperModel(
    whisper_path, 
    device="cuda", 
    device_index=whisper_device_index, 
    compute_type="float16"
)

print(f"Loading IndicTrans2 Models Offline on {translation_device}...")
en_model_path = "/kaggle/input/models/aadithn/indictrans2-en/pytorch/default/1/indictrans2-en"
hi_model_path = "/kaggle/input/models/aadithn/indictrans2-hi/pytorch/default/1/indictrans2-hi" # Adjusted folder name

en_tokenizer = AutoTokenizer.from_pretrained(en_model_path, trust_remote_code=True)
en_model = AutoModelForSeq2SeqLM.from_pretrained(en_model_path, trust_remote_code=True).to(translation_device)

hi_tokenizer = AutoTokenizer.from_pretrained(hi_model_path, trust_remote_code=True)
hi_model = AutoModelForSeq2SeqLM.from_pretrained(hi_model_path, trust_remote_code=True).to(translation_device)

ip = IndicProcessor(inference=True)

def format_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"

def get_model_and_code(source_lang):
    if source_lang == "en":
        return en_model, en_tokenizer, "eng_Latn"
    return hi_model, hi_tokenizer, "hin_Deva"

def generate_subtitles(video_path, source_lang="en"):
    print(f"\n🔄 --- AI PIPELINE STARTED [{source_lang.upper()} -> MALAYALAM] ---")
    
    # PHASE 1: WHISPER
    print("🎙️ [Phase 1] Faster-Whisper: Transcribing Audio (GPU 0)...")
    p1_start = time.time()
    prompt = "यह एक हिंदी वीडियो है जिसमें कुछ English शब्दों का प्रयोग किया गया है।" if source_lang == "hi" else None
    
    segments_generator, _ = whisper_model.transcribe(video_path, language=source_lang, initial_prompt=prompt) 
    segments = [{"start": s.start, "end": s.end, "text": s.text} for s in segments_generator]
    p1_end = time.time()
    print(f"✅ [Phase 1] Complete! Found {len(segments)} lines of dialogue.")
    
    # PHASE 2: INDICTRANS2
    print(f"\n🧠 [Phase 2] IndicTrans2: Generating Formal Malayalam (GPU 1)...")
    p2_start = time.time()
    local_translations = []
    gpu_batch_size = 16 
    t_model, t_tok, src_code = get_model_and_code(source_lang)
    
    for i in range(0, len(segments), gpu_batch_size):
        chunk_segs = segments[i:i+gpu_batch_size]
        source_texts = [seg["text"].strip() for seg in chunk_segs]
        
        print(f"   ⚙️ Processing Batch {i//gpu_batch_size + 1} (Lines {i+1}-{min(i+gpu_batch_size, len(segments))})...")
        
        batch = ip.preprocess_batch(source_texts, src_lang=src_code, tgt_lang="mal_Mlym")
        inputs = t_tok(batch, truncation=True, padding="longest", return_tensors="pt").to(translation_device)
        outputs = t_model.generate(**inputs, max_new_tokens=256, use_cache=False)
        raw_translations = t_tok.batch_decode(outputs, skip_special_tokens=True)
        formal_mals = ip.postprocess_batch(raw_translations, lang="mal_Mlym")
        
        for idx, seg in enumerate(chunk_segs):
            print(f"      [{i+idx+1}] Source : {source_texts[idx]}")
            print(f"      [{i+idx+1}] Formal : {formal_mals[idx].strip()}")
            local_translations.append({
                "start": seg["start"], "end": seg["end"],
                "source_text": source_texts[idx], "formal_text": formal_mals[idx].strip()
            })
    p2_end = time.time()
    print("✅ [Phase 2] Complete!")

    # PHASE 3: GROQ POLISH
    print(f"\n🌐 [Phase 3] Groq Llama 3.3 70B: Polishing to Natural Malayalam...")
    p3_start = time.time()
    subtitles = []
    groq_batch_size = 20 
    
    for i in range(0, len(local_translations), groq_batch_size):
        chunk = local_translations[i:i+groq_batch_size]
        print(f"   ✨ Polishing Batch {i//groq_batch_size + 1} (Lines {i+1}-{min(i+groq_batch_size, len(local_translations))})...")
        
        chunk_prompt = "".join([f"Line {idx+1}:\nSource: {item['source_text']}\nFormal Mal: {item['formal_text']}\n\n" for idx, item in enumerate(chunk)])
            
        # 1. Dynamically name the language for the AI
        lang_name = "English" if source_lang == "en" else "Hindi/Hinglish"
        
        # 2. Build the dynamic prompt
        system_prompt = f"""You are a Master Malayalam Linguist and Subtitle Editor. Fix machine translations from {lang_name} to sound logical, natural, and native.

### UNIVERSAL EDITING RULES:
1. DYNAMIC CONTEXT & PRONOUNS: Use the [PREVIOUS STORY CONTEXT] to identify the subject, gender, and tone. 
   - Maintain strict pronoun consistency (അവൻ/അവൾ/അദ്ദേഹം/അവർ). 
   - Use 'അവ' or 'അത്' for inanimate objects/animals unless the context clearly personifies them.
2. THE DATIVE TRAP: NEVER randomly inject phrases like "എനിക്കറിയാം" (I know) unless the {lang_name} source explicitly contains that exact meaning. Translate ONLY the information present in the source text.
3. SMART TYPO CORRECTION: The {lang_name} source text is generated by a speech-to-text AI and may contain phonetic spelling mistakes. Translate the *logical intent* of the sentence based on the surrounding context, not the literal broken word.
4. MODERN PHRASING: If the speaker is using modern concepts, retain common English loan words written in Malayalam script (e.g., ഓഫീസ്, ഫോൺ, ക്ലാസ്) instead of forcing robotic, archaic dictionary words.
5. STRICT FORMATTING: Output ONLY the polished Malayalam text, separated by the exact delimiter "|||". Do not include "Line X" markers, quotes, or conversational filler.
Example: [Polished Line 1] ||| [Polished Line 2]"""

        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chunk_prompt}
            ],
            model="llama-3.3-70b-versatile", 
            temperature=0.1, 
        )
        
        raw_content = chat_completion.choices[0].message.content.strip()
        polished_lines = [line.strip() for line in raw_content.split("|||")]
        
        for idx, item in enumerate(chunk):
            natural_text = polished_lines[idx] if idx < len(polished_lines) else item['formal_text']
            natural_text = re.sub(r'<think>.*?</think>', '', natural_text, flags=re.DOTALL).strip()
            natural_text = re.sub(r'^Line \d+:\s*', '', natural_text).strip()
            
            print(f"      [{i+idx+1}] Natural: {natural_text}")
            
            subtitles.append({
                "start": item["start"], "end": item["end"],
                "source_text": item["source_text"], "formal_text": item["formal_text"],
                "natural_text": natural_text
            })
            
    p3_end = time.time()
    print("✅ [Phase 3] Complete!\n")
    return subtitles, {"p1": p1_end - p1_start, "p2": p2_end - p2_start, "p3": p3_end - p3_start}
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

# 2. DUAL-GPU SPLIT
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
hi_model_path = "/kaggle/input/models/aadithn/indictrans2-hi/pytorch/default/1/indictrans2-hi"
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

def generate_subtitles(video_path, source_lang="en", video_title="Unknown Video"):
    print(f"\n🔄 --- AI PIPELINE STARTED [{source_lang.upper()} -> MALAYALAM] ---")
    
    # PHASE 1: WHISPER
    print("🎙️ [Phase 1] Faster-Whisper: Transcribing Audio (GPU 0)...")
    p1_start = time.time()
    if source_lang == "hi":
        prompt = f"यह '{video_title}' नामक एक स्पष्ट हिंदी वीडियो है। कृपया सही व्याकरण (grammar) और शब्दों का प्रयोग करें।"
    else:
        prompt = f"This is a clear English video titled '{video_title}'. Please transcribe accurately using proper context."
    
    segments_generator, _ = whisper_model.transcribe(
    video_path, 
    language=source_lang, 
    initial_prompt=prompt,
    vad_filter=True,                                  
    vad_parameters=dict(min_silence_duration_ms=400)   
    ) 
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
    print(f"\n🌐 [Phase 3] Groq OpenAI GPT-OSS 120B: Polishing to Natural Malayalam...")
    p3_start = time.time()
    subtitles = []
    groq_batch_size = 20 
    
    for i in range(0, len(local_translations), groq_batch_size):
        chunk = local_translations[i:i+groq_batch_size]
        print(f"   ✨ Polishing Batch {i//groq_batch_size + 1} (Lines {i+1}-{min(i+groq_batch_size, len(local_translations))})...")
        
        chunk_prompt = "".join([f"Line {idx+1}:\nSource: {item['source_text']}\nFormal Mal: {item['formal_text']}\n\n" for idx, item in enumerate(chunk)])
            
        lang_name = "English" if source_lang == "en" else "Hindi/Hinglish"
        
        system_prompt = f"""You are a Master Malayalam Translator and Subtitle Editor. Your task is to rewrite stiff, machine-translated "Formal Malayalam" into highly engaging, natural, and everyday spoken Malayalam.

### CRITICAL CONTEXT:
The text you are translating is from a video titled: "{video_title}"
Use this title to deduce the genre (e.g., gaming, sports commentary, tech, vlog). Adapt your vocabulary to perfectly match this specific genre.

### LINGUISTIC RULES & ANCHORING BIAS:
1. DO NOT TRUST THE DRAFT FOR METAPHORS: The "Formal Mal" draft was generated by a flawed AI that takes English idioms and descriptive words too literally. If the draft's literal meaning doesn't fit the video's genre, IGNORE THE DRAFT completely and translate the {lang_name} Source from scratch.
2. DE-FORMALIZE (അച്ചടി ഭാഷ ഒഴിവാക്കുക): Make it sound like a natural human speaking. Relax strict verb endings.
3. DROP DEAD WEIGHT: Spoken Malayalam frequently drops pronouns (ഞാൻ, നീ, അത്, അവൻ). Strip them out unless absolutely necessary.
4. MANGILISH: Retain common English words in Malayalam script (e.g., ഫോൺ, ഗെയിം, മാച്ച്, ഗോൾ, ട്രോഫി) rather than forcing robotic dictionary words.

### EXAMPLE OF FIXING MACHINE LITERALS:
Source: "He was on fire today."
Machine Draft: "അവൻ ഇന്ന് തീയിലായിരുന്നു." (Literal: He was physically in fire)
Your Polished Output: "അവൻ ഇന്ന് മിന്നുന്ന ഫോമിലായിരുന്നു." (Contextual: He was in dazzling form)

### FORMATTING:
Output ONLY the polished Malayalam sentences, separated by the exact delimiter "|||". Do not output conversational filler.

Example Output Format:
[Polished Line 1] ||| [Polished Line 2] ||| [Polished Line 3]"""

        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chunk_prompt}
            ],
            model="openai/gpt-oss-120b", 
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
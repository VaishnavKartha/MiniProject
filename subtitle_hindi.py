import re
import time
import os
import torch
from faster_whisper import WhisperModel
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from IndicTransToolkit import IndicProcessor 
from dotenv import load_dotenv
from groq import Groq

# 1. Load environment variables securely
load_dotenv()
hf_token = os.getenv("HF_TOKEN")
groq_api_key = os.getenv("GROQ_API_KEY")

# 2. Initialize Groq Client
groq_client = Groq(api_key=groq_api_key)

# 3. SPLIT DEVICES
whisper_device = "cuda"
translation_device = "cuda"  

print("Loading Faster-Whisper (Large-v3) on: CUDA...")
# compute_type="float16" forces it to use the GPU's fastest memory mode
whisper_model = WhisperModel("large-v3", device="cuda", compute_type="float16")

print(f"Loading IndicTrans2 (Indic-to-Indic) on: {translation_device.upper()}...")
model_name = "ai4bharat/indictrans2-indic-indic-1B"

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
    """Pipeline: Native Whisper (GPU) -> IndicTrans2 (GPU Batched) -> Llama 3.3 70B (Cloud Batched)"""
    print(f"Transcribing Hindi/Hinglish audio for: {video_path}")
    
    # --- PHASE 1: FASTER-WHISPER ---
    # Faster-whisper returns a generator, meaning it streams results instantly
    p1_start = time.time()
    segments_generator, info = whisper_model.transcribe(
        video_path, 
        language="hi",
        initial_prompt="यह एक हिंदी वीडियो है जिसमें कुछ English शब्दों का प्रयोग किया गया है।"
    ) 
    
    # Unpack the fast stream into our standard dictionary format
    segments = []
    for s in segments_generator:
        segments.append({
            "start": s.start,
            "end": s.end,
            "text": s.text
        })
        
    p1_end = time.time()
    print(f"Transcription complete! Found {len(segments)} lines of dialogue.")
    
    # --- PHASE 2: BATCHED GPU TRANSLATION (INDIC TRANS 2) ---
    print("Translating Malayalam locally via GPU (Batched)...")
    p2_start = time.time()
    local_translations = []
    gpu_batch_size = 16  # Feed 16 sentences to the GPU at once!
    
    for i in range(0, len(segments), gpu_batch_size):
        chunk_segs = segments[i:i+gpu_batch_size]
        hindi_texts = [seg["text"].strip() for seg in chunk_segs]
        print(f"GPU Translating lines {i+1} to {min(i+gpu_batch_size, len(segments))}...")
        
        batch = ip.preprocess_batch(hindi_texts, src_lang="hin_Deva", tgt_lang="mal_Mlym")
        inputs = tokenizer(batch, truncation=True, padding="longest", return_tensors="pt").to(translation_device)
        
        outputs = model.generate(**inputs, max_new_tokens=256, use_cache=False)
        raw_translations = tokenizer.batch_decode(outputs, skip_special_tokens=True)
        formal_malayalams = ip.postprocess_batch(raw_translations, lang="mal_Mlym")
        
        for idx, seg in enumerate(chunk_segs):
            local_translations.append({
                "start": seg["start"],
                "end": seg["end"],
                "hindi_text": hindi_texts[idx],
                "formal_text": formal_malayalams[idx].strip()
            })
    p2_end = time.time()

    # --- PHASE 3: BATCHED CLOUD POLISHING (GROQ 70B MODEL) ---
    print("Sending batched translations to Groq (Llama 3.3 70B) for polishing...")
    p3_start = time.time()
    subtitles = []
    groq_batch_size = 20 # Process 20 lines in a single API call!
    
    for i in range(0, len(local_translations), groq_batch_size):
        chunk = local_translations[i:i+groq_batch_size]
        print(f"Polishing lines {i+1} to {min(i+groq_batch_size, len(local_translations))}...")
        
        chunk_prompt = ""
        for idx, item in enumerate(chunk):
            chunk_prompt += f"Line {idx+1}:\nHindi: {item['hindi_text']}\nFormal Mal: {item['formal_text']}\n\n"
            
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": """You are a Master Malayalam Linguist and Subtitle Editor. Your mission is to fix machine translations to sound like a native speaker while maintaining the strict timing and meaning of the Hindi/Hinglish source.

### UNIVERSAL TRANSLATION LAWS:
1. CONTEXTUAL AWARENESS: Analyze the entire batch of lines to determine the domain (e.g., educational, narrative story, casual vlog). Maintain consistent terminology for subjects and objects throughout the batch. Do not randomly change the species, gender, or core identity of a subject mid-conversation.
2. TRANSLATE INTENT, NOT LITERAL WORDS: If the Hindi source uses slang, idioms, or conversational threats (e.g., "पंगा मत लेना"), translate the *intent* into a natural Malayalam equivalent (e.g., "എന്നോട് കളിക്കാൻ നിൽക്കരുത്"). Never translate idioms word-for-word if it creates nonsense.
3. THE DATIVE CASE: Malayalam relies heavily on the dative case for feelings, knowledge, and abilities. "I know" MUST be 'എനിക്കറിയാം'. Do not use literal subject-verb pairings for these states.
4. PRONOUN & GENDER CONSISTENCY:
   - Track characters accurately. If a subject is established as male, strictly use അവൻ/അദ്ദേഹം. Do not accidentally swap to അവൾ (She).
   - Maintain a consistent level of formality (നീ vs നിങ്ങൾ) between speakers. Ensure the verb suffixes match the chosen pronoun.
5. HINGLISH TO MALAYALAM: If the speaker uses English loan words for modern concepts, retain the English word written in Malayalam script rather than forcing a highly archaic, robotic Malayalam translation.

### OUTPUT FORMAT:
I will provide a batch of lines. You MUST output ONLY the polished Malayalam translations, separated by the exact delimiter "|||". Do not include "Line X:" markers.
Example:
[Polished Line 1] ||| [Polished Line 2] ||| [Polished Line 3]"""
                },
                {
                    "role": "user",
                    "content": chunk_prompt
                }
            ],
            model="llama-3.3-70b-versatile", # UPGRADED TO 70B!
            temperature=0.1, 
        )
        
        raw_content = chat_completion.choices[0].message.content.strip()
        
        # Split the batched response back into individual lines based on our delimiter
        polished_lines = [line.strip() for line in raw_content.split("|||")]
        
        # Re-attach timings and append to final subtitles list
        for idx, item in enumerate(chunk):
            # Fallback to formal text if Groq missed a delimiter
            natural_text = polished_lines[idx] if idx < len(polished_lines) else item['formal_text']
            
            # Clean up potential <think> tags or leftover "Line X:" markers
            natural_text = re.sub(r'<think>.*?</think>', '', natural_text, flags=re.DOTALL).strip()
            natural_text = re.sub(r'^Line \d+:\s*', '', natural_text).strip()
            
            subtitles.append({
                "start": item["start"],
                "end": item["end"],
                "hindi_text": item["hindi_text"],
                "formal_text": item["formal_text"],
                "natural_text": natural_text
            })
    p3_end = time.time()
    phase_times = {
        "p1_min": (p1_end - p1_start) / 60,
        "p2_min": (p2_end - p2_start) / 60,
        "p3_min": (p3_end - p3_start) / 60
    }

    return subtitles,phase_times

def process_live_chunk(audio_path, previous_context=""):
    """Processes a single live audio chunk with VAD and Contextual Memory."""
    
    # 1. WHISPER WITH VAD: Strips silence and perfectly pads the audio
    segments_generator, info = whisper_model.transcribe(
        audio_path, 
        language="hi",
        initial_prompt="यह एक हिंदी वीडियो है जिसमें कुछ English शब्दों का प्रयोग किया गया है।",
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500, # The "Post-roll" cut
            speech_pad_ms=300            # The "Pre-roll" buffer
        )
    )
    
    hindi_text = " ".join([s.text for s in segments_generator]).strip()
    
    # If the VAD filtered out all the noise and found no voice, abort!
    if not hindi_text:
        return ""

    # 2. INDICTRANS2: Translate locally
    batch = ip.preprocess_batch([hindi_text], src_lang="hin_Deva", tgt_lang="mal_Mlym")
    inputs = tokenizer(batch, truncation=True, padding="longest", return_tensors="pt").to(translation_device)
    outputs = model.generate(**inputs, max_new_tokens=256, use_cache=False)
    raw_translation = tokenizer.batch_decode(outputs, skip_special_tokens=True)
    formal_malayalam = ip.postprocess_batch(raw_translation, lang="mal_Mlym")[0]

    # 3. GROQ: Cloud Polish with Memory
    chat_completion = groq_client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a real-time Malayalam translator. Fix the machine translation to sound natural. Output ONLY the Malayalam text, no quotes or explanations."
            },
            {
                "role": "user",
                "content": f"[PREVIOUS CONTEXT - DO NOT TRANSLATE]: {previous_context}\n\n[TRANSLATE THIS]:\nHindi: {hindi_text}\nFormal Mal: {formal_malayalam}"
            }
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.1, 
    )
    
    natural_malayalam = chat_completion.choices[0].message.content.strip()
    natural_malayalam = re.sub(r'<think>.*?</think>', '', natural_malayalam, flags=re.DOTALL).strip()
    
    return natural_malayalam
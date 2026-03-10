import re
import os
import torch
import whisper
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from IndicTransToolkit import IndicProcessor 
from dotenv import load_dotenv
from groq import Groq  # <-- NEW IMPORT

# 1. Load environment variables securely
load_dotenv()
hf_token = os.getenv("HF_TOKEN")
groq_api_key = os.getenv("GROQ_API_KEY")

# 2. Initialize Groq Client
groq_client = Groq(api_key=groq_api_key)

# 3. SPLIT DEVICES: Whisper to GPU (Small), IndicTrans2 to CPU (Massive)
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
    """Pipeline: Whisper (Local) -> IndicTrans2 (Local) -> Llama 3.3 (Cloud Polish)"""
    print(f"Transcribing audio for: {video_path}")
    
    # Phase 1: Whisper runs locally on GPU
    result = whisper_model.transcribe(video_path, fp16=False)  
    segments = result["segments"]
    
    subtitles = []

    print("Translating and Polishing Malayalam... (Processing line-by-line)")
    for seg in segments:
        english_text = seg["text"].strip()
        
        # --- PHASE 2: Local Formal Translation (IndicTrans2) ---
        batch = ip.preprocess_batch([english_text], src_lang="eng_Latn", tgt_lang="mal_Mlym")
        inputs = tokenizer(batch, truncation=True, padding="longest", return_tensors="pt").to(translation_device)
        outputs = model.generate(**inputs, max_new_tokens=256)
        raw_translation = tokenizer.batch_decode(outputs, skip_special_tokens=True)
        formal_malayalam = ip.postprocess_batch(raw_translation, lang="mal_Mlym")[0]
        
        # --- PHASE 3: Cloud Conversational Polish (Groq Llama 3.3) ---
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": """You are a Master Malayalam Linguist and Subtitle Editor. Your mission is to fix the 'Uncanny Valley' of robotic machine translation. You must produce text that sounds like a native speaker from Kerala while maintaining the strict timing and meaning of the English source.

### PHASE 1: THE "NATIVE EAR" GRAMMAR CHECK
1. DATIVE CASE (THE 'TO ME' RULE): Never translate 'I know' as 'ഞാൻ അറിയാം'. Use the dative: 'എനിക്കറിയാം'. Apply this to all feelings/knowledge (e.g., 'എനിക്ക് ഇഷ്ടമാണ്', 'എനിക്ക് വിശക്കുന്നു').
2. INANIMATE PRONOUNS: If 'They' or 'It' refers to plants, animals, or objects, use 'അവ' or 'അവയ്ക്ക്'. NEVER use 'അവർ' (Human-only) for non-humans.
3. AGE-APPROPRIATE SOCIAL TONE: 
   - Use 'അവൻ/അവൾ' for children or younger people.
   - Use 'അദ്ദേഹം/അവർ' for respected elders.
   - NEVER use 'അയാൾ' for a child; it is socially jarring.

### PHASE 2: SUBJECT-VERB HARMONY & CONSISTENCY
1. SUFFIX MATCHING: Ensure verb endings match the pronoun choice. 
   - If using 'നിങ്ങൾ', verbs must end in formal/neutral tones (-ഉന്നു, -അണ്).
   - If using 'നീ', verbs must end in informal/familiar tones.
2. CONSISTENCY: Do not flip-flop between formal (നിങ്ങൾ) and informal (നീ) within the same conversation.
3. PRONOUN LOOPS: Avoid 'നിനക്ക്' if you started with 'നിങ്ങൾ'. Match the respect level throughout.

### PHASE 3: VOCABULARY & LOAN WORDS (90% RULE)
1. LOAN WORDS: Use English words written in Malayalam script for technology and modern life.
   - USE: ഗാർഡൻ (Garden), ഫോട്ടോ (Photo), ക്ലാസ് (Class), കറൻ്റ് (Current), ഹോസ്പിറ്റൽ (Hospital).
   - AVOID: 'പൂന്തോട്ടം നടത്തുക' (sounds robotic); use 'ഗാർഡനിംഗ്' or 'ചെടി വളർത്തുക'.
2. NATURAL PHRASING: Instead of '...ലേക്ക് സ്വാഗതം', use '...ലേക്ക് വെൽക്കം' for casual video intros.

### PHASE 4: RECENT FAILURE FIXES (THE "STRICT" RULES)
1. NO SLANG HALLUCINATIONS: Never use 'അടിയോ' or weird slang for exclamations like 'Oh geez'. Use natural Malayalam sounds like 'എന്റെ ഈശ്വരാ' (My God) or 'കഷ്ടം' (Too bad).
2. IDIOM PROTECTION: In educational contexts, do not simplify the idiom. If the English says 'weed', use 'കള' (weed), not 'ചെടി' (plant).
3. NO FILLERS: Remove 'ആകുന്നു' or 'താന്' (than) as sentence endings. For 'He is only 10', use 'അവന് പത്ത് വയസ്സേയുള്ളൂ'.
4. NO ADDITIONS: Do not add tag questions like 'അല്ലേ?' unless the English source is a question.

### PHASE 5: INPUT STRUCTURE
I will provide:
- English Original: [Raw Source]
- Formal Malayalam Reference: [Structure provided by IndicTrans2]

Your task is to use the 'Formal Malayalam' as a structural guide but rewrite it entirely using the 'Native Ear' rules above.

OUTPUT ONLY THE REWRITTEN MALAYALAM SCRIPT. NO QUOTES. NO EXPLANATIONS."""
                },
                {
                    "role": "user",
                    "content": f"English Original: {english_text}\nFormal Malayalam Translation: {formal_malayalam}"
                }
            ],
            model="llama-3.3-70b-versatile", 
            temperature=0.1, 
        )
        

        # ... inside your loop after getting chat_completion ...
        raw_content = chat_completion.choices[0].message.content.strip()

        # Use Regex to remove the <think> blocks so they don't end up in your subtitles
        natural_malayalam = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()
        
        # Save all three versions in the dictionary to pass to main.py
        subtitles.append({
            "start": seg["start"],
            "end": seg["end"],
            "english_text": english_text,
            "formal_text": formal_malayalam.strip(),
            "natural_text": natural_malayalam
        })
        
    return subtitles
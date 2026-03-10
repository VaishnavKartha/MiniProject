import re
import os
import torch
import shutil
import nemo.collections.asr as nemo_asr
# 1. Import the SPECIFIC model class to fix the Abstract Class error
from nemo.collections.asr.models import EncDecHybridRNNTCTCBPEModel
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from IndicTransToolkit import IndicProcessor 
from dotenv import load_dotenv
from groq import Groq
from omegaconf import open_dict

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 2. DEVICE SETUP
asr_device = "cuda" if torch.cuda.is_available() else "cpu"
translation_device = "cpu" 

import tarfile
from huggingface_hub import hf_hub_download
from omegaconf import OmegaConf

# 3. LOAD AI4BHARAT INDICCONFORMER (TOTAL OVERRIDE MODE)
print(f"Loading AI4Bharat IndicConformer on: {asr_device.upper()}")

model_repo = "ai4bharat/indicconformer_stt_hi_hybrid_rnnt_large"
nemo_filename = "indicconformer_stt_hi_hybrid_rnnt_large.nemo"

# Step 1: Download
nemo_path = hf_hub_download(repo_id=model_repo, filename=nemo_filename)

# Step 2: Full Extraction
extract_dir = os.path.join(os.getcwd(), "full_model_extract")
if not os.path.exists(extract_dir):
    os.makedirs(extract_dir, exist_ok=True)
    with tarfile.open(nemo_path, "r") as tar:
        tar.extractall(path=extract_dir)

# Step 3: Physical YAML Edit
yaml_path = os.path.join(extract_dir, "model_config.yaml")
with open(yaml_path, "r") as f:
    lines = f.readlines()

# Rewrite the file without the 'dir' lines to stop the pop() crash
with open(yaml_path, "w") as f:
    for line in lines:
        if "dir:" not in line: 
            f.write(line)

# Step 4: Load using the patched YAML
patched_cfg = OmegaConf.load(yaml_path)

# THE DUMMY FIX: Create folders and files so the registration doesn't crash
dummy_dir = os.path.join(extract_dir, "dummy_tokenizer")
os.makedirs(dummy_dir, exist_ok=True)
vocab_file = os.path.join(dummy_dir, "vocab.txt")
if not os.path.exists(vocab_file):
    with open(vocab_file, "w") as f:
        f.write("")

with open_dict(patched_cfg):
    # 1. DUMMY DATASETS (The "Struct-Safe" Fix)
    # We add 'shuffle' and 'batch_size' so NeMo doesn't crash trying to add them
    dummy_ds = {
        'manifest_filepath': None, 
        'sample_rate': 16000,
        'shuffle': False,
        'batch_size': 1
    }
    
    patched_cfg.train_ds = None
    patched_cfg.validation_ds = dummy_ds 
    patched_cfg.test_ds = None

    # 2. COMPONENT-SPECIFIC MAPPING
    # RNNT Decoder: Remove all manual size keys. 
    # It will pull the '256' count from the tokenizer automatically.
    if 'decoder' in patched_cfg:
        patched_cfg.decoder.pop('vocabulary_size', None)
        patched_cfg.decoder.pop('num_classes', None)
        patched_cfg.decoder.pop('multisoftmax', None)
            
    # CTC Decoder: Needs num_classes
    if 'aux_ctc' in patched_cfg and 'decoder' in patched_cfg.aux_ctc:
        patched_cfg.aux_ctc.decoder.num_classes = 256
        patched_cfg.aux_ctc.decoder.pop('multisoftmax', None)
    
    # RNNT Joint: Needs num_classes
    if 'joint' in patched_cfg:
        patched_cfg.joint.num_classes = 256
        for arg in ['multilingual', 'language_keys', 'fuse_loss_softmax']:
            patched_cfg.joint.pop(arg, None)

    # 3. TOKENIZER SETUP (Verified Working)
    if 'tokenizer' in patched_cfg:
        patched_cfg.tokenizer.dir = dummy_dir
        patched_cfg.tokenizer.type = 'bpe'
        tokenizer_file = next((f for f in os.listdir(extract_dir) if f.endswith('.model')), "tokenizer.model")
        patched_cfg.tokenizer.model_path = os.path.join(extract_dir, tokenizer_file)
        patched_cfg.tokenizer.vocab_path = vocab_file
    
    # 4. SRT DECODING PREP
    if 'decoding' in patched_cfg:
        patched_cfg.decoding.strategy = "greedy"
        # Force the model to NOT use CUDA graphs
        patched_cfg.decoding.cuda_graphs = False 
        patched_cfg.decoding.preserve_alignments = True
        patched_cfg.decoding.compute_timestamps = True

# 3. Instantiate model - Now it won't try to shuffle non-existent data
print("Instantiating model architecture...")
asr_model = EncDecHybridRNNTCTCBPEModel(cfg=patched_cfg)

# ... [Rest of your loading code: load_state_dict, freeze, etc.] ...

# 4. Manually load the weights
print("Loading and slicing model weights...")
ckpt_path = os.path.join(extract_dir, "model_weights.ckpt")
state_dict = torch.load(ckpt_path, map_location='cpu')

# SURGICAL WEIGHT SLICING:
# The checkpoint has 5633 entries, but our model needs only 257.
# We slice the tensors to match our architecture.
keys_to_slice = [
    "decoder.prediction.embed.weight",
    "ctc_decoder.decoder_layers.0.weight",
    "ctc_decoder.decoder_layers.0.bias",
    "joint.joint_net.0.weight", # Also check if Joint net needs slicing
    "joint.joint_net.0.bias"
]

for key in list(state_dict.keys()):
    if key in keys_to_slice:
        original_weight = state_dict[key]
        # Slice to the first 257 entries
        state_dict[key] = original_weight[:257]
        print(f"Slicing {key}: {original_weight.shape} -> {state_dict[key].shape}")

# Now load the sliced state_dict
asr_model.load_state_dict(state_dict, strict=False)

asr_model.freeze()
asr_model = asr_model.to(asr_device)
asr_model.eval()
print("\n--- IndicConformer loaded successfully! ---")

# 4. LOAD INDICTRANS2
print("Loading IndicTrans2 (1B Indic-Indic) on CPU...")
it_model_name = "ai4bharat/indictrans2-indic-indic-1B"
tokenizer = AutoTokenizer.from_pretrained(it_model_name, trust_remote_code=True)
model = AutoModelForSeq2SeqLM.from_pretrained(it_model_name, trust_remote_code=True).to(translation_device).float()
ip = IndicProcessor(inference=True)

def format_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"

def format_srt_custom(subtitles, key_name):
    srt_content = ""
    for i, sub in enumerate(subtitles):
        srt_content += f"{i+1}\n{format_time(sub['start'])} --> {format_time(sub['end'])}\n{sub[key_name]}\n\n"
    return srt_content

import librosa # Add this to your imports at the top

import traceback # Add this to your imports at the top
import librosa
import subprocess
def generate_hin_subtitles(video_path):
    print(f"\n--- Starting Processing: {video_path} ---")
    # NEW: Convert Video to Clean WAV to bypass 'torchaudio.io' errors
    audio_wav_path = video_path.replace(".mp4", "_temp.wav")
    print("DEBUG: Converting video to 16kHz Mono WAV...")
    
    conversion_cmd = [
        'ffmpeg', '-y', '-i', video_path, 
        '-vn', '-acodec', 'pcm_s16le', 
        '-ar', '16000', '-ac', '1', 
        audio_wav_path
    ]
    
    try:
        subprocess.run(conversion_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"DEBUG: FFmpeg conversion failed: {e}")
        # If conversion fails, we try to proceed, but it'll likely hit the torchaudio error again

    try:
        # Step 1: Duration Check
        print("DEBUG: Calculating video duration...")
        try:
            y, sr = librosa.load(video_path, sr=None)
            video_duration = librosa.get_duration(y=y, sr=sr)
            print(f"DEBUG: Duration is {video_duration:.2f}s")
        except Exception as e:
            print(f"DEBUG Librosa error: {e}")
            video_duration = 30.0

        # Step 2: Transcription
        print("DEBUG: Running ASR model.transcribe()...")
        with torch.no_grad():
            # Use the WAV path instead of the MP4 path!
            raw_result = asr_model.transcribe([audio_wav_path], batch_size=1)
        
        # Step 3: Precise Unpacking of Hypothesis Object
        if isinstance(raw_result, tuple):
            print("DEBUG: Unpacking tuple result...")
            full_result = raw_result[0]
        else:
            full_result = raw_result

        # If it's a list (usually is), get the first item
        if isinstance(full_result, list) and len(full_result) > 0:
            full_result = full_result[0]
        
        # EXTRACT TEXT: Check if it's a NeMo Hypothesis object
        if hasattr(full_result, 'text'):
            full_hindi_text = full_result.text
        else:
            full_hindi_text = str(full_result)
        
        full_hindi_text = full_hindi_text.strip()
        print(f"DEBUG: Cleaned Hindi Text: {full_hindi_text[:50]}...")

        # Step 4: Segmentation
        print("DEBUG: Segmenting text...")
        raw_segments = re.split(r'([।?!.])', full_hindi_text)
        sentences = []
        for i in range(0, len(raw_segments)-1, 2):
            combined = (raw_segments[i] + raw_segments[i+1]).strip()
            if len(combined) > 1: sentences.append(combined)
        
        if not sentences: sentences = [full_hindi_text]

        # Step 5: Translation Loop
        subtitles = []
        total_chars = sum(len(s) for s in sentences)
        time_per_char = video_duration / max(1, total_chars)
        current_time = 0.0
        
        print(f"DEBUG: Starting translation for {len(sentences)} segments...")
        for i, text in enumerate(sentences):
            duration = len(text) * time_per_char
            end_time = min(current_time + duration, video_duration)

            # Phase 3: Translation (HIN -> MAL)
            # Updated call to fix the AttributeError
            batch = ip.preprocess_batch([text], src_lang="hin_Deva", tgt_lang="mal_Mlym")
            inputs = tokenizer(batch, truncation=True, padding="longest", return_tensors="pt").to(translation_device)

            with torch.no_grad():
                outputs = model.generate(
                    **inputs, 
                    max_new_tokens=256, 
                    num_beams=5,          # Changed from 1 to 5
                    use_cache=False,      # Added to prevent the NoneType shape error
                    early_stopping=True
                )

            formal_malayalam = ip.postprocess_batch(
                tokenizer.batch_decode(outputs, skip_special_tokens=True), 
                lang="mal_Mlym"
            )[0]
            
            # Groq
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a Hindi-to-Malayalam subtitle editor. Output ONLY Malayalam script."},
                    {"role": "user", "content": f"Hindi: {text}\nFormal: {formal_malayalam}"}
                ],
                model="llama-3.3-70b-versatile", 
                temperature=0.1, 
            )
            natural_malayalam = re.sub(r'<think>.*?</think>', '', chat_completion.choices[0].message.content, flags=re.DOTALL).strip()

            subtitles.append({
                "start": current_time,
                "end": end_time,
                "hindi_text": text,
                "formal_text": formal_malayalam,
                "natural_text": natural_malayalam
            })
            
            current_time = end_time
            print(f"DEBUG: Segment {i+1} complete.")
            torch.cuda.empty_cache()

        if os.path.exists(audio_wav_path):
            os.remove(audio_wav_path)
        print("--- Processing Successful ---")
        return subtitles

    except Exception as e:
        # THIS IS THE PART THAT TRACKS THE LINE
        print("\n" + "="*50)
        print("CRITICAL ERROR IN generate_hin_subtitles")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {e}")
        print("Traceback:")
        traceback.print_exc() # This prints the line number
        print("="*50 + "\n")
        if os.path.exists(audio_wav_path):
            os.remove(audio_wav_path)
        raise e # Still raise it so FastAPI knows it's a 500 error
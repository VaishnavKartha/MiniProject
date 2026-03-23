import os
from huggingface_hub import snapshot_download
from dotenv import load_dotenv

# 1. Load your existing .env file
load_dotenv()
hf_token = os.getenv("HF_TOKEN")

models = {
    "indictrans2-en": "ai4bharat/indictrans2-en-indic-1B",
    "indictrans2-hi": "ai4bharat/indictrans2-indic-indic-1B",
    "whisper-large-v3": "Systran/faster-whisper-large-v3"
}

base_dir = os.path.expanduser("~/Desktop/Bhasha_Models")
os.makedirs(base_dir, exist_ok=True)

for folder_name, repo_id in models.items():
    print(f"\n📥 Downloading {repo_id}...")
    target_path = os.path.join(base_dir, folder_name)
    
    snapshot_download(
        repo_id=repo_id, 
        local_dir=target_path, 
        token=hf_token  # <--- This uses your saved token!
    )
    print(f"✅ {folder_name} is ready.")
import os
import shutil
import time
import subprocess
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from subtitle import generate_subtitles, format_time

app = FastAPI(title="Bhasha Live API - MEC Demo")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
RESULTS_DIR = "results"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# Helper function for the metrics table
def sec_to_min_sec(seconds):
    """Converts raw seconds into a human-readable 'X min Y sec' format."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m > 0:
        return f"{m} min {s} sec"
    return f"{s} sec"

# ---------------------------------------------------------
# ROUTE 1: FULL VIDEO UPLOAD (Generates Comparison SRT)
# ---------------------------------------------------------
@app.post("/generate-subtitles")
async def generate(video: UploadFile = File(...), lang: str = Form("en")):
    print(f"\n" + "="*50)
    print(f"🎬 [API ROUTE 1] FULL VIDEO UPLOAD INITIATED")
    print(f"   ├─ File: {video.filename}")
    print(f"   └─ Mode: {lang.upper()}")
    print("="*50)

    video_path = f"{UPLOAD_DIR}/{video.filename}"
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)
        
    print("✅ Video saved to disk. Triggering AI Pipeline...")
    start_time = time.time()
    
    # Run the pipeline
    subtitles, phase_times = generate_subtitles(video_path, source_lang=lang)

    # Calculate Metrics
    end_time = time.time()
    processing_time = end_time - start_time
    video_duration = subtitles[-1]["end"] if subtitles else 0
    rtf = processing_time / video_duration if video_duration > 0 else 0

    print("\n" + "="*55)
    print("📊 PIPELINE PERFORMANCE METRICS")
    print("="*55)
    print(f"🎞️  Audio Duration    : {sec_to_min_sec(video_duration)}")
    print(f"⏱️  Total Processing  : {sec_to_min_sec(processing_time)}")
    print(f"   ├─ 🎙️ Whisper (Ph1) : {sec_to_min_sec(phase_times['p1'])}")
    print(f"   ├─ 🧠 Indic (Ph2)   : {sec_to_min_sec(phase_times['p2'])}")
    print(f"   └─ 🌐 Groq (Ph3)    : {sec_to_min_sec(phase_times['p3'])}")
    print(f"⚡ Real-Time Factor  : {rtf:.2f}x")
    
    if rtf < 1.0:
        print(f"🚀 (Awesome! Processed faster than real-time)")
    else:
        print(f"🐢 (Processed slower than real-time)")
    print("="*55 + "\n")

    print("📁 Generating local SRT files...")
    base_name = os.path.splitext(video.filename)[0]
    natural_path = os.path.join(RESULTS_DIR, f"{base_name}_{lang}_natural.srt")
    combined_path = os.path.join(RESULTS_DIR, f"{base_name}_{lang}_comparison.srt")

    with open(natural_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(subtitles, 1):
            f.write(f"{i}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n{seg['natural_text']}\n\n")

    with open(combined_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(subtitles, 1):
            f.write(f"{i}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n")
            f.write(f"[{lang.upper()}]: {seg['source_text']}\n\n")
            f.write(f"[FORMAL]: {seg['formal_text']}\n\n")
            f.write(f"[NATURAL]: {seg['natural_text']}\n\n\n")

    os.remove(video_path) 
    print(f"✅ Cleanup complete. Sending {combined_path} to user.\n")
    return FileResponse(combined_path, media_type="text/plain", filename=f"{base_name}_comparison.srt")

# ---------------------------------------------------------
# ROUTE 2: THE 60-SECOND SEGMENT FETCHER (For the Extension)
# ---------------------------------------------------------
@app.post("/get-initial-batch")
async def get_initial_batch(video_url: str = Form(...), start_time: float = Form(...), lang: str = Form("en")):
    # 1. CLEAN THE URL: Strip out playlists or extra parameters that confuse yt-dlp
    clean_url = video_url.split("&")[0]
    
    end_time = start_time + 60
    audio_file = os.path.join(UPLOAD_DIR, f"temp_slice_{start_time}.mp3")
    
    print(f"\n" + "="*50)
    print(f"🌐 [API ROUTE 2] EXTENSION SYNC REQUEST")
    print(f"   ├─ Raw URL: {video_url}")
    print(f"   ├─ Clean URL: {clean_url}")
    print(f"   ├─ Slice: {start_time}s to {end_time}s")
    print(f"   └─ Mode: {lang.upper()}")
    print("="*50)
    
    print(f"📥 [yt-dlp] Extracting pure audio track over network...")
    
    # 2. THE ANTI-BOT COMMAND: Android client spoofing is the gold standard for Kaggle/Colab
    command = [
        "yt-dlp", 
        "-x", "--audio-format", "mp3", 
        "--download-sections", f"*{start_time}-{end_time}", 
        "--force-overwrites", 
        "--no-check-certificate", 
        "--extractor-args", "youtube:player_client=android,web",  # <-- THE MAGIC BYPASS
        "-o", audio_file, 
        clean_url
    ]
    
    # 3. CAPTURE REAL ERRORS: Do not use DEVNULL. We need to see what YouTube is doing.
    result = subprocess.run(command, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ [yt-dlp] FATAL ERROR:\n{result.stderr}")
        return JSONResponse({
            "error": "Failed to extract video audio. Check Kaggle terminal.", 
            "details": result.stderr
        }, status_code=400)
        
    if not os.path.exists(audio_file):
        print("❌ [yt-dlp] Command succeeded but the file is missing from the directory!")
        return JSONResponse({"error": "File system error on Kaggle"}, status_code=500)

    print("✅ [yt-dlp] Audio slice saved locally. Triggering AI Pipeline...")
    
    # Process the slice through the unified pipeline
    subtitles, _ = generate_subtitles(audio_file, source_lang=lang)
    
    # Clean up the temp file
    os.remove(audio_file)
    
    print(f"✅ [API] Success! Sending {len(subtitles)} JSON captions back to Chrome Extension.\n")
    return {"status": "success", "start_time": start_time, "captions": subtitles}
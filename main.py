
import os
import shutil
import time
import subprocess
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from subtitle import generate_subtitles, format_time
from tts import MalayalamTTS
from fastapi.responses import StreamingResponse
from pydub import AudioSegment
import io
import base64

app = FastAPI(title="Bhasha Live API - MEC Demo")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

tts_engine = MalayalamTTS()


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
async def get_initial_batch(video_url: str = Form(...), start_time: float = Form(...), lang: str = Form("en"),tts: bool = Form(False)):
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

    if tts:
        tts_clips = []
        for seg in subtitles:
            # 1. Calculate the exact slot duration
            slot_start_ms = int(seg["start"] * 1000)
            slot_end_ms   = int(seg["end"] * 1000)
            slot_ms       = slot_end_ms - slot_start_ms

            # 2. Add the missing speaker_id
            audio_seg = tts_engine.text_to_audio_segment(
                seg["natural_text"],
                speaker_id="ritu" 
            )
            
            # 3. Fit the audio to the subtitle slot so the extension plays it perfectly
            fitted_seg = tts_engine.fit_audio_to_slot(audio_seg, slot_ms)

            # 4. Safely export and encode the fitted audio
            buffer = io.BytesIO()
            fitted_seg.export(buffer, format="mp3")
            buffer.seek(0) # Ensure we read from the beginning of the buffer
            
            audio_b64 = base64.b64encode(buffer.read()).decode()
            
            tts_clips.append({
                "start": seg["start"],
                "end": seg["end"],
                "audio_b64": audio_b64   
            })
        print(f"✅ [API] Success! Sending {len(subtitles)} JSON captions with {len(tts_clips)} audio clips back to Chrome Extension.\n")
        return {"status": "success", "start_time": start_time,
                "captions": subtitles, "tts_clips": tts_clips}
        
    print(f"✅ [API] Success! Sending {len(subtitles)} JSON captions back to Chrome Extension.\n")
    return {"status": "success", "start_time": start_time, "captions": subtitles}
    
    
    #return {"status": "success", "start_time": start_time, "captions": subtitles}



def process_dubbed_tts(seg, tts_engine):
    """Handles a single dubbed segment for audio composition in an isolated thread."""
    slot_start_ms = int(seg["start"] * 1000)
    slot_end_ms   = int(seg["end"] * 1000)
    slot_ms       = slot_end_ms - slot_start_ms

    # TTS for this line
    audio_seg = tts_engine.text_to_audio_segment(
        seg["natural_text"],
        speaker_id="SPEAKER_00"  # single voice; extend with diarization later
    )

    # Speed-fit the audio to its subtitle slot
    fitted = tts_engine.fit_audio_to_slot(audio_seg, slot_ms)

    # Return the start time (for positioning) and the raw AudioSegment
    return slot_start_ms, fitted

@app.post("/generate-dubbed-audio")
async def generate_dubbed_audio(video: UploadFile = File(...), lang: str = Form("en")):
    """
    Runs the full subtitle pipeline, then converts natural Malayalam
    subtitles to a dubbed audio track using threaded TTS generation.
    """
    video_path = f"{UPLOAD_DIR}/{video.filename}"
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)

    subtitles, _ = generate_subtitles(video_path, source_lang=lang)
    os.remove(video_path)

    if not subtitles:
        return JSONResponse({"error": "No subtitles generated"}, status_code=400)

    print(f"⚡ [API] Parallelizing Dubbed TTS generation for {len(subtitles)} segments...")
    
    # 1. Fire all TTS generation tasks simultaneously
    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(TTS_THREAD_POOL, process_dubbed_tts, seg, tts_engine)
        for seg in subtitles
    ]
    
    # Wait for all audio clips to finish generating
    dubbed_clips = await asyncio.gather(*tasks)

    # 2. Build the master audio track
    total_duration_ms = int(subtitles[-1]["end"] * 1000)
    final_audio = AudioSegment.silent(duration=total_duration_ms)

    # 3. Overlay all the downloaded clips onto the silent track
    print("🎧 [API] Compositing audio clips into final track...")
    for slot_start_ms, fitted_seg in dubbed_clips:
        final_audio = final_audio.overlay(fitted_seg, position=slot_start_ms)

    # Export to MP3 and stream back
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3")
    buffer.seek(0)

    print("✅ [API] Dubbed audio complete. Sending to user.\n")
    return StreamingResponse(
        buffer, 
        media_type="audio/mpeg",
        headers={"Content-Disposition": "attachment; filename=dubbed_malayalam.mp3"}
    )
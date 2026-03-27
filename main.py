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
from concurrent.futures import ThreadPoolExecutor
import asyncio

app = FastAPI(title="Bhasha Live API - MEC Demo")
TTS_THREAD_POOL = ThreadPoolExecutor(max_workers=5)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

tts_engine = MalayalamTTS()


UPLOAD_DIR = "uploads"
RESULTS_DIR = "results"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
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
    os.remove(video_path) 

    if not subtitles:
        return JSONResponse({"error": "No subtitles generated"}, status_code=400)

    # Calculate Metrics
    end_time = time.time()
    processing_time = end_time - start_time
    video_duration = subtitles[-1]["end"] if subtitles else 0
    rtf = processing_time / video_duration if video_duration > 0 else 0

    metrics = {
        "video_duration": video_duration,
        "processing_time": processing_time,
        "rtf": round(rtf, 2),
        "phase_times": phase_times
    }

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

    natural_srt = ""
    comparison_srt = ""
    for i, seg in enumerate(subtitles, 1):
        time_block = f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n"
        natural_srt += f"{i}\n{time_block}{seg['natural_text']}\n\n"
        comparison_srt += f"{i}\n{time_block}[{lang.upper()}]: {seg['source_text']}\n[FORMAL]: {seg['formal_text']}\n[NATURAL]: {seg['natural_text']}\n\n"
        
    return JSONResponse({
        "status": "success",
        "comparison_srt": comparison_srt,
        "natural_srt": natural_srt,
        "metrics": metrics
    })

def process_single_tts(seg, tts_engine):
    """Handles a single subtitle segment in an isolated thread."""
    slot_start_ms = int(seg["start"] * 1000)
    slot_end_ms   = int(seg["end"] * 1000)
    slot_ms       = slot_end_ms - slot_start_ms

    # Generate Audio
    audio_seg = tts_engine.text_to_audio_segment(
        seg["natural_text"],
        speaker_id="ritu" 
    )
    
    # Fit Audio
    fitted_seg = tts_engine.fit_audio_to_slot(audio_seg, slot_ms)

    # Export Audio (Using a lower bitrate speeds up the export massively)
    buffer = io.BytesIO()
    fitted_seg.export(buffer, format="mp3", bitrate="64k") 
    buffer.seek(0)
    
    return {
        "start": seg["start"],
        "end": seg["end"],
        "audio_b64": base64.b64encode(buffer.read()).decode()
    }

# ---------------------------------------------------------
# ROUTE 2: THE 60-SECOND SEGMENT FETCHER (For the Extension)
# ---------------------------------------------------------
@app.post("/get-initial-batch")
async def get_initial_batch(video_url: str = Form(...), start_time: float = Form(...), lang: str = Form("en"),tts: bool = Form(False)):
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
    
    print(f"📥 [yt-dlp] Fetching video title...")
    title_command = [
        "yt-dlp", 
        "--get-title", 
        "--no-check-certificate", 
        clean_url
    ]
    title_result = subprocess.run(title_command, capture_output=True, text=True)
    video_title = title_result.stdout.strip() if title_result.returncode == 0 else "Unknown Video"
    print(f"🎬 Title Found: {video_title}")

    print(f"📥 [yt-dlp] Extracting pure audio track over network...")
    command = [
        "yt-dlp", 
        "-x", "--audio-format", "mp3", 
        "--download-sections", f"*{start_time}-{end_time}", 
        "--force-overwrites", 
        "--no-check-certificate", 
        "--extractor-args", "youtube:player_client=android,web",
        "-o", audio_file, 
        clean_url
    ]
    
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
    
    # --- 3. PASS THE TITLE TO THE PIPELINE ---
    subtitles, _ = generate_subtitles(audio_file, source_lang=lang, video_title=video_title)
    
    os.remove(audio_file)

    if tts:
        print(f"⚡ [API] Parallelizing TTS generation for {len(subtitles)} segments...")
        loop = asyncio.get_running_loop()
        
        tasks = [
            loop.run_in_executor(TTS_THREAD_POOL, process_single_tts, seg, tts_engine) 
            for seg in subtitles
        ]
        
        tts_clips = await asyncio.gather(*tasks)
        
        print(f"✅ [API] Success! Sending {len(subtitles)} JSON captions with {len(tts_clips)} audio clips back to Chrome Extension.\n")
        return {"status": "success", "start_time": start_time,
                "captions": subtitles, "tts_clips": tts_clips}
        
    print(f"✅ [API] Success! Sending {len(subtitles)} JSON captions back to Chrome Extension.\n")
    return {"status": "success", "start_time": start_time, "captions": subtitles}
    
    

def process_dubbed_tts(seg, tts_engine):
    """Handles a single dubbed segment for audio composition in an isolated thread."""
    slot_start_ms = int(seg["start"] * 1000)
    slot_end_ms   = int(seg["end"] * 1000)
    slot_ms       = slot_end_ms - slot_start_ms

    audio_seg = tts_engine.text_to_audio_segment(
        seg["natural_text"],
        speaker_id="SPEAKER_00" 
    )

    fitted = tts_engine.fit_audio_to_slot(audio_seg, slot_ms)

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

    start_time = time.time()

    subtitles, phase_times = generate_subtitles(video_path, source_lang=lang)
    os.remove(video_path)

    if not subtitles:
        return JSONResponse({"error": "No subtitles generated"}, status_code=400)
    
    natural_srt = ""
    comparison_srt = ""
    for i, seg in enumerate(subtitles, 1):
        time_block = f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n"
        natural_srt += f"{i}\n{time_block}{seg['natural_text']}\n\n"
        comparison_srt += f"{i}\n{time_block}[{lang.upper()}]: {seg['source_text']}\n[FORMAL]: {seg['formal_text']}\n[NATURAL]: {seg['natural_text']}\n\n"

    print(f"⚡ [API] Parallelizing Dubbed TTS generation for {len(subtitles)} segments...")
    tts_start = time.time()
    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(TTS_THREAD_POOL, process_dubbed_tts, seg, tts_engine)
        for seg in subtitles
    ]
    
    dubbed_clips = await asyncio.gather(*tasks)

    total_duration_ms = int(subtitles[-1]["end"] * 1000)
    final_audio = AudioSegment.silent(duration=total_duration_ms)

    print("🎧 [API] Compositing audio clips into final track...")
    for slot_start_ms, fitted_seg in dubbed_clips:
        final_audio = final_audio.overlay(fitted_seg, position=slot_start_ms)

    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3")
    buffer.seek(0)
    audio_b64 = base64.b64encode(buffer.read()).decode('utf-8')

    tts_end = time.time()
    phase_times["p4"] = tts_end - tts_start

    end_time = time.time()
    processing_time = end_time - start_time
    video_duration = subtitles[-1]["end"] if subtitles else 0
    rtf = processing_time / video_duration if video_duration > 0 else 0

    metrics = {
        "video_duration": video_duration,
        "processing_time": processing_time,
        "rtf": round(rtf, 2),
        "phase_times": phase_times
    }

    print("\n" + "="*55)
    print("📊 PIPELINE PERFORMANCE METRICS")
    print("="*55)
    print(f"🎞️  Audio Duration    : {sec_to_min_sec(video_duration)}")
    print(f"⏱️  Total Processing  : {sec_to_min_sec(processing_time)}")
    print(f"   ├─ 🎙️ Whisper (Ph1) : {sec_to_min_sec(phase_times['p1'])}")
    print(f"   ├─ 🧠 Indic (Ph2)   : {sec_to_min_sec(phase_times['p2'])}")
    print(f"   ├─ 🌐 Groq (Ph3)    : {sec_to_min_sec(phase_times['p3'])}")
    print(f"   └─ 🔊 TTS Audio(Ph4): {sec_to_min_sec(phase_times['p4'])}")
    print(f"⚡ Real-Time Factor  : {rtf:.2f}x")
    
    if rtf < 1.0:
        print(f"🚀 (Awesome! Processed faster than real-time)")
    else:
        print(f"🐢 (Processed slower than real-time)")
    print("="*55 + "\n")

    print("✅ [API] Dubbed audio complete. Sending to user.\n")
    return JSONResponse({
        "status": "success",
        "audio_base64": audio_b64,
        "comparison_srt": comparison_srt,
        "natural_srt": natural_srt,
        "metrics": metrics
    })
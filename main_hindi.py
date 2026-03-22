import os
import shutil
import time
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
import tempfile
from fastapi.middleware.cors import CORSMiddleware
from subtitle_hindi import generate_subtitles, format_time, process_live_chunk

app = FastAPI()
# --- ADD THIS TO ALLOW CHROME EXTENSION CONNECTIONS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
RESULTS_DIR = "results"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# --- NEW HELPER FUNCTION ---
def sec_to_min_sec(seconds):
    """Converts raw seconds into a human-readable 'X min Y sec' format."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m > 0:
        return f"{m} min {s} sec"
    return f"{s} sec"

@app.post("/generate-hindi-subtitles")
async def generate(video: UploadFile = File(...)):
    # 1. Save uploaded video
    video_path = f"{UPLOAD_DIR}/{video.filename}"
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)
        
    # --- START TIMER ---
    print(f"\n🚀 Starting AI Pipeline for: {video.filename}")
    start_time = time.time()

    # 2. Process (Unpack both subtitles and phase times)
    subtitles, phase_times = generate_subtitles(video_path)

    # --- END TIMER & CALCULATE METRICS ---
    end_time = time.time()
    processing_time = end_time - start_time

    # Extract approximate video duration from the final subtitle's end timestamp
    video_duration = subtitles[-1]["end"] if subtitles else 0
    
    # Calculate Real-Time Factor (RTF)
    rtf = processing_time / video_duration if video_duration > 0 else 0

    # Convert the decimal minutes from subtitle_hindi back to raw seconds for our new formatter
    p1_sec = phase_times['p1_min'] * 60
    p2_sec = phase_times['p2_min'] * 60
    p3_sec = phase_times['p3_min'] * 60

    print("\n" + "="*55)
    print("📊 PIPELINE PERFORMANCE METRICS")
    print("="*55)
    print(f"🎞️  Audio Duration    : {sec_to_min_sec(video_duration)}")
    print(f"⏱️  Total Processing  : {sec_to_min_sec(processing_time)}")
    print(f"   ├─ 🗣️ Whisper (Ph1) : {sec_to_min_sec(p1_sec)}")
    print(f"   ├─ 🧠 Indic (Ph2)   : {sec_to_min_sec(p2_sec)}")
    print(f"   └─ 🌐 Groq (Ph3)    : {sec_to_min_sec(p3_sec)}")
    print(f"⚡ Real-Time Factor  : {rtf:.2f}x")
    
    if rtf < 1.0:
        print(f"🚀 (Awesome! Processed faster than real-time)")
    else:
        print(f"🐢 (Processed slower than real-time)")
    print("="*55 + "\n")

    # 3. Define paths for local project folder storage
    base_name = os.path.splitext(video.filename)[0]
    hin_path = os.path.join(RESULTS_DIR, f"{base_name}_hindi.srt")
    formal_path = os.path.join(RESULTS_DIR, f"{base_name}_formal_mal.srt")
    natural_path = os.path.join(RESULTS_DIR, f"{base_name}_natural_mal.srt")

    # 4. Helper function to write SRT lines
    def write_srt(file_path, data_key):
        with open(file_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(subtitles, 1):
                start = format_time(seg["start"])
                end = format_time(seg["end"])
                f.write(f"{i}\n{start} --> {end}\n{seg[data_key]}\n\n")

    # 5. Save all three files locally
    write_srt(hin_path, "hindi_text")
    write_srt(formal_path, "formal_text")
    write_srt(natural_path, "natural_text")

    # 6. Cleanup video
    os.remove(video_path) 
    
    # 7. Return the natural Malayalam version for immediate download
    return FileResponse(
        natural_path, 
        media_type="text/plain", 
        filename=f"{video.filename}_natural_mal.srt"
    )

@app.websocket("/ws/live-captions")
async def live_captions_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🟢 Live Captioning WebSocket Connected!")
    
    conversation_memory = ""
    
    try:
        while True:
            audio_bytes = await websocket.receive_bytes()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_file:
                tmp_file.write(audio_bytes)
                temp_audio_path = tmp_file.name

            # Process chunk with rolling memory
            malayalam_text = process_live_chunk(temp_audio_path, previous_context=conversation_memory)
            
            if malayalam_text:
                # Save the last bit of text to give context to the NEXT 3-second chunk
                conversation_memory = malayalam_text[-100:] 
                await websocket.send_json({"text": malayalam_text})
            
            os.remove(temp_audio_path)

    except WebSocketDisconnect:
        print("🔴 Live Captioning WebSocket Disconnected.")
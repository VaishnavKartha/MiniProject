import os
import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from subtitle import generate_subtitles, format_time

app = FastAPI()

UPLOAD_DIR = "uploads"
RESULTS_DIR = "results" # New folder for your local storage

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

@app.post("/generate-subtitles")
async def generate(video: UploadFile = File(...)):
    # 1. Save uploaded video
    video_path = f"{UPLOAD_DIR}/{video.filename}"
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)

    # 2. Process
    subtitles = generate_subtitles(video_path)

    # 3. Define paths for local project folder storage
    base_name = os.path.splitext(video.filename)[0]
    eng_path = os.path.join(RESULTS_DIR, f"{base_name}_english.srt")
    formal_path = os.path.join(RESULTS_DIR, f"{base_name}_formal.srt")
    natural_path = os.path.join(RESULTS_DIR, f"{base_name}_natural.srt")

    # 4. Helper function to write SRT lines
    def write_srt(file_path, data_key):
        with open(file_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(subtitles, 1):
                start = format_time(seg["start"])
                end = format_time(seg["end"])
                f.write(f"{i}\n{start} --> {end}\n{seg[data_key]}\n\n")

    # 5. Save all three files locally in /results
    write_srt(eng_path, "english_text")
    write_srt(formal_path, "formal_text")
    write_srt(natural_path, "natural_text")

    # 6. Cleanup video
    os.remove(video_path) 
    
    # 7. Return the natural version for immediate download
    return FileResponse(
        natural_path, 
        media_type="text/plain", 
        filename=f"{video.filename}_natural.srt"
    )
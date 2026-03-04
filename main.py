from fastapi import FastAPI, UploadFile, File
import shutil
import os

from subtitle import generate_subtitles, format_time

app = FastAPI()

UPLOAD_DIR = "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/generate-subtitles")
async def generate(video: UploadFile = File(...)):

    video_path = f"{UPLOAD_DIR}/{video.filename}"

    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)

    subtitles = generate_subtitles(video_path)

    srt_path = video_path + ".srt"

    with open(srt_path, "w", encoding="utf-8") as f:

        for i, seg in enumerate(subtitles, 1):

            start = format_time(seg["start"])
            end = format_time(seg["end"])

            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(seg["text"] + "\n\n")

    return {
        "message": "Subtitle generated",
        "srt_file": srt_path
    }
from fastapi import FastAPI, UploadFile, File, HTTPException
import shutil
import os
import uvicorn
from subtitle_hindi import generate_hin_subtitles, format_srt_custom

app = FastAPI()

RESULT_DIR = "results_hindi"
UPLOAD_DIR = "uploads"

# Ensure directories exist
os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/generate-hindi-subtitles")
async def generate_hindi(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    base_name = os.path.splitext(file.filename)[0]
    
    try:
        # Save video
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process with AI4Bharat Stack
        subs_data = generate_hin_subtitles(file_path)
        
        # Generate 3 comparison versions
        files = {
            "hindi": os.path.join(RESULT_DIR, f"{base_name}_original_hindi.srt"),
            "formal": os.path.join(RESULT_DIR, f"{base_name}_formal_mal.srt"),
            "natural": os.path.join(RESULT_DIR, f"{base_name}_natural_mal.srt")
        }
        
        # Save files
        with open(files["hindi"], "w", encoding="utf-8") as f:
            f.write(format_srt_custom(subs_data, "hindi_text"))
            
        with open(files["formal"], "w", encoding="utf-8") as f:
            f.write(format_srt_custom(subs_data, "formal_text"))
            
        with open(files["natural"], "w", encoding="utf-8") as f:
            f.write(format_srt_custom(subs_data, "natural_text"))
            
        return {
            "status": "success", 
            "message": "AI4Bharat Stack Comparison Ready",
            "saved_files": files
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Run on 8001
    uvicorn.run(app, host="0.0.0.0", port=8001)
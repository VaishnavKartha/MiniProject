// --- CONFIGURATION ---
// ⚠️ PASTE YOUR CURRENT NGROK HTTPS URL HERE ⚠️
const API_BASE_URL = "https://unabstractive-surgeonless-jennette.ngrok-free.dev"; 

let subtitles = [];
let audioClips = [];
let currentLang = "en";
let ttsEnabled = false;
let isFetching = false;
let ytVideo = null;

// A strict registry to track exactly which 60s blocks we have downloaded
let downloadedChunks = new Set(); 

// --- 1. SETUP THE UI OVERLAY ---
const captionContainer = document.createElement('div');
captionContainer.style.cssText = `
    position: absolute; bottom: 10%; left: 50%; transform: translateX(-50%);
    width: 80%; text-align: center; pointer-events: none; z-index: 999999; display: none;
`;

const captionText = document.createElement('div');
captionText.style.cssText = `
    display: inline-block; background-color: rgba(0, 0, 0, 0.85); color: #FFD700;
    font-family: 'Noto Sans Malayalam', sans-serif; font-size: 26px; font-weight: bold;
    padding: 8px 16px; border-radius: 8px; text-shadow: 2px 2px 4px #000;
`;
captionContainer.appendChild(captionText);

// --- 2. LISTEN FOR POPUP CLICK ---
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "init_captions") {
        ytVideo = document.querySelector('video');
        if (!ytVideo) return;

        const player = document.getElementById('movie_player') || document.body;
        player.appendChild(captionContainer);
        captionContainer.style.display = 'block';

        currentLang = request.lang;
        ttsEnabled = request.tts || false;
        subtitles = [];
        audioClips = [];
        downloadedChunks.clear();
        ytVideo.muted = false; // clean reset before starting 
        
        ytVideo.pause();
        
        const startChunk = Math.floor(ytVideo.currentTime / 60) * 60;
        downloadedChunks.add(startChunk); 
        fetchSegment(startChunk, false); 
        
        setupVideoListeners();
        sendResponse({status: "started"});
    }
});

// --- 3. FETCH DATA FROM KAGGLE ---
async function fetchSegment(startTime, isBackground = false) {
    if (isFetching) return;
    isFetching = true;
    
    if (!isBackground) {
        captionText.innerText = `⏳ AI is processing 60 seconds of ${currentLang.toUpperCase()} audio...`;
        captionText.style.color = "#fff";
        captionContainer.style.display = 'block';
    } else {
        console.log(`Bhasha: Background buffering chunk at ${startTime}s...`);
    }

    try {
        const formData = new FormData();
        formData.append("video_url", window.location.href);
        formData.append("start_time", startTime);
        formData.append("lang", currentLang);
        formData.append("tts", ttsEnabled ? "true" : "false");

        const response = await fetch(`${API_BASE_URL}/get-initial-batch`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.details || "Backend server error");
        }

        const data = await response.json();
        
        if (data.status === "success" && data.captions) {
            
            // 🚨 THE FIX: OFFSET THE TIMESTAMPS BY THE CHUNK'S START TIME
            const offsetCaptions = data.captions.map(caption => ({
                ...caption,
                start: caption.start + startTime,
                end: caption.end + startTime
            }));

            // Append the corrected captions to our master list
            subtitles = subtitles.concat(offsetCaptions);

            // Store TTS clips if they came back
            if (data.tts_clips) {
                const offsetClips = data.tts_clips.map(clip => ({
                    ...clip,
                    start: clip.start + startTime,
                    end: clip.end + startTime,
                    played: false
                }));
                audioClips = audioClips.concat(offsetClips);
            }
            
            if (!isBackground) {
                captionText.innerText = "✅ Malayalam Captions Ready! Playing...";
                captionText.style.color = "#10B981";
                
                setTimeout(() => { 
                    captionText.style.color = "#FFD700"; 
                    captionText.innerText = "";
                    if (ttsEnabled) ytVideo.muted = true; // mute YT audio when TTS is on
                    ytVideo.play(); 
                }, 1500);
            }
        }
    } catch (err) {
        console.error("Bhasha Error:", err);
        downloadedChunks.delete(startTime); 
        if (!isBackground) {
            captionText.innerText = "❌ Connection Failed. Check Console.";
            captionText.style.color = "#EF4444";
        }
    } finally {
        isFetching = false;
    }
}

// --- 4. THE SYNC ENGINE ---
function setupVideoListeners() {
    ytVideo.ontimeupdate = () => {
        const currentSecs = ytVideo.currentTime;
        let activeCaption = null;

        for (let i = 0; i < subtitles.length; i++) {
            if (currentSecs >= subtitles[i].start && currentSecs <= subtitles[i].end) {
                activeCaption = subtitles[i].natural_text;
                break;
            }
        }

        if (activeCaption) {
            captionText.innerText = activeCaption;
            captionContainer.style.display = 'block';
        } else {
            captionText.innerText = ""; 
        }

        // TTS PLAYBACK
        if (ttsEnabled) {
            for (let clip of audioClips) {
                if (!clip.played && currentSecs >= clip.start && currentSecs <= clip.end) {
                    clip.played = true;
                    const audioBytes = Uint8Array.from(atob(clip.audio_b64), c => c.charCodeAt(0));
                    const blob = new Blob([audioBytes], { type: "audio/mp3" });
                    const url = URL.createObjectURL(blob);
                    const audio = new Audio(url);
                    audio.play();
                    audio.onended = () => URL.revokeObjectURL(url);
                    break;
                }
            }
        }

        // BACKGROUND BUFFERING LOGIC
        if (!isFetching) {
            const currentChunk = Math.floor(currentSecs / 60) * 60;
            const nextChunk = currentChunk + 60;
            
            if ((nextChunk - currentSecs < 30) && currentSecs < ytVideo.duration) {
                if (!downloadedChunks.has(nextChunk)) {
                    downloadedChunks.add(nextChunk); 
                    fetchSegment(nextChunk, true); 
                }
            }
        }
    };

    ytVideo.onseeked = () => {
        if (isFetching) return;
        
        const seekChunk = Math.floor(ytVideo.currentTime / 60) * 60;
        
        if (!downloadedChunks.has(seekChunk)) {
            ytVideo.pause();
            downloadedChunks.add(seekChunk);
            fetchSegment(seekChunk, false);
        }
    };
}
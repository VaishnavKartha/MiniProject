const API_BASE_URL = "https://unabstractive-surgeonless-jennette.ngrok-free.dev";

let subtitles = [];
let audioClips = [];       
let currentLang = "en";
let ttsEnabled = false;
let isFetching = false;
let ytVideo = null;
let audioCtx = null;       
let activeSource = null;  

let completedChunks = new Set();
let fetchingChunks = new Set();
let isWaitingForData = false;

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

// --- HELPER: decode all base64 clips into AudioBuffers upfront ---
async function decodeClips(rawClips, startTime) {
    const decoded = [];
    for (const clip of rawClips) {
        try {
            const binary = atob(clip.audio_b64);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
            const buffer = await audioCtx.decodeAudioData(bytes.buffer);
            decoded.push({
                start: clip.start + startTime,
                end: clip.end + startTime,
                buffer,
                played: false
            });
        } catch (e) {
            console.warn("Bhasha: failed to decode clip", e);
        }
    }
    return decoded;
}

// --- HELPER: stop any currently playing TTS clip ---
function stopActiveSource() {
    if (activeSource) {
        try { activeSource.stop(); } catch (_) {}
        activeSource = null;
    }
}

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
        
        completedChunks.clear();
        fetchingChunks.clear();
        isWaitingForData = false;
        
        ytVideo.muted = false;
        stopActiveSource();

        if (ttsEnabled) {
            if (!audioCtx || audioCtx.state === 'closed') {
                audioCtx = new AudioContext();
            } else if (audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
        }

        ytVideo.pause();

        const startChunk = Math.floor(ytVideo.currentTime / 60) * 60;
        
        fetchSegment(startChunk, false);

        setupVideoListeners();
        
        sendResponse({ status: "started" });
    }
    
    return true; 
});

// --- 3. FETCH DATA FROM KAGGLE ---
async function fetchSegment(startTime, isBackground = false) {
    if (fetchingChunks.has(startTime)) return;
    fetchingChunks.add(startTime);

    if (!isBackground) {
        captionText.style.color = "#fff";
        captionText.innerText = "🔗 Connecting to AI Server...";
        captionContainer.style.display = 'block';
    }

    try {
        const formData = new FormData();
        formData.append("video_url", window.location.href);
        formData.append("start_time", startTime);
        formData.append("lang", currentLang);
        formData.append("tts", ttsEnabled ? "true" : "false");

        if (!isBackground) {
            captionText.innerText = ttsEnabled 
                ? `⏳ Extracting Audio & Generating Captions...` 
                : `⏳ Generating Captions...`;
        }

        const response = await fetch(`${API_BASE_URL}/get-initial-batch`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error("Backend server error");

        if (!isBackground) {
            captionText.innerText = "📥 Downloading Data...";
        }
        const data = await response.json();

        if (data.status === "success" && data.captions) {
            const offsetCaptions = data.captions.map(caption => ({
                ...caption,
                start: caption.start + startTime,
                end: caption.end + startTime
            }));
            subtitles = subtitles.concat(offsetCaptions);

            if (ttsEnabled && data.tts_clips && data.tts_clips.length > 0) {
                if (!isBackground) captionText.innerText = "🔊 Decoding Audio...";
                const decoded = await decodeClips(data.tts_clips, startTime);
                audioClips = audioClips.concat(decoded);
            }

            completedChunks.add(startTime);
            fetchingChunks.delete(startTime);

            if (!isBackground) {
                captionText.innerText = "✅ Ready! Playing...";
                captionText.style.color = "#10B981";
                setTimeout(() => {
                    captionText.style.color = "#FFD700";
                    captionText.innerText = "";
                    if (ttsEnabled) ytVideo.muted = true;
                    ytVideo.play();
                }, 1000);
            } else if (isWaitingForData) {
                isWaitingForData = false;
                captionText.innerText = "";
                ytVideo.play();
            }
        }
    } catch (err) {
        console.error("Bhasha Error:", err);
        fetchingChunks.delete(startTime);
        if (!isBackground) {
            captionText.innerText = "❌ Connection Failed. Retrying on play...";
            captionText.style.color = "#EF4444";
        }
    }
}

// --- 4. THE SYNC ENGINE ---
function setupVideoListeners() {
    ytVideo.ontimeupdate = () => {
        const currentSecs = ytVideo.currentTime;
        const currentChunk = Math.floor(currentSecs / 60) * 60;

        // 1. AUTO-PAUSE LOGIC (Buffering)
        if (!completedChunks.has(currentChunk)) {
            if (!ytVideo.paused) {
                ytVideo.pause();
                isWaitingForData = true;
                captionText.innerText = `⏳ Waiting for AI data...`;
                captionText.style.color = "#FFD700";
                captionContainer.style.display = 'block';
            }
            if (!fetchingChunks.has(currentChunk)) {
                fetchSegment(currentChunk, false);
            }
            return;
        }

        // 2. CAPTION DISPLAY
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
            if (!isWaitingForData && !fetchingChunks.size) {
                captionText.innerText = "";
            }
        }

        // 3. ROBUST TTS PLAYBACK
        if (ttsEnabled && audioCtx) {
            for (let clip of audioClips) {
                if (!clip.played && currentSecs >= clip.start && currentSecs <= clip.end) {
                    clip.played = true;
                    stopActiveSource();
                    
                    const source = audioCtx.createBufferSource();
                    source.buffer = clip.buffer;
                    source.connect(audioCtx.destination);
                    
                    const offset = Math.max(0, currentSecs - clip.start);
                    source.start(0, offset);
                    
                    activeSource = source;
                    break;
                }
            }
        }

        // 4. BACKGROUND BUFFERING
        const nextChunk = currentChunk + 60;
        if ((nextChunk - currentSecs < 50) && nextChunk < ytVideo.duration) {
            if (!completedChunks.has(nextChunk) && !fetchingChunks.has(nextChunk)) {
                fetchSegment(nextChunk, true);
            }
        }
    };

    ytVideo.onseeked = () => {
        stopActiveSource();
        const seekTime = ytVideo.currentTime;
        const seekChunk = Math.floor(seekTime / 60) * 60;

        for (let clip of audioClips) {
            clip.played = clip.end < seekTime;
        }

        if (!completedChunks.has(seekChunk)) {
            ytVideo.pause();
            fetchSegment(seekChunk, false);
        }
    };

    ytVideo.onpause = () => {
        stopActiveSource();
        const currentSecs = ytVideo.currentTime;
        for (let clip of audioClips) {
            if (currentSecs >= clip.start && currentSecs <= clip.end) {
                clip.played = false;
            }
        }
    };
}
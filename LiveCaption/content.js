// --- CONFIGURATION ---
// ⚠️ PASTE YOUR CURRENT NGROK HTTPS URL HERE ⚠️
const API_BASE_URL = "https://unabstractive-surgeonless-jennette.ngrok-free.dev";

let subtitles = [];
let audioClips = [];       // { start, end, buffer: AudioBuffer, played: bool }
let currentLang = "en";
let ttsEnabled = false;
let isFetching = false;
let ytVideo = null;
let audioCtx = null;       // single shared AudioContext
let activeSource = null;   // currently playing AudioBufferSourceNode

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
        downloadedChunks.clear();
        ytVideo.muted = false;
        stopActiveSource();

        // Create AudioContext on user gesture (required by browsers)
        if (ttsEnabled) {
            if (!audioCtx || audioCtx.state === 'closed') {
                audioCtx = new AudioContext();
            } else if (audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
        }

        ytVideo.pause();

        const startChunk = Math.floor(ytVideo.currentTime / 60) * 60;
        downloadedChunks.add(startChunk);
        fetchSegment(startChunk, false);

        setupVideoListeners();
        sendResponse({ status: "started" });
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

            // OFFSET TIMESTAMPS BY CHUNK START TIME
            const offsetCaptions = data.captions.map(caption => ({
                ...caption,
                start: caption.start + startTime,
                end: caption.end + startTime
            }));
            subtitles = subtitles.concat(offsetCaptions);

            // PRE-DECODE ALL TTS CLIPS INTO AudioBuffers WHILE VIDEO IS STILL PAUSED
            if (ttsEnabled && data.tts_clips && data.tts_clips.length > 0) {
                if (!isBackground) {
                    captionText.innerText = "🔊 Pre-loading Malayalam audio...";
                }
                const decoded = await decodeClips(data.tts_clips, startTime);
                audioClips = audioClips.concat(decoded);
            }

            if (!isBackground) {
                captionText.innerText = "✅ Malayalam Ready! Playing...";
                captionText.style.color = "#10B981";

                setTimeout(() => {
                    captionText.style.color = "#FFD700";
                    captionText.innerText = "";
                    if (ttsEnabled) ytVideo.muted = true;
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

        // CAPTION DISPLAY
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

        // TTS PLAYBACK — fires pre-decoded AudioBuffers instantly, zero latency
        if (ttsEnabled && audioCtx) {
            for (let clip of audioClips) {
                if (!clip.played && currentSecs >= clip.start && currentSecs <= clip.end) {
                    clip.played = true;
                    stopActiveSource();
                    const source = audioCtx.createBufferSource();
                    source.buffer = clip.buffer;
                    source.connect(audioCtx.destination);
                    source.start(0);
                    activeSource = source;
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

        // Stop any playing audio immediately on seek
        stopActiveSource();

        // Reset played state based on new seek position
        const seekTime = ytVideo.currentTime;
        for (let clip of audioClips) {
            clip.played = clip.end < seekTime;
        }

        const seekChunk = Math.floor(seekTime / 60) * 60;
        if (!downloadedChunks.has(seekChunk)) {
            ytVideo.pause();
            downloadedChunks.add(seekChunk);
            fetchSegment(seekChunk, false);
        }
    };

    // Stop TTS audio if user manually pauses
    ytVideo.onpause = () => {
        stopActiveSource();
    };
}
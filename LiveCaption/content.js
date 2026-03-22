let socket = null;
let mediaRecorder = null;
let stream = null;

// 1. Create the UI Overlay
const captionContainer = document.createElement('div');
captionContainer.style.cssText = `
    position: fixed; bottom: 10%; left: 50%; transform: translateX(-50%);
    width: 80%; text-align: center; pointer-events: none; z-index: 999999; display: none;
`;

const captionText = document.createElement('div');
captionText.style.cssText = `
    display: inline-block; background-color: rgba(0, 0, 0, 0.8); color: white;
    font-family: 'Noto Sans Malayalam', sans-serif; font-size: 28px; font-weight: bold;
    padding: 10px 20px; border-radius: 8px; text-shadow: 2px 2px 4px #000000;
`;
captionText.innerText = "Waiting for audio...";

captionContainer.appendChild(captionText);
document.body.appendChild(captionContainer);

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "start_capture") {
        startLiveCaptioning();
    } else if (request.action === "stop_capture") {
        stopLiveCaptioning();
    }
});

async function startLiveCaptioning() {
    console.log("🎬 Capturing tab audio...");
    try {
        // THE FIX: These flags force the current YouTube tab to be selectable!
        stream = await navigator.mediaDevices.getDisplayMedia({
            video: { displaySurface: "browser" },
            audio: {
                echoCancellation: false,
                noiseSuppression: false,
                autoGainControl: false
            },
            selfBrowserSurface: "include", 
            preferCurrentTab: true         
        });

        const audioTracks = stream.getAudioTracks();
        if (audioTracks.length === 0) {
            alert("❌ You forgot to toggle 'Also share tab audio'! Refresh and try again.");
            stopLiveCaptioning();
            return;
        }

        captionContainer.style.display = 'block';
        captionText.innerText = "Connecting to AI Backend...";

        // PASTE YOUR CURRENT NGROK URL HERE
        const NGROK_URL = 'wss://unabstractive-surgeonless-jennette.ngrok-free.dev/ws/live-captions';
        socket = new WebSocket(NGROK_URL);

        socket.onopen = () => {
            captionText.innerText = "Listening... 🎙️";
            
            // Extract only the audio track so Chrome doesn't crash on video Codecs
            const audioOnlyStream = new MediaStream([audioTracks[0]]);

            function recordNextChunk() {
                if (!socket || socket.readyState !== WebSocket.OPEN) return;

                try {
                    let chunkRecorder = new MediaRecorder(audioOnlyStream, { mimeType: 'audio/webm' });
                    
                    chunkRecorder.ondataavailable = (event) => {
                        if (event.data.size > 0 && socket.readyState === WebSocket.OPEN) {
                            socket.send(event.data);
                        }
                    };

                    chunkRecorder.onstop = () => {
                        recordNextChunk();
                    };

                    chunkRecorder.start();
                    
                    setTimeout(() => {
                        if (chunkRecorder.state === "recording") {
                            chunkRecorder.stop();
                        }
                    }, 3000);

                } catch (e) {
                    console.error("Recorder start failed:", e);
                }
            }

            // Kick off the infinite loop!
            recordNextChunk();
        };

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.text) {
                captionText.innerText = data.text;
            }
        };

        // If user hits "Stop Sharing" on Chrome's banner
        stream.getVideoTracks()[0].onended = () => {
            stopLiveCaptioning();
        };

    } catch (err) {
        console.error("Capture error: ", err);
    }
}

function stopLiveCaptioning() {
    captionContainer.style.display = 'none';
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
    if (socket) {
        socket.close();
    }
}
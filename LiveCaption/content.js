let socket = null;
let mediaRecorder = null;
let stream = null;
let recordInterval = null;

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
    if (request.action === "start_capture" && request.streamId) {
        startLiveCaptioning(request.streamId);
    } else if (request.action === "stop_capture") {
        stopLiveCaptioning();
    }
});

// 3. Start Capture using the Stream ID (No popups!)
async function startLiveCaptioning(streamId) {
    console.log("🎬 Silently capturing tab audio...");
    try {
        // Use getUserMedia with the specific Tab Stream ID
        stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                mandatory: {
                    chromeMediaSource: 'tab',
                    chromeMediaSourceId: streamId
                }
            },
            video: false // We don't want video at all!
        });

        captionContainer.style.display = 'block';
        captionText.innerText = "Connecting to AI Backend...";

        // FIX 2: UPDATE THIS URL EVERY TIME YOU RESTART KAGGLE!
        const NGROK_URL = 'wss://unabstractive-surgeonless-jennette.ngrok-free.dev/ws/live-captions';
        socket = new WebSocket(NGROK_URL);

        socket.onopen = () => {
            captionText.innerText = "Listening... 🎙️";

            const audioTracks = stream.getAudioTracks();
            
            if (!stream || audioTracks.length === 0) {
                console.error("❌ No audio track found.");
                captionText.innerText = "⚠️ Error: No Audio Detected.";
                stopLiveCaptioning(); 
                return;
            }

            const audioOnlyStream = new MediaStream([audioTracks[0]]);

            // THE FIX: A function that creates a completely new, self-contained file every 3 seconds
            function recordNextChunk() {
                if (!socket || socket.readyState !== WebSocket.OPEN) return;

                try {
                    // Create a BRAND NEW recorder so this chunk gets fresh file headers!
                    let chunkRecorder = new MediaRecorder(audioOnlyStream, { mimeType: 'audio/webm' });
                    
                    chunkRecorder.ondataavailable = (event) => {
                        if (event.data.size > 0 && socket.readyState === WebSocket.OPEN) {
                            socket.send(event.data);
                            console.log("📤 Standalone Chunk Sent to Kaggle:", event.data.size);
                        }
                    };

                    // As soon as this chunk finishes packaging, instantly start the next one
                    chunkRecorder.onstop = () => {
                        recordNextChunk();
                    };

                    chunkRecorder.start();
                    
                    // Stop the recording after 3 seconds to trigger the packaging
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

        if (stream.getAudioTracks().length > 0) {
            stream.getAudioTracks()[0].onended = () => {
                stopLiveCaptioning();
            };
        }

    } catch (err) {
        console.error("Capture error: ", err);
        alert("Capture failed or cancelled. Make sure you check 'Share Tab Audio'!");
    }
}

function stopLiveCaptioning() {
    captionContainer.style.display = 'none';
    clearInterval(recordInterval);
    
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
    }
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
    if (socket) {
        socket.close();
    }
}
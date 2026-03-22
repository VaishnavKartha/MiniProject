document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('toggleBtn');
    let isListening = false;

    btn.addEventListener('click', async () => {
        let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        if (!tab.url || tab.url.startsWith("chrome://")) {
            alert("Please open a YouTube video first!");
            return;
        }

        isListening = !isListening;
        
        if (isListening) {
            btn.innerText = "Stop Listening";
            btn.classList.add("off");
            
            // SECURITY FIX: Add consumerTabId so Chrome allows the content script to use it
            chrome.tabCapture.getMediaStreamId({ 
                targetTabId: tab.id,
                consumerTabId: tab.id 
            }, (streamId) => {
                if (streamId) {
                    chrome.tabs.sendMessage(tab.id, { action: "start_capture", streamId: streamId });
                } else {
                    console.error("Could not get Tab Stream ID");
                    btn.innerText = "Start Listening";
                    btn.classList.remove("off");
                    isListening = false;
                }
            });
        } else {
            btn.innerText = "Start Listening";
            btn.classList.remove("off");
            chrome.tabs.sendMessage(tab.id, { action: "stop_capture" });
        }
    });
});
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
            chrome.tabs.sendMessage(tab.id, { action: "start_capture" });
        } else {
            btn.innerText = "Start Listening";
            btn.classList.remove("off");
            chrome.tabs.sendMessage(tab.id, { action: "stop_capture" });
        }
    });
});
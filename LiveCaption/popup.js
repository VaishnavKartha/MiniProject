document.addEventListener('DOMContentLoaded', () => {
    const loadBtn = document.getElementById('loadBtn');
    const langSelect = document.getElementById('langSelect');
    const ttsToggle = document.getElementById('ttsToggle');

    loadBtn.addEventListener('click', async () => {
        let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        if (!tab.url.includes("youtube.com/watch")) {
            alert("Please open a YouTube video first!");
            return;
        }

        const selectedLang = langSelect.value;
        const ttsEnabled = ttsToggle.checked;

        loadBtn.innerText = "Initializing...";
        loadBtn.style.backgroundColor = "#F59E0B";
        
        chrome.tabs.sendMessage(tab.id, { 
            action: "init_captions", 
            lang: selectedLang,
            tts: ttsEnabled
        }, () => {
            window.close();
        });
    });
});
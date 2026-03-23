document.addEventListener('DOMContentLoaded', () => {
    const loadBtn = document.getElementById('loadBtn');
    const langSelect = document.getElementById('langSelect');

    loadBtn.addEventListener('click', async () => {
        let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        if (!tab.url.includes("youtube.com/watch")) {
            alert("Please open a YouTube video first!");
            return;
        }

        const selectedLang = langSelect.value;
        loadBtn.innerText = "Initializing...";
        loadBtn.style.backgroundColor = "#F59E0B"; // Yellow warning color
        
        // Tell the content script to pause the video and fetch the data
        chrome.tabs.sendMessage(tab.id, { 
            action: "init_captions", 
            lang: selectedLang 
        }, () => {
            window.close(); // Close the popup so they can watch the video
        });
    });
});
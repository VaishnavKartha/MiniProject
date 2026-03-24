# 🌐 Bhasha Live: Real-Time AI Video Translation & Dubbing

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-F7DF1E.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

**Bhasha Live** is an end-to-end AI pipeline and Chrome Extension designed to bring real-time Malayalam translation and audio dubbing to YouTube videos. Built for the MEC Demo, it dynamically extracts YouTube audio, processes it through a 3-phase neural translation pipeline, and synchronizes the localized subtitles and Text-to-Speech (TTS) back into the browser via a custom Web Audio API engine.

---

## ✨ Key Features

* **3-Phase AI Translation Pipeline:**
  1. **Transcription:** Faster-Whisper (Large v3) for English/Hindi extraction.
  2. **Translation:** IndicTrans2 for high-fidelity formal Malayalam.
  3. **Context Polishing:** Groq API (Llama 3.3 70B) to naturalize the Malayalam output based on conversational context.
* **Dual-GPU Optimization:** Explicitly splits Whisper and IndicTrans2 across `cuda:0` and `cuda:1` for maximum VRAM efficiency.
* **Network-Bypass Audio Extraction:** Utilizes `yt-dlp` with Android client spoofing (`Youtubeer_client=android,web`) to fetch 60-second audio slices without triggering bot-protection blocks.
* **Synchronized TTS Dubbing:** Integrates Sarvam Bulbul v3 with a custom speed-fitting algorithm to perfectly match generated Malayalam audio to the exact duration of the original dialogue.
* **Intelligent Chrome Extension:** An offline-first sync engine that auto-buffers audio chunks, decodes Base64 streams on the fly, and overlays subtitles directly onto the YouTube player.

---

## 🏗️ Architecture

The project consists of two main components:
1. **The Backend (`/backend`):** A FastAPI server (designed to run on Kaggle/Colab) that handles all heavy ML processing and API routing.
2. **The Extension (`/extension`):** A vanilla JavaScript Chrome Extension that acts as the client-side media player and sync engine.

---

## 🚀 Prerequisites

Before you begin, ensure you have the following:

* **Hardware:** A Linux environment (like Linux Mint or Ubuntu) or a cloud notebook (Kaggle/Colab) with at least one, preferably two, NVIDIA GPUs.
* **Software:** Python 3.10+, `ffmpeg` installed on your system.
* **API Keys:**
  * [Groq API Key](https://console.groq.com/) (For Llama 3 context polishing).
  * [Sarvam AI API Key](https://dashboard.sarvam.ai/) (For Malayalam TTS).
* **Models:** Pre-downloaded weights for Faster-Whisper and IndicTrans2 (paths configured in `subtitle.py`).

---

## 🛠️ Installation & Setup

### 1. Backend Server Setup

Clone the repository and navigate to the backend directory:
```bash
git clone [https://github.com/yourusername/bhasha-live.git](https://github.com/yourusername/bhasha-live.git)
cd bhasha-live
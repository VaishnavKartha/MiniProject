import { useState, useRef, useCallback } from 'react';
import axios from 'axios';

export function useJobApi(baseUrl) {
  const [status,    setStatus]    = useState('idle');
  const [progress,  setProgress]  = useState(0);
  const [termLines, setTermLines] = useState([]);
  const [metrics,   setMetrics]   = useState(null);
  const [blobs,     setBlobs]     = useState({ comparison: null, natural: null, audio: null });
  const [errorMsg,  setErrorMsg]  = useState('');

  const abortRef     = useRef(null);
  const timerRef     = useRef(null);
  const startedAtRef = useRef(null);

  /* ── helpers ── */
  const addLine = (msg) => setTermLines(prev => [...prev, { _system: msg }]);

  const startFakeTicker = (totalEstSec) => {
    const TICK_MS   = 800;
    const increment = (90 / ((totalEstSec * 1000) / TICK_MS));
    timerRef.current = setInterval(() => {
      setProgress(prev => Math.min(prev + increment, 90));
    }, TICK_MS);
  };

  const stopTicker = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };

  const reset = useCallback(() => {
    stopTicker();
    setStatus('idle');
    setProgress(0);
    setTermLines([]);
    setMetrics(null);
    setBlobs({ comparison: null, natural: null, audio: null });
    setErrorMsg('');
    startedAtRef.current = null;
  }, []);

  const cancelJob = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
    stopTicker();
    reset();
  }, [reset]);

  const startJob = useCallback(async ({ file, lang, generateAudio, fileDurationSec }) => {
    reset();
    setStatus('uploading');
    startedAtRef.current = Date.now();

    const controller = new AbortController();
    abortRef.current = controller;

    const estSec = (fileDurationSec ?? 30) * 0.22 + 5;
    startFakeTicker(estSec);

    addLine('⬆ Uploading video to backend pipeline…');

    try {
      const form = new FormData();
      form.append('video', file);
      form.append('lang', lang);

      // 1. Pick the single unified endpoint
      const endpoint = generateAudio ? '/generate-dubbed-audio' : '/generate-subtitles';

      setStatus('processing');
      addLine('🎙 Phase 1 — Whisper: extracting audio transcription…');
      addLine('📖 Phase 2 — IndicTrans2: running formal translation…');
      addLine('✨ Phase 3 — Groq Llama: polishing to natural Malayalam…');
      if (generateAudio) addLine('🔊 Phase 4 — Generating Malayalam audio track (TTS)…');

      // 2. Make the request (Expecting JSON, not Blob)
      const { data } = await axios.post(
        `${baseUrl}${endpoint}`,
        form,
        { signal: controller.signal } 
      );

      if (data.status !== 'success') throw new Error(data.error || 'Unknown error from server');

      addLine('📁 Building files…');

      // 3. Reconstruct text blobs from JSON strings
      const compBlob = new Blob([data.comparison_srt], { type: 'text/plain' });
      const naturalBlob = new Blob([data.natural_srt], { type: 'text/plain' });

      // 4. Reconstruct audio blob from Base64
      let audioBlob = null;
      if (data.audio_base64) {
        const byteChars = atob(data.audio_base64);
        const byteNums = new Array(byteChars.length);
        for (let i = 0; i < byteChars.length; i++) {
          byteNums[i] = byteChars.charCodeAt(i);
        }
        audioBlob = new Blob([new Uint8Array(byteNums)], { type: 'audio/mpeg' });
        addLine('✅ Audio track decoded successfully.');
      }

      stopTicker();

      // 5. Update State with accurate backend data!
      setMetrics(data.metrics); 
      setBlobs({ comparison: compBlob, natural: naturalBlob, audio: audioBlob });
      setProgress(100);
      setStatus('done');

      addLine('✔ Pipeline complete. Files ready for download.');

    } catch (err) {
      stopTicker();
      if (axios.isCancel(err) || err.name === 'CanceledError') {
        reset();
      } else {
        const msg = err?.response?.data?.error || err.message || 'Unknown error';
        setErrorMsg(msg);
        setStatus('error');
        addLine(`❌ Error: ${msg}`);
      }
    }
  }, [baseUrl, reset]);

  return {
    status, progress, termLines, metrics, blobs, errorMsg,
    startJob, cancelJob, reset,
  };
}
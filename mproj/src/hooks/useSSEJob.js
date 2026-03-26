import { useState, useRef, useCallback } from 'react';
import axios from 'axios';

/**
 * useJobApi
 * Drives the Bhasha Studio FastAPI backend – no SSE.
 *
 * Flow:
 *   POST /generate-subtitles  (multipart: video, lang)  → comparison SRT blob
 *   POST /generate-dubbed-audio (multipart: video, lang) → MP3 blob  (optional)
 *
 * Exposes:
 *   status       – idle | uploading | processing | done | error
 *   progress     – 0-100, incremented via a fake timed ticker
 *   termLines    – system log strings shown in the terminal
 *   metrics      – { duration, processingTime, rtf } (estimated client-side)
 *   blobs        – { comparison: Blob|null, natural: Blob|null, audio: Blob|null }
 *   startJob()   – kicks off the job
 *   cancelJob()  – aborts any in-flight request and resets
 *   reset()      – clears all state
 */
export function useJobApi(baseUrl) {
  const [status,    setStatus]    = useState('idle');
  const [progress,  setProgress]  = useState(0);
  const [termLines, setTermLines] = useState([]);
  const [metrics,   setMetrics]   = useState(null);
  const [blobs,     setBlobs]     = useState({ comparison: null, natural: null, audio: null });
  const [errorMsg,  setErrorMsg]  = useState('');

  const abortRef    = useRef(null);
  const timerRef    = useRef(null);
  const startedAtRef = useRef(null);

  /* ── helpers ── */
  const addLine = (msg) => setTermLines(prev => [...prev, { _system: msg }]);

  const startFakeTicker = (totalEstSec) => {
    // Advance progress to ~90% over the estimated duration; backend will push to 100
    const TICK_MS   = 800;
    const increment = (90 / ((totalEstSec * 1000) / TICK_MS));
    timerRef.current = setInterval(() => {
      setProgress(prev => Math.min(prev + increment, 90));
    }, TICK_MS);
  };

  const stopTicker = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };

  /* ── Parses a comparison SRT blob to create a "natural-only" SRT blob ── */
  const extractNaturalSrt = async (blob) => {
    const text   = await blob.text();
    const blocks = text.trim().split(/\n\n+/);
    let out = '';
    let idx = 1;
    for (const block of blocks) {
      const lines = block.split('\n');
      // Find the [NATURAL]: line
      const naturalLine = lines.find(l => l.startsWith('[NATURAL]:'));
      const timeLine    = lines.find(l => l.includes('-->'));
      if (naturalLine && timeLine) {
        out += `${idx}\n${timeLine}\n${naturalLine.replace('[NATURAL]: ', '').trim()}\n\n`;
        idx++;
      }
    }
    return new Blob([out], { type: 'text/plain' });
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

  /**
   * fileDurationSec – crude estimate passed in from App (used for ETA + RTF)
   */
  const startJob = useCallback(async ({ file, lang, generateAudio, fileDurationSec }) => {
    reset();
    setStatus('uploading');
    startedAtRef.current = Date.now();

    const controller = new AbortController();
    abortRef.current = controller;

    // Rough estimate: RTF ~0.22 → total AI time + overhead
    const estSec = (fileDurationSec ?? 30) * 0.22 + 5;
    startFakeTicker(estSec);

    addLine('⬆ Uploading video to backend pipeline…');

    try {
      /* ── 1. Subtitle generation ── */
      const form1 = new FormData();
      form1.append('video', file);
      form1.append('lang', lang);         // "en" | "hi"

      setStatus('processing');
      addLine('🎙 Phase 1 — Whisper: extracting audio transcription…');

      const { data: compBlob } = await axios.post(
        `${baseUrl}/generate-subtitles`,
        form1,
        { responseType: 'blob', signal: controller.signal }
      );

      addLine('📖 Phase 2 — IndicTrans2: running formal translation…');
      addLine('✨ Phase 3 — Groq Llama: polishing to natural Malayalam…');
      addLine('📁 Writing SRT files…');

      // Build natural SRT client-side by parsing comparison SRT
      const naturalBlob = await extractNaturalSrt(compBlob);

      /* ── 2. Optional TTS dubbed audio ── */
      let audioBlob = null;
      if (generateAudio) {
        addLine('🔊 Generating Malayalam audio track (TTS)…');
        const form2 = new FormData();
        form2.append('video', file);
        form2.append('lang', lang);

        const { data: audioData } = await axios.post(
          `${baseUrl}/generate-dubbed-audio`,
          form2,
          { responseType: 'blob', signal: controller.signal }
        );
        audioBlob = audioData;
        addLine('✅ Audio track generated.');
      }

      stopTicker();

      /* ── 3. Compute metrics ── */
      const processingTime = (Date.now() - startedAtRef.current) / 1000;
      const duration       = fileDurationSec ?? null;
      const rtf            = duration ? (processingTime / duration) : null;

      setMetrics({ duration, processingTime, rtf });
      setBlobs({ comparison: compBlob, natural: naturalBlob, audio: audioBlob });
      setProgress(100);
      setStatus('done');

      addLine('✔ Pipeline complete. Files ready for download.');

    } catch (err) {
      stopTicker();
      if (axios.isCancel(err) || err.name === 'CanceledError') {
        reset();
      } else {
        const msg = err?.response?.data
          ? await (err.response.data instanceof Blob ? err.response.data.text() : Promise.resolve(String(err.response.data)))
          : err.message ?? 'Unknown error';
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

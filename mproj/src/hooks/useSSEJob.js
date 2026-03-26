import { useState, useRef, useCallback } from 'react';
import axios from 'axios';

/**
 * useSSEJob
 * Manages the full lifecycle of a Bhasha Studio job:
 *   1. POST /process  → gets job_id
 *   2. GET  /stream/{job_id} (SSE) → real-time events
 *
 * SSE event shapes expected from backend:
 *   { type: 'phase',    data: { phase: 1|2|3 } }
 *   { type: 'line',     data: { time, en, formal, natural } }
 *   { type: 'progress', data: { value: 0-100 } }
 *   { type: 'metrics',  data: { duration, processingTime, rtf } }
 *   { type: 'done' }
 *   { type: 'error',    data: { message } }
 */
export function useSSEJob(baseUrl) {
  const [status, setStatus]   = useState('idle');   // idle | uploading | streaming | done | error
  const [phase, setPhase]     = useState(0);         // 0 = none, 1-3 = active phase
  const [lines, setLines]     = useState([]);
  const [progress, setProgress] = useState(0);
  const [metrics, setMetrics] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');

  const esRef    = useRef(null);   // EventSource
  const abortRef = useRef(null);   // AbortController for upload

  const reset = useCallback(() => {
    setStatus('idle');
    setPhase(0);
    setLines([]);
    setProgress(0);
    setMetrics(null);
    setErrorMsg('');
  }, []);

  const cancelJob = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
    if (esRef.current)    esRef.current.close();
    reset();
  }, [reset]);

  const startJob = useCallback(async ({ file, sourceLang, generateAudio }) => {
    reset();
    setStatus('uploading');

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const form = new FormData();
      form.append('file', file);
      form.append('source_lang', sourceLang);
      form.append('generate_audio', String(generateAudio));

      const { data } = await axios.post(`${baseUrl}/process`, form, {
        signal: controller.signal,
        onUploadProgress: () => {},   // could expose upload progress here
      });

      const jobId = data.job_id;
      setStatus('streaming');

      // Open SSE stream
      const es = new EventSource(`${baseUrl}/stream/${jobId}`);
      esRef.current = es;

      es.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          switch (msg.type) {
            case 'phase':
              setPhase(msg.data.phase);
              break;

            case 'line':
              setLines(prev => [...prev, msg.data]);
              break;

            case 'progress':
              setProgress(msg.data.value);
              break;

            case 'metrics':
              setMetrics(msg.data);
              break;

            case 'done':
              setProgress(100);
              setStatus('done');
              es.close();
              break;

            case 'error':
              setErrorMsg(msg.data?.message || 'Backend error');
              setStatus('error');
              es.close();
              break;

            default:
              break;
          }
        } catch (parseErr) {
          console.warn('SSE parse error:', parseErr);
        }
      };

      es.onerror = () => {
        setErrorMsg('Lost connection to backend stream.');
        setStatus('error');
        es.close();
      };

    } catch (err) {
      if (axios.isCancel(err) || err.name === 'CanceledError') {
        reset();
      } else {
        setErrorMsg(err?.response?.data?.detail || err.message || 'Upload failed');
        setStatus('error');
      }
    }
  }, [baseUrl, reset]);

  return {
    status,
    phase,
    lines,
    progress,
    metrics,
    errorMsg,
    startJob,
    cancelJob,
    reset,
  };
}

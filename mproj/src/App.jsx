import { useState, useRef } from 'react';
import { Sparkles, XCircle } from 'lucide-react';

import ConnectivityDot from './components/ConnectivityDot';
import DropZone        from './components/DropZone';
import ConfigBar       from './components/ConfigBar';
import PipelineStepper from './components/PipelineStepper';
import LiveTerminal    from './components/LiveTerminal';
import ProgressBar     from './components/ProgressBar';
import MetricsPanel    from './components/MetricsPanel';
import DownloadBay     from './components/DownloadBay';
import { useSSEJob }   from './hooks/useSSEJob';

const DEFAULT_BASE_URL = 'http://localhost:8000';

/* ─── tiny toast ─────────────────────────────── */
function Toast({ message, onDismiss }) {
  if (!message) return null;
  return (
    <div className="toast" role="alert">
      <XCircle size={16} />
      {message}
      <button
        onClick={onDismiss}
        style={{ marginLeft: 'auto', background: 'none', border: 'none',
                 color: 'inherit', cursor: 'pointer', padding: '0 2px' }}
      >✕</button>
    </div>
  );
}

/* ─── main app ───────────────────────────────── */
export default function App() {
  const [baseUrl, setBaseUrl]           = useState(DEFAULT_BASE_URL);
  const [file, setFile]                 = useState(null);
  const [sourceLang, setSourceLang]     = useState('english');
  const [generateAudio, setGenerateAudio] = useState(false);
  const [jobId, setJobId]               = useState(null);
  const [startedAt, setStartedAt]       = useState(null);
  const [toast, setToast]               = useState('');

  const {
    status, phase, lines, progress, metrics, errorMsg,
    startJob, cancelJob, reset,
  } = useSSEJob(baseUrl);

  /* Crude estimate: MP4/MOV ~1MB/s at 30fps low-res → duration ≈ filesize/1_000_000 */
  const fileDurationSec = file
    ? Math.max(10, (file.size / 1_000_000) * 0.9)
    : null;

  const handleStart = async () => {
    if (!file) { setToast('Please select a video or audio file first.'); return; }
    setJobId(null);
    setStartedAt(Date.now());

    // startJob resolves after upload; jobId comes back via SSE "done" metrics
    await startJob({ file, sourceLang, generateAudio });
  };

  const handleCancel = () => {
    cancelJob();
    setJobId(null);
    setStartedAt(null);
  };

  // Capture job_id from metrics event if backend sends it there, or from POST response.
  // We expose a simple prop for it via a workaround: store from errorMsg data or metrics.
  // If your backend sends job_id inside the 'done' SSE event, handle here:
  // (The useSSEJob hook already exposes `metrics`; adapt as needed)
  const resolvedJobId = jobId ?? (metrics?.job_id ?? null);

  const isProcessing = status === 'uploading' || status === 'streaming';
  const isDone       = status === 'done';
  const isIdle       = status === 'idle';

  // Show error as toast
  const activeToast = toast || (status === 'error' ? errorMsg : '');

  return (
    <div className="app-shell">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="logo-block">
          <div className="logo-icon">🌿</div>
          <div>
            <div className="logo-name">
              <span className="text-gradient">Bhasha</span> Studio
            </div>
            <div className="logo-tagline">Malayalam AI Dubbing Pipeline</div>
          </div>
        </div>
        <ConnectivityDot baseUrl={baseUrl} onBaseUrlChange={setBaseUrl} />
      </header>

      {/* ── Main ── */}
      <main className="app-main">

        {/* ══ ZONE 1: Input (visible when idle or processing) ══ */}
        {(isIdle || isProcessing) && (
          <section className="zone-section">
            <DropZone
              file={file}
              onFile={setFile}
              disabled={isProcessing}
            />

            <ConfigBar
              sourceLang={sourceLang}
              onSourceLang={setSourceLang}
              generateAudio={generateAudio}
              onGenerateAudio={setGenerateAudio}
              disabled={isProcessing}
            />

            <div className="action-row">
              <button
                id="btn-generate"
                className="btn-ignite"
                onClick={handleStart}
                disabled={isProcessing || !file}
              >
                <span className="btn-inner">
                  {status === 'uploading' ? (
                    <>
                      <span style={{
                        display:'inline-block', width:18, height:18,
                        border:'2px solid rgba(255,255,255,0.3)',
                        borderTopColor:'#fff', borderRadius:'50%',
                        animation:'spin 0.7s linear infinite'
                      }} />
                      Uploading…
                    </>
                  ) : (
                    <>
                      <Sparkles size={18} />
                      Generate Malayalam Subtitles
                    </>
                  )}
                </span>
              </button>

              {isProcessing && (
                <button id="btn-cancel" className="btn-cancel" onClick={handleCancel}>
                  <XCircle size={16} /> Cancel
                </button>
              )}
            </div>
          </section>
        )}

        {/* ══ ZONE 2: Processing Engine ══ */}
        {(isProcessing || isDone) && (
          <section className="zone-section" style={{ marginTop: isIdle ? 0 : 28 }}>
            <div className="section-divider">
              <span>⚙ Processing Engine</span>
            </div>

            <PipelineStepper activePhase={isDone ? 4 : phase} />

            <div style={{ marginTop: 16 }}>
              <LiveTerminal lines={lines} isLive={isProcessing} />
            </div>

            <ProgressBar
              progress={isDone ? 100 : progress}
              fileDurationSec={fileDurationSec}
              startedAt={startedAt}
            />
          </section>
        )}

        {/* ══ ZONE 3: Analytics & Output Hub ══ */}
        {isDone && (
          <section className="zone-section" style={{ marginTop: 28 }}>
            <div className="section-divider">
              <span>📊 Analytics & Output</span>
            </div>

            <MetricsPanel metrics={metrics} />

            <div style={{ marginTop: 16 }}>
              <DownloadBay
                jobId={resolvedJobId}
                baseUrl={baseUrl}
                generateAudio={generateAudio}
              />
            </div>

            <div style={{ marginTop: 20, textAlign: 'center' }}>
              <button
                id="btn-new-job"
                className="btn-ignite"
                style={{ maxWidth: 260, margin: '0 auto' }}
                onClick={() => { reset(); setFile(null); setJobId(null); setStartedAt(null); }}
              >
                <span className="btn-inner">
                  <Sparkles size={16} /> Process Another File
                </span>
              </button>
            </div>
          </section>
        )}

      </main>

      {/* ── Global Toast ── */}
      <Toast message={activeToast} onDismiss={() => setToast('')} />
    </div>
  );
}

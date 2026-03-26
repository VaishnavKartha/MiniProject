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
import { useJobApi }   from './hooks/useSSEJob';

const DEFAULT_BASE_URL = 'https://unabstractive-surgeonless-jennette.ngrok-free.dev';

/* ─── Map of fake terminal lines → which phase they belong to ────── */
const PHASE_TRIGGERS = {
  '🎙 Phase 1': 1,
  '📖 Phase 2': 2,
  '✨ Phase 3': 3,
};

function resolvePhase(lines) {
  let phase = 1;
  for (const l of lines) {
    const msg = l._system ?? '';
    for (const [key, p] of Object.entries(PHASE_TRIGGERS)) {
      if (msg.startsWith(key)) phase = p;
    }
  }
  return phase;
}

/* ─── Toast ──────────────────────────────────────────────────────── */
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

/* ─── App ─────────────────────────────────────────────────────────── */
export default function App() {
  const [baseUrl,        setBaseUrl]        = useState(DEFAULT_BASE_URL);
  const [file,           setFile]           = useState(null);
  const [sourceLang,     setSourceLang]     = useState('en');   // "en" | "hi"
  const [generateAudio,  setGenerateAudio]  = useState(false);
  const [startedAt,      setStartedAt]      = useState(null);
  const [toast,          setToast]          = useState('');

  const {
    status, progress, termLines, metrics, blobs, errorMsg,
    startJob, cancelJob, reset,
  } = useJobApi(baseUrl);

  /* Crude duration estimate: ~1 MB/s video = 1 s/MB */
  const fileDurationSec = file ? Math.max(10, file.size / 1_000_000 * 0.9) : null;

  const handleStart = async () => {
    if (!file) { setToast('Please select a video or audio file first.'); return; }
    setStartedAt(Date.now());
    await startJob({ file, lang: sourceLang, generateAudio, fileDurationSec });
  };

  const handleCancel = () => {
    cancelJob();
    setStartedAt(null);
  };

  const handleReset = () => {
    reset();
    setFile(null);
    setStartedAt(null);
  };

  const isProcessing = status === 'uploading' || status === 'processing';
  const isDone       = status === 'done';
  const isIdle       = status === 'idle';

  const activePhase = resolvePhase(termLines);
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

        {/* ══ ZONE 1: Input ══ */}
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
                  {isProcessing ? (
                    <>
                      <span style={{
                        display: 'inline-block', width: 18, height: 18,
                        border: '2px solid rgba(255,255,255,0.3)',
                        borderTopColor: '#fff', borderRadius: '50%',
                        animation: 'spin 0.7s linear infinite',
                      }} />
                      Processing…
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
          <section className="zone-section" style={{ marginTop: 28 }}>
            <div className="section-divider">
              <span>⚙ Processing Engine</span>
            </div>

            <PipelineStepper activePhase={isDone ? 4 : activePhase} />

            <div style={{ marginTop: 16 }}>
              <LiveTerminal lines={termLines} isLive={isProcessing} />
            </div>

            <ProgressBar
              progress={isDone ? 100 : progress}
              fileDurationSec={fileDurationSec}
              startedAt={startedAt}
            />
          </section>
        )}

        {/* ══ ZONE 3: Analytics & Output ══ */}
        {isDone && (
          <section className="zone-section" style={{ marginTop: 28 }}>
            <div className="section-divider">
              <span>📊 Analytics &amp; Output</span>
            </div>

            <MetricsPanel metrics={metrics} />

            <div style={{ marginTop: 16 }}>
              <DownloadBay
                blobs={blobs}
                fileName={file?.name}
                generateAudio={generateAudio}
              />
            </div>

            <div style={{ marginTop: 20, textAlign: 'center' }}>
              <button
                id="btn-new-job"
                className="btn-ignite"
                style={{ maxWidth: 260, margin: '0 auto' }}
                onClick={handleReset}
              >
                <span className="btn-inner">
                  <Sparkles size={16} /> Process Another File
                </span>
              </button>
            </div>
          </section>
        )}

      </main>

      {/* ── Toast ── */}
      <Toast message={activeToast} onDismiss={() => setToast('')} />
    </div>
  );
}

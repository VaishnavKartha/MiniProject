import { Clock, Timer, Zap, Mic, BrainCircuit, Globe, Volume2 } from 'lucide-react';

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// Quick helper for phase times (like 1.4s)
function formatSeconds(seconds) {
  if (!seconds) return '—';
  return `${seconds < 1 ? seconds.toFixed(2) : Math.round(seconds)} sec`;
}

export default function MetricsPanel({ metrics }) {
  if (!metrics) return null;

  // Destructure matching the new backend JSON payload
  const { video_duration, processing_time, rtf, phase_times } = metrics;

  const cards = [
    {
      icon: <Clock size={14} />,
      label: 'Video Duration',
      value: formatDuration(video_duration),
      sub: 'source media length',
    },
    {
      icon: <Timer size={14} />,
      label: 'Processing Time',
      value: formatDuration(processing_time),
      sub: 'end-to-end pipeline',
    },
    {
      icon: <Zap size={14} />,
      label: 'Real-Time Factor',
      value: rtf != null ? `${Number(rtf).toFixed(2)}x` : '—',
      sub: 'lower = faster than realtime',
    },
  ];

  return (
    <div className="metrics-panel">
      {/* ── Top Level Cards ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        {cards.map((c) => (
          <div key={c.label} className="metric-card" style={{ padding: '12px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
            <div className="metric-icon-label" style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#a0aec0', marginBottom: '8px' }}>
              {c.icon}
              {c.label}
            </div>
            <div className="metric-value" style={{ fontSize: '20px', fontWeight: 'bold' }}>{c.value}</div>
            <div className="metric-sub" style={{ fontSize: '11px', color: '#718096', marginTop: '4px' }}>{c.sub}</div>
          </div>
        ))}
      </div>

      {/* ── Phase Breakdown ── */}
      {phase_times && (
        <div className="phase-breakdown" style={{ padding: '12px', borderTop: '1px solid rgba(255,255,255,0.1)', fontSize: '13px', color: '#e2e8f0' }}>
          <div style={{ marginBottom: '8px', fontWeight: '600', color: '#a0aec0' }}>Phase Breakdown</div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Mic size={14} /> <span style={{ opacity: 0.8 }}>Whisper:</span> {formatSeconds(phase_times.p1)}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <BrainCircuit size={14} /> <span style={{ opacity: 0.8 }}>IndicTrans2:</span> {formatSeconds(phase_times.p2)}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Globe size={14} /> <span style={{ opacity: 0.8 }}>Groq:</span> {formatSeconds(phase_times.p3)}
            </div>
            {phase_times.p4 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#ecc94b' }}>
                <Volume2 size={14} /> <span style={{ opacity: 0.8 }}>TTS Audio:</span> {formatSeconds(phase_times.p4)}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
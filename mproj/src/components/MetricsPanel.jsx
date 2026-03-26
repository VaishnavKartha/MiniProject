import { Clock, Timer, Zap } from 'lucide-react';

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default function MetricsPanel({ metrics }) {
  if (!metrics) return null;

  const { duration, processingTime, rtf } = metrics;

  const cards = [
    {
      icon: <Clock size={14} />,
      label: 'Video Duration',
      value: formatDuration(duration),
      sub: 'source media length',
    },
    {
      icon: <Timer size={14} />,
      label: 'Processing Time',
      value: formatDuration(processingTime),
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
      {cards.map((c) => (
        <div key={c.label} className="metric-card">
          <div className="metric-icon-label">
            {c.icon}
            {c.label}
          </div>
          <div className="metric-value">{c.value}</div>
          <div className="metric-sub">{c.sub}</div>
        </div>
      ))}
    </div>
  );
}

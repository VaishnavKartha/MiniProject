import { useEffect, useState } from 'react';
import { Clock } from 'lucide-react';

/**
 * RTF ≈ 0.2 means for a 60s video → ~12s processing time.
 * fileDuration is in seconds (optional, estimated from file size if not provided).
 */
const ESTIMATED_RTF = 0.22;

function formatCountdown(secs) {
  if (secs <= 0) return '00:00';
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default function ProgressBar({ progress, fileDurationSec, startedAt }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startedAt) return;
    const id = setInterval(() => {
      setElapsed((Date.now() - startedAt) / 1000);
    }, 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  // Estimate total time
  const estimatedTotal = fileDurationSec ? fileDurationSec * ESTIMATED_RTF : null;
  const remaining = estimatedTotal ? Math.max(0, estimatedTotal - elapsed) : null;

  return (
    <div className="progress-section">
      <div className="progress-header">
        <span className="progress-pct">{Math.round(progress)}%</span>
        {remaining !== null && progress < 100 && (
          <span className="progress-eta">
            <Clock size={11} style={{ display: 'inline', marginRight: 4 }} />
            ETA {formatCountdown(remaining)}
          </span>
        )}
        {progress >= 100 && (
          <span className="progress-eta" style={{ color: 'var(--accent-green)' }}>
            ✓ Complete
          </span>
        )}
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}

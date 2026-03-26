import { useState, useEffect } from 'react';

export default function ConnectivityDot({ baseUrl, onBaseUrlChange }) {
  const [status, setStatus] = useState('checking');

  useEffect(() => {
    let cancelled = false;

    const ping = async () => {
      setStatus('checking');
      try {
        // /docs is always served by FastAPI — safe ping target
        const res = await fetch(`${baseUrl}/docs`, {
          signal: AbortSignal.timeout(4000),
          method: 'HEAD',
        });
        if (!cancelled) setStatus(res.ok ? 'online' : 'offline');
      } catch {
        if (!cancelled) setStatus('offline');
      }
    };

    ping();
    const id = setInterval(ping, 5000);
    return () => { cancelled = true; clearInterval(id); };
  }, [baseUrl]);

  const label = {
    checking: 'Checking…',
    online:   'Backend Online',
    offline:  'Connection Lost',
  }[status];

  return (
    <div className="connectivity-block">
      <input
        className="url-input"
        type="text"
        placeholder="https://xxxx.ngrok-free.app"
        defaultValue={baseUrl}
        onBlur={(e)  => onBaseUrlChange(e.target.value.replace(/\/$/, ''))}
        onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur(); }}
        title="Backend base URL (Kaggle / Ngrok tunnel)"
      />
      <div className="conn-status">
        <span className={`conn-dot ${status}`} />
        {label}
      </div>
    </div>
  );
}

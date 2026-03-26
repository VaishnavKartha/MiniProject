import { useState, useEffect, useRef } from 'react';

/**
 * ConnectivityDot – top-right header widget
 * Pings `baseUrl/health` every 5 s and shows online/offline status.
 * Also renders the ngrok URL input.
 */
export default function ConnectivityDot({ baseUrl, onBaseUrlChange }) {
  const [status, setStatus] = useState('checking'); // checking | online | offline
  const inputRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    const ping = async () => {
      setStatus('checking');
      try {
        const res = await fetch(`${baseUrl}/health`, { signal: AbortSignal.timeout(4000) });
        if (!cancelled) setStatus(res.ok ? 'online' : 'offline');
      } catch {
        if (!cancelled) setStatus('offline');
      }
    };

    ping();
    const id = setInterval(ping, 5000);
    return () => { cancelled = true; clearInterval(id); };
  }, [baseUrl]);

  const label = { checking: 'Checking…', online: 'Backend Online', offline: 'Connection Lost' }[status];

  return (
    <div className="connectivity-block">
      <input
        ref={inputRef}
        className="url-input"
        type="text"
        placeholder="https://xxxx.ngrok-free.app"
        defaultValue={baseUrl}
        onBlur={(e) => onBaseUrlChange(e.target.value.replace(/\/$/, ''))}
        onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur(); }}
        title="Backend base URL (your Kaggle/Ngrok tunnel)"
      />
      <div className="conn-status">
        <span className={`conn-dot ${status}`} />
        {label}
      </div>
    </div>
  );
}

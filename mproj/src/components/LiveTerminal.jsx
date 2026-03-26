import { useEffect, useRef } from 'react';

function TerminalLine({ line, index }) {
  // system / info messages
  if (line._system) {
    return (
      <div className="terminal-line">
        <span className="terminal-line-system">{line._system}</span>
      </div>
    );
  }

  return (
    <div className="terminal-line">
      <span className="terminal-time">[{line.time ?? '00:00'}]</span>
      {'  '}
      <span className="terminal-lang en">EN</span>
      <span className="terminal-text">: "{line.en}"</span>
      <br />
      {'           '}
      <span className="terminal-lang formal">MAL (Formal)</span>
      <span className="terminal-text">: {line.formal}</span>
      <br />
      {'           '}
      <span className="terminal-lang natural">MAL (Natural)</span>
      <span className="terminal-text">: {line.natural}</span>
    </div>
  );
}

export default function LiveTerminal({ lines, isLive }) {
  const bottomRef = useRef(null);

  // Auto-scroll to bottom whenever lines change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [lines]);

  return (
    <div className="terminal-wrapper">
      <div className="terminal-header">
        <div className="terminal-dots">
          <span className="terminal-dot red" />
          <span className="terminal-dot yellow" />
          <span className="terminal-dot green" />
        </div>
        <span className="terminal-title">bhasha-studio — live translation output</span>
      </div>

      <div className="terminal-body">
        {lines.length === 0 && (
          <span className="terminal-line-system">
            Initialising pipeline… waiting for first segment
          </span>
        )}
        {lines.map((line, i) => (
          <TerminalLine key={i} line={line} index={i} />
        ))}
        {isLive && <span className="terminal-cursor" />}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

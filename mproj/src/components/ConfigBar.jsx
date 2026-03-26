export default function ConfigBar({ sourceLang, onSourceLang, generateAudio, onGenerateAudio, disabled }) {
  return (
    <div className="config-bar">
      <div className="config-group">
        <label className="config-label" htmlFor="source-lang">Source Language</label>
        <select
          id="source-lang"
          className="config-select"
          value={sourceLang}
          onChange={e => onSourceLang(e.target.value)}
          disabled={disabled}
        >
          {/* Values match the backend `lang` form field exactly */}
          <option value="en">English</option>
          <option value="hi">Hindi / Hinglish</option>
        </select>
      </div>

      <div className="toggle-group">
        <label className="config-label">Audio Output</label>
        <label className="toggle-row" htmlFor="audio-toggle">
          <span className="toggle-switch">
            <input
              id="audio-toggle"
              type="checkbox"
              checked={generateAudio}
              onChange={e => onGenerateAudio(e.target.checked)}
              disabled={disabled}
            />
            <span className="toggle-slider" />
          </span>
          <span className="toggle-label-text">Generate Malayalam Audio Track</span>
        </label>
        <span className="toggle-subtext">
          {generateAudio
            ? '⚡ Audio synthesis enabled — calls /generate-dubbed-audio (increases processing time)'
            : 'Subtitles only — calls /generate-subtitles'}
        </span>
      </div>
    </div>
  );
}

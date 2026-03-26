import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Film, Music, X, UploadCloud, AlertCircle } from 'lucide-react';

const ACCEPTED_MIME = {
  'video/mp4':        ['.mp4'],
  'video/quicktime':  ['.mov'],
  'audio/wav':        ['.wav'],
  'audio/mpeg':       ['.mp3'],
};
const MAX_SIZE_MB = 50;
const MAX_SIZE_B  = MAX_SIZE_MB * 1024 * 1024;

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileIcon({ mime }) {
  const isAudio = mime?.startsWith('audio');
  const Icon = isAudio ? Music : Film;
  return (
    <div className="file-thumbnail">
      <Icon size={22} color="var(--accent-cyan)" />
    </div>
  );
}

export default function DropZone({ file, onFile, disabled }) {
  const [dragError, setDragError] = useState('');
  const [shaking, setShaking] = useState(false);

  const triggerShake = (msg) => {
    setDragError(msg);
    setShaking(true);
    setTimeout(() => setShaking(false), 600);
  };

  const onDrop = useCallback((accepted, rejected) => {
    setDragError('');
    if (rejected.length > 0) {
      const r = rejected[0];
      if (r.errors.some(e => e.code === 'file-too-large')) {
        triggerShake(`File too large — max ${MAX_SIZE_MB} MB`);
      } else {
        triggerShake('Unsupported file type — use .mp4, .mov, .wav, or .mp3');
      }
      return;
    }
    if (accepted.length > 0) {
      setDragError('');
      onFile(accepted[0]);
    }
  }, [onFile]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_MIME,
    maxSize: MAX_SIZE_B,
    multiple: false,
    disabled,
  });

  const clearFile = (e) => {
    e.stopPropagation();
    onFile(null);
    setDragError('');
  };

  const cls = [
    'dropzone-wrapper',
    isDragActive ? 'drag-active' : '',
    file          ? 'has-file'    : '',
    shaking       ? 'error-shake' : '',
  ].filter(Boolean).join(' ');

  return (
    <div>
      <div {...getRootProps({ className: cls })}>
        <input {...getInputProps()} />

        {file ? (
          <div className="file-preview" onClick={e => e.stopPropagation()}>
            <FileIcon mime={file.type} />
            <div className="file-info">
              <div className="file-name">{file.name}</div>
              <div className="file-size">{formatBytes(file.size)}</div>
            </div>
            <button className="file-remove-btn" onClick={clearFile} title="Remove file">
              <X size={16} />
            </button>
          </div>
        ) : (
          <>
            <div className="dropzone-icon">
              <UploadCloud size={28} color={isDragActive ? 'var(--accent-violet)' : 'var(--text-muted)'} />
            </div>
            <div className="dropzone-title">
              {isDragActive ? 'Drop it here' : 'Drag & Drop Video Here or Click to Browse'}
            </div>
            <div className="dropzone-sub">
              AI-powered Malayalam subtitle generation
            </div>
            <div className="dropzone-chips">
              {['.mp4', '.mov', '.wav', '.mp3'].map(ext => (
                <span key={ext} className="chip">{ext}</span>
              ))}
              <span className="chip">max {MAX_SIZE_MB} MB</span>
            </div>
          </>
        )}
      </div>

      {dragError && (
        <div className="dropzone-error">
          <AlertCircle size={13} />
          {dragError}
        </div>
      )}
    </div>
  );
}

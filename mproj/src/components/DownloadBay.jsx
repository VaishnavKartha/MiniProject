import { Download, FileText, Volume2 } from 'lucide-react';

/**
 * DownloadBay
 * Downloads files from in-memory Blobs (no server round-trip needed —
 * the backend returned the file directly in the POST response body).
 */
function blobDownload(blob, filename) {
  if (!blob) return;
  const url = URL.createObjectURL(blob);
  const a   = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export default function DownloadBay({ blobs, fileName, generateAudio }) {
  if (!blobs?.comparison) return null;

  const base = fileName
    ? fileName.replace(/\.[^.]+$/, '')
    : 'bhasha_output';

  return (
    <div className="download-bay">
      <div className="download-title">⬇ Download Files</div>
      <div className="download-buttons">
        <button
          id="btn-download-comparison"
          className="btn-download comparison"
          onClick={() => blobDownload(blobs.comparison, `${base}_comparison.srt`)}
        >
          <FileText size={16} />
          Download Comparison SRT
        </button>

        <button
          id="btn-download-natural"
          className="btn-download natural"
          onClick={() => blobDownload(blobs.natural, `${base}_natural.srt`)}
          disabled={!blobs.natural}
        >
          <Download size={16} />
          Download Natural SRT
        </button>

        {generateAudio && (
          <button
            id="btn-download-audio"
            className="btn-download audio"
            onClick={() => blobDownload(blobs.audio, `${base}_dubbed.mp3`)}
            disabled={!blobs.audio}
          >
            <Volume2 size={16} />
            Download Translated Audio (.mp3)
          </button>
        )}
      </div>
    </div>
  );
}

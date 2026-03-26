import { Download, FileText, Volume2 } from 'lucide-react';

export default function DownloadBay({ jobId, baseUrl, generateAudio }) {
  if (!jobId) return null;

  const dl = (path) => {
    window.open(`${baseUrl}${path}`, '_blank');
  };

  return (
    <div className="download-bay">
      <div className="download-title">⬇ Download Files</div>
      <div className="download-buttons">
        <button
          id="btn-download-comparison"
          className="btn-download comparison"
          onClick={() => dl(`/download/${jobId}/comparison`)}
        >
          <FileText size={16} />
          Download Comparison SRT
        </button>

        <button
          id="btn-download-natural"
          className="btn-download natural"
          onClick={() => dl(`/download/${jobId}/natural`)}
        >
          <Download size={16} />
          Download Natural SRT
        </button>

        {generateAudio && (
          <button
            id="btn-download-audio"
            className="btn-download audio"
            onClick={() => dl(`/download/${jobId}/audio`)}
          >
            <Volume2 size={16} />
            Download Translated Audio (.mp3)
          </button>
        )}
      </div>
    </div>
  );
}

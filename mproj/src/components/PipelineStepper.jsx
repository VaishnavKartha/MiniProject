import { Check } from 'lucide-react';

export default function PipelineStepper({ activePhase, generateAudio }) {
  // 1. Define the base 3 phases that always happen
  const basePhases = [
    { id: 1, icon: '🎙️', label: 'Whisper Extraction' },
    { id: 2, icon: '📖', label: 'IndicTrans2 Translation' },
    { id: 3, icon: '✨', label: 'Groq Llama Polish' },
  ];

  // 2. Conditionally add Phase 4 if the user requested audio
  const phases = generateAudio 
    ? [...basePhases, { id: 4, icon: '🔊', label: 'TTS Audio Dubbing' }]
    : basePhases;

  return (
    <div className="pipeline-stepper" style={{ display: 'flex', gap: '12px', overflowX: 'auto' }}>
      {phases.map((p) => {
        const isCompleted = activePhase > p.id;
        const isActive    = activePhase === p.id;
        
        const cls = ['step-item', isActive ? 'active' : '', isCompleted ? 'completed' : '']
          .filter(Boolean).join(' ');

        return (
          <div key={p.id} className={cls}>
            <div className="step-circle">
              {isCompleted ? <Check size={18} color="var(--accent-violet)" /> : p.icon}
            </div>
            <div className="step-label">
              Phase {p.id}<br />{p.label}
            </div>
          </div>
        );
      })}
    </div>
  );
}
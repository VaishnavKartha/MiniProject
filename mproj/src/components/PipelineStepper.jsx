import { Check } from 'lucide-react';

const PHASES = [
  { id: 1, icon: '🎙️', label: 'Whisper Audio Extraction' },
  { id: 2, icon: '📖', label: 'IndicTrans2 Formal Translation' },
  { id: 3, icon: '✨', label: 'Groq Llama Polish' },
];

export default function PipelineStepper({ activePhase }) {
  return (
    <div className="pipeline-stepper">
      {PHASES.map((p, idx) => {
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

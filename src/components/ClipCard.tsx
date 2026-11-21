import { Trash2 } from 'lucide-react';
import { ClipSegment } from '../types';

interface Props {
  clip: ClipSegment;
  onRemove: (id: string) => void;
}

export const ClipCard: React.FC<Props> = ({ clip, onRemove }) => {
  const duration = clip.end - clip.start;
  const durationPercent = Math.min((duration / 60) * 100, 100);

  return (
    <div className="glass-card flex items-center gap-3 px-3.5 py-2.5 rounded-lg border border-slate-700/50 transition-all group hover:border-accent/50">
      <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent/20 to-accent/5 flex items-center justify-center text-accent text-xs font-bold shadow-[0_0_15px_rgba(56,189,248,0.2)]">
        {clip.id.slice(0, 2).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex justify-between items-start text-sm">
          <span className="text-white truncate font-medium">{clip.reason}</span>
          <span className="text-accent font-mono text-xs">
            {clip.start.toFixed(1)}s → {clip.end.toFixed(1)}s
          </span>
        </div>
        <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-accent to-accent-dim transition-all duration-300"
            style={{ width: `${durationPercent}%` }}
          />
        </div>
        <div className="flex justify-between items-center mt-1">
          <span className="text-xs text-muted">{duration.toFixed(1)}с</span>
          <span className={`text-xs font-medium badge border ${clip.score > 0.7 ? 'border-success/30 bg-success/10 text-success' : 'border-muted/30 bg-muted/10 text-muted'}`}>
            {`${(clip.score * 100).toFixed(0)}%`}
          </span>
        </div>
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onRemove(clip.id);
        }}
        className="p-1.5 text-slate-500 hover:text-danger hover:bg-danger/10 rounded transition-colors"
        title="Удалить"
      >
        <Trash2 size={16} />
      </button>
    </div>
  );
};

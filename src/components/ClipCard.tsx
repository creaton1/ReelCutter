import { Trash2 } from 'lucide-react';
import { ClipSegment } from '../types';

interface Props {
  clip: ClipSegment;
  onRemove: (id: string) => void;
}

export const ClipCard: React.FC<Props> = ({ clip, onRemove }) => {

  return (
    <div className="flex items-center gap-3 px-3 py-2 bg-surface hover:bg-surface-hover rounded-lg border border-slate-700/50 transition-colors cursor-pointer group">
      <div className="w-8 h-8 rounded bg-accent/20 flex items-center justify-center text-accent text-xs font-bold">
        {clip.id.slice(0, 2).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex justify-between text-sm">
          <span className="text-slate-300 truncate">{clip.reason}</span>
          <span className="text-accent font-mono text-xs">
            {clip.start.toFixed(1)}s → {clip.end.toFixed(1)}s
          </span>
        </div>
        <div className="w-full bg-slate-800 h-1.5 rounded-full mt-1 overflow-hidden">
          <div
            className="h-full bg-accent"
            style={{ width: `${((clip.end - clip.start) / 60) * 100}%` }}
          />
        </div>
      </div>
      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove(clip.id);
          }}
          className="p-1.5 hover:bg-red-500/20 text-red-400 rounded"
          title="Удалить"
        >
          <Trash2 size={16} />
        </button>
      </div>
    </div>
  );
};

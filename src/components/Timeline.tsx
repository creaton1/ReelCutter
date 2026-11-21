import { Scissors, Play, Save } from 'lucide-react';
import { useStore } from '../lib/store';
import { Highlight, ClipSegment } from '../types';
import { ClipCard } from './ClipCard';

export const Timeline = () => {
  const { highlights, clips, setClips, saveCurrentClips, activeProjectId } = useStore();

  const addHighlight = (h: Highlight) => {
    const clip: ClipSegment = {
      id: crypto.randomUUID(),
      start: h.start,
      end: h.end,
      score: h.score,
      reason: h.reason,
      output_path: undefined,
    };
    setClips([...clips, clip]);
  };

  const removeClip = (id: string) => {
    setClips(clips.filter((c) => c.id !== id));
  };

  const totalDuration = clips.reduce((acc, c) => acc + (c.end - c.start), 0);

  return (
    <div className="glass-panel flex flex-col p-5 min-h-[420px] animate-slide-up">
      <div className="flex items-center justify-between mb-1">
        <h3 className="font-semibold text-white">Таймлайн клипов</h3>
        {totalDuration > 0 && (
          <span className="text-xs font-mono text-accent">
            {totalDuration.toFixed(1)}с всего
          </span>
        )}
      </div>

      <div className="flex gap-2 overflow-x-auto pb-4 scrollbar-hide">
        {highlights.map((h) => (
          <button
            key={`${h.start}-${h.end}`}
            onClick={() => addHighlight(h)}
            className="flex items-center gap-2 px-3 py-2 bg-surface hover:bg-surface-hover border border-accent/40 text-accent text-xs rounded-lg transition-all active:scale-95 whitespace-nowrap"
          >
            <Play size={14} />
            <span>{`+ ${h.start.toFixed(1)}–${h.end.toFixed(1)}с`}</span>
          </button>
        ))}
        {highlights.length === 0 && (
          <span className="px-3 py-2 bg-slate-800/50 border border-slate-700/50 text-muted text-xs rounded-lg">
            Нет доступных моментов
          </span>
        )}
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto pr-2">
        {clips.length === 0 ? (
          <div className="empty-state flex-1">
            <Scissors size={32} className="mx-auto mb-3 opacity-20 text-slate-500" />
            <p className="text-muted text-sm">Клипов не добавлено</p>
            <p className="text-xs text-slate-500">Выделите моменты выше, чтобы добавить их на таймлайн</p>
          </div>
        ) : (
          clips.map((c) => (
            <ClipCard key={c.id} clip={c} onRemove={removeClip} />
          ))
        )}
      </div>

      {clips.length > 0 && activeProjectId && (
        <button
          onClick={saveCurrentClips}
          className="btn-primary w-full flex items-center justify-center gap-2"
        >
          <Save size={16} /> Сохранить клипы в проект
        </button>
      )}
    </div>
  );
};

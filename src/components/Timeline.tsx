import { Scissors } from 'lucide-react';
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

  return (
    <div className="flex flex-col gap-4 bg-surface-hover rounded-xl p-4 border border-slate-700/50">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-300">Таймлайн клипов</h3>
        <div className="flex gap-2">
          {highlights.map((h) => (
            <button
              key={`${h.start}-${h.end}`}
              onClick={() => addHighlight(h)}
              className="px-3 py-1.5 text-xs bg-surface hover:bg-surface-hover border border-accent/50 text-accent rounded transition-colors"
            >
              {`+ ${h.start.toFixed(1)}–${h.end.toFixed(1)}с`}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2">
        {clips.length === 0 ? (
          <div className="text-center text-slate-500 text-sm py-8">
            <Scissors size={24} className="mx-auto mb-2 opacity-30" />
            <p>Клипов не добавлено. Выделите моменты выше.</p>
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
          className="w-full py-2 bg-accent text-black font-medium rounded hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Сохранить клипы в проект
        </button>
      )}
    </div>
  );
};

import { FilePlus } from 'lucide-react';
import { useStore } from '../lib/store';

export const VideoPreview = () => {
  const { sourcePath, videoInfo, isLoadingVideo, highlights } = useStore();

  return (
    <div className="flex flex-col gap-4 bg-surface-hover rounded-xl p-4 border border-slate-700/50 min-h-[300px]">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-300">Исходное видео</h3>
        {isLoadingVideo ? (
          <span className="text-xs text-accent animate-pulse">Загрузка...</span>
        ) : null}
      </div>

      {sourcePath ? (
        <div className="relative w-full aspect-video bg-black rounded-lg overflow-hidden flex items-center justify-center">
          <video
            src={sourcePath}
            className="w-full h-full object-cover"
            controls
          />
          {videoInfo && (
            <div className="absolute bottom-4 right-4 bg-black/60 px-3 py-1 rounded text-xs text-slate-200">
              {videoInfo.duration.toFixed(1)}с • {videoInfo.width}x{videoInfo.height} • {videoInfo.fps.toFixed(1)} FPS
            </div>
          )}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center h-64 text-slate-500">
          <FilePlus size={48} className="mb-2 opacity-50" />
          <p>Видео не выбрано</p>
        </div>
      )}

      {highlights.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-2">
          {highlights.map((h, i) => (
            <span
              key={i}
              className="px-2 py-1 text-xs bg-slate-800 rounded text-accent border border-accent/30 whitespace-nowrap"
            >
              {`${h.start.toFixed(1)}–${h.end.toFixed(1)}с • ${h.reason} (${(h.score * 100).toFixed(0)}%)`}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

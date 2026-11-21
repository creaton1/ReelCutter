import { FilePlus, Clock } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useStore } from '../lib/store';

export const VideoPreview = () => {
  const { sourcePath, videoInfo, isLoadingVideo, highlights } = useStore();
  const [previewUrl, setPreviewUrl] = useState<string | undefined>(undefined);
  const prevUrlRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (prevUrlRef.current) {
      URL.revokeObjectURL(prevUrlRef.current);
      prevUrlRef.current = undefined;
    }
    if (!sourcePath) {
      setPreviewUrl(undefined);
      return;
    }
    let cancelled = false;
    (async () => {
      const bytes = await invoke<number[]>('read_file_bytes', { path: sourcePath });
      if (cancelled) return;
      const url = URL.createObjectURL(new Blob([new Uint8Array(bytes)], { type: 'video/mp4' }));
      prevUrlRef.current = url;
      setPreviewUrl(url);
    })();
    return () => {
      cancelled = true;
      if (prevUrlRef.current) {
        URL.revokeObjectURL(prevUrlRef.current);
        prevUrlRef.current = undefined;
      }
    };
  }, [sourcePath]);

  return (
    <div className="glass-panel flex flex-col gap-4 p-5 min-h-[420px] animate-fade-in">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-white">Исходное видео</h3>
        {isLoadingVideo ? (
          <span className="flex items-center gap-1.5 text-xs text-accent animate-pulse">
            <Clock size={12} /> Загрузка…
          </span>
        ) : null}
      </div>

      {sourcePath ? (
        <div className="relative w-full aspect-video bg-black rounded-lg overflow-hidden flex items-center justify-center shadow-[0_0_0_1px_rgba(255,255,255,0.05)]">
          <video
            src={previewUrl}
            className="w-full h-full object-cover"
            controls
            playsInline
          />
          {videoInfo && (
            <div className="absolute bottom-3 right-3 bg-black/70 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-white/10">
              <div className="text-xs font-mono text-accent">
                {videoInfo.duration.toFixed(1)}с
              </div>
              <div className="text-xs text-slate-300">
                {videoInfo.width}×{videoInfo.height} • {videoInfo.fps.toFixed(1)} FPS
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center h-64 text-center">
          <FilePlus size={48} className="mb-3 opacity-30 text-slate-500" />
          <p className="text-slate-500 text-sm">Видео не выбрано</p>
        </div>
      )}

      {highlights.length > 0 && (
        <div className="pt-2 border-t border-slate-700/40">
          <h4 className="text-xs font-semibold text-slate-400 mb-3 uppercase tracking-wider">
            Найденные моменты ({highlights.length})
          </h4>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {highlights.map((h, i) => (
              <span
                key={i}
                className="px-2.5 py-1 bg-surface/40 border border-accent/30 rounded-full text-accent text-xs whitespace-nowrap animate-slide-up"
                style={{ animationDelay: `${i * 50}ms` }}
              >
                {`${h.start.toFixed(1)}–${h.end.toFixed(1)}с • ${(h.score * 100).toFixed(0)}%`}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

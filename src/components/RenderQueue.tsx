import { Play, RefreshCw, FolderOpen, AlertCircle } from 'lucide-react';
import { useStore } from '../lib/store';

export const RenderQueue = () => {
  const { renderJobs, isRendering, renderProgress, renderCurrentProject, openOutputFolder } = useStore();

  return (
    <div className="flex flex-col gap-4 bg-surface-hover rounded-xl p-4 border border-slate-700/50">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-300">Очередь рендера</h3>
        <button
          onClick={renderCurrentProject}
          disabled={isRendering}
          className="flex items-center gap-2 px-3 py-1.5 bg-accent text-black font-medium rounded hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isRendering ? (
            <span className="flex items-center gap-1"><RefreshCw size={16} className="animate-spin" /> Рендеринг…</span>
          ) : (
            <span><Play size={16} /> Рендерить все клипы</span>
          )}
        </button>
      </div>

      {isRendering && (
        <>
          <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
            <div
              className="h-full bg-accent transition-all duration-300"
              style={{ width: `${renderProgress}%` }}
            />
          </div>
          <p className="text-xs text-slate-400 text-center">{renderProgress.toFixed(0)}%</p>
        </>
      )}

      <div className="space-y-2 max-h-[200px] overflow-y-auto pr-2">
        {renderJobs.length === 0 ? (
          <div className="text-center text-slate-500 text-sm py-4">Заданий нет</div>
        ) : (
          renderJobs.map((job) => (
            <div key={job.id} className="flex items-center justify-between px-2 py-2 bg-slate-800/50 rounded">
              <div className="flex-1">
                <div className="text-sm text-slate-200">{job.id.slice(0, 8)}…</div>
                <div className="text-xs text-slate-500">{job.status}</div>
              </div>
              <div className="flex items-center gap-2">
                {job.status === 'error' && (
                  <AlertCircle
                    size={16}
                    className="text-red-400"
                    aria-label={job.error ?? 'Ошибка'}
                  />
                )}
                {job.output_path && (
                  <button
                    onClick={() => openOutputFolder(job.output_path as string)}
                    className="p-1 hover:bg-slate-700 rounded text-slate-400"
                    title="Открыть папку"
                  >
                    <FolderOpen size={16} />
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

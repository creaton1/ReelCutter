import { Play, RefreshCw, FolderOpen, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useStore } from '../lib/store';

export const RenderQueue = () => {
  const { renderJobs, isRendering, renderProgress, renderCurrentProject, openOutputFolder } = useStore();

  const doneJobs = renderJobs.filter((j) => j.status === 'done');
  const errorJobs = renderJobs.filter((j) => j.status === 'error');

  return (
    <div className="glass-panel flex flex-col p-5 min-h-[420px] animate-slide-up">
      <div className="flex items-center justify-between mb-1">
        <h3 className="font-semibold text-white">Очередь рендера</h3>
        <button
          onClick={renderCurrentProject}
          disabled={isRendering}
          className="btn-primary flex items-center gap-2 px-3 py-1.5 text-xs"
        >
          {isRendering ? (
            <span className="flex items-center gap-1.5"><RefreshCw size={14} className="animate-spin" /> Рендеринг…</span>
          ) : (
            <span><Play size={14} /> Рендерить все клипы</span>
          )}
        </button>
      </div>

      {isRendering && (
        <div className="mt-4 space-y-2">
          <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden border border-slate-700/50">
            <div
              className="h-full bg-gradient-to-r from-accent to-accent-dim transition-all duration-500"
              style={{ width: `${renderProgress}%` }}
            />
          </div>
          <p className="text-xs font-mono text-center text-accent">
            {renderProgress.toFixed(0)}% завершено
          </p>
        </div>
      )}

      <div className="flex-1 space-y-2 overflow-y-auto pr-2">
        {renderJobs.length === 0 ? (
          <div className="empty-state flex-1">
            <RefreshCw size={32} className="mx-auto mb-3 opacity-20 text-slate-500" />
            <p className="text-muted text-sm">Заданий нет</p>
            <p className="text-xs text-slate-500">Сохраните клипы и нажмите «Рендерить»</p>
          </div>
        ) : (
          <>
            {doneJobs.length > 0 && (
              <div className="flex items-center gap-2 px-3 py-2 bg-success/10 border border-success/20 rounded-lg text-success text-xs font-medium mb-2">
                <CheckCircle2 size={14} />
                <span>{doneJobs.length} готово</span>
              </div>
            )}
            {errorJobs.length > 0 && (
              <div className="flex items-center gap-2 px-3 py-2 bg-danger/10 border border-danger/20 rounded-lg text-danger text-xs font-medium mb-2">
                <AlertCircle size={14} />
                <span>{errorJobs.length} с ошибкой</span>
              </div>
            )}
            {renderJobs.map((job) => (
              <div key={job.id} className="flex items-center justify-between px-3 py-2.5 bg-slate-800/40 rounded-lg border border-slate-700/40 transition-all">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="text-xs font-mono text-slate-300 truncate">
                      {job.id.slice(0, 8)}…
                    </div>
                    <span
                      className={`ml-auto px-2 py-0.5 rounded-full text-xs font-medium border ${job.status === 'done' ? 'border-success/30 bg-success/10 text-success' : job.status === 'error' ? 'border-danger/30 bg-danger/10 text-danger' : 'border-accent/30 bg-accent/10 text-accent'}`}
                    >
                      {job.status === 'done' ? 'Готово' : job.status === 'error' ? 'Ошибка' : 'В очереди'}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 mt-1">
                    {job.error ?? ''}
                  </div>
                </div>
                {job.status === 'done' && job.output_path && (
                  <button
                    onClick={() => openOutputFolder(job.output_path!)}
                    className="p-1.5 text-muted hover:text-accent hover:bg-accent/10 rounded transition-colors"
                    title="Открыть папку"
                  >
                    <FolderOpen size={14} />
                  </button>
                )}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
};

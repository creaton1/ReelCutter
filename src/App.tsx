import { useEffect } from 'react';
import { useStore } from './lib/store';
import { VideoPreview } from './components/VideoPreview';
import { Timeline } from './components/Timeline';
import { SettingsPanel } from './components/SettingsPanel';
import { RenderQueue } from './components/RenderQueue';
import { ImportButton } from './components/ImportButton';
import { Monitor, Save } from 'lucide-react';

export default function App() {
  const { sourcePath, init } = useStore();

  useEffect(() => {
    // Инициализируем БД в директории приложения Tauri.
    // Для демо используем относительный путь; в продакшене — tauri path resolver.
    init('./reelcutter.db');
  }, [init]);

  return (
    <div className="min-h-screen bg-surface text-slate-200 p-4 md:p-6">
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div className="flex items-center gap-2">
          <Monitor size={28} className="text-accent" />
          <span className="text-xl font-bold tracking-tight">ReelCutter</span>
        </div>
        <div className="flex items-center gap-3">
          <ImportButton label="Импортировать видео" />
          {sourcePath && (
            <button className="px-4 py-2 bg-surface hover:bg-surface-hover border border-slate-600 rounded-lg text-sm transition-colors">
              <Save size={18} /> Сохранить проект
            </button>
          )}
        </div>
      </header>

      {!sourcePath ? (
        <div className="flex flex-col items-center justify-center h-[500px] text-center rounded-2xl bg-surface-hover border-2 border-dashed border-slate-700/50">
          <Monitor size={64} className="mb-4 text-slate-600" />
          <h2 className="text-lg font-semibold text-slate-300 mb-2">Резак вертикальных клипов</h2>
          <p className="text-slate-500 max-w-sm mb-6">
            Загрузите длинное видео — приложение найдёт яркие моменты, нарежет их в 9:16 с блюром
            по бокам, добавит субтитры и экспортирует готовые Reels / Shorts / TikTok.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Левая колонка — превью и анализ */}
          <div className="lg:col-span-5 space-y-6">
            <VideoPreview />
            <button
              onClick={() => {
                // Анализ уже вызывается при загрузке; кнопка для повторного анализа
              }}
              className="w-full py-2 bg-accent/10 hover:bg-accent/20 border border-accent/30 text-accent text-sm rounded transition-colors"
            >
              Повторный анализ моментов
            </button>
          </div>

          {/* Правая колонка — таймлайн, настройки, очередь */}
          <div className="lg:col-span-7 space-y-6">
            <Timeline />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <SettingsPanel />
              <RenderQueue />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

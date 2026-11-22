import { useEffect, useState } from 'react';
import { useStore } from './lib/store';
import { VideoPreview } from './components/VideoPreview';
import { SubtitlesPanel } from './components/SubtitlesPanel';
import { Timeline } from './components/Timeline';
import { SettingsPanel } from './components/SettingsPanel';
import { RenderQueue } from './components/RenderQueue';
import { Monitor, Save, Play, Wand2, Film } from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';

export default function App() {
  const { sourcePath, init, loadSource } = useStore();
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    init('./reelcutter.db');
  }, [init]);

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length) {
      // Вебвью не даёт абсолютный путь к файлу — открываем системный диалог
      const selected = await invoke<string | null>('select_video');
      if (selected) await loadSource(selected);
    }
  };

  const handleImportClick = async () => {
    const selected = await invoke<string | null>('select_video');
    if (selected) await loadSource(selected);
  };

  return (
    <div className="min-h-screen bg-surface text-slate-200 p-4 md:p-6">
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 animate-fade-in">
        <div className="glass-panel p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent to-accent-dim flex items-center justify-center shadow-[0_0_20px_rgba(56,189,248,0.4)]">
            <Monitor size={24} className="text-surface" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">ReelCutter</h1>
            <p className="text-xs text-muted">Вертикальные клипы из длинного видео</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleImportClick}
            className="btn-secondary flex items-center gap-2"
          >
            <Film size={18} />
            <span className="hidden sm:inline">Импортировать видео</span>
          </button>
          {sourcePath && (
            <button
              className="btn-primary flex items-center gap-2"
            >
              <Save size={18} /> Сохранить проект
            </button>
          )}
        </div>
      </header>

      {!sourcePath ? (
        <div
          className="glass-panel flex flex-col items-center justify-center min-h-[600px] text-center"
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {isDragging ? (
            <div className="flex flex-col items-center gap-4 animate-pulse-slow">
              <Wand2 size={48} className="text-accent animate-bounce" />
              <span className="text-accent font-medium">Отпустите файл здесь</span>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-4">
              <Monitor size={64} className="text-slate-600" />
              <h2 className="text-lg font-semibold text-white mb-2">Резак вертикальных клипов</h2>
              <p className="text-muted max-w-sm mb-6">
                Загрузите длинное видео — приложение найдёт яркие моменты, нарежет их в 9:16 с блюром
                по бокам, добавит субтитры и экспортирует готовые Reels / Shorts / TikTok.
              </p>
              <button
                onClick={handleImportClick}
                className="btn-primary flex items-center gap-2"
              >
                <Play size={18} /> Выбрать видео
              </button>
              <p className="text-xs text-slate-500">
                Поддерживаются MP4, MOV, MKV, AVI — или перетащите файл прямо сюда
              </p>
            </div>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Левая колонка — превью, анализ и субтитры */}
          <div className="lg:col-span-5 space-y-6">
            <VideoPreview />
            <SubtitlesPanel />
            <button
              onClick={() => {
                // Анализ уже вызывается при загрузке; кнопка для повторного анализа
              }}
              className="btn-accent w-full flex items-center justify-center gap-2"
            >
              <Wand2 size={16} /> Повторный анализ моментов
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

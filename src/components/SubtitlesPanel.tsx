import React from 'react';
import { Subtitles, Play, RefreshCw } from 'lucide-react';
import { useStore } from '../lib/store';

export const SubtitlesPanel = () => {
  const {
    sourcePath,
    subtitleSegments,
    subtitleStatus,
    subtitleError,
    translationStatus,
    translationError,
    settings,
    generateSubtitles: genSubtitles,
    translateSubtitles: transSubtitles,
  } = useStore();

  const [whisperModelPath, setWhisperModelPath] = React.useState(
    'models/whisper/base.bin'
  );

  const handleGenerate = async () => {
    if (!sourcePath) return;
    await genSubtitles({
      video_path: sourcePath,
      model_path: whisperModelPath,
      language: settings.subtitle_language,
      translate_to_en: false,
    });
  };

  const handleTranslate = async () => {
    if (subtitleSegments.length === 0) return;
    await transSubtitles({
      segments: subtitleSegments,
      api_url: settings.translation_api_url,
      api_key: settings.translation_api_key ?? undefined,
      source_lang: settings.subtitle_language,
      target_lang: settings.translation_target_lang,
    });
  };

  return (
    <div className="glass-panel flex flex-col p-5 min-h-[420px] animate-fade-in">
      <div className="flex items-center gap-3 mb-1">
        <Subtitles size={20} className="text-accent" />
        <h3 className="font-semibold text-white">Субтитры и перевод</h3>
      </div>

      <div className="space-y-4">
        {/* Путь к модели Whisper */}
        <div className="space-y-2">
          <label className="label-text">Модель Whisper (.bin)</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={whisperModelPath}
              onChange={(e) => setWhisperModelPath(e.target.value)}
              className="input-field flex-1"
              placeholder="models/whisper/base.bin"
            />
            <button
              onClick={handleGenerate}
              disabled={subtitleStatus === 'generating' || !sourcePath}
              className="btn-accent px-4 py-2 text-xs"
            >
              {subtitleStatus === 'generating' ? 'Генерация…' : 'Генерировать'}
            </button>
          </div>
          {subtitleError && (
            <p className="text-xs text-red-400">{subtitleError}</p>
          )}
        </div>

        {/* Статус генерации */}
        {subtitleStatus === 'done' && (
          <div className="flex items-center gap-2 text-xs text-green-400">
            <Play size={12} />
            <span>{subtitleSegments.length} сегментов субтитров готово</span>
          </div>
        )}
        {translationStatus === 'translating' && (
          <div className="flex items-center gap-2 text-xs text-accent animate-pulse">
            <RefreshCw size={12} />
            <span>Перевод…</span>
          </div>
        )}
        {translationError && (
          <p className="text-xs text-red-400">{translationError}</p>
        )}

        {/* Перевод */}
        {subtitleSegments.length > 0 && (
          <div className="space-y-2 p-3 bg-surface/30 rounded-lg border border-slate-700/40">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-white">Перевод</span>
              <button
                onClick={handleTranslate}
                disabled={
                  translationStatus === 'translating' ||
                  !settings.translation_enabled
                }
                className="btn-accent px-3 py-1 text-xs"
              >
                Перевести на {settings.translation_target_lang.toUpperCase()}
              </button>
            </div>
            <p className="text-xs text-muted">
              API: <code className="text-accent">{settings.translation_api_url}</code>
            </p>
          </div>
        )}

        {/* Список сегментов */}
        <div className="flex-1 overflow-y-auto space-y-2 pr-2">
          {subtitleSegments.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Subtitles size={48} className="mx-auto mb-3 opacity-20 text-slate-500" />
              <p className="text-muted text-sm">Субтитры не сгенерированы</p>
              <p className="text-xs text-slate-500">
                Нажмите «Генерировать», чтобы распознать речь через Whisper
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              {subtitleSegments.map((seg, i) => (
                <div
                  key={i}
                  className="flex gap-2 p-2 bg-slate-800/40 rounded border border-slate-700/40 text-xs"
                >
                  <span className="w-16 font-mono text-accent">
                    {seg.start.toFixed(1)}s – {seg.end.toFixed(1)}s
                  </span>
                  <p className="flex-1 text-white leading-snug">{seg.text}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

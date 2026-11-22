import { Settings, Image, Music, Subtitles, Languages, Bot, Mic, Volume2 } from 'lucide-react';
import { useStore } from '../lib/store';

const SUBTITLE_LANGS = [
  { value: 'auto', label: 'Авто-определение' },
  { value: 'ru', label: 'Русский' },
  { value: 'en', label: 'English' },
];

const TRANSLATE_LANGS = [
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Español' },
  { value: 'fr', label: 'Français' },
  { value: 'de', label: 'Deutsch' },
  { value: 'zh', label: '中文' },
];

export const SettingsPanel = () => {
  const { settings, updateSettings } = useStore();

  const presets = [
    { value: 'Reels', label: 'Instagram Reels', max: '90с' },
    { value: 'Shorts', label: 'YouTube Shorts', max: '60с' },
    { value: 'TikTok', label: 'TikTok', max: '60с' },
    { value: 'VK Clips', label: 'VK Clips', max: '60с' },
  ];

  return (
    <div className="glass-panel flex flex-col p-5 min-h-[420px] animate-fade-in">
      <div className="flex items-center gap-3 mb-1">
        <Settings size={20} className="text-accent" />
        <h3 className="font-semibold text-white">Настройки рендера</h3>
      </div>

      <div className="space-y-5">
        {/* Платформа */}
        <div>
          <label className="label-text">Платформа</label>
          <select
            value={settings.preset}
            onChange={(e) => updateSettings({ preset: e.target.value })}
            className="input-field"
          >
            {presets.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label} ({p.max})
              </option>
            ))}
          </select>
          <p className="text-xs text-muted mt-1">
            Максимальная длительность клипа
          </p>
        </div>

        {/* Переключатели */}
        <div className="grid grid-cols-2 gap-4">
          <ToggleRow
            label="Субтитры"
            description="Авто-субтитры из речи (Whisper)"
            icon={<Subtitles size={16} />}
            checked={settings.subtitles}
            onChange={(e) => updateSettings({ subtitles: e.target.checked })}
          />
          <ToggleRow
            label="Перевод субтитров"
            description="Перевести на другой язык"
            icon={<Languages size={16} />}
            checked={settings.translation_enabled}
            onChange={(e) => updateSettings({ translation_enabled: e.target.checked })}
          />
          <ToggleRow
            label="Баннер / логотип"
            description="Водяной знак на видео"
            icon={<Image size={16} />}
            checked={settings.banner}
            onChange={(e) => updateSettings({ banner: e.target.checked })}
          />
          <ToggleRow
            label="Дублирование звука (TTS)"
            description="Озвучка переведённых субтитров вместо оригинала"
            icon={<Mic size={16} />}
            checked={settings.dubbing_enabled}
            onChange={(e) => updateSettings({ dubbing_enabled: e.target.checked })}
          />
        </div>

        {/* Язык субтитров */}
        <div>
          <label className="label-text">Язык субтитров</label>
          <select
            value={settings.subtitle_language}
            onChange={(e) => updateSettings({ subtitle_language: e.target.value })}
            className="input-field"
          >
            {SUBTITLE_LANGS.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
        </div>

        {/* Настройки перевода */}
        {settings.translation_enabled && (
          <div className="space-y-3 p-3 bg-accent/10 rounded-lg border border-accent/30">
            <div className="flex items-center gap-2 text-xs text-accent font-semibold uppercase tracking-wider mb-1">
              <Bot size={14} />
              <span>Перевод субтитров</span>
            </div>
            <div>
              <label className="label-text">На какой язык</label>
              <select
                value={settings.translation_target_lang}
                onChange={(e) =>
                  updateSettings({ translation_target_lang: e.target.value })
                }
                className="input-field"
              >
                {TRANSLATE_LANGS.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label-text">URL API перевода</label>
              <input
                type="text"
                value={settings.translation_api_url}
                onChange={(e) =>
                  updateSettings({ translation_api_url: e.target.value })
                }
                className="input-field"
                placeholder="https://libretranslate.de/translate"
              />
            </div>
            <div>
              <label className="label-text">API ключ (опционально)</label>
              <input
                type="text"
                value={settings.translation_api_key ?? ''}
                onChange={(e) =>
                  updateSettings({ translation_api_key: e.target.value || null })
                }
                className="input-field"
                placeholder="Bearer token"
              />
            </div>
          </div>
        )}

        {/* Настройки дублирования (TTS) */}
        {settings.dubbing_enabled && (
          <div className="space-y-3 p-3 bg-accent/10 rounded-lg border border-accent/30">
            <div className="flex items-center gap-2 text-xs text-accent font-semibold uppercase tracking-wider mb-1">
              <Volume2 size={14} />
              <span>Озвучка (TTS)</span>
            </div>
            <div>
              <label className="label-text">Голос</label>
              <input
                type="text"
                value={settings.tts_voice}
                onChange={(e) => updateSettings({ tts_voice: e.target.value })}
                className="input-field"
                placeholder="Rachel"
              />
            </div>
            <div>
              <label className="label-text">Модель TTS</label>
              <input
                type="text"
                value={settings.tts_model}
                onChange={(e) => updateSettings({ tts_model: e.target.value })}
                className="input-field"
                placeholder="eleven_multilingual_v2"
              />
            </div>
            <div>
              <label className="label-text">URL TTS API</label>
              <input
                type="text"
                value={settings.tts_api_url}
                onChange={(e) => updateSettings({ tts_api_url: e.target.value })}
                className="input-field"
                placeholder="https://api.elevenlabs.io/v1/text-to-speech/VOICE_ID"
              />
            </div>
            <div>
              <label className="label-text">API ключ TTS (опционально)</label>
              <input
                type="text"
                value={settings.tts_api_key ?? ''}
                onChange={(e) => updateSettings({ tts_api_key: e.target.value || null })}
                className="input-field"
                placeholder="Bearer token"
              />
            </div>
          </div>
        )}

        {/* Настройки субтитров */}
        <div className="space-y-3">
          <div>
            <label className="label-text">Размер шрифта субтитров</label>
            <div className="flex items-center gap-3">
              <input
                type="number"
                value={settings.subtitle_size}
                onChange={(e) => updateSettings({ subtitle_size: parseInt(e.target.value) || 24 })}
                className="input-field w-24"
              />
              <span className="text-xs text-muted">px</span>
            </div>
          </div>
          <div>
            <label className="label-text">Громкость фоновой музыки</label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={settings.music_volume}
                onChange={(e) => updateSettings({ music_volume: parseFloat(e.target.value) })}
                className="w-full accent-accent h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer"
              />
              <span className="text-xs font-mono text-muted">
                {(settings.music_volume * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        </div>

        <div className="pt-3 border-t border-slate-700/40 flex items-center gap-2 text-xs text-slate-500">
          <Music size={14} className="opacity-50" />
          <span>Баннер и музыка выбираются через системное окно файлов.</span>
        </div>
      </div>
    </div>
  );
};

function ToggleRow({
  label,
  description,
  icon,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  icon: JSX.Element;
  checked: boolean;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <div className="flex items-center gap-3 p-3 bg-surface/30 rounded-lg border border-slate-700/40 hover:border-slate-600/60 transition-colors cursor-pointer">
      {icon}
      <div className="flex-1">
        <div className="flex justify-between items-baseline">
          <span className="text-sm text-white font-medium">{label}</span>
        </div>
        <p className="text-xs text-muted">{description}</p>
      </div>
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="rounded bg-slate-800 border-slate-600 text-accent focus:ring-accent"
      />
    </div>
  );
}

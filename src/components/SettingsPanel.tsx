import { Settings, Image, Music, Subtitles } from 'lucide-react';
import { useStore } from '../lib/store';

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
            description="Авто-субтитры на клипах"
            icon={<Subtitles size={16} />}
            checked={settings.subtitles}
            onChange={(e) => updateSettings({ subtitles: e.target.checked })}
          />
          <ToggleRow
            label="Баннер / логотип"
            description="Водяной знак на видео"
            icon={<Image size={16} />}
            checked={settings.banner}
            onChange={(e) => updateSettings({ banner: e.target.checked })}
          />
        </div>

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

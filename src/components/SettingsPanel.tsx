import { Settings, Image } from 'lucide-react';
import { useStore } from '../lib/store';

export const SettingsPanel = () => {
  const { settings, updateSettings } = useStore();

  const presets = ['Reels', 'Shorts', 'TikTok', 'VK Clips'] as const;

  return (
    <div className="flex flex-col gap-4 bg-surface-hover rounded-xl p-4 border border-slate-700/50">
      <div className="flex items-center gap-2">
        <Settings size={20} className="text-accent" />
        <h3 className="font-semibold text-slate-300">Настройки рендера</h3>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Платформа</label>
          <select
            value={settings.preset}
            onChange={(e) => updateSettings({ preset: e.target.value })}
            className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-sm text-slate-200 focus:ring-2 focus:ring-accent outline-none"
          >
            {presets.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center gap-2">
            <input
              id="subtitles"
              type="checkbox"
              checked={settings.subtitles}
              onChange={(e) => updateSettings({ subtitles: e.target.checked })}
              className="rounded bg-slate-800 border-slate-600 text-accent focus:ring-accent"
            />
            <label htmlFor="subtitles" className="text-sm text-slate-200">
              Субтитры
            </label>
          </div>
          <div className="flex items-center gap-2">
            <input
              id="banner"
              type="checkbox"
              checked={settings.banner}
              onChange={(e) => updateSettings({ banner: e.target.checked })}
              className="rounded bg-slate-800 border-slate-600 text-accent focus:ring-accent"
            />
            <label htmlFor="banner" className="text-sm text-slate-200">
              Баннер / логотип
            </label>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Размер шрифта</label>
            <input
              type="number"
              value={settings.subtitle_size}
              onChange={(e) => updateSettings({ subtitle_size: parseInt(e.target.value) || 24 })}
              className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-slate-200 focus:ring-2 focus:ring-accent outline-none"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Громкость музыки</label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={settings.music_volume}
              onChange={(e) => updateSettings({ music_volume: parseFloat(e.target.value) })}
              className="w-full accent-accent"
            />
          </div>
        </div>

        <div className="pt-2 border-t border-slate-700/50 flex items-center gap-2 text-xs text-slate-400">
          <Image size={14} />
          <span>Баннер и музыка подключаются через системный выбор файлов в следующей итерации.</span>
        </div>
      </div>
    </div>
  );
};

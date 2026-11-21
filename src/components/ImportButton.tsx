import { Plus } from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';
import { useStore } from '../lib/store';

interface Props {
  label?: string;
}

export const ImportButton = ({ label = 'Импортировать видео' }: Props) => {
  const loadSource = useStore((s) => s.loadSource);

  const handleImport = async () => {
    // select_video открывает системный диалог выбора файла и возвращает абсолютный путь
    const selected = await invoke<string | null>('select_video');
    if (selected) {
      await loadSource(selected);
    }
  };

  return (
    <button
      onClick={handleImport}
      className="flex items-center gap-2 px-4 py-2 bg-surface hover:bg-surface-hover border border-slate-600 rounded-lg text-sm transition-all active:scale-95"
    >
      <Plus size={18} />
      {label}
    </button>
  );
};

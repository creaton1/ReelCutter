import { useStore } from '../lib/store';

export const ImportButton = () => {
  const loadSource = useStore((s) => s.loadSource);

  return (
    <input
      type="file"
      accept="video/mp4,video/mov,video/mkv,video/avi"
      className="hidden"
      onChange={(e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        loadSource(file.name);
      }}
    />
  );
};

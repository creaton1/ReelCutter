import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useStore } from './store';
import type { RenderSettings } from '../types';

// --- Мокаем таури-команды, чтобы тесты шли без реального IPC ---
const mInvoke = vi.hoisted(() => ({
  initApp: vi.fn(() => Promise.resolve()),
  probeVideo: vi.fn(() => Promise.resolve()),
  detectHighlights: vi.fn(() => Promise.resolve([])),
  generateSubtitles: vi.fn(() => Promise.resolve({ segments: [], output_path: '' })),
  translateSubtitles: vi.fn(() => Promise.resolve([])),
  createProject: vi.fn(() =>
    Promise.resolve({ id: 'p-1', name: 'Test', source_path: 's.mp4', preset: 'Shorts', created_at: '', updated_at: '' })
  ),
  listProjects: vi.fn(() => Promise.resolve([])),
  saveClips: vi.fn(() => Promise.resolve()),
  listClips: vi.fn(() => Promise.resolve([])),
  renderClips: vi.fn(() => Promise.resolve('job-1')),
  listRenderJobs: vi.fn(() => Promise.resolve([])),
}));

vi.mock('./tauri', () => ({
  probeVideo: mInvoke.probeVideo,
  detectHighlights: mInvoke.detectHighlights,
  generateSubtitles: mInvoke.generateSubtitles,
  translateSubtitles: mInvoke.translateSubtitles,
  createProject: mInvoke.createProject,
  listProjects: mInvoke.listProjects,
  saveClips: mInvoke.saveClips,
  listClips: mInvoke.listClips,
  renderClips: mInvoke.renderClips,
  listRenderJobs: mInvoke.listRenderJobs,
  initApp: mInvoke.initApp,
}));

const initialSettings: RenderSettings = {
  preset: 'Shorts',
  subtitles: true,
  subtitle_font: 'Arial',
  subtitle_size: 24,
  subtitle_color: '#FFFFFF',
  subtitle_language: 'auto',
  translation_enabled: false,
  translation_target_lang: 'en',
  translation_api_url: 'https://libretranslate.de/translate',
  translation_api_key: null,
  dubbing_enabled: false,
  tts_api_url: 'https://api.elevenlabs.io/v1/text-to-speech/',
  tts_api_key: null,
  tts_voice: 'Rachel',
  tts_model: 'eleven_multilingual_v2',
  banner: false,
  banner_path: null,
  banner_opacity: 0.5,
  music: false,
  music_path: null,
  music_volume: 0.3,
};

function resetStore() {
  useStore.setState({
    sourcePath: null,
    videoInfo: null,
    isLoadingVideo: false,
    highlights: [],
    clips: [],
    settings: { ...initialSettings },
    projects: [],
    renderJobs: [],
    activeProjectId: null,
    isRendering: false,
    renderProgress: 0,
    subtitleSegments: [],
    subtitleStatus: 'idle',
    subtitleError: null,
    translationStatus: 'idle',
    translationError: null,
  });
}

beforeEach(() => {
  resetStore();
  vi.clearAllMocks();
});

describe('useStore', () => {
  it('setClips replaces the clips list', () => {
    const clips = [
      { id: 'c1', start: 0, end: 5, score: 0.9, reason: 'пик', output_path: null },
      { id: 'c2', start: 10, end: 20, score: 0.5, reason: 'сцена', output_path: null },
    ];
    useStore.getState().setClips(clips);
    expect(useStore.getState().clips).toHaveLength(2);
    expect(useStore.getState().clips[0].id).toBe('c1');
  });

  it('updateSettings merges patch immutably (old fields preserved)', () => {
    useStore.getState().updateSettings({ preset: 'Reels', subtitle_size: 48 });
    const s = useStore.getState().settings;
    expect(s.preset).toBe('Reels');
    expect(s.subtitle_size).toBe(48);
    // поля, не затронутые патчем, остались прежними
    expect(s.subtitle_font).toBe('Arial');
    expect(s.music_volume).toBe(0.3);
    // свежая ссылка — исходный объект не мутирован
    expect(s).not.toBe(initialSettings);
  });

  it('createNewProject creates project and sets active id', async () => {
    useStore.setState({ sourcePath: 'video.mp4' });
    const project = await useStore.getState().createNewProject('Моя работа', 'Reels');
    expect(mInvoke.createProject).toHaveBeenCalledWith('Моя работа', 'video.mp4', 'Reels');
    expect(project.id).toBe('p-1');
    expect(useStore.getState().activeProjectId).toBe('p-1');
    expect(useStore.getState().projects).toHaveLength(1);
  });

  it('saveCurrentClips saves clips under active project', async () => {
    useStore.setState({ sourcePath: 'video.mp4' });
    useStore.getState().setClips([
      { id: 'c1', start: 0, end: 5, score: 0.9, reason: 'пик', output_path: null },
    ]);
    await useStore.getState().createNewProject('Проект', 'Shorts');
    await useStore.getState().saveCurrentClips();
    expect(mInvoke.saveClips).toHaveBeenCalled();
    expect(mInvoke.saveClips).toHaveBeenCalledWith('p-1', expect.arrayContaining([
      expect.objectContaining({ id: 'c1', start: 0, end: 5 }),
    ]));
  });

  it('renderCurrentProject rejects when no source video', async () => {
    await expect(useStore.getState().renderCurrentProject()).rejects.toThrow('No project or source');
    expect(mInvoke.renderClips).not.toHaveBeenCalled();
  });
});

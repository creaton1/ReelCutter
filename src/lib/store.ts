import { create } from 'zustand';
import {
  ClipSegment,
  RenderSettings,
  Project,
  RenderJob,
  Highlight,
  VideoInfo,
} from '../types';
import {
  probeVideo,
  detectHighlights,
  generateSubtitles,
  translateSubtitles,
  ttsSynthesize,
  createProject,
  listProjects,
  saveClips,
  listClips,
  renderClips,
  listRenderJobs,
  initApp,
} from './tauri';

export interface AppState {
  sourcePath: string | null;
  videoInfo: VideoInfo | null;
  isLoadingVideo: boolean;
  highlights: Highlight[];
  clips: ClipSegment[];
  settings: RenderSettings;
  projects: Project[];
  renderJobs: RenderJob[];
  activeProjectId: string | null;
  isRendering: boolean;
  renderProgress: number;

  // Субтитры
  subtitleSegments: Array<{ start: number; end: number; text: string }>;
  subtitleStatus: 'idle' | 'generating' | 'done' | 'error';
  subtitleError: string | null;

  // Перевод
  translationStatus: 'idle' | 'translating' | 'done' | 'error';
  translationError: string | null;

  // Дублирование (TTS)
  ttsSegments: Array<{ start: number; end: number; text: string; audio_path: string }>;
  ttsStatus: 'idle' | 'synthesizing' | 'done' | 'error';
  ttsError: string | null;
  dubAudioPath: string | null;

  openOutputFolder: (path: string) => Promise<void>;

  loadSource: (path: string) => Promise<void>;
  analyzeHighlights: () => Promise<void>;
  setClips: (clips: ClipSegment[]) => void;
  generateSubtitles: (req: {
    video_path: string;
    model_path: string;
    language: string;
    translate_to_en: boolean;
  }) => Promise<void>;
  translateSubtitles: (req: {
    segments: Array<{ start: number; end: number; text: string }>;
    api_url: string;
    api_key?: string | null;
    source_lang: string;
    target_lang: string;
  }) => Promise<void>;
  createNewProject: (name: string, preset: string) => Promise<Project>;
  loadProjects: () => Promise<void>;
  selectProject: (id: string) => Promise<void>;
  saveCurrentClips: () => Promise<void>;
  renderCurrentProject: () => Promise<string>;
  loadRenderJobs: () => Promise<void>;
  updateSettings: (patch: Partial<RenderSettings>) => void;
  init: (dbPath: string) => Promise<void>;
}

export const useStore = create<AppState>((set, get) => ({
  sourcePath: null,
  videoInfo: null,
  isLoadingVideo: false,
  highlights: [],
  clips: [],
  settings: {
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
  },
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
  ttsSegments: [],
  ttsStatus: 'idle',
  ttsError: null,
  dubAudioPath: null,

  init: async (dbPath: string) => {
    await initApp(dbPath);
    await get().loadProjects();
  },

  loadSource: async (path: string) => {
    set({ isLoadingVideo: true, sourcePath: path });
    try {
      const info = await probeVideo(path);
      set({ videoInfo: info, isLoadingVideo: false });
    } catch (e) {
      console.error(e);
      set({ isLoadingVideo: false });
    }
  },

  analyzeHighlights: async () => {
    const { sourcePath, settings } = get();
    if (!sourcePath) return;
    try {
      const highlights = await detectHighlights(sourcePath, settings.preset);
      set({ highlights });
    } catch (e) {
      console.error(e);
    }
  },

  generateSubtitles: async (req) => {
    set({ subtitleStatus: 'generating', subtitleError: null });
    try {
      const res = await generateSubtitles(req);
      set({
        subtitleSegments: res.segments,
        subtitleStatus: 'done',
      });
    } catch (e: any) {
      set({ subtitleStatus: 'error', subtitleError: e?.message || String(e) });
    }
  },

  translateSubtitles: async (req) => {
    set({ translationStatus: 'translating', translationError: null });
    try {
      const translated = await translateSubtitles(req);
      set({
        subtitleSegments: translated,
        translationStatus: 'done',
      });
    } catch (e: any) {
      set({ translationStatus: 'error', translationError: e?.message || String(e) });
    }
  },

  synthesizeTts: async (req: {
    segments: Array<{ start: number; end: number; text: string }>;
    api_url: string;
    api_key?: string | null;
    voice: string;
    model: string;
    output_dir: string;
  }) => {
    set({ ttsStatus: 'synthesizing', ttsError: null });
    try {
      const res = await ttsSynthesize({
        segments: req.segments,
        api_url: req.api_url,
        api_key: req.api_key ?? undefined,
        voice: req.voice,
        model: req.model,
        output_dir: req.output_dir,
      });
      set({
        dubAudioPath: res.combined_audio,
        ttsStatus: 'done',
      });
    } catch (e: any) {
      set({ ttsStatus: 'error', ttsError: e?.message || String(e) });
    }
  },

  setClips: (clips: ClipSegment[]) => set({ clips }),

  createNewProject: async (name: string, preset: string) => {
    const { sourcePath } = get();
    if (!sourcePath) throw new Error('No source video');
    const project = await createProject(name, sourcePath, preset);
    set((s) => ({
      projects: [project, ...s.projects],
      activeProjectId: project.id,
    }));
    return project;
  },

  loadProjects: async () => {
    const projects = await listProjects();
    set({ projects });
  },

  selectProject: async (id: string) => {
    set({ activeProjectId: id, clips: [], renderJobs: [] });
    const clips = await listClips(id);
    set({ clips });
    const jobs = await listRenderJobs(id);
    set({ renderJobs: jobs });
  },

  saveCurrentClips: async () => {
    const { activeProjectId, clips } = get();
    if (!activeProjectId) throw new Error('No project');
    await saveClips(activeProjectId, clips);
  },

  renderCurrentProject: async () => {
    const { activeProjectId, sourcePath, clips, settings, subtitleSegments, dubAudioPath } = get();
    if (!activeProjectId || !sourcePath) throw new Error('No project or source');
    set({ isRendering: true, renderProgress: 0 });
    try {
      const jobId = await renderClips(
        activeProjectId,
        sourcePath,
        clips,
        settings,
        settings.subtitles ? subtitleSegments : undefined,
        settings.dubbing_enabled ? dubAudioPath : null
      );
      set({ isRendering: false, renderProgress: 100 });
      await get().loadRenderJobs();
      return jobId;
    } catch (e) {
      set({ isRendering: false });
      throw e;
    }
  },

  loadRenderJobs: async () => {
    const { activeProjectId } = get();
    if (!activeProjectId) return;
    const jobs = await listRenderJobs(activeProjectId);
    set({ renderJobs: jobs });
  },

  updateSettings: (patch: Partial<RenderSettings>) =>
    set((s) => ({ settings: { ...s.settings, ...patch } })),

  openOutputFolder: async (path: string) => {
    console.log('Открыть папку:', path);
  },
}));

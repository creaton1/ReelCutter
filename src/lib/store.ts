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

  openOutputFolder: (path: string) => Promise<void>;

  loadSource: (path: string) => Promise<void>;
  analyzeHighlights: () => Promise<void>;
  setClips: (clips: ClipSegment[]) => void;
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
    const { activeProjectId, sourcePath, clips, settings } = get();
    if (!activeProjectId || !sourcePath) throw new Error('No project or source');
    set({ isRendering: true, renderProgress: 0 });
    try {
      const jobId = await renderClips(activeProjectId, sourcePath, clips, settings);
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

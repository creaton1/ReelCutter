import { invoke } from '@tauri-apps/api/core';
import type {
  VideoInfo,
  Project,
  ClipSegment,
  RenderSettings,
  RenderJob,
  Highlight,
} from '../types';

export const probeVideo = (path: string) => invoke<VideoInfo>('probe_video', { path });
export const detectHighlights = (path: string, preset: string) =>
  invoke<Highlight[]>('detect_highlights', { path, preset });
export const generateSubtitles = (req: {
  video_path: string;
  model_path: string;
  language: string;
  translate_to_en: boolean;
}) => invoke<{ segments: any[]; output_path: string }>('generate_subtitles_cmd', req);
export const translateSubtitles = (req: {
  segments: any[];
  api_url: string;
  api_key?: string | null;
  source_lang: string;
  target_lang: string;
}) => invoke<any[]>('translate_subtitles_cmd', req);
export const ttsSynthesize = (req: {
  segments: any[];
  api_url: string;
  api_key?: string | null;
  voice: string;
  model: string;
  output_dir: string;
}) => invoke<{ combined_audio: string; segments_count: number }>('tts_synthesize_cmd', req);
export const createProject = (name: string, sourcePath: string, preset: string) =>
  invoke<Project>('create_project_cmd', { name, source_path: sourcePath, preset });
export const listProjects = () => invoke<Project[]>('list_projects_cmd');
export const saveClips = (projectId: string, clips: ClipSegment[]) =>
  invoke('save_clips_cmd', { project_id: projectId, clips });
export const listClips = (projectId: string) =>
  invoke<ClipSegment[]>('list_clips_cmd', { project_id: projectId });
export const renderClips = (
  projectId: string,
  source: string,
  clips: ClipSegment[],
  settings: RenderSettings,
  subtitleSegments?: any[],
  dubAudioPath?: string | null
) => invoke<string>('render_clips_cmd', { project_id: projectId, source, clips, settings, subtitle_segments: subtitleSegments, dub_audio_path: dubAudioPath });
export const listRenderJobs = (projectId: string) =>
  invoke<RenderJob[]>('list_render_jobs_cmd', { project_id: projectId });
export const initApp = (dbPath: string) => invoke('init_app', { db_path: dbPath });

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
  settings: RenderSettings
) => invoke<string>('render_clips_cmd', { project_id: projectId, source, clips, settings });
export const listRenderJobs = (projectId: string) =>
  invoke<RenderJob[]>('list_render_jobs_cmd', { project_id: projectId });
export const initApp = (dbPath: string) => invoke('init_app', { db_path: dbPath });

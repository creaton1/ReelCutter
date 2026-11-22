export interface PlatformPreset {
  name: string;
  max_duration: number;
  width: number;
  height: number;
}

export interface Highlight {
  start: number;
  end: number;
  score: number;
  reason: string;
}

export interface ClipSegment {
  id: string;
  start: number;
  end: number;
  score: number;
  reason: string;
  output_path?: string | null;
}

export interface RenderSettings {
  preset: string;
  subtitles: boolean;
  subtitle_font: string;
  subtitle_size: number;
  subtitle_color: string;
  subtitle_language: string;
  translation_enabled: boolean;
  translation_target_lang: string;
  translation_api_url: string;
  translation_api_key?: string | null;
  dubbing_enabled: boolean;
  tts_api_url: string;
  tts_api_key?: string | null;
  tts_voice: string;
  tts_model: string;
  banner: boolean;
  banner_path?: string | null;
  banner_opacity: number;
  music: boolean;
  music_path?: string | null;
  music_volume: number;
}

export interface VideoInfo {
  duration: number;
  width: number;
  height: number;
  fps: number;
  has_audio: boolean;
}

export interface Project {
  id: string;
  name: string;
  source_path: string;
  preset: string;
  created_at: string;
  updated_at: string;
}

export interface RenderJob {
  id: string;
  project_id: string;
  status: string;
  progress: number;
  output_path?: string | null;
  error?: string | null;
}

use crate::core::types::*;
use anyhow::Result;

pub fn analyze_video_file(path: &str) -> Result<(VideoInfo, Vec<Highlight>)> {
    let info = crate::core::probe_video(path)?;
    let preset = &crate::core::types::PRESETS[1]; // Shorts по умолчанию
    let highlights = crate::core::detect_highlights(path, preset.max_duration)?;
    Ok((info, highlights))
}

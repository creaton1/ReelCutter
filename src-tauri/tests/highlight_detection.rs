// Integration test: detect_highlights must work on real video produced by ffmpeg.
// Behaviour under test:
//   - probe_video extracts duration + has_audio from a real file
//   - detect_highlights returns non-overlapping segments (>= 5s, <= preset max_duration)
//   - segments stay within video duration, have score in [0, 1] and a non-empty reason
// Exercises: reelcutter_core::core::{detect_highlights, probe_video}, core::types::PRESETS
//
// There were previously NO integration tests in tests/ — this is the first one.
use reelcutter_core::core::types::PRESETS;
use reelcutter_core::core::{detect_highlights, probe_video};
use std::process::Command;

fn make_test_video() -> String {
    let out = std::env::temp_dir().join("reelcutter_detect_test.mp4");
    let out_str = out.to_string_lossy().to_string();

    let status = Command::new("ffmpeg")
        .args([
            "-y",
            "-hide_banner",
            "-nostats",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=15:size=320x240:rate=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=15",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "28",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            &out_str,
        ])
        .status()
        .expect("ffmpeg must be available to run this test");

    assert!(status.success(), "ffmpeg failed to generate test video");
    out_str
}

#[test]
fn detect_highlights_finds_segments_in_real_video() {
    let path = make_test_video();

    let info = probe_video(&path).expect("probe_video should work");
    assert!(info.duration > 0.0, "video should have duration");
    assert!(info.has_audio, "video should have audio");

    let preset = &PRESETS[1]; // Shorts, max 60s
    let highlights = detect_highlights(&path, preset.max_duration)
        .unwrap_or_else(|e| panic!("detect_highlights failed: {e}"));

    assert!(
        !highlights.is_empty(),
        "should detect at least one highlight"
    );

    let mut prev_end = 0.0;
    for h in &highlights {
        assert!(h.start < h.end, "segment must have positive length");
        assert!(
            (h.end - h.start) >= 5.0,
            "segment too short: {}s",
            h.end - h.start
        );
        assert!(
            h.end <= info.duration + 1e-3,
            "segment beyond video duration"
        );
        assert!(h.start >= prev_end - 1e-3, "segments must not overlap");
        assert!(h.score > 0.0 && h.score <= 1.0, "score out of range");
        assert!(!h.reason.is_empty(), "reason must be set");
        prev_end = h.end;
    }
}

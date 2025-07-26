import subprocess
from pathlib import Path
from typing import List, Tuple
import re

def extract_frames(
    video_path: Path, output_dir: Path, method: str = "scene", fps: float = 1.0, max_frames: int = 8
) -> List[Tuple[Path, float]]:
    """
    Extract frames from a video using ffmpeg.
    Args:
        video_path: Path to the input video file.
        output_dir: Directory to save extracted frames.
        method: 'scene' for scene change detection, 'fps' for fixed rate.
        fps: Frames per second if method is 'fps'.
    Returns:
        List of tuples: (frame_path, timestamp_seconds)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_pattern = str(output_dir / "frame_%05d.jpg")
    if method == "scene":
        # Extract frames on scene change (ffmpeg scene filter) with limit
        ffmpeg_cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vf",
            f"select='gt(scene,0.3)',showinfo",
            "-vsync",
            "vfr",
            "-vframes",
            str(max_frames),
            frame_pattern,
            "-hide_banner",
            "-loglevel",
            "info",
        ]
    else:
        # Extract at fixed fps with limit
        ffmpeg_cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vf",
            f"fps={fps}",
            "-vframes",
            str(max_frames),
            frame_pattern,
            "-hide_banner",
            "-loglevel",
            "info",
        ]
    # Run ffmpeg and capture output
    proc = subprocess.run(
        ffmpeg_cmd, capture_output=True, text=True, check=True
    )
    # Parse timestamps from ffmpeg showinfo output (if scene method)
    timestamps = []
    if method == "scene":
        showinfo_lines = [
            l for l in proc.stderr.split("\n") if "showinfo" in l and "pts_time" in l
        ]
        for line in showinfo_lines:
            m = re.search(r"pts_time:([0-9.]+)", line)
            if m:
                timestamps.append(float(m.group(1)))
    else:
        # For fps, calculate timestamps by frame index
        frame_files = sorted(output_dir.glob("frame_*.jpg"))
        timestamps = [i / fps for i in range(len(frame_files))]
    # Collect frame paths
    frame_files = sorted(output_dir.glob("frame_*.jpg"))
    print(f"[FrameExtractor] Extracted {len(frame_files)} frames to {output_dir}")
    for f in frame_files:
        print(f"[FrameExtractor] Frame: {f}")
    return list(zip(frame_files, timestamps)) 
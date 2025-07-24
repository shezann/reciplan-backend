import subprocess
import os
from pathlib import Path
import shutil
from contextlib import contextmanager

class VideoUnavailableError(Exception):
    pass

@contextmanager
def temp_job_dir(base_dir="/tmp/ingest", job_id=None):
    """
    Context manager to create and clean up a temp job directory.
    Usage:
        with temp_job_dir() as job_dir:
            ...
    """
    if job_id is None:
        job_id = os.urandom(8).hex()
    job_dir = Path(base_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield job_dir
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)

def download_video(url, output_dir="/tmp/ingest"):  # output_dir can be customized
    """
    Download a video from TikTok using yt-dlp.
    Returns the path to the downloaded video file.
    Raises VideoUnavailableError if the video is private or not found.
    """
    job_id = os.urandom(8).hex()
    job_dir = Path(output_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    output_path = job_dir / "video.mp4"
    cmd = [
        "yt-dlp",
        "-f", "mp4",
        "-o", str(output_path),
        url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if not output_path.exists():
            raise VideoUnavailableError("Video not downloaded (file missing)")
        return output_path
    except subprocess.CalledProcessError as e:
        if "This video is private" in e.stderr or "HTTP Error 404" in e.stderr:
            raise VideoUnavailableError("Video is private or not found")
        raise VideoUnavailableError(f"yt-dlp failed: {e.stderr}") 
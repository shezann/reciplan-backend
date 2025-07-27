import subprocess
import os
from pathlib import Path
import shutil
from contextlib import contextmanager
import json
import re

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

def download_video(url, output_dir="/tmp/ingest"):
    """
    Download a video from TikTok using yt-dlp.
    Returns a tuple: (video_path, title, thumbnail_url)
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
        "--write-info-json",
        "--write-description",
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if not output_path.exists():
            raise VideoUnavailableError("Video not downloaded (file missing)")
        
        # Extract title and thumbnail from metadata
        title = _extract_title_from_metadata(job_dir)
        thumbnail_url = _extract_thumbnail_from_metadata(job_dir)
        return output_path, title, thumbnail_url
        
    except subprocess.CalledProcessError as e:
        if "This video is private" in e.stderr or "HTTP Error 404" in e.stderr:
            raise VideoUnavailableError("Video is private or not found")
        raise VideoUnavailableError(f"yt-dlp failed: {e.stderr}")


def _extract_title_from_metadata(job_dir):
    """Extract and clean title from yt-dlp metadata"""
    # Find the metadata file (yt-dlp writes .info.json)
    info_json = None
    for file in job_dir.iterdir():
        if file.suffix == ".json" and file.stem.startswith("video"):
            info_json = file
            break
    
    if not info_json or not info_json.exists():
        return None
    
    try:
        with open(info_json, "r", encoding="utf-8") as f:
            meta = json.load(f)
            
        # Try to get the full title
        title = meta.get("title", "")
        description = meta.get("description", "")
        
        # If title is truncated (ends with ...), try to get full version from description
        if title and title.endswith("..."):
            title_start = title.replace("...", "").strip()
            if title_start and title_start in description:
                # Find where the title content appears in description
                start_idx = description.find(title_start)
                if start_idx != -1:
                    # Get the full text from where title starts
                    full_text = description[start_idx:].strip()
                    # Take up to the first line break
                    title = full_text.split('\n')[0] if full_text else title
        
        # Fallback to other fields if no title
        if not title:
            title = (
                meta.get("alt_title") or
                meta.get("description", "").split('\n')[0] or
                meta.get("uploader", "") + " recipe"
            )
        
        # Clean up the title
        if title:
            # Remove common TikTok suffixes and hashtags
            title = title.replace(" | TikTok", "").replace(" - TikTok", "")
            title = re.sub(r'#\w+', '', title).strip()
        
        return title
        
    except (json.JSONDecodeError, IOError):
        return None


def _extract_thumbnail_from_metadata(job_dir):
    """Extract thumbnail URL from yt-dlp metadata"""
    # Find the metadata file (yt-dlp writes .info.json)
    info_json = None
    for file in job_dir.iterdir():
        if file.suffix == ".json" and file.stem.startswith("video"):
            info_json = file
            break
    
    if not info_json or not info_json.exists():
        return None
    
    try:
        with open(info_json, "r", encoding="utf-8") as f:
            meta = json.load(f)
            
        # Try to get the best thumbnail URL
        # yt-dlp provides thumbnails in order of preference
        thumbnails = meta.get("thumbnails", [])
        if thumbnails:
            # Get the first thumbnail (usually the best quality)
            return thumbnails[0].get("url")
        
        # Fallback to thumbnail field if thumbnails array is not available
        return meta.get("thumbnail")
        
    except (json.JSONDecodeError, IOError):
        return None 
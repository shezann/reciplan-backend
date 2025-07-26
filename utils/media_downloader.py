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

def download_video(url, output_dir="/tmp/ingest"):  # output_dir can be customized
    """
    Download a video from TikTok using yt-dlp.
    Returns a tuple: (video_path, title)
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
        
        # Find the metadata file (yt-dlp writes .info.json)
        info_json = None
        for file in job_dir.iterdir():
            if file.suffix == ".json" and file.stem.startswith("video"):
                info_json = file
                break
        
        title = None
        if info_json and info_json.exists():
            with open(info_json, "r", encoding="utf-8") as f:
                meta = json.load(f)
                print(f"[DEBUG] Raw metadata title: {meta.get('title', 'No title')}")
                print(f"[DEBUG] Raw metadata alt_title: {meta.get('alt_title', 'No alt_title')}")
                print(f"[DEBUG] Raw metadata description: {meta.get('description', 'No description')[:200]}...")
                print(f"[DEBUG] Raw metadata uploader: {meta.get('uploader', 'No uploader')}")
                print(f"[DEBUG] Title ends with '...': {meta.get('title', '').endswith('...')}")
                
                # Try to get the full title by combining title and description
                title = meta.get("title", "")
                description = meta.get("description", "")
                
                # If title is truncated (ends with ...), try to get the full version from description
                if title and title.endswith("..."):
                    # Look for the title content in the description
                    title_start = title.replace("...", "").strip()
                    if title_start and title_start in description:
                        # Find where the title content appears in description and get the full text
                        start_idx = description.find(title_start)
                        if start_idx != -1:
                            # Get the full text from where title starts
                            full_text = description[start_idx:].strip()
                            # Take up to the first line break or reasonable length
                            lines = full_text.split('\n')
                            raw_title = lines[0] if lines else full_text
                        else:
                            raw_title = title
                    else:
                        raw_title = title
                else:
                    # Title is not truncated, use as is
                    raw_title = title
                
                # Fallback to other fields if no title
                if not raw_title:
                    raw_title = (
                        meta.get("alt_title") or  # Alternative title
                        meta.get("description", "").split('\n')[0] or  # First line of description
                        meta.get("uploader") + " recipe"  # Fallback to uploader name
                    )
                
                # Clean up the title
                if raw_title:
                    # Remove common TikTok suffixes
                    title = raw_title.replace(" | TikTok", "").replace(" - TikTok", "")
                    # Remove hashtags but keep emojis
                    title = re.sub(r'#\w+', '', title).strip()
                    # Keep the full title - don't remove prefixes
                    # TikTok creators often put full recipes in titles including prefixes
                    
                    # No length limit - keep the full title
                    # TikTok creators often put full recipes in titles
                    
                    print(f"[DEBUG] Cleaned metadata title: {title}")
                    print(f"[DEBUG] Final combined title: {raw_title}")
                else:
                    print(f"[DEBUG] No valid metadata title found")
        
        print(f"[DEBUG] Extracted title: {title}")
        print(f"[DEBUG] Returning tuple: ({output_path}, {title})")
        return output_path, title
        
    except subprocess.CalledProcessError as e:
        if "This video is private" in e.stderr or "HTTP Error 404" in e.stderr:
            raise VideoUnavailableError("Video is private or not found")
        raise VideoUnavailableError(f"yt-dlp failed: {e.stderr}") 
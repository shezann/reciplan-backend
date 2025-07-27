import subprocess
from pathlib import Path

class AudioExtractionError(Exception):
    pass

def extract_audio(video_path, output_dir=None):
    """
    Extract audio from video using ffmpeg, output as 16kHz mono WAV.
    Returns the path to the audio file.
    Raises AudioExtractionError on failure.
    """
    video_path = Path(video_path)
    if output_dir is None:
        output_dir = video_path.parent
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / "audio.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-ac", "1",
        "-ar", "16000",
        str(audio_path)
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        if not audio_path.exists():
            raise AudioExtractionError("Audio not extracted (file missing)")
        return audio_path
    except subprocess.CalledProcessError as e:
        raise AudioExtractionError(f"ffmpeg failed: {e.stderr}") 
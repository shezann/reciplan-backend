import pytest
from utils.audio_extractor import extract_audio, AudioExtractionError
from unittest.mock import patch
from pathlib import Path
import subprocess

def test_extract_audio_success(tmp_path):
    video_path = tmp_path / "video.mp4"
    video_path.touch()
    audio_path = tmp_path / "audio.wav"
    with patch("subprocess.run") as mock_run, \
         patch("pathlib.Path.exists", side_effect=lambda: True if str(audio_path) in str(audio_path) else False):
        result = extract_audio(video_path, output_dir=tmp_path)
        assert isinstance(result, Path)
        assert result.name == "audio.wav"

def test_extract_audio_missing_file(tmp_path):
    video_path = tmp_path / "video.mp4"
    video_path.touch()
    with patch("subprocess.run") as mock_run, \
         patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(AudioExtractionError) as exc:
            extract_audio(video_path, output_dir=tmp_path)
        assert "Audio not extracted" in str(exc.value)

def test_extract_audio_ffmpeg_error(tmp_path):
    video_path = tmp_path / "video.mp4"
    video_path.touch()
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg", stderr="ffmpeg error")), \
         patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(AudioExtractionError) as exc:
            extract_audio(video_path, output_dir=tmp_path)
        assert "ffmpeg failed" in str(exc.value) 
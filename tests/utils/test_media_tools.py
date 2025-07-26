import pytest
from utils.media_downloader import download_video, VideoUnavailableError, temp_job_dir
from utils.audio_extractor import extract_audio, AudioExtractionError
from unittest.mock import patch
from pathlib import Path
import subprocess
import shutil
import os

def test_download_video_success(tmp_path):
    url = "https://www.tiktok.com/@user/video/1234567890"
    output_dir = tmp_path
    fake_video_path = output_dir / "fakejob" / "video.mp4"
    fake_video_path.parent.mkdir(parents=True, exist_ok=True)
    fake_video_path.touch()
    with patch("os.urandom", return_value=b"fakejobid"), \
         patch("subprocess.run") as mock_run, \
         patch("pathlib.Path.exists", return_value=True):
        result = download_video(url, output_dir=output_dir)
        assert isinstance(result, tuple)
        assert isinstance(result[0], Path)
        assert result[0].name == "video.mp4"

def test_download_video_private(tmp_path):
    url = "https://www.tiktok.com/@user/video/private"
    with patch("os.urandom", return_value=b"fakejobid"), \
         patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "yt-dlp", stderr="This video is private")), \
         patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(VideoUnavailableError) as exc:
            download_video(url, output_dir=tmp_path)
        assert "private" in str(exc.value)

def test_download_video_404(tmp_path):
    url = "https://www.tiktok.com/@user/video/404"
    with patch("os.urandom", return_value=b"fakejobid"), \
         patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "yt-dlp", stderr="HTTP Error 404")), \
         patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(VideoUnavailableError) as exc:
            download_video(url, output_dir=tmp_path)
        assert "not found" in str(exc.value)

def test_download_video_other_error(tmp_path):
    url = "https://www.tiktok.com/@user/video/error"
    with patch("os.urandom", return_value=b"fakejobid"), \
         patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "yt-dlp", stderr="Some other error")), \
         patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(VideoUnavailableError) as exc:
            download_video(url, output_dir=tmp_path)
        assert "yt-dlp failed" in str(exc.value)

def test_media_pipeline_success(tmp_path):
    url = "https://www.tiktok.com/@user/video/1234567890"
    with patch("subprocess.run") as mock_run:
        with temp_job_dir(base_dir=tmp_path, job_id="pipelinejob") as job_dir:
            video_path = job_dir / "video.mp4"
            audio_path = job_dir / "audio.wav"
            video_path.touch()
            # Simulate download_video
            assert video_path.exists()
            # Simulate extract_audio
            audio_path.touch()
            assert audio_path.exists()
        # After context, temp dir should be cleaned up
        assert not (tmp_path / "pipelinejob").exists()

def test_media_pipeline_cleanup_on_error(tmp_path):
    url = "https://www.tiktok.com/@user/video/1234567890"
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "yt-dlp", stderr="fail")):
        with pytest.raises(VideoUnavailableError):
            with temp_job_dir(base_dir=tmp_path, job_id="pipelinefail") as job_dir:
                # Simulate download_video raising error
                raise VideoUnavailableError("fail")
        # After context, temp dir should be cleaned up
        assert not (tmp_path / "pipelinefail").exists() 
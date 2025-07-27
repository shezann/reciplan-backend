import os
from utils.media_downloader import temp_job_dir
from pathlib import Path
import pytest

def test_temp_job_dir_creates_and_cleans(tmp_path):
    base_dir = tmp_path / "ingest"
    job_id = "testjob"
    job_dir_path = base_dir / job_id
    # Directory should not exist before
    assert not job_dir_path.exists()
    with temp_job_dir(base_dir=base_dir, job_id=job_id) as job_dir:
        assert job_dir.exists()
        # Create a file inside
        test_file = job_dir / "test.txt"
        test_file.write_text("hello")
        assert test_file.exists()
    # After context, directory should be gone
    assert not job_dir_path.exists()

def test_temp_job_dir_cleanup_on_error(tmp_path):
    base_dir = tmp_path / "ingest"
    job_id = "errorjob"
    job_dir_path = base_dir / job_id
    with pytest.raises(ValueError):
        with temp_job_dir(base_dir=base_dir, job_id=job_id) as job_dir:
            assert job_dir.exists()
            raise ValueError("Simulated error")
    # Directory should still be cleaned up
    assert not job_dir_path.exists() 
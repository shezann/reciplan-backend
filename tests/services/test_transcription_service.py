import pytest
from services.transcription_service import TranscriptionService, TranscriptionError
from pathlib import Path
from unittest.mock import patch

def test_transcribe_error(tmp_path):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake audio")
    with patch("openai.audio.transcriptions.create", side_effect=TranscriptionError("ASR_FAILED: Rate limit exceeded after retries.")):
        with pytest.raises(TranscriptionError):
            TranscriptionService.transcribe(audio_path)
    assert not audio_path.exists()

def test_transcribe_success_cleanup(tmp_path):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake audio")
    with patch("openai.audio.transcriptions.create", return_value="mock transcript"):
        result = TranscriptionService.transcribe(audio_path)
        assert result == "mock transcript"
    assert not audio_path.exists()

def test_transcribe_asr_failed(tmp_path):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake audio")
    # Simulate OpenAI returning a 429 error
    class MockRateLimitError(Exception):
        http_status = 429
    with patch("openai.audio.transcriptions.create", side_effect=MockRateLimitError()):
        with pytest.raises(TranscriptionError) as exc:
            TranscriptionService.transcribe(audio_path, max_retries=1)
        assert "ASR_FAILED" in str(exc.value)
    assert not audio_path.exists() 
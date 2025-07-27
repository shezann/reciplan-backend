import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

class MockFirestoreDoc:
    def __init__(self):
        self.data = {}
    def update(self, data):
        self.data.update(data)
    def set(self, data):
        self.data.update(data)
    def get(self):
        return MagicMock(exists=True, to_dict=lambda: self.data)

class MockFirestore:
    def __init__(self):
        self.docs = {}
    def collection(self, name):
        return self
    def document(self, job_id):
        if job_id not in self.docs:
            self.docs[job_id] = MockFirestoreDoc()
        return self.docs[job_id]

@patch("services.tiktok_ingest_service.get_firestore_db")
@patch("tasks.tiktok_tasks.OCRService")
@patch("tasks.tiktok_tasks.extract_frames")
@patch("tasks.tiktok_tasks.get_firestore_db")
@patch("tasks.tiktok_tasks.TranscriptionService.transcribe", return_value="transcript text")
@patch("tasks.tiktok_tasks.extract_audio")
@patch("tasks.tiktok_tasks.download_video")
@patch("tasks.tiktok_tasks.LLMRefineService")
def test_ingest_tiktok_pipeline(mock_llm_service, mock_download, mock_extract, mock_transcribe, mock_get_db, mock_extract_frames, mock_ocr_service, mock_get_db_ingest_service, tmp_path):
    from tasks.tiktok_tasks import ingest_tiktok
    # Setup mocks
    mock_get_db.return_value = MockFirestore()
    mock_get_db_ingest_service.return_value = mock_get_db.return_value
    mock_download.return_value = tmp_path / "video.mp4"
    mock_extract.return_value = tmp_path / "audio.wav"
    # Mock frame extraction to avoid ffmpeg dependency
    mock_extract_frames.return_value = [
        (tmp_path / "frame1.jpg", 0.0),
        (tmp_path / "frame2.jpg", 1.0)
    ]
    # Mock OCRService to avoid PaddleOCR model loading
    mock_ocr_instance = mock_ocr_service.return_value
    mock_ocr_instance.run_ocr_on_frames.return_value = [
        {"timestamp": 0.0, "text_blocks": [{"text": "1 cup flour", "bbox": [[0,0],[1,0],[1,1],[0,1]]}]},
        {"timestamp": 1.0, "text_blocks": [{"text": "2 tbsp sugar", "bbox": [[2,2],[3,2],[3,3],[2,3]]}]}
    ]
    mock_ocr_instance.dedupe_text_blocks.side_effect = lambda blocks, threshold=0.85: blocks
    mock_ocr_instance.extract_ingredient_candidates.side_effect = lambda blocks: [b["text"] for b in blocks]
    
    # Mock LLM service to return successful result
    mock_llm_instance = mock_llm_service.return_value
    mock_llm_instance.refine_with_validation_retry.return_value = (
        {"title": "Test Recipe", "ingredients": [], "instructions": ["Test"]}, None
    )
    
    job_id = "testjobid"
    url = "https://www.tiktok.com/@user/video/1234567890"
    owner_uid = "user123"
    recipe_id = "recipe123"
    # Call the Celery task directly (not async)
    result = ingest_tiktok(
        None,  # self for bind=True
        job_id,
        url,
        owner_uid,
        recipe_id
    )
    assert result["status"] == "DRAFT_PARSED"  # Pipeline now includes LLM processing
    # Check Firestore status transitions
    doc = mock_get_db.return_value.document(job_id)
    assert doc.data["status"] == "DRAFT_PARSED"  # Final status after LLM processing
    assert doc.data["transcript"] == "transcript text" 
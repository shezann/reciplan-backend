import pytest
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path
from tasks.tiktok_tasks import ingest_tiktok

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
def test_recipe_persistence_integration_success(
    mock_llm_service, mock_download, mock_extract, mock_transcribe, 
    mock_get_db, mock_extract_frames, mock_ocr_service, 
    mock_get_db_ingest_service, tmp_path
):
    """Test successful recipe persistence integration"""
    from tasks.tiktok_tasks import ingest_tiktok
    
    # Setup mocks
    mock_get_db.return_value = MockFirestore()
    mock_get_db_ingest_service.return_value = mock_get_db.return_value
    
    mock_download.return_value = tmp_path / "video.mp4"
    mock_extract.return_value = tmp_path / "audio.wav"
    
    # Mock frame extraction
    mock_extract_frames.return_value = [
        (tmp_path / "frame1.jpg", 0.0),
        (tmp_path / "frame2.jpg", 1.0)
    ]
    
    # Mock OCRService
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
    
    # Mock RecipePersistService
    mock_recipe_persist_service = Mock()
    mock_recipe_persist_service.save_recipe_and_update_job.return_value = "rec_test_recipe_123"
    
    with patch("tasks.tiktok_tasks.RecipePersistService", return_value=mock_recipe_persist_service):
        job_id = "testjobid"
        url = "https://www.tiktok.com/@user/video/1234567890"
        owner_uid = "user123"
        recipe_id = "recipe123"
        
        # Call the Celery task directly
        result = ingest_tiktok(
            None,  # self for bind=True
            job_id,
            url,
            owner_uid,
            recipe_id
        )
    
    # Verify the result
    assert result["status"] == "COMPLETED"
    assert result["recipe_id"] == "rec_test_recipe_123"
    
    # Verify RecipePersistService was called
    mock_recipe_persist_service.save_recipe_and_update_job.assert_called_once()
    call_args = mock_recipe_persist_service.save_recipe_and_update_job.call_args[1]
    assert call_args["recipe_json"] == {"title": "Test Recipe", "ingredients": [], "instructions": ["Test"]}
    assert call_args["job_id"] == job_id
    assert call_args["owner_uid"] == owner_uid
    assert call_args["source_url"] == url

@patch("services.tiktok_ingest_service.get_firestore_db")
@patch("tasks.tiktok_tasks.OCRService")
@patch("tasks.tiktok_tasks.extract_frames")
@patch("tasks.tiktok_tasks.get_firestore_db")
@patch("tasks.tiktok_tasks.TranscriptionService.transcribe", return_value="transcript text")
@patch("tasks.tiktok_tasks.extract_audio")
@patch("tasks.tiktok_tasks.download_video")
@patch("tasks.tiktok_tasks.LLMRefineService")
def test_recipe_persistence_integration_failure(
    mock_llm_service, mock_download, mock_extract, mock_transcribe, 
    mock_get_db, mock_extract_frames, mock_ocr_service, 
    mock_get_db_ingest_service, tmp_path
):
    """Test recipe persistence integration when persistence fails"""
    from tasks.tiktok_tasks import ingest_tiktok
    
    # Setup mocks
    mock_get_db.return_value = MockFirestore()
    mock_get_db_ingest_service.return_value = mock_get_db.return_value
    
    mock_download.return_value = tmp_path / "video.mp4"
    mock_extract.return_value = tmp_path / "audio.wav"
    
    # Mock frame extraction
    mock_extract_frames.return_value = [
        (tmp_path / "frame1.jpg", 0.0),
        (tmp_path / "frame2.jpg", 1.0)
    ]
    
    # Mock OCRService
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
    
    # Mock RecipePersistService to fail
    mock_recipe_persist_service = Mock()
    mock_recipe_persist_service.save_recipe_and_update_job.return_value = None
    
    with patch("tasks.tiktok_tasks.RecipePersistService", return_value=mock_recipe_persist_service):
        job_id = "testjobid"
        url = "https://www.tiktok.com/@user/video/1234567890"
        owner_uid = "user123"
        recipe_id = "recipe123"
        
        # Call the Celery task directly
        result = ingest_tiktok(
            None,  # self for bind=True
            job_id,
            url,
            owner_uid,
            recipe_id
        )
    
    # Verify the result - should stay as DRAFT_PARSED when persistence fails
    assert result["status"] == "DRAFT_PARSED"
    assert result["recipe_id"] is None
    
    # Verify RecipePersistService was called
    mock_recipe_persist_service.save_recipe_and_update_job.assert_called_once()

@patch("services.tiktok_ingest_service.get_firestore_db")
@patch("tasks.tiktok_tasks.OCRService")
@patch("tasks.tiktok_tasks.extract_frames")
@patch("tasks.tiktok_tasks.get_firestore_db")
@patch("tasks.tiktok_tasks.TranscriptionService.transcribe", return_value="transcript text")
@patch("tasks.tiktok_tasks.extract_audio")
@patch("tasks.tiktok_tasks.download_video")
@patch("tasks.tiktok_tasks.LLMRefineService")
def test_recipe_persistence_integration_llm_failure(
    mock_llm_service, mock_download, mock_extract, mock_transcribe, 
    mock_get_db, mock_extract_frames, mock_ocr_service, 
    mock_get_db_ingest_service, tmp_path
):
    """Test recipe persistence integration when LLM fails"""
    from tasks.tiktok_tasks import ingest_tiktok
    from services.llm_refine_service import LLMRefineError
    
    # Setup mocks
    mock_get_db.return_value = MockFirestore()
    mock_get_db_ingest_service.return_value = mock_get_db.return_value
    
    mock_download.return_value = tmp_path / "video.mp4"
    mock_extract.return_value = tmp_path / "audio.wav"
    
    # Mock frame extraction
    mock_extract_frames.return_value = [
        (tmp_path / "frame1.jpg", 0.0),
        (tmp_path / "frame2.jpg", 1.0)
    ]
    
    # Mock OCRService
    mock_ocr_instance = mock_ocr_service.return_value
    mock_ocr_instance.run_ocr_on_frames.return_value = [
        {"timestamp": 0.0, "text_blocks": [{"text": "1 cup flour", "bbox": [[0,0],[1,0],[1,1],[0,1]]}]},
        {"timestamp": 1.0, "text_blocks": [{"text": "2 tbsp sugar", "bbox": [[2,2],[3,2],[3,3],[2,3]]}]}
    ]
    mock_ocr_instance.dedupe_text_blocks.side_effect = lambda blocks, threshold=0.85: blocks
    mock_ocr_instance.extract_ingredient_candidates.side_effect = lambda blocks: [b["text"] for b in blocks]
    
    # Mock LLM service to fail
    mock_llm_instance = mock_llm_service.return_value
    mock_llm_instance.refine_with_validation_retry.side_effect = LLMRefineError("LLM API error")
    
    # Mock RecipePersistService
    mock_recipe_persist_service = Mock()
    
    with patch("tasks.tiktok_tasks.RecipePersistService", return_value=mock_recipe_persist_service):
        job_id = "testjobid"
        url = "https://www.tiktok.com/@user/video/1234567890"
        owner_uid = "user123"
        recipe_id = "recipe123"
        
        # Call the Celery task directly
        result = ingest_tiktok(
            None,  # self for bind=True
            job_id,
            url,
            owner_uid,
            recipe_id
        )
    
    # Verify the result - should be LLM_FAILED_BUT_CONTINUED and no recipe persistence
    assert result["status"] == "LLM_FAILED_BUT_CONTINUED"
    assert result["recipe_id"] is None
    
    # Verify RecipePersistService was NOT called (LLM failed)
    mock_recipe_persist_service.save_recipe_and_update_job.assert_not_called() 
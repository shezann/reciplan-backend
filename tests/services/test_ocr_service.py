import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from services.ocr_service import OCRService

@pytest.fixture
def sample_text_blocks():
    return [
        {"text": "1 cup flour", "bbox": [[0,0],[1,0],[1,1],[0,1]]},
        {"text": "1 cup  flour", "bbox": [[2,2],[3,2],[3,3],[2,3]]},
        {"text": "2 tbsp sugar", "bbox": [[4,4],[5,4],[5,5],[4,5]]},
        {"text": "Mix well", "bbox": [[6,6],[7,6],[7,7],[6,7]]},
    ]

def test_dedupe_text_blocks(sample_text_blocks):
    deduped = OCRService.dedupe_text_blocks(sample_text_blocks, threshold=0.9)
    texts = [b["text"] for b in deduped]
    assert "1 cup flour" in texts or "1 cup  flour" in texts
    assert len(deduped) == 3  # One duplicate removed

def test_extract_ingredient_candidates(sample_text_blocks):
    candidates = OCRService.extract_ingredient_candidates(sample_text_blocks)
    assert "1 cup flour" in candidates
    assert "2 tbsp sugar" in candidates
    assert "Mix well" not in candidates

@patch("services.ocr_service.PaddleOCR")
def test_run_ocr_on_frames(mock_paddleocr):
    # Mock PaddleOCR output
    mock_ocr_instance = MagicMock()
    mock_ocr_instance.ocr.return_value = [
        [
            ([[0,0],[1,0],[1,1],[0,1]], ("1 cup flour", 0.99)),
            ([[2,2],[3,2],[3,3],[2,3]], ("2 tbsp sugar", 0.98)),
        ]
    ]
    mock_paddleocr.return_value = mock_ocr_instance
    ocr_service = OCRService()
    frames = [(Path("frame1.jpg"), 0.0)]
    results = ocr_service.run_ocr_on_frames(frames)
    assert len(results) == 1
    assert results[0]["timestamp"] == 0.0
    texts = [tb["text"] for tb in results[0]["text_blocks"]]
    assert "1 cup flour" in texts
    assert "2 tbsp sugar" in texts 
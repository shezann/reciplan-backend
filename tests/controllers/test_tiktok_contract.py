import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
import pytest
from app import create_app
import json
from unittest.mock import patch

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_post_ingest_tiktok_valid(client):
    payload = {"url": "https://www.tiktok.com/@user/video/1234567890"}
    response = client.post("/ingest/tiktok", json=payload)
    assert response.status_code == 202
    data = response.get_json()
    assert set(data.keys()) == {"job_id", "recipe_id", "status"}
    assert data["status"] == "QUEUED"

def test_post_ingest_tiktok_invalid_url(client):
    payload = {"url": "not_a_tiktok_url"}
    response = client.post("/ingest/tiktok", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "details" in data

def test_get_ingest_job_status(client):
    job_id = "mock-job-id"
    response = client.get(f"/ingest/jobs/{job_id}")
    assert response.status_code == 200
    data = response.get_json()
    # Check that all expected fields are present (including new LLM fields)
    expected_fields = {
        "status", "title", "transcript", "error_code",
        "recipe_json", "parse_errors", "llm_model_used",
        "llm_processing_time_seconds", "llm_processing_completed_at",
        "has_parse_errors", "recipe_stats", "llm_error_message",
        "recipe_id"
    }
    assert set(data.keys()) == expected_fields

@patch("services.tiktok_ingest_service.get_firestore_db")
@patch("tasks.tiktok_tasks.ingest_tiktok.delay")
def test_job_flow(mock_celery_delay, mock_get_firestore_db, client):
    # Mock Firestore job doc
    class MockDoc:
        def __init__(self, data):
            self._data = data
            self.exists = True
        def to_dict(self):
            return self._data
    # Mock Firestore DB
    class MockCollection:
        def __init__(self):
            self.docs = {}
        def collection(self, name):
            return self
        def document(self, job_id):
            return self
        def set(self, data):
            self.docs[data.get("job_id", "mock-job-id")] = data
        def get(self):
            # Simulate IN_PROGRESS state
            return MockDoc({
                "status": "IN_PROGRESS", 
                "title": None, 
                "transcript": None, 
                "error_code": None,
                "recipe_json": None,
                "parse_errors": None,
                "llm_model_used": None,
                "llm_processing_time_seconds": None,
                "llm_processing_completed_at": None,
                "has_parse_errors": None,
                "recipe_stats": None,
                "llm_error_message": None
            })
        def update(self, data):
            pass
    mock_get_firestore_db.return_value = MockCollection()
    # POST to create job
    payload = {"url": "https://www.tiktok.com/@user/video/1234567890"}
    response = client.post("/ingest/tiktok", json=payload)
    assert response.status_code == 202
    job_id = response.get_json()["job_id"]
    # GET to check job status
    response = client.get(f"/ingest/jobs/{job_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "IN_PROGRESS" 
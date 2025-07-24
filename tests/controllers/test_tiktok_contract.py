import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
import pytest
from app import create_app
import json

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
    assert set(data.keys()) == {"status", "title", "transcript", "error_code"} 
import pytest
from unittest.mock import patch, Mock
from flask import Flask
from controllers.tiktok_controller import tiktok_bp
from services.tiktok_ingest_service import TikTokIngestService

@pytest.fixture
def app():
    """Create a test Flask app"""
    app = Flask(__name__)
    app.register_blueprint(tiktok_bp)
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()

class TestJobStatusResponse:
    
    def test_get_job_status_basic_fields(self, client):
        """Test that basic job status fields are returned"""
        job_id = "test-job-123"
        
        # Mock the service to return basic data
        mock_response = {
            "status": "DRAFT_PARSED",
            "title": "Test Recipe",
            "transcript": "This is a test transcript",
            "error_code": None
        }
        
        with patch.object(TikTokIngestService, 'mock_get_job_status', return_value=mock_response):
            response = client.get(f'/ingest/jobs/{job_id}')
            
            assert response.status_code == 200
            data = response.get_json()
            
            assert data["status"] == "DRAFT_PARSED"
            assert data["title"] == "Test Recipe"
            assert data["transcript"] == "This is a test transcript"
            assert data["error_code"] is None
    
    def test_get_job_status_with_llm_success(self, client):
        """Test job status with successful LLM processing"""
        job_id = "test-job-123"
        
        # Mock the service to return LLM success data
        mock_response = {
            "status": "DRAFT_PARSED",
            "title": "Test Recipe",
            "transcript": "This is a test transcript",
            "error_code": None,
            "recipe_json": {
                "title": "Test Recipe",
                "ingredients": [{"name": "flour", "quantity": "1 cup"}],
                "instructions": ["Mix ingredients"]
            },
            "parse_errors": None,
            "llm_model_used": "gpt-4o-mini",
            "llm_processing_time_seconds": 5.2,
            "llm_processing_completed_at": "2025-01-01T12:00:00+00:00",
            "has_parse_errors": False,
            "recipe_stats": {
                "ingredients_count": 1,
                "instructions_count": 1,
                "has_prep_time": True,
                "has_cook_time": True
            },
            "llm_error_message": None
        }
        
        with patch.object(TikTokIngestService, 'mock_get_job_status', return_value=mock_response):
            response = client.get(f'/ingest/jobs/{job_id}')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Check basic fields
            assert data["status"] == "DRAFT_PARSED"
            assert data["title"] == "Test Recipe"
            
            # Check LLM fields
            assert data["recipe_json"]["title"] == "Test Recipe"
            assert data["recipe_json"]["ingredients"][0]["name"] == "flour"
            assert data["parse_errors"] is None
            assert data["llm_model_used"] == "gpt-4o-mini"
            assert data["llm_processing_time_seconds"] == 5.2
            assert data["has_parse_errors"] is False
            assert data["recipe_stats"]["ingredients_count"] == 1
            assert data["llm_error_message"] is None
    
    def test_get_job_status_with_llm_parse_errors(self, client):
        """Test job status with LLM parse errors"""
        job_id = "test-job-123"
        
        # Mock the service to return LLM parse error data
        mock_response = {
            "status": "DRAFT_PARSED_WITH_ERRORS",
            "title": "Test Recipe",
            "transcript": "This is a test transcript",
            "error_code": None,
            "recipe_json": {
                "title": "",
                "ingredients": [],
                "instructions": []
            },
            "parse_errors": "Schema validation failed: Title cannot be empty",
            "llm_model_used": "gpt-4o-mini",
            "llm_processing_time_seconds": 3.1,
            "llm_processing_completed_at": "2025-01-01T12:00:00+00:00",
            "has_parse_errors": True,
            "recipe_stats": {
                "ingredients_count": 0,
                "instructions_count": 0,
                "has_prep_time": False,
                "has_cook_time": False
            },
            "llm_error_message": None
        }
        
        with patch.object(TikTokIngestService, 'mock_get_job_status', return_value=mock_response):
            response = client.get(f'/ingest/jobs/{job_id}')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Check status indicates parse errors
            assert data["status"] == "DRAFT_PARSED_WITH_ERRORS"
            assert data["has_parse_errors"] is True
            assert data["parse_errors"] == "Schema validation failed: Title cannot be empty"
            assert data["recipe_json"]["title"] == ""
    
    def test_get_job_status_with_llm_failure(self, client):
        """Test job status with LLM failure"""
        job_id = "test-job-123"
        
        # Mock the service to return LLM failure data
        mock_response = {
            "status": "LLM_FAILED",
            "title": "Test Recipe",
            "transcript": "This is a test transcript",
            "error_code": "LLM_FAILED",
            "recipe_json": None,
            "parse_errors": None,
            "llm_model_used": None,
            "llm_processing_time_seconds": None,
            "llm_processing_completed_at": "2025-01-01T12:00:00+00:00",
            "has_parse_errors": None,
            "recipe_stats": None,
            "llm_error_message": "OpenAI API error: Rate limit exceeded"
        }
        
        with patch.object(TikTokIngestService, 'mock_get_job_status', return_value=mock_response):
            response = client.get(f'/ingest/jobs/{job_id}')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Check LLM failure fields
            assert data["status"] == "LLM_FAILED"
            assert data["error_code"] == "LLM_FAILED"
            assert data["recipe_json"] is None
            assert data["llm_error_message"] == "OpenAI API error: Rate limit exceeded"
            assert data["llm_model_used"] is None
    
    def test_get_job_status_queued_state(self, client):
        """Test job status in queued state (no LLM processing yet)"""
        job_id = "test-job-123"
        
        # Mock the service to return queued state
        mock_response = {
            "status": "QUEUED",
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
        }
        
        with patch.object(TikTokIngestService, 'mock_get_job_status', return_value=mock_response):
            response = client.get(f'/ingest/jobs/{job_id}')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Check queued state
            assert data["status"] == "QUEUED"
            assert data["title"] is None
            assert data["recipe_json"] is None
            assert data["llm_model_used"] is None
    
    def test_get_job_status_processing_state(self, client):
        """Test job status in processing state (LLM_REFINING)"""
        job_id = "test-job-123"
        
        # Mock the service to return processing state
        mock_response = {
            "status": "LLM_REFINING",
            "title": "Test Recipe",
            "transcript": "This is a test transcript",
            "error_code": None,
            "recipe_json": None,
            "parse_errors": None,
            "llm_model_used": None,
            "llm_processing_time_seconds": None,
            "llm_processing_completed_at": None,
            "has_parse_errors": None,
            "recipe_stats": None,
            "llm_error_message": None
        }
        
        with patch.object(TikTokIngestService, 'mock_get_job_status', return_value=mock_response):
            response = client.get(f'/ingest/jobs/{job_id}')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Check processing state
            assert data["status"] == "LLM_REFINING"
            assert data["title"] == "Test Recipe"
            assert data["recipe_json"] is None  # Not ready yet
    
    def test_get_job_status_service_exception(self, client):
        """Test job status when service throws an exception"""
        job_id = "test-job-123"
        
        with patch.object(TikTokIngestService, 'mock_get_job_status', side_effect=Exception("Service error")):
            response = client.get(f'/ingest/jobs/{job_id}')
            
            assert response.status_code == 500
            data = response.get_json()
            assert "error" in data
            assert "Failed to retrieve job status" in data["error"]
    
    def test_get_job_status_schema_validation_fallback(self, client):
        """Test that schema validation failures don't break the endpoint"""
        job_id = "test-job-123"
        
        # Mock the service to return data that might fail schema validation
        mock_response = {
            "status": "DRAFT_PARSED",
            "title": "Test Recipe",
            "transcript": "This is a test transcript",
            "error_code": None,
            "recipe_json": {
                "title": "Test Recipe",
                "ingredients": [{"name": "flour", "quantity": "1 cup"}],
                "instructions": ["Mix ingredients"]
            },
            "parse_errors": None,
            "llm_model_used": "gpt-4o-mini",
            "llm_processing_time_seconds": "invalid_float",  # This should cause validation error
            "llm_processing_completed_at": "2025-01-01T12:00:00+00:00",
            "has_parse_errors": False,
            "recipe_stats": {
                "ingredients_count": 1,
                "instructions_count": 1
            },
            "llm_error_message": None
        }
        
        with patch.object(TikTokIngestService, 'mock_get_job_status', return_value=mock_response):
            response = client.get(f'/ingest/jobs/{job_id}')
            
            # Should still return 200 even with validation issues
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "DRAFT_PARSED"
            assert data["title"] == "Test Recipe"
    
    def test_get_job_status_all_fields_present(self, client):
        """Test that all expected fields are present in the response"""
        job_id = "test-job-123"
        
        # Mock the service to return complete data
        mock_response = {
            "status": "DRAFT_PARSED",
            "title": "Test Recipe",
            "transcript": "This is a test transcript",
            "error_code": None,
            "recipe_json": {
                "title": "Test Recipe",
                "ingredients": [{"name": "flour", "quantity": "1 cup"}],
                "instructions": ["Mix ingredients"]
            },
            "parse_errors": None,
            "llm_model_used": "gpt-4o-mini",
            "llm_processing_time_seconds": 5.2,
            "llm_processing_completed_at": "2025-01-01T12:00:00+00:00",
            "has_parse_errors": False,
            "recipe_stats": {
                "ingredients_count": 1,
                "instructions_count": 1,
                "has_prep_time": True,
                "has_cook_time": True,
                "has_servings": True,
                "has_difficulty": True,
                "has_nutrition": False,
                "has_tags": False,
                "has_description": False
            },
            "llm_error_message": None
        }
        
        with patch.object(TikTokIngestService, 'mock_get_job_status', return_value=mock_response):
            response = client.get(f'/ingest/jobs/{job_id}')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Check all expected fields are present
            expected_fields = [
                "status", "title", "transcript", "error_code",
                "recipe_json", "parse_errors", "llm_model_used",
                "llm_processing_time_seconds", "llm_processing_completed_at",
                "has_parse_errors", "recipe_stats", "llm_error_message"
            ]
            
            for field in expected_fields:
                assert field in data, f"Field {field} missing from response" 
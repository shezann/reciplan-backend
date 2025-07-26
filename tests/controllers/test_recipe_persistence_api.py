#!/usr/bin/env python3
"""
API integration tests for recipe persistence flow (Task 903)
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
import pytest
from app import create_app
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class MockFirestoreDoc:
    def __init__(self, exists=True, data=None):
        self.exists = exists
        self.data = data or {}
        self.set_called = False
        self.update_called = False
        self.set_args = None
        self.update_args = None
    
    def set(self, data):
        self.set_called = True
        self.set_args = data
        return True
    
    def update(self, data):
        self.update_called = True
        self.update_args = data
        return True
    
    def get(self):
        return self


class MockFirestore:
    def __init__(self):
        self.collections = {}
        self.documents = {}
    
    def collection(self, name):
        if name not in self.collections:
            self.collections[name] = Mock()
            self.collections[name].document = Mock()
        return self.collections[name]


@pytest.fixture
def sample_recipe_json():
    """Sample recipe JSON for testing"""
    return {
        "title": "Test Recipe",
        "description": "A test recipe for API testing",
        "ingredients": [
            {"name": "Test Ingredient", "quantity": "1 cup"}
        ],
        "instructions": ["Step 1", "Step 2"],
        "prep_time": 10,
        "cook_time": 20,
        "servings": 4,
        "difficulty": 3
    }


@pytest.fixture
def mock_job_data_completed(sample_recipe_json):
    """Mock job data for a completed job with recipe_id"""
    return {
        "status": "COMPLETED",
        "title": "Test Recipe Title",
        "transcript": "This is a test transcript",
        "recipe_json": sample_recipe_json,
        "recipe_id": "rec_12345678-1234-1234-1234-123456789abc",  # Proper UUID format
        "llm_model_used": "gpt-4o-mini",
        "llm_processing_time_seconds": 2.5,
        "llm_processing_completed_at": "2025-01-01T12:00:00Z",
        "has_parse_errors": False,
        "recipe_stats": {
            "ingredients_count": 1,
            "instructions_count": 2,
            "total_time": 30
        }
    }


@pytest.fixture
def mock_job_data_draft_parsed(sample_recipe_json):
    """Mock job data for a draft parsed job without recipe_id"""
    return {
        "status": "DRAFT_PARSED",
        "title": "Test Recipe Title",
        "transcript": "This is a test transcript",
        "recipe_json": sample_recipe_json,
        "recipe_id": None,  # No recipe_id yet
        "llm_model_used": "gpt-4o-mini",
        "llm_processing_time_seconds": 2.5,
        "llm_processing_completed_at": "2025-01-01T12:00:00Z",
        "has_parse_errors": False,
        "recipe_stats": {
            "ingredients_count": 1,
            "instructions_count": 2,
            "total_time": 30
        }
    }


class TestRecipePersistenceAPI:
    """Test API integration for recipe persistence flow"""
    
    @patch('services.tiktok_ingest_service.get_firestore_db')
    def test_get_job_status_returns_recipe_id_when_completed(self, mock_get_db, client, mock_job_data_completed):
        """Test that GET /ingest/jobs/{id} returns recipe_id when job is completed"""
        # Arrange
        job_id = "test_job_123"
        
        # Mock the service to return our test data
        with patch('services.tiktok_ingest_service.TikTokIngestService.mock_get_job_status', return_value=mock_job_data_completed):
            # Act
            response = client.get(f"/ingest/jobs/{job_id}")
            
            # Assert
            assert response.status_code == 200
            data = response.get_json()
            
            # Check that recipe_id is present
            assert "recipe_id" in data
            assert data["recipe_id"] == "rec_12345678-1234-1234-1234-123456789abc"
            
            # Check that all other expected fields are present
            expected_fields = {
                "status", "title", "transcript", "recipe_json", "recipe_id",
                "llm_model_used", "llm_processing_time_seconds", "llm_processing_completed_at",
                "has_parse_errors", "recipe_stats"
            }
            for field in expected_fields:
                assert field in data
    
    @patch('services.tiktok_ingest_service.get_firestore_db')
    def test_get_job_status_returns_none_recipe_id_when_not_completed(self, mock_get_db, client, mock_job_data_draft_parsed):
        """Test that GET /ingest/jobs/{id} returns None recipe_id when job is not completed"""
        # Arrange
        job_id = "test_job_123"
        
        # Mock the service to return our test data
        with patch('services.tiktok_ingest_service.TikTokIngestService.mock_get_job_status', return_value=mock_job_data_draft_parsed):
            # Act
            response = client.get(f"/ingest/jobs/{job_id}")
            
            # Assert
            assert response.status_code == 200
            data = response.get_json()
            
            # Check that recipe_id is present but None
            assert "recipe_id" in data
            assert data["recipe_id"] is None
            
            # Check that status is not COMPLETED
            assert data["status"] == "DRAFT_PARSED"
    
    @patch('services.tiktok_ingest_service.get_firestore_db')
    def test_get_job_status_recipe_id_field_structure(self, mock_get_db, client, mock_job_data_completed):
        """Test that recipe_id field has the correct structure and format"""
        # Arrange
        job_id = "test_job_123"
        
        # Mock the service to return our test data
        with patch('services.tiktok_ingest_service.TikTokIngestService.mock_get_job_status', return_value=mock_job_data_completed):
            # Act
            response = client.get(f"/ingest/jobs/{job_id}")
            
            # Assert
            assert response.status_code == 200
            data = response.get_json()
            
            # Check recipe_id format
            recipe_id = data["recipe_id"]
            assert isinstance(recipe_id, str)
            assert recipe_id.startswith("rec_")
            assert len(recipe_id) == 40  # "rec_" + 36 char UUID
    
    @patch('services.tiktok_ingest_service.get_firestore_db')
    def test_get_job_status_schema_validation_with_recipe_id(self, mock_get_db, client, mock_job_data_completed):
        """Test that the response validates against the schema with recipe_id field"""
        # Arrange
        job_id = "test_job_123"
        
        # Mock the service to return our test data
        with patch('services.tiktok_ingest_service.TikTokIngestService.mock_get_job_status', return_value=mock_job_data_completed):
            # Act
            response = client.get(f"/ingest/jobs/{job_id}")
            
            # Assert
            assert response.status_code == 200
            data = response.get_json()
            
            # The schema validation should pass (no ValidationError raised)
            # This test ensures the TikTokJobStatusResponseSchema includes recipe_id field
            from schemas.tiktok import TikTokJobStatusResponseSchema
            schema = TikTokJobStatusResponseSchema()
            
            # This should not raise a ValidationError
            validated_data = schema.load(data)
            assert "recipe_id" in validated_data
            assert validated_data["recipe_id"] == "rec_12345678-1234-1234-1234-123456789abc"
    
    @patch('services.tiktok_ingest_service.get_firestore_db')
    def test_get_job_status_complete_flow_simulation(self, mock_get_db, client, sample_recipe_json):
        """Test a simulation of the complete flow from job creation to completion"""
        # Arrange - Simulate different job states
        job_id = "test_job_123"
        
        # State 1: Job in progress (no recipe_id)
        job_in_progress = {
            "status": "IN_PROGRESS",
            "title": None,
            "transcript": None,
            "recipe_json": None,
            "recipe_id": None,
            "llm_model_used": None,
            "llm_processing_time_seconds": None,
            "llm_processing_completed_at": None,
            "has_parse_errors": None,
            "recipe_stats": None
        }
        
        # State 2: Job with LLM results but no persistence (no recipe_id)
        job_with_llm = {
            "status": "DRAFT_PARSED",
            "title": "Test Recipe",
            "transcript": "Test transcript",
            "recipe_json": sample_recipe_json,
            "recipe_id": None,  # Not persisted yet
            "llm_model_used": "gpt-4o-mini",
            "llm_processing_time_seconds": 2.5,
            "llm_processing_completed_at": "2025-01-01T12:00:00Z",
            "has_parse_errors": False,
            "recipe_stats": {"ingredients_count": 1, "instructions_count": 2}
        }
        
        # State 3: Job completed with recipe persistence
        job_completed = {
            "status": "COMPLETED",
            "title": "Test Recipe",
            "transcript": "Test transcript",
            "recipe_json": sample_recipe_json,
            "recipe_id": "rec_test_recipe_123",  # Now persisted
            "llm_model_used": "gpt-4o-mini",
            "llm_processing_time_seconds": 2.5,
            "llm_processing_completed_at": "2025-01-01T12:00:00Z",
            "has_parse_errors": False,
            "recipe_stats": {"ingredients_count": 1, "instructions_count": 2}
        }
        
        # Test State 1: In Progress
        with patch('services.tiktok_ingest_service.TikTokIngestService.mock_get_job_status', return_value=job_in_progress):
            response = client.get(f"/ingest/jobs/{job_id}")
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "IN_PROGRESS"
            assert data["recipe_id"] is None
        
        # Test State 2: LLM Complete but not persisted
        with patch('services.tiktok_ingest_service.TikTokIngestService.mock_get_job_status', return_value=job_with_llm):
            response = client.get(f"/ingest/jobs/{job_id}")
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "DRAFT_PARSED"
            assert data["recipe_json"] is not None
            assert data["recipe_id"] is None  # Not persisted yet
        
        # Test State 3: Completed with recipe persistence
        with patch('services.tiktok_ingest_service.TikTokIngestService.mock_get_job_status', return_value=job_completed):
            response = client.get(f"/ingest/jobs/{job_id}")
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "COMPLETED"
            assert data["recipe_json"] is not None
            assert data["recipe_id"] == "rec_test_recipe_123"  # Now persisted
    
    @patch('services.tiktok_ingest_service.get_firestore_db')
    def test_get_job_status_error_handling_with_recipe_id(self, mock_get_db, client):
        """Test error handling when recipe_id field is present but service fails"""
        # Arrange
        job_id = "test_job_123"
        
        # Mock service to raise an exception
        with patch('services.tiktok_ingest_service.TikTokIngestService.mock_get_job_status', side_effect=Exception("Service error")):
            # Act
            response = client.get(f"/ingest/jobs/{job_id}")
            
            # Assert
            assert response.status_code == 500
            data = response.get_json()
            assert "error" in data
    
    @patch('services.tiktok_ingest_service.get_firestore_db')
    def test_get_job_status_recipe_id_edge_cases(self, mock_get_db, client):
        """Test edge cases for recipe_id field"""
        # Arrange
        job_id = "test_job_123"
        
        # Test case 1: Empty string recipe_id
        job_empty_recipe_id = {
            "status": "COMPLETED",
            "title": "Test Recipe",
            "recipe_id": "",
            "recipe_json": {"title": "Test"},
            "llm_model_used": "gpt-4o-mini"
        }
        
        with patch('services.tiktok_ingest_service.TikTokIngestService.mock_get_job_status', return_value=job_empty_recipe_id):
            response = client.get(f"/ingest/jobs/{job_id}")
            assert response.status_code == 200
            data = response.get_json()
            assert data["recipe_id"] == ""
        
        # Test case 2: Very long recipe_id
        job_long_recipe_id = {
            "status": "COMPLETED",
            "title": "Test Recipe",
            "recipe_id": "rec_" + "a" * 100,  # Very long ID
            "recipe_json": {"title": "Test"},
            "llm_model_used": "gpt-4o-mini"
        }
        
        with patch('services.tiktok_ingest_service.TikTokIngestService.mock_get_job_status', return_value=job_long_recipe_id):
            response = client.get(f"/ingest/jobs/{job_id}")
            assert response.status_code == 200
            data = response.get_json()
            assert data["recipe_id"] == "rec_" + "a" * 100


class TestRecipePersistenceEndToEnd:
    """End-to-end tests for recipe persistence flow"""
    
    @patch('services.tiktok_ingest_service.get_firestore_db')
    def test_complete_persistence_flow_api_integration(self, mock_get_db, client, sample_recipe_json):
        """Test the complete flow from job creation to API response with recipe_id"""
        # This test simulates the complete flow:
        # 1. Job is created and processed
        # 2. LLM generates recipe_json
        # 3. Recipe is persisted to recipes collection
        # 4. Job is updated with recipe_id
        # 5. API returns recipe_id in response
        
        job_id = "test_job_123"
        owner_uid = "test_user_123"
        source_url = "https://www.tiktok.com/@user/video/123"
        
        # Simulate the final state after recipe persistence
        final_job_data = {
            "status": "COMPLETED",
            "title": "Test Recipe",
            "transcript": "Test transcript",
            "recipe_json": sample_recipe_json,
            "recipe_id": "rec_12345678-1234-1234-1234-123456789abc",  # Proper UUID format
            "llm_model_used": "gpt-4o-mini",
            "llm_processing_time_seconds": 2.5,
            "llm_processing_completed_at": "2025-01-01T12:00:00Z",
            "has_parse_errors": False,
            "recipe_stats": {
                "ingredients_count": 1,
                "instructions_count": 2,
                "total_time": 30
            }
        }
        
        # Mock the service to return our final state
        with patch('services.tiktok_ingest_service.TikTokIngestService.mock_get_job_status', return_value=final_job_data):
            # Act - Simulate API call after recipe persistence
            response = client.get(f"/ingest/jobs/{job_id}")
            
            # Assert
            assert response.status_code == 200
            data = response.get_json()
            
            # Verify all expected fields are present
            assert data["status"] == "COMPLETED"
            assert data["recipe_id"] == "rec_12345678-1234-1234-1234-123456789abc"
            assert data["recipe_json"] == sample_recipe_json
            assert data["title"] == "Test Recipe"
            assert data["llm_model_used"] == "gpt-4o-mini"
            
            # Verify recipe_id format
            assert data["recipe_id"].startswith("rec_")
            assert len(data["recipe_id"]) == 40
            
            # Verify the complete response structure
            expected_fields = {
                "status", "title", "transcript", "recipe_json", "recipe_id",
                "llm_model_used", "llm_processing_time_seconds", "llm_processing_completed_at",
                "has_parse_errors", "recipe_stats"
            }
            for field in expected_fields:
                assert field in data 
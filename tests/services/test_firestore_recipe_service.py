import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from services.firestore_recipe_service import FirestoreRecipeService

class TestFirestoreRecipeService:
    
    @pytest.fixture
    def mock_firestore_db(self):
        """Mock Firestore database client"""
        return Mock()
    
    @pytest.fixture
    def firestore_service(self, mock_firestore_db):
        """FirestoreRecipeService instance with mocked database"""
        return FirestoreRecipeService(mock_firestore_db)
    
    @pytest.fixture
    def sample_recipe_json(self):
        """Sample recipe JSON for testing"""
        return {
            "title": "Test Recipe",
            "description": "A test recipe",
            "ingredients": [
                {"name": "flour", "quantity": "1 cup"},
                {"name": "sugar", "quantity": "2 tbsp"}
            ],
            "instructions": [
                "Mix ingredients",
                "Bake at 350F"
            ],
            "prep_time": 10,
            "cook_time": 30,
            "servings": 4,
            "difficulty": 2,
            "tags": ["dessert", "quick"],
            "nutrition": {
                "calories": 300,
                "carbs": 40,
                "fat": 15,
                "protein": 8
            }
        }
    
    @pytest.fixture
    def sample_llm_metadata(self):
        """Sample LLM metadata for testing"""
        return {
            "llm_model_used": "gpt-4o-mini",
            "llm_processing_time_seconds": 5.2,
            "llm_processing_completed_at": "2025-01-01T12:00:00+00:00",
            "llm_validation_retries": 2,
            "ocr_frames_processed": 8
        }
    
    def test_init(self, mock_firestore_db):
        """Test service initialization"""
        service = FirestoreRecipeService(mock_firestore_db)
        assert service.db == mock_firestore_db
    
    def test_extract_recipe_stats(self, firestore_service, sample_recipe_json):
        """Test recipe statistics extraction"""
        stats = firestore_service._extract_recipe_stats(sample_recipe_json)
        
        assert stats["ingredients_count"] == 2
        assert stats["instructions_count"] == 2
        assert stats["has_prep_time"] is True
        assert stats["has_cook_time"] is True
        assert stats["has_servings"] is True
        assert stats["has_difficulty"] is True
        assert stats["has_nutrition"] is True
        assert stats["has_tags"] is True
        assert stats["has_description"] is True
    
    def test_extract_recipe_stats_minimal(self, firestore_service):
        """Test recipe statistics extraction with minimal data"""
        minimal_recipe = {
            "title": "Minimal Recipe",
            "ingredients": [],
            "instructions": []
        }
        
        stats = firestore_service._extract_recipe_stats(minimal_recipe)
        
        assert stats["ingredients_count"] == 0
        assert stats["instructions_count"] == 0
        assert stats["has_prep_time"] is False
        assert stats["has_cook_time"] is False
        assert stats["has_servings"] is False
        assert stats["has_difficulty"] is False
        assert stats["has_nutrition"] is False
        assert stats["has_tags"] is False
        assert stats["has_description"] is False
    
    def test_update_both_collections_success(self, firestore_service, mock_firestore_db):
        """Test successful update of both collections"""
        update_data = {
            "status": "DRAFT_PARSED",
            "updatedAt": "2025-01-01T12:00:00+00:00",
            "recipe_json": {"title": "Test"}
        }
        
        # Mock the document references and update method
        mock_job_doc = Mock()
        mock_recipe_doc = Mock()
        
        # Create separate collection mocks
        mock_ingest_collection = Mock()
        mock_recipe_collection = Mock()
        mock_ingest_collection.document.return_value = mock_job_doc
        mock_recipe_collection.document.return_value = mock_recipe_doc
        
        # Configure the collection mock to return different collections
        def mock_collection_side_effect(collection_name):
            if collection_name == "ingest_jobs":
                return mock_ingest_collection
            elif collection_name == "recipes":
                return mock_recipe_collection
            return Mock()
        
        mock_firestore_db.collection.side_effect = mock_collection_side_effect
        
        result = firestore_service._update_both_collections("job-123", "recipe-456", update_data)
        
        assert result is True
        mock_job_doc.update.assert_called_once_with(update_data)
        mock_recipe_doc.update.assert_called_once_with(update_data)
    
    def test_update_both_collections_firestore_error(self, firestore_service, mock_firestore_db):
        """Test handling of Firestore update errors"""
        update_data = {
            "status": "DRAFT_PARSED",
            "updatedAt": "2025-01-01T12:00:00+00:00",
            "recipe_json": {"title": "Test"}
        }

        # Mock the document references to fail
        mock_job_doc = Mock()
        mock_job_doc.update.side_effect = Exception("Firestore error")

        # Create collection mock
        mock_ingest_collection = Mock()
        mock_ingest_collection.document.return_value = mock_job_doc

        # Configure the collection mock
        mock_firestore_db.collection.return_value = mock_ingest_collection

        result = firestore_service._update_both_collections("job-123", "recipe-456", update_data)

        # Should fail due to Firestore error
        assert result is False
        # Should have attempted the update
        assert mock_job_doc.update.call_count >= 1

    def test_update_both_collections_fallback_fails(self, firestore_service, mock_firestore_db):
        """Test handling when Firestore updates fail"""
        update_data = {
            "status": "DRAFT_PARSED",
            "updatedAt": "2025-01-01T12:00:00+00:00",
            "recipe_json": {"title": "Test"}
        }

        # Mock the document references to fail
        mock_job_doc = Mock()
        mock_job_doc.update.side_effect = Exception("Firestore error")

        # Create collection mock
        mock_ingest_collection = Mock()
        mock_ingest_collection.document.return_value = mock_job_doc

        # Configure the collection mock
        mock_firestore_db.collection.return_value = mock_ingest_collection

        result = firestore_service._update_both_collections("job-123", "recipe-456", update_data)

        assert result is False
        # Should have attempted the update
        assert mock_job_doc.update.call_count >= 1
    
    def test_update_recipe_with_llm_results_success(self, firestore_service, sample_recipe_json, sample_llm_metadata):
        """Test successful recipe update with LLM results"""
        # Mock the _update_both_collections method
        with patch.object(firestore_service, '_update_both_collections', return_value=True):
            result = firestore_service.update_recipe_with_llm_results(
                job_id="job-123",
                recipe_id="recipe-456",
                recipe_json=sample_recipe_json,
                llm_metadata=sample_llm_metadata,
                parse_error=None
            )
        
        assert result is True
    
    def test_update_recipe_with_llm_results_with_parse_error(self, firestore_service, sample_recipe_json, sample_llm_metadata):
        """Test recipe update with parse error"""
        parse_error = "Schema validation failed: Title cannot be empty"
        
        # Mock the _update_both_collections method
        with patch.object(firestore_service, '_update_both_collections', return_value=True) as mock_update:
            result = firestore_service.update_recipe_with_llm_results(
                job_id="job-123",
                recipe_id="recipe-456",
                recipe_json=sample_recipe_json,
                llm_metadata=sample_llm_metadata,
                parse_error=parse_error
            )
        
        assert result is True
        
        # Verify the update data includes parse error
        call_args = mock_update.call_args[0]
        update_data = call_args[2]  # Third argument is update_data
        
        assert update_data["status"] == "DRAFT_PARSED_WITH_ERRORS"
        assert update_data["parse_errors"] == parse_error
        assert update_data["has_parse_errors"] is True
        assert "recipe_stats" in update_data
    
    def test_update_recipe_with_llm_results_update_fails(self, firestore_service, sample_recipe_json, sample_llm_metadata):
        """Test recipe update when Firestore update fails"""
        # Mock the _update_both_collections method to fail
        with patch.object(firestore_service, '_update_both_collections', return_value=False):
            result = firestore_service.update_recipe_with_llm_results(
                job_id="job-123",
                recipe_id="recipe-456",
                recipe_json=sample_recipe_json,
                llm_metadata=sample_llm_metadata,
                parse_error=None
            )
        
        assert result is False
    
    def test_update_recipe_llm_failure_success(self, firestore_service):
        """Test successful LLM failure update"""
        error_message = "OpenAI API error: Rate limit exceeded"
        
        # Mock the _update_both_collections method
        with patch.object(firestore_service, '_update_both_collections', return_value=True) as mock_update:
            result = firestore_service.update_recipe_llm_failure(
                job_id="job-123",
                recipe_id="recipe-456",
                error_message=error_message
            )
        
        assert result is True
        
        # Verify the update data includes LLM failure info
        call_args = mock_update.call_args[0]
        update_data = call_args[2]  # Third argument is update_data
        
        assert update_data["status"] == "LLM_FAILED"
        assert update_data["error_code"] == "LLM_FAILED"
        assert update_data["llm_error_message"] == error_message
    
    def test_update_recipe_llm_failure_update_fails(self, firestore_service):
        """Test LLM failure update when Firestore update fails"""
        error_message = "OpenAI API error: Rate limit exceeded"
        
        # Mock the _update_both_collections method to fail
        with patch.object(firestore_service, '_update_both_collections', return_value=False):
            result = firestore_service.update_recipe_llm_failure(
                job_id="job-123",
                recipe_id="recipe-456",
                error_message=error_message
            )
        
        assert result is False
    
    def test_get_recipe_document_exists(self, firestore_service, mock_firestore_db):
        """Test getting existing recipe document"""
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"title": "Test Recipe", "ingredients": []}
        
        mock_doc_ref = Mock()
        mock_doc_ref.get.return_value = mock_doc
        mock_firestore_db.collection.return_value.document.return_value = mock_doc_ref
        
        result = firestore_service.get_recipe_document("recipe-123")
        
        assert result == {"title": "Test Recipe", "ingredients": []}
        mock_firestore_db.collection.assert_called_once_with("recipes")
        mock_firestore_db.collection.return_value.document.assert_called_once_with("recipe-123")
    
    def test_get_recipe_document_not_exists(self, firestore_service, mock_firestore_db):
        """Test getting non-existent recipe document"""
        mock_doc = Mock()
        mock_doc.exists = False
        
        mock_doc_ref = Mock()
        mock_doc_ref.get.return_value = mock_doc
        mock_firestore_db.collection.return_value.document.return_value = mock_doc_ref
        
        result = firestore_service.get_recipe_document("recipe-123")
        
        assert result is None
    
    def test_get_recipe_document_error(self, firestore_service, mock_firestore_db):
        """Test getting recipe document with error"""
        mock_firestore_db.collection.side_effect = Exception("Firestore error")
        
        result = firestore_service.get_recipe_document("recipe-123")
        
        assert result is None
    
    def test_get_job_document_exists(self, firestore_service, mock_firestore_db):
        """Test getting existing job document"""
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"status": "DRAFT_PARSED", "job_id": "job-123"}
        
        mock_doc_ref = Mock()
        mock_doc_ref.get.return_value = mock_doc
        mock_firestore_db.collection.return_value.document.return_value = mock_doc_ref
        
        result = firestore_service.get_job_document("job-123")
        
        assert result == {"status": "DRAFT_PARSED", "job_id": "job-123"}
        mock_firestore_db.collection.assert_called_once_with("ingest_jobs")
        mock_firestore_db.collection.return_value.document.assert_called_once_with("job-123")
    
    def test_get_job_document_not_exists(self, firestore_service, mock_firestore_db):
        """Test getting non-existent job document"""
        mock_doc = Mock()
        mock_doc.exists = False
        
        mock_doc_ref = Mock()
        mock_doc_ref.get.return_value = mock_doc
        mock_firestore_db.collection.return_value.document.return_value = mock_doc_ref
        
        result = firestore_service.get_job_document("job-123")
        
        assert result is None
    
    def test_get_job_document_error(self, firestore_service, mock_firestore_db):
        """Test getting job document with error"""
        mock_firestore_db.collection.side_effect = Exception("Firestore error")
        
        result = firestore_service.get_job_document("job-123")
        
        assert result is None 
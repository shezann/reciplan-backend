#!/usr/bin/env python3
"""
Unit tests for RecipePersistService
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import uuid

from services.recipe_persist_service import RecipePersistService


class TestRecipePersistService:
    
    @pytest.fixture
    def mock_firestore_db(self):
        """Mock Firestore database"""
        mock_db = Mock()
        
        # Create separate mocks for different collections
        mock_recipes_collection = Mock()
        mock_ingest_collection = Mock()
        mock_recipes_document = Mock()
        mock_ingest_document = Mock()
        
        # Set up side effect to return different collections
        def collection_side_effect(collection_name):
            if collection_name == "recipes":
                return mock_recipes_collection
            elif collection_name == "ingest_jobs":
                return mock_ingest_collection
            else:
                return Mock()
        
        mock_db.collection.side_effect = collection_side_effect
        mock_recipes_collection.document.return_value = mock_recipes_document
        mock_ingest_collection.document.return_value = mock_ingest_document
        
        return mock_db, mock_recipes_collection, mock_ingest_collection, mock_recipes_document, mock_ingest_document
    
    @pytest.fixture
    def sample_recipe_json(self):
        """Sample recipe JSON data"""
        return {
            "title": "Test Recipe",
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
            "servings": 4
        }
    
    @pytest.fixture
    def recipe_persist_service(self, mock_firestore_db):
        """RecipePersistService instance with mocked Firestore"""
        mock_db, _, _, _, _ = mock_firestore_db
        
        with patch('services.recipe_persist_service.get_firestore_db', return_value=mock_db):
            service = RecipePersistService()
            return service
    
    def test_init_with_firestore(self, mock_firestore_db):
        """Test service initialization with Firestore connection"""
        mock_db, _, _, _, _ = mock_firestore_db
        
        with patch('services.recipe_persist_service.get_firestore_db', return_value=mock_db):
            service = RecipePersistService()
            assert service.db == mock_db
    
    def test_init_without_firestore(self):
        """Test service initialization without Firestore connection"""
        with patch('services.recipe_persist_service.get_firestore_db', return_value=None):
            service = RecipePersistService()
            assert service.db is None
    
    def test_save_recipe_success(self, recipe_persist_service, sample_recipe_json, mock_firestore_db):
        """Test successful recipe saving"""
        mock_db, mock_recipes_collection, mock_ingest_collection, mock_recipes_document, mock_ingest_document = mock_firestore_db
        
        # Mock UUID generation
        test_uuid = "test-uuid-123"
        with patch('uuid.uuid4', return_value=test_uuid):
            with patch('services.recipe_persist_service.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

                recipe_id = recipe_persist_service.save_recipe(
                    recipe_json=sample_recipe_json,
                    owner_uid="user123",
                    source_url="https://tiktok.com/test",
                    original_job_id="job123"
                )

        # Verify recipe_id format
        expected_recipe_id = f"rec_{test_uuid}"
        assert recipe_id == expected_recipe_id
        assert recipe_id.startswith("rec_")
        assert len(recipe_id) == 17  # "rec_" + 13 char test UUID
        
        # Verify document was set
        mock_recipes_document.set.assert_called_once()
        call_args = mock_recipes_document.set.call_args[0][0]
        
        assert call_args["recipe_json"] == sample_recipe_json
        assert call_args["owner_uid"] == "user123"
        assert call_args["createdAt"] == "2025-01-01T12:00:00+00:00"
        assert call_args["updatedAt"] == "2025-01-01T12:00:00+00:00"
        assert call_args["source_url"] == "https://tiktok.com/test"
        assert call_args["original_job_id"] == "job123"
        assert call_args["status"] == "ACTIVE"
    
    def test_save_recipe_no_firestore(self, sample_recipe_json):
        """Test recipe saving without Firestore connection"""
        with patch('services.recipe_persist_service.get_firestore_db', return_value=None):
            service = RecipePersistService()
            recipe_id = service.save_recipe(
                recipe_json=sample_recipe_json,
                owner_uid="user123"
            )
            assert recipe_id is None
    
    def test_save_recipe_firestore_error(self, recipe_persist_service, sample_recipe_json, mock_firestore_db):
        """Test recipe saving with Firestore error"""
        mock_db, mock_recipes_collection, mock_ingest_collection, mock_recipes_document, mock_ingest_document = mock_firestore_db
        
        # Mock Firestore error
        mock_recipes_document.set.side_effect = Exception("Firestore error")
        
        recipe_id = recipe_persist_service.save_recipe(
            recipe_json=sample_recipe_json,
            owner_uid="user123"
        )
        
        assert recipe_id is None
    
    def test_update_job_with_recipe_id_success(self, recipe_persist_service, mock_firestore_db):
        """Test successful job update with recipe_id"""
        mock_db, mock_recipes_collection, mock_ingest_collection, mock_recipes_document, mock_ingest_document = mock_firestore_db
        
        with patch('services.recipe_persist_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

            success = recipe_persist_service.update_job_with_recipe_id(
                job_id="job123",
                recipe_id="rec_recipe456"
            )

        assert success is True
        
        # Verify update was called
        mock_ingest_document.update.assert_called_once()
        call_args = mock_ingest_document.update.call_args[0][0]
        
        assert call_args["status"] == "COMPLETED"
        assert call_args["recipe_id"] == "rec_recipe456"
        assert call_args["updatedAt"] == "2025-01-01T12:00:00+00:00"
    
    def test_update_job_no_firestore(self):
        """Test job update without Firestore connection"""
        with patch('services.recipe_persist_service.get_firestore_db', return_value=None):
            service = RecipePersistService()
            success = service.update_job_with_recipe_id("job123", "rec_recipe456")
            assert success is False
    
    def test_update_job_firestore_error(self, recipe_persist_service, mock_firestore_db):
        """Test job update with Firestore error"""
        mock_db, mock_recipes_collection, mock_ingest_collection, mock_recipes_document, mock_ingest_document = mock_firestore_db
        
        # Mock Firestore error
        mock_ingest_document.update.side_effect = Exception("Firestore error")
        
        success = recipe_persist_service.update_job_with_recipe_id(
            job_id="job123",
            recipe_id="rec_recipe456"
        )
        
        assert success is False
    
    def test_save_recipe_and_update_job_success(self, recipe_persist_service, sample_recipe_json, mock_firestore_db):
        """Test complete workflow success"""
        mock_db, mock_recipes_collection, mock_ingest_collection, mock_recipes_document, mock_ingest_document = mock_firestore_db
        
        # Mock UUID generation
        test_uuid = "test-uuid-123"
        with patch('uuid.uuid4', return_value=test_uuid):
            with patch('services.recipe_persist_service.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

                recipe_id = recipe_persist_service.save_recipe_and_update_job(
                    recipe_json=sample_recipe_json,
                    job_id="job123",
                    owner_uid="user123",
                    source_url="https://tiktok.com/test"
                )

        expected_recipe_id = f"rec_{test_uuid}"
        assert recipe_id == expected_recipe_id
        
        # Verify both operations were called
        mock_recipes_document.set.assert_called_once()
        mock_ingest_document.update.assert_called_once()
    
    def test_save_recipe_and_update_job_recipe_save_fails(self, recipe_persist_service, sample_recipe_json, mock_firestore_db):
        """Test workflow when recipe saving fails"""
        mock_db, mock_recipes_collection, mock_ingest_collection, mock_recipes_document, mock_ingest_document = mock_firestore_db
        
        # Mock recipe save failure
        mock_recipes_document.set.side_effect = Exception("Recipe save failed")

        recipe_id = recipe_persist_service.save_recipe_and_update_job(
            recipe_json=sample_recipe_json,
            job_id="job123",
            owner_uid="user123"
        )

        assert recipe_id is None
        
        # Verify only recipe save was attempted, job update was not
        mock_recipes_document.set.assert_called_once()
        mock_ingest_document.update.assert_not_called()

    def test_save_recipe_and_update_job_job_update_fails(self, recipe_persist_service, sample_recipe_json, mock_firestore_db):
        """Test workflow when job update fails"""
        mock_db, mock_recipes_collection, mock_ingest_collection, mock_recipes_document, mock_ingest_document = mock_firestore_db
        
        # Mock job update failure
        mock_ingest_document.update.side_effect = Exception("Job update failed")

        recipe_id = recipe_persist_service.save_recipe_and_update_job(
            recipe_json=sample_recipe_json,
            job_id="job123",
            owner_uid="user123"
        )

        assert recipe_id is None
        
        # Verify both operations were attempted
        mock_recipes_document.set.assert_called_once()
        mock_ingest_document.update.assert_called_once()
    
    def test_get_recipe_by_id_success(self, recipe_persist_service, mock_firestore_db):
        """Test successful recipe retrieval"""
        mock_db, mock_recipes_collection, mock_ingest_collection, mock_recipes_document, mock_ingest_document = mock_firestore_db
        
        # Mock existing document
        mock_doc_data = {
            "recipe_json": {"title": "Test Recipe"},
            "owner_uid": "user123",
            "createdAt": "2025-01-01T12:00:00Z"
        }
        mock_recipes_document.get.return_value = Mock(exists=True, to_dict=lambda: mock_doc_data)

        result = recipe_persist_service.get_recipe_by_id("rec_recipe123")

        assert result == mock_doc_data
        
        # Verify get was called
        mock_recipes_document.get.assert_called_once()
    
    def test_get_recipe_by_id_not_found(self, recipe_persist_service, mock_firestore_db):
        """Test recipe retrieval when document doesn't exist"""
        mock_db, mock_recipes_collection, mock_ingest_collection, mock_recipes_document, mock_ingest_document = mock_firestore_db
        
        # Mock non-existing document
        mock_recipes_document.get.return_value = Mock(exists=False)
        
        result = recipe_persist_service.get_recipe_by_id("rec_recipe123")
        
        assert result is None
    
    def test_get_recipe_by_id_firestore_error(self, recipe_persist_service, mock_firestore_db):
        """Test recipe retrieval with Firestore error"""
        mock_db, mock_recipes_collection, mock_ingest_collection, mock_recipes_document, mock_ingest_document = mock_firestore_db
        
        # Mock Firestore error
        mock_recipes_document.get.side_effect = Exception("Firestore error")
        
        result = recipe_persist_service.get_recipe_by_id("rec_recipe123")
        
        assert result is None
    
    def test_get_recipe_by_id_no_firestore(self):
        """Test recipe retrieval without Firestore connection"""
        with patch('services.recipe_persist_service.get_firestore_db', return_value=None):
            service = RecipePersistService()
            result = service.get_recipe_by_id("rec_recipe123")
            assert result is None
    
    def test_recipe_id_format(self, recipe_persist_service, sample_recipe_json, mock_firestore_db):
        """Test that recipe IDs are generated with correct format"""
        mock_db, mock_recipes_collection, mock_ingest_collection, mock_recipes_document, mock_ingest_document = mock_firestore_db
        
        # Mock UUID generation
        test_uuid = "550e8400-e29b-41d4-a716-446655440000"
        with patch('uuid.uuid4', return_value=test_uuid):
            recipe_id = recipe_persist_service.save_recipe(
                recipe_json=sample_recipe_json,
                owner_uid="user123"
            )
        
        expected_recipe_id = f"rec_{test_uuid}"
        assert recipe_id == expected_recipe_id
        assert recipe_id.startswith("rec_")
        assert len(recipe_id) == 40  # "rec_" + 36 char UUID
    
    def test_recipe_document_structure(self, recipe_persist_service, sample_recipe_json, mock_firestore_db):
        """Test that recipe document has correct structure"""
        mock_db, mock_recipes_collection, mock_ingest_collection, mock_recipes_document, mock_ingest_document = mock_firestore_db
        
        with patch('uuid.uuid4', return_value="test-uuid"):
            with patch('services.recipe_persist_service.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
                
                recipe_persist_service.save_recipe(
                    recipe_json=sample_recipe_json,
                    owner_uid="user123",
                    source_url="https://tiktok.com/test",
                    original_job_id="job123"
                )
        
        # Verify document structure
        mock_recipes_document.set.assert_called_once()
        call_args = mock_recipes_document.set.call_args[0][0]
        
        required_fields = ["recipe_json", "owner_uid", "createdAt", "updatedAt", "source_url", "original_job_id", "status"]
        for field in required_fields:
            assert field in call_args
        
        assert call_args["recipe_json"] == sample_recipe_json
        assert call_args["owner_uid"] == "user123"
        assert call_args["source_url"] == "https://tiktok.com/test"
        assert call_args["original_job_id"] == "job123"
        assert call_args["status"] == "ACTIVE" 
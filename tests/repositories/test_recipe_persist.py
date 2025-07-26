#!/usr/bin/env python3
"""
Tests for recipe persistence flow (Task 903)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from services.recipe_persist_service import RecipePersistService


class MockFirestoreDoc:
    def __init__(self, exists=True, data=None):
        self.exists = exists
        self.data = data or {}
        self.set_called = False
        self.update_called = False
        self.set_args = None
        self.update_args = None
        self.set_side_effect = None
        self.update_side_effect = None
        self.get_side_effect = None
    
    def set(self, data):
        if self.set_side_effect:
            raise self.set_side_effect
        self.set_called = True
        self.set_args = data
        return True
    
    def update(self, data):
        if self.update_side_effect:
            raise self.update_side_effect
        self.update_called = True
        self.update_args = data
        return True
    
    def get(self):
        if self.get_side_effect:
            raise self.get_side_effect
        return self
    
    def to_dict(self):
        return self.data


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
def mock_firestore_db():
    """Mock Firestore database"""
    mock_db = MockFirestore()
    
    # Mock recipes collection
    mock_recipes_collection = Mock()
    mock_recipes_document = MockFirestoreDoc()
    mock_recipes_collection.document.return_value = mock_recipes_document
    mock_db.collections["recipes"] = mock_recipes_collection
    
    # Mock ingest_jobs collection
    mock_ingest_collection = Mock()
    mock_ingest_document = MockFirestoreDoc()
    mock_ingest_collection.document.return_value = mock_ingest_document
    mock_db.collections["ingest_jobs"] = mock_ingest_collection
    
    return mock_db


@pytest.fixture
def sample_recipe_json():
    """Sample recipe JSON for testing"""
    return {
        "title": "Test Recipe",
        "description": "A test recipe for unit testing",
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
def recipe_persist_service(mock_firestore_db):
    """RecipePersistService instance with mocked Firestore"""
    with patch('services.recipe_persist_service.get_firestore_db', return_value=mock_firestore_db):
        return RecipePersistService()


class TestRecipePersistenceFlow:
    """Test the complete recipe persistence flow"""
    
    def test_save_recipe_creates_recipe_document(self, recipe_persist_service, sample_recipe_json, mock_firestore_db):
        """Test that save_recipe creates a new recipe document"""
        # Arrange
        owner_uid = "test_user_123"
        source_url = "https://www.tiktok.com/@user/video/123"
        original_job_id = "job_123"
        
        # Act
        recipe_id = recipe_persist_service.save_recipe(
            recipe_json=sample_recipe_json,
            owner_uid=owner_uid,
            source_url=source_url,
            original_job_id=original_job_id
        )
        
        # Assert
        assert recipe_id is not None
        assert recipe_id.startswith("rec_")
        assert len(recipe_id) == 40  # "rec_" + 36 char UUID
        
        # Verify recipe document was created
        mock_recipes_doc = mock_firestore_db.collections["recipes"].document.return_value
        assert mock_recipes_doc.set_called
        
        # Verify document content
        set_args = mock_recipes_doc.set_args
        assert set_args["recipe_json"] == sample_recipe_json
        assert set_args["owner_uid"] == owner_uid
        assert set_args["source_url"] == source_url
        assert set_args["original_job_id"] == original_job_id
        assert set_args["status"] == "ACTIVE"
        assert "createdAt" in set_args
        assert "updatedAt" in set_args
    
    def test_save_recipe_generates_unique_ids(self, recipe_persist_service, sample_recipe_json):
        """Test that save_recipe generates unique recipe IDs"""
        # Act
        recipe_id_1 = recipe_persist_service.save_recipe(
            recipe_json=sample_recipe_json,
            owner_uid="user1"
        )
        recipe_id_2 = recipe_persist_service.save_recipe(
            recipe_json=sample_recipe_json,
            owner_uid="user2"
        )
        
        # Assert
        assert recipe_id_1 != recipe_id_2
        assert recipe_id_1.startswith("rec_")
        assert recipe_id_2.startswith("rec_")
    
    def test_update_job_with_recipe_id_updates_job_document(self, recipe_persist_service, mock_firestore_db):
        """Test that update_job_with_recipe_id updates the job document"""
        # Arrange
        job_id = "test_job_123"
        recipe_id = "rec_test_recipe_456"
        
        # Act
        success = recipe_persist_service.update_job_with_recipe_id(job_id, recipe_id)
        
        # Assert
        assert success is True
        
        # Verify job document was updated
        mock_ingest_doc = mock_firestore_db.collections["ingest_jobs"].document.return_value
        assert mock_ingest_doc.update_called
        
        # Verify update content
        update_args = mock_ingest_doc.update_args
        assert update_args["status"] == "COMPLETED"
        assert update_args["recipe_id"] == recipe_id
        assert "updatedAt" in update_args
    
    def test_save_recipe_and_update_job_complete_flow(self, recipe_persist_service, sample_recipe_json, mock_firestore_db):
        """Test the complete save_recipe_and_update_job flow"""
        # Arrange
        job_id = "test_job_123"
        owner_uid = "test_user_123"
        source_url = "https://www.tiktok.com/@user/video/123"
        
        # Act
        recipe_id = recipe_persist_service.save_recipe_and_update_job(
            recipe_json=sample_recipe_json,
            job_id=job_id,
            owner_uid=owner_uid,
            source_url=source_url
        )
        
        # Assert
        assert recipe_id is not None
        assert recipe_id.startswith("rec_")
        
        # Verify recipe document was created
        mock_recipes_doc = mock_firestore_db.collections["recipes"].document.return_value
        assert mock_recipes_doc.set_called
        
        # Verify job document was updated
        mock_ingest_doc = mock_firestore_db.collections["ingest_jobs"].document.return_value
        assert mock_ingest_doc.update_called
        
        # Verify recipe document content
        recipe_set_args = mock_recipes_doc.set_args
        assert recipe_set_args["recipe_json"] == sample_recipe_json
        assert recipe_set_args["owner_uid"] == owner_uid
        assert recipe_set_args["source_url"] == source_url
        assert recipe_set_args["original_job_id"] == job_id
        
        # Verify job update content
        job_update_args = mock_ingest_doc.update_args
        assert job_update_args["status"] == "COMPLETED"
        assert job_update_args["recipe_id"] == recipe_id
    
    def test_save_recipe_and_update_job_recipe_save_fails(self, recipe_persist_service, sample_recipe_json, mock_firestore_db):
        """Test save_recipe_and_update_job when recipe save fails"""
        # Arrange
        mock_recipes_doc = mock_firestore_db.collections["recipes"].document.return_value
        mock_recipes_doc.set_side_effect = Exception("Firestore error")
        
        # Act
        recipe_id = recipe_persist_service.save_recipe_and_update_job(
            recipe_json=sample_recipe_json,
            job_id="test_job_123",
            owner_uid="test_user_123"
        )
        
        # Assert
        assert recipe_id is None
        
        # Verify job was not updated
        mock_ingest_doc = mock_firestore_db.collections["ingest_jobs"].document.return_value
        assert not mock_ingest_doc.update_called
    
    def test_save_recipe_and_update_job_job_update_fails(self, recipe_persist_service, sample_recipe_json, mock_firestore_db):
        """Test save_recipe_and_update_job when job update fails"""
        # Arrange
        mock_ingest_doc = mock_firestore_db.collections["ingest_jobs"].document.return_value
        mock_ingest_doc.update_side_effect = Exception("Firestore error")
        
        # Act
        recipe_id = recipe_persist_service.save_recipe_and_update_job(
            recipe_json=sample_recipe_json,
            job_id="test_job_123",
            owner_uid="test_user_123"
        )
        
        # Assert
        assert recipe_id is None
        
        # Verify recipe was created but job update failed
        mock_recipes_doc = mock_firestore_db.collections["recipes"].document.return_value
        assert mock_recipes_doc.set_called
        # The update was attempted but failed, so we don't check update_called
    
    def test_get_recipe_by_id_success(self, recipe_persist_service, sample_recipe_json, mock_firestore_db):
        """Test get_recipe_by_id when recipe exists"""
        # Arrange
        recipe_id = "rec_test_recipe_123"
        mock_doc = MockFirestoreDoc(exists=True, data=sample_recipe_json)
        mock_firestore_db.collections["recipes"].document.return_value = mock_doc
        
        # Act
        recipe = recipe_persist_service.get_recipe_by_id(recipe_id)
        
        # Assert
        assert recipe == sample_recipe_json
        mock_firestore_db.collections["recipes"].document.assert_called_with(recipe_id)
    
    def test_get_recipe_by_id_not_found(self, recipe_persist_service, mock_firestore_db):
        """Test get_recipe_by_id when recipe doesn't exist"""
        # Arrange
        recipe_id = "rec_nonexistent_recipe"
        mock_doc = MockFirestoreDoc(exists=False)
        mock_firestore_db.collections["recipes"].document.return_value = mock_doc
        
        # Act
        recipe = recipe_persist_service.get_recipe_by_id(recipe_id)
        
        # Assert
        assert recipe is None
    
    def test_get_recipe_by_id_firestore_error(self, recipe_persist_service, mock_firestore_db):
        """Test get_recipe_by_id when Firestore error occurs"""
        # Arrange
        recipe_id = "rec_test_recipe_123"
        mock_doc = MockFirestoreDoc()
        mock_doc.get_side_effect = Exception("Firestore error")
        mock_firestore_db.collections["recipes"].document.return_value = mock_doc
        
        # Act
        recipe = recipe_persist_service.get_recipe_by_id(recipe_id)
        
        # Assert
        assert recipe is None
    
    def test_service_without_firestore_connection(self, sample_recipe_json):
        """Test service behavior when no Firestore connection is available"""
        # Arrange
        with patch('services.recipe_persist_service.get_firestore_db', return_value=None):
            service = RecipePersistService()
        
        # Act & Assert
        recipe_id = service.save_recipe(sample_recipe_json, "test_user")
        assert recipe_id is None
        
        success = service.update_job_with_recipe_id("job_123", "recipe_123")
        assert success is False
        
        recipe = service.get_recipe_by_id("recipe_123")
        assert recipe is None
    
    def test_recipe_document_structure(self, recipe_persist_service, sample_recipe_json, mock_firestore_db):
        """Test that recipe document has the correct structure"""
        # Arrange
        owner_uid = "test_user_123"
        source_url = "https://www.tiktok.com/@user/video/123"
        original_job_id = "job_123"
        
        # Act
        recipe_id = recipe_persist_service.save_recipe(
            recipe_json=sample_recipe_json,
            owner_uid=owner_uid,
            source_url=source_url,
            original_job_id=original_job_id
        )
        
        # Assert
        mock_recipes_doc = mock_firestore_db.collections["recipes"].document.return_value
        set_args = mock_recipes_doc.set_args
        
        # Check required fields
        required_fields = ["recipe_json", "owner_uid", "createdAt", "updatedAt", "source_url", "original_job_id", "status"]
        for field in required_fields:
            assert field in set_args
        
        # Check field types and values
        assert set_args["recipe_json"] == sample_recipe_json
        assert set_args["owner_uid"] == owner_uid
        assert set_args["source_url"] == source_url
        assert set_args["original_job_id"] == original_job_id
        assert set_args["status"] == "ACTIVE"
        
        # Check timestamp format
        assert isinstance(set_args["createdAt"], str)
        assert isinstance(set_args["updatedAt"], str)
        
        # Verify timestamps are ISO format
        datetime.fromisoformat(set_args["createdAt"])
        datetime.fromisoformat(set_args["updatedAt"])
    
    def test_job_update_structure(self, recipe_persist_service, mock_firestore_db):
        """Test that job update has the correct structure"""
        # Arrange
        job_id = "test_job_123"
        recipe_id = "rec_test_recipe_456"
        
        # Act
        success = recipe_persist_service.update_job_with_recipe_id(job_id, recipe_id)
        
        # Assert
        assert success is True
        
        mock_ingest_doc = mock_firestore_db.collections["ingest_jobs"].document.return_value
        update_args = mock_ingest_doc.update_args
        
        # Check required fields
        required_fields = ["status", "recipe_id", "updatedAt"]
        for field in required_fields:
            assert field in update_args
        
        # Check field values
        assert update_args["status"] == "COMPLETED"
        assert update_args["recipe_id"] == recipe_id
        
        # Check timestamp format
        assert isinstance(update_args["updatedAt"], str)
        datetime.fromisoformat(update_args["updatedAt"])


class TestRecipePersistenceIntegration:
    """Integration tests for recipe persistence flow"""
    
    @patch('services.recipe_persist_service.get_firestore_db')
    def test_end_to_end_persistence_flow(self, mock_get_db, sample_recipe_json):
        """Test the complete end-to-end persistence flow"""
        # Arrange
        mock_db = MockFirestore()
        mock_get_db.return_value = mock_db
        
        # Set up the collections properly
        mock_recipes_collection = Mock()
        mock_ingest_collection = Mock()
        
        # Set up the mock to return the recipe data when get_recipe_by_id is called
        mock_recipe_doc = MockFirestoreDoc(exists=True, data={
            "recipe_json": sample_recipe_json,
            "owner_uid": "test_user_123",
            "source_url": "https://www.tiktok.com/@user/video/123",
            "original_job_id": "test_job_123"
        })
        mock_recipes_collection.document.return_value = mock_recipe_doc
        
        mock_ingest_doc = MockFirestoreDoc()
        mock_ingest_collection.document.return_value = mock_ingest_doc
        
        mock_db.collections["recipes"] = mock_recipes_collection
        mock_db.collections["ingest_jobs"] = mock_ingest_collection
        
        service = RecipePersistService()
        job_id = "test_job_123"
        owner_uid = "test_user_123"
        source_url = "https://www.tiktok.com/@user/video/123"
        
        # Act
        recipe_id = service.save_recipe_and_update_job(
            recipe_json=sample_recipe_json,
            job_id=job_id,
            owner_uid=owner_uid,
            source_url=source_url
        )
        
        # Assert
        assert recipe_id is not None
        assert recipe_id.startswith("rec_")
        
        # Verify recipe document exists
        recipe_doc = service.get_recipe_by_id(recipe_id)
        assert recipe_doc is not None
        assert recipe_doc["recipe_json"] == sample_recipe_json
        assert recipe_doc["owner_uid"] == owner_uid
        assert recipe_doc["source_url"] == source_url
        assert recipe_doc["original_job_id"] == job_id
    
    def test_persistence_flow_with_error_handling(self, sample_recipe_json):
        """Test persistence flow with various error scenarios"""
        # Test with no Firestore connection
        with patch('services.recipe_persist_service.get_firestore_db', return_value=None):
            service = RecipePersistService()
            
            recipe_id = service.save_recipe_and_update_job(
                recipe_json=sample_recipe_json,
                job_id="test_job_123",
                owner_uid="test_user_123"
            )
            
            assert recipe_id is None
        
        # Test with Firestore errors
        mock_db = MockFirestore()
        # Set up the collections properly
        mock_recipes_collection = Mock()
        mock_recipes_document = MockFirestoreDoc()
        mock_recipes_document.set_side_effect = Exception("Database error")
        mock_recipes_collection.document.return_value = mock_recipes_document
        mock_db.collections["recipes"] = mock_recipes_collection
        
        with patch('services.recipe_persist_service.get_firestore_db', return_value=mock_db):
            service = RecipePersistService()
            
            recipe_id = service.save_recipe_and_update_job(
                recipe_json=sample_recipe_json,
                job_id="test_job_123",
                owner_uid="test_user_123"
            )
            
            assert recipe_id is None 
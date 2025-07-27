import pytest
from unittest.mock import patch, Mock, mock_open
from datetime import datetime, timezone
import json

from services.llm_refine_service import LLMRefineService, LLMRefineError
from services.firestore_recipe_service import FirestoreRecipeService

class TestLLMIntegration:
    
    @pytest.fixture
    def mock_firestore_db(self):
        """Mock Firestore database"""
        mock_db = Mock()
        mock_job_doc = Mock()
        mock_recipe_doc = Mock()
        
        # Mock job document
        mock_job_doc.get.return_value.to_dict.return_value = {
            "status": "OCR_DONE",
            "title": "Test Recipe",
            "transcript": "This is a test transcript",
            "ocr_results": [
                {
                    "timestamp": 1.0,
                    "text_blocks": [
                        {"text": "1 cup flour", "score": 0.9},
                        {"text": "2 tbsp sugar", "score": 0.8}
                    ]
                }
            ]
        }
        
        # Mock recipe document
        mock_recipe_doc.get.return_value.to_dict.return_value = {
            "status": "OCR_DONE",
            "recipe_id": "test-recipe-123"
        }
        
        # Mock collection and document methods
        mock_ingest_collection = Mock()
        mock_ingest_collection.document.return_value = mock_job_doc
        
        mock_recipe_collection = Mock()
        mock_recipe_collection.document.return_value = mock_recipe_doc
        
        mock_db.collection.side_effect = lambda name: {
            "ingest_jobs": mock_ingest_collection,
            "recipes": mock_recipe_collection
        }[name]
        
        return mock_db
    
    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM response with valid recipe JSON"""
        return {
            "choices": [
                {
                    "message": {
                        "content": """```json
{
  "title": "Test Recipe",
  "description": "A delicious test recipe",
  "ingredients": [
    {
      "name": "flour",
      "quantity": "1 cup"
    },
    {
      "name": "sugar",
      "quantity": "2 tbsp"
    }
  ],
  "instructions": [
    "Mix flour and sugar together",
    "Bake at 350F for 20 minutes"
  ],
  "prep_time": 5,
  "cook_time": 20,
  "servings": 4,
  "difficulty": 2,
  "tags": ["test", "quick"],
  "nutrition": {
    "calories": 300,
    "carbs": 40,
    "fat": 15,
    "protein": 8
  }
}
```"""
                    }
                }
            ]
        }
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    @patch('services.llm_refine_service.OpenAI')
    def test_llm_service_integration_success(self, mock_openai, mock_llm_response):
        """Test successful LLM service integration"""
        
        # Mock OpenAI
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = mock_llm_response["choices"][0]["message"]["content"]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        # Mock prompt template
        with patch('builtins.open', mock_open(read_data="Test prompt template")):
            service = LLMRefineService()
            
            # Test recipe refinement
            result, error = service.refine_recipe(
                title="Test Recipe",
                transcript="This is a test transcript",
                ocr_results=[
                    {
                        "timestamp": 1.0,
                        "text_blocks": [
                            {"text": "1 cup flour", "score": 0.9},
                            {"text": "2 tbsp sugar", "score": 0.8}
                        ]
                    }
                ],
                source_url="https://tiktok.com/@user/video/123",
                tiktok_author="testuser"
            )
            
            # Verify LLM was called
            mock_client.chat.completions.create.assert_called_once()
            
            # Verify result structure
            assert result["title"] == "Test Recipe"
            assert result["source_url"] == "https://tiktok.com/@user/video/123"
            assert result["tiktok_author"] == "testuser"
            assert len(result["ingredients"]) == 2
            assert len(result["instructions"]) == 2
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    @patch('services.llm_refine_service.OpenAI')
    def test_llm_service_integration_validation_failure(self, mock_openai):
        """Test LLM service integration with validation failure"""
        
        # Mock OpenAI to return invalid JSON
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"title": "", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        # Mock prompt template
        with patch('builtins.open', mock_open(read_data="Test prompt template")):
            service = LLMRefineService()
            
            # Test recipe refinement with validation failure
            result, error = service.refine_recipe(
                title="Test Recipe",
                transcript="This is a test transcript",
                ocr_results=[
                    {
                        "timestamp": 1.0,
                        "text_blocks": [
                            {"text": "1 cup flour", "score": 0.9}
                        ]
                    }
                ]
            )
            
            # Verify LLM was called
            mock_client.chat.completions.create.assert_called_once()
            
            # Verify validation failure
            assert result is None
            assert "Title cannot be empty" in error
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    @patch('services.llm_refine_service.OpenAI')
    def test_llm_service_integration_api_error(self, mock_openai):
        """Test LLM service integration with API error"""
        
        # Mock OpenAI to throw an error
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("OpenAI API Error")
        mock_openai.return_value = mock_client
        
        # Mock prompt template
        with patch('builtins.open', mock_open(read_data="Test prompt template")):
            service = LLMRefineService()
            
            # Test recipe refinement with API error
            result, error = service.refine_recipe(
                title="Test Recipe",
                transcript="This is a test transcript",
                ocr_results=[
                    {
                        "timestamp": 1.0,
                        "text_blocks": [
                            {"text": "1 cup flour", "score": 0.9}
                        ]
                    }
                ]
            )
            
            # Verify API error handling
            assert result is None
            assert "LLM processing error" in error
            
            # Verify LLM was called
            mock_client.chat.completions.create.assert_called()
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_llm_service_error_handling(self):
        """Test LLM service error handling"""
        
        # Test missing API key
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(LLMRefineError, match="OpenAI API key not found"):
                LLMRefineService()
        
        # Test missing prompt template
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
                with pytest.raises(LLMRefineError, match="Prompt template file not found"):
                    LLMRefineService()
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_llm_service_ocr_handling(self):
        """Test LLM service OCR text preparation"""
        
        service = LLMRefineService()
        
        # Test empty OCR results
        result = service._prepare_ocr_text([])
        assert result == "No OCR text detected."
        
        # Test OCR results with no readable text
        ocr_results = [
            {
                "timestamp": 1.0,
                "text_blocks": [
                    {"text": "", "score": 0.9},
                    {"text": "   ", "score": 0.8}
                ]
            }
        ]
        result = service._prepare_ocr_text(ocr_results)
        assert result == "No readable text detected."
        
        # Test valid OCR results
        ocr_results = [
            {
                "timestamp": 1.0,
                "text_blocks": [
                    {"text": "1 cup flour", "score": 0.9},
                    {"text": "2 tbsp sugar", "score": 0.8}
                ]
            }
        ]
        result = service._prepare_ocr_text(ocr_results)
        assert "Frame at 1.0s: 1 cup flour | 2 tbsp sugar" in result
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_llm_service_json_extraction(self):
        """Test LLM service JSON extraction"""
        
        service = LLMRefineService()
        
        # Test JSON extraction from code block
        response = """Here's the recipe:
```json
{"title": "Test Recipe", "ingredients": []}
```
Hope this helps!"""
        
        result, error = service._extract_json_from_response(response)
        assert result["title"] == "Test Recipe"
        assert result["ingredients"] == []
        
        # Test JSON extraction from plain JSON
        response = '{"title": "Test Recipe", "ingredients": []}'
        result, error = service._extract_json_from_response(response)
        assert result["title"] == "Test Recipe"
        
        # Test invalid JSON
        response = "This is not valid JSON"
        result, error = service._extract_json_from_response(response)
        assert result is None
        assert "Invalid JSON format" in error
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_llm_service_validation_retry(self):
        """Test LLM service validation retry mechanism"""
        
        with patch('builtins.open', mock_open(read_data="Test prompt template")):
            with patch('services.llm_refine_service.OpenAI') as mock_openai:
                mock_client = Mock()
                # First call returns invalid JSON, second call returns valid data
                mock_response1 = Mock()
                mock_response1.choices = [Mock()]
                mock_response1.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]'
                
                mock_response2 = Mock()
                mock_response2.choices = [Mock()]
                mock_response2.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                
                mock_client.chat.completions.create.side_effect = [mock_response1, mock_response2]
                mock_openai.return_value = mock_client
                
                service = LLMRefineService()
                recipe_json, parse_error = service.refine_with_validation_retry(
                    title="Test Recipe",
                    transcript="This is a test transcript",
                    ocr_results=[
                        {
                            "timestamp": 1.0,
                            "text_blocks": [
                                {"text": "1 cup flour", "score": 0.9}
                            ]
                        }
                    ],
                    max_validation_retries=1
                )
                
                assert recipe_json["title"] == "Test Recipe"
                assert parse_error is None
                assert mock_client.chat.completions.create.call_count == 2
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_firestore_recipe_service_integration(self, mock_firestore_db):
        """Test Firestore recipe service integration with LLM results"""
        
        service = FirestoreRecipeService(mock_firestore_db)
        
        # Test updating recipe with LLM results
        recipe_json = {
            "title": "Test Recipe",
            "ingredients": [{"name": "flour", "quantity": "1 cup"}],
            "instructions": ["Mix ingredients"]
        }
        
        llm_metadata = {
            "llm_model_used": "gpt-4o-mini",
            "llm_processing_time_seconds": 5.2,
            "llm_processing_completed_at": "2025-01-01T12:00:00+00:00"
        }
        
        success = service.update_recipe_with_llm_results(
            job_id="test-job-123",
            recipe_id="test-recipe-123",
            recipe_json=recipe_json,
            llm_metadata=llm_metadata
        )
        
        assert success is True
        
        # Verify Firestore was called (only ingest_jobs, recipes is managed by RecipePersistService)
        mock_firestore_db.collection.assert_any_call("ingest_jobs")
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_end_to_end_llm_workflow(self, mock_firestore_db, mock_llm_response):
        """Test end-to-end LLM workflow integration"""
        
        with patch('services.llm_refine_service.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = mock_llm_response["choices"][0]["message"]["content"]
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            with patch('builtins.open', mock_open(read_data="Test prompt template")):
                # Initialize services
                llm_service = LLMRefineService()
                firestore_service = FirestoreRecipeService(mock_firestore_db)
                
                # Test LLM refinement
                recipe_json, parse_error = llm_service.refine_with_validation_retry(
                    title="Test Recipe",
                    transcript="This is a test transcript",
                    ocr_results=[
                        {
                            "timestamp": 1.0,
                            "text_blocks": [
                                {"text": "1 cup flour", "score": 0.9},
                                {"text": "2 tbsp sugar", "score": 0.8}
                            ]
                        }
                    ],
                    source_url="https://tiktok.com/@user/video/123",
                    tiktok_author="testuser"
                )
                
                # Verify LLM processing
                assert recipe_json["title"] == "Test Recipe"
                assert parse_error is None
                assert mock_client.chat.completions.create.called
                
                # Test Firestore persistence
                llm_metadata = {
                    "llm_model_used": "gpt-4o-mini",
                    "llm_processing_time_seconds": 5.2,
                    "llm_processing_completed_at": "2025-01-01T12:00:00+00:00"
                }
                
                success = firestore_service.update_recipe_with_llm_results(
                    job_id="test-job-123",
                    recipe_id="test-recipe-123",
                    recipe_json=recipe_json,
                    llm_metadata=llm_metadata
                )
                
                assert success is True
                
                # Verify Firestore calls (only ingest_jobs, recipes is managed by RecipePersistService)
                mock_firestore_db.collection.assert_any_call("ingest_jobs") 
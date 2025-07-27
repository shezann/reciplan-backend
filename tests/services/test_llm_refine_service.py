import pytest
import os
import json
from unittest.mock import patch, MagicMock, mock_open
from services.llm_refine_service import LLMRefineService, LLMRefineError

class TestLLMRefineService:
    """Tests for LLMRefineService"""

    def test_init_success(self):
        """Test successful initialization"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            service = LLMRefineService()
            assert service.api_key == 'test-key'
            assert service.model == 'gpt-4o-mini'

    def test_init_missing_api_key(self):
        """Test initialization without API key"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(LLMRefineError, match="OpenAI API key not found"):
                LLMRefineService()

    def test_load_prompt_template_success(self):
        """Test successful prompt template loading"""
        mock_content = "Test prompt template"
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data=mock_content)):
                service = LLMRefineService()
                assert service.prompt_template == mock_content

    def test_load_prompt_template_file_not_found(self):
        """Test prompt template file not found"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', side_effect=FileNotFoundError()):
                with pytest.raises(LLMRefineError, match="Prompt template file not found"):
                    LLMRefineService()

    def test_prepare_ocr_text_with_results(self):
        """Test OCR text preparation with results"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                service = LLMRefineService()
                ocr_results = [
                    {
                        "timestamp": 1.0,
                        "text_blocks": [
                            {"text": "1 cup flour"},
                            {"text": "2 tbsp sugar"}
                        ]
                    }
                ]
                result = service._prepare_ocr_text(ocr_results)
                assert "1 cup flour" in result
                assert "2 tbsp sugar" in result

    def test_prepare_ocr_text_empty_results(self):
        """Test OCR text preparation with empty results"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                service = LLMRefineService()
                result = service._prepare_ocr_text([])
                assert result == "No OCR text detected."

    def test_prepare_ocr_text_no_readable_text(self):
        """Test OCR text preparation with no readable text"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                service = LLMRefineService()
                ocr_results = [
                    {
                        "timestamp": 1.0,
                        "text_blocks": []
                    }
                ]
                result = service._prepare_ocr_text(ocr_results)
                assert result == "No readable text detected."

    def test_extract_json_from_response_json_block(self):
        """Test JSON extraction from response with JSON block"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                service = LLMRefineService()
                response = '```json\n{"title": "Test Recipe"}\n```'
                result, error = service._extract_json_from_response(response)
                assert result["title"] == "Test Recipe"
                assert error is None

    def test_extract_json_from_response_plain_json(self):
        """Test JSON extraction from response with plain JSON"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                service = LLMRefineService()
                response = '{"title": "Test Recipe"}'
                result, error = service._extract_json_from_response(response)
                assert result["title"] == "Test Recipe"
                assert error is None

    def test_extract_json_from_response_invalid_json(self):
        """Test JSON extraction from response with invalid JSON"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                service = LLMRefineService()
                response = 'invalid json'
                result, error = service._extract_json_from_response(response)
                assert result is None
                assert "Invalid JSON format" in error

    def test_validate_recipe_data_valid(self):
        """Test recipe data validation with valid data"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                service = LLMRefineService()
                recipe_data = {
                    "title": "Test Recipe",
                    "ingredients": [{"name": "flour", "quantity": "1 cup"}],
                    "instructions": ["Mix ingredients"]
                }
                is_valid, error = service._validate_recipe_data(recipe_data)
                assert is_valid
                assert error is None

    def test_validate_recipe_data_invalid(self):
        """Test recipe data validation with invalid data"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                service = LLMRefineService()
                recipe_data = {"title": ""}  # Missing required fields
                is_valid, error = service._validate_recipe_data(recipe_data)
                assert not is_valid
                assert "Missing required field" in error

    def test_create_reprompt_message(self):
        """Test reprompt message creation"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                service = LLMRefineService()
                error = "JSON parsing error"
                original_response = "invalid response"
                result = service._create_reprompt_message(error, original_response)
                assert "JSON parsing error" in result
                assert "invalid response" in result

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_recipe_success(self, mock_openai_class):
        """Test successful recipe refinement"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                result, error = service.refine_recipe("Test", "transcript", [], "url", "author")
                print(f"Result: {result}")
                print(f"Error: {error}")
                assert result is not None
                assert result["title"] == "Test Recipe"
                assert error is None

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_recipe_validation_failure(self, mock_openai_class):
        """Test recipe refinement with validation failure"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices[0].message.content = '{"title": "", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                result, error = service.refine_recipe("Test", "transcript", [], "url", "author")
                assert result is None
                assert "Title cannot be empty" in error

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_with_validation_retry_success_first_attempt(self, mock_openai_class):
        """Test validation retry with success on first attempt"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                result, error = service.refine_with_validation_retry("Test", "transcript", [], "url", "author")
                assert result["title"] == "Test Recipe"
                assert error is None

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_with_validation_retry_success_second_attempt(self, mock_openai_class):
        """Test validation retry with success on second attempt"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                
                # First response is invalid JSON, second is valid
                mock_response1 = MagicMock()
                mock_response1.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]'
                mock_response2 = MagicMock()
                mock_response2.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                mock_client.chat.completions.create.side_effect = [mock_response1, mock_response2]
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                result, error = service.refine_with_validation_retry("Test", "transcript", [], "url", "author", max_validation_retries=1)
                assert result["title"] == "Test Recipe"
                assert error is None

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_with_validation_retry_all_attempts_fail(self, mock_openai_class):
        """Test validation retry with all attempts failing"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices[0].message.content = '{"title": "", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                result, error = service.refine_with_validation_retry("Test", "transcript", [], "url", "author", max_validation_retries=1)
                assert result is None
                assert "Title cannot be empty" in error

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_with_validation_retry_api_error(self, mock_openai_class):
        """Test validation retry with API error"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_client.chat.completions.create.side_effect = Exception("API error")
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                result, error = service.refine_with_validation_retry("Test", "transcript", [], "url", "author", max_validation_retries=1)
                assert result is None
                assert "LLM processing error" in error

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_with_retry_success_on_second_attempt(self, mock_openai_class):
        """Test general retry with success on second attempt"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                result, error = service.refine_with_retry("Test", "transcript", [], "url", "author", max_retries=1)
                assert result["title"] == "Test Recipe"
                assert error is None

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_with_retry_all_attempts_fail(self, mock_openai_class):
        """Test general retry with all attempts failing"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_client.chat.completions.create.side_effect = Exception("API error")
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                result, error = service.refine_with_retry("Test", "transcript", [], "url", "author", max_retries=1)
                assert result is None
                assert "LLM processing error" in error

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_with_empty_transcript(self, mock_openai_class):
        """Test refinement with empty transcript"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                result, error = service.refine_recipe("Test", "", [], "url", "author")
                assert result["title"] == "Test Recipe"
                assert error is None

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_with_long_title(self, mock_openai_class):
        """Test refinement with long title"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                long_title = "A" * 1000
                result, error = service.refine_recipe(long_title, "transcript", [], "url", "author")
                assert result["title"] == "Test Recipe"
                assert error is None

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_with_special_characters(self, mock_openai_class):
        """Test refinement with special characters"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                result, error = service.refine_recipe("Test 🍕", "transcript", [], "url", "author")
                assert result["title"] == "Test Recipe"
                assert error is None

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_with_max_validation_retries_zero(self, mock_openai_class):
        """Test refinement with zero validation retries"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                result, error = service.refine_with_validation_retry("Test", "transcript", [], "url", "author", max_validation_retries=0)
                assert result["title"] == "Test Recipe"
                assert error is None

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_with_large_ocr_results(self, mock_openai_class):
        """Test refinement with large OCR results"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                large_ocr = [{"timestamp": i, "text_blocks": [{"text": f"text {i}"}]} for i in range(100)]
                result, error = service.refine_recipe("Test", "transcript", large_ocr, "url", "author")
                assert result["title"] == "Test Recipe"
                assert error is None

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_with_malformed_ocr_results(self, mock_openai_class):
        """Test refinement with malformed OCR results"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                malformed_ocr = [{"invalid": "data"}]
                result, error = service.refine_recipe("Test", "transcript", malformed_ocr, "url", "author")
                assert result["title"] == "Test Recipe"
                assert error is None

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_with_none_values(self, mock_openai_class):
        """Test refinement with None values"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                result, error = service.refine_recipe("Test", None, None, None, None)
                assert result["title"] == "Test Recipe"
                assert error is None

    @patch('services.llm_refine_service.OpenAI')
    def test_refine_with_unicode_characters(self, mock_openai_class):
        """Test refinement with unicode characters"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('builtins.open', mock_open(read_data="test")):
                # Mock the OpenAI client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices[0].message.content = '{"title": "Test Recipe", "ingredients": [{"name": "flour", "quantity": "1 cup"}], "instructions": ["Mix ingredients"]}'
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai_class.return_value = mock_client
                
                service = LLMRefineService()
                result, error = service.refine_recipe("Test 🍕", "transcript", [], "url", "author")
                assert result["title"] == "Test Recipe"
                assert error is None 
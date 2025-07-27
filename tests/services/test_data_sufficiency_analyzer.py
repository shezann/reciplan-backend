"""
Tests for DataSufficiencyAnalyzer service (OpenAI-based)
"""

import pytest
from unittest.mock import patch, MagicMock
from services.data_sufficiency_analyzer import DataSufficiencyAnalyzer, SufficiencyResult


class TestDataSufficiencyAnalyzer:
    
    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = DataSufficiencyAnalyzer()
    
    @patch('services.data_sufficiency_analyzer.client')
    def test_sufficient_data_scenario(self, mock_client):
        """Test scenario with sufficient data - should skip OCR"""
        # Mock OpenAI response indicating sufficient data (v1.0+ format)
        mock_choice = MagicMock()
        mock_choice.message.content = """{
            "is_sufficient": true,
            "confidence_score": 0.85,
            "reasoning": "Contains detailed ingredients (chicken, oil, vegetables, garlic, onion, soy sauce) with measurements (2 tbsp, 1 pound, 1 cup, 2 cloves) and clear cooking steps (heat, add, cook, stir, serve) with timing (5 minutes, 3 minutes).",
            "estimated_completeness": {
                "ingredients": "complete",
                "instructions": "complete",
                "timing": "complete",
                "measurements": "complete"
            }
        }"""
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        title = "Easy Chicken Stir Fry Recipe"
        transcript = """
        Today I'm making a delicious chicken stir fry. First, I'll heat 2 tablespoons of oil 
        in a large pan. Then I'll add 1 pound of chicken breast, diced into small pieces. 
        Cook for 5 minutes until golden. Next, add 1 cup of mixed vegetables, 2 cloves of garlic, 
        and 1 onion. Stir everything together and cook for another 3 minutes. 
        Finally, add 2 tablespoons of soy sauce and serve over rice.
        """
        
        result = self.analyzer.analyze_sufficiency(title, transcript)
        
        assert result.is_sufficient is True
        assert result.confidence_score >= 0.8
        assert "complete" in result.estimated_completeness["ingredients"]
        assert "complete" in result.estimated_completeness["instructions"]
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('services.data_sufficiency_analyzer.client')
    def test_insufficient_data_scenario(self, mock_client):
        """Test scenario with insufficient data - should run OCR"""
        # Mock OpenAI response indicating insufficient data
        mock_choice = MagicMock()
        mock_choice.message.content = """{
                        "is_sufficient": false,
                        "confidence_score": 0.2,
                        "reasoning": "Very limited information. No specific ingredients, measurements, or cooking instructions provided. Only general enthusiasm about cooking.",
                        "estimated_completeness": {
                            "ingredients": "missing",
                            "instructions": "missing",
                            "timing": "missing",
                            "measurements": "missing"
                        }
                    }"""
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        title = "Cooking Video"
        transcript = "Hey everyone, today I'm cooking something delicious. It's really good!"
        
        result = self.analyzer.analyze_sufficiency(title, transcript)
        
        assert result.is_sufficient is False
        assert result.confidence_score < 0.6
        assert "missing" in result.estimated_completeness["ingredients"]
        assert "missing" in result.estimated_completeness["instructions"]
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('services.data_sufficiency_analyzer.client')
    def test_borderline_sufficient_scenario(self, mock_client):
        """Test borderline case with minimal sufficient data"""
        mock_choice = MagicMock()
        mock_choice.message.content = """{
                        "is_sufficient": true,
                        "confidence_score": 0.65,
                        "reasoning": "Contains basic recipe elements: pasta, oil, salt, pepper with measurements (1 cup, 2 tablespoons) and cooking steps (cook, add, mix, serve) with timing (10 minutes). Minimal but sufficient for a simple recipe.",
                        "estimated_completeness": {
                            "ingredients": "complete",
                            "instructions": "partial",
                            "timing": "partial",
                            "measurements": "complete"
                        }
                    }"""
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        title = "Quick Pasta Recipe"
        transcript = """
        Cook 1 cup pasta in boiling water for 10 minutes. 
        Add 2 tablespoons olive oil, salt, and pepper. Mix well and serve.
        """
        
        result = self.analyzer.analyze_sufficiency(title, transcript)
        
        assert result.is_sufficient is True
        assert result.confidence_score >= 0.6
        assert "complete" in result.estimated_completeness["ingredients"]
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('services.data_sufficiency_analyzer.client')
    def test_with_metadata(self, mock_client):
        """Test analysis with additional metadata"""
        mock_choice = MagicMock()
        mock_choice.message.content = """{
                        "is_sufficient": true,
                        "confidence_score": 0.75,
                        "reasoning": "Recipe details found in description provide sufficient information: flour, sugar with measurements (2 cups, 1 cup) and cooking instructions (mix, bake) with timing (30 minutes).",
                        "estimated_completeness": {
                            "ingredients": "complete",
                            "instructions": "partial",
                            "timing": "complete",
                            "measurements": "complete"
                        }
                    }"""
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        title = "Cooking Video"
        transcript = "Making something tasty"
        metadata = {
            'description': 'Recipe: 2 cups flour, 1 cup sugar, mix well and bake for 30 minutes'
        }
        
        result = self.analyzer.analyze_sufficiency(title, transcript, metadata)
        
        assert result.is_sufficient is True
        assert result.confidence_score >= 0.7
        assert "complete" in result.estimated_completeness["ingredients"]
        mock_client.chat.completions.create.assert_called_once()
    
    def test_empty_inputs(self):
        """Test with empty or None inputs"""
        result = self.analyzer.analyze_sufficiency("", "", None)
        
        assert result.is_sufficient is False
        assert result.confidence_score == 0.0
        assert result.reasoning == "No data provided for analysis"
        assert all(status == "missing" for status in result.estimated_completeness.values())
    
    @patch('services.data_sufficiency_analyzer.client')
    def test_analysis_summary(self, mock_client):
        """Test analysis summary generation"""
        mock_choice = MagicMock()
        mock_choice.message.content = """{
                        "is_sufficient": true,
                        "confidence_score": 0.7,
                        "reasoning": "Basic pasta recipe with sufficient details",
                        "estimated_completeness": {
                            "ingredients": "complete",
                            "instructions": "partial",
                            "timing": "missing",
                            "measurements": "complete"
                        }
                    }"""
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        title = "Pasta Recipe"
        transcript = "Cook pasta with oil, salt, and pepper. Add garlic and mix well."
        
        result = self.analyzer.analyze_sufficiency(title, transcript)
        summary = self.analyzer.get_analysis_summary(result)
        
        assert "is_sufficient" in summary
        assert "confidence_score" in summary
        assert "reasoning" in summary
        assert "estimated_completeness" in summary
        assert isinstance(summary["confidence_score"], float)
        assert isinstance(summary["estimated_completeness"], dict)
    
    @patch('services.data_sufficiency_analyzer.client')
    def test_openai_api_error_handling(self, mock_client):
        """Test handling of OpenAI API errors"""
        # Mock OpenAI API failure
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        title = "Recipe Title"
        transcript = "Some cooking instructions"
        
        result = self.analyzer.analyze_sufficiency(title, transcript)
        
        # Should default to requiring OCR on error
        assert result.is_sufficient is False
        assert result.confidence_score == 0.0
        assert "Analysis failed" in result.reasoning
        assert all(status == "unknown" for status in result.estimated_completeness.values())
    
    @patch('services.data_sufficiency_analyzer.client')
    def test_malformed_json_response(self, mock_client):
        """Test handling of malformed JSON response from OpenAI"""
        # Mock OpenAI response with malformed JSON
        mock_choice = MagicMock()
        mock_choice.message.content = "This response looks sufficient to me! The recipe has enough details."
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        title = "Recipe Title"
        transcript = "Cooking instructions here"
        
        result = self.analyzer.analyze_sufficiency(title, transcript)
        
        # Should fallback to text parsing
        assert isinstance(result.is_sufficient, bool)
        assert result.confidence_score >= 0.0
        assert "Parsed from text response" in result.reasoning
        assert all(status == "unknown" for status in result.estimated_completeness.values())
    
    @patch('services.data_sufficiency_analyzer.client')
    def test_json_with_code_blocks(self, mock_client):
        """Test parsing JSON response wrapped in markdown code blocks"""
        mock_choice = MagicMock()
        mock_choice.message.content = """```json
                    {
                        "is_sufficient": true,
                        "confidence_score": 0.8,
                        "reasoning": "Good recipe data",
                        "estimated_completeness": {
                            "ingredients": "complete",
                            "instructions": "complete",
                            "timing": "partial",
                            "measurements": "complete"
                        }
                    }
                    ```"""
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        result = self.analyzer.analyze_sufficiency("Title", "Transcript")
        
        assert result.is_sufficient is True
        assert result.confidence_score == 0.8
        assert result.reasoning == "Good recipe data"
        assert result.estimated_completeness["ingredients"] == "complete"
    
    @patch('services.data_sufficiency_analyzer.client')
    def test_complex_recipe_scenario(self, mock_client):
        """Test with a complex, detailed recipe"""
        mock_choice = MagicMock()
        mock_choice.message.content = """{
                        "is_sufficient": true,
                        "confidence_score": 0.95,
                        "reasoning": "Extremely detailed recipe with comprehensive ingredients list (butter, brown sugar, eggs, vanilla, flour, baking soda, salt, chocolate chips), precise measurements (1 cup, 3/4 cup, 2 large, 1 tsp, 2 1/4 cups, etc.), detailed cooking instructions (preheat, cream, add, whisk, mix, fold, drop, bake, cool), and specific timing (375 degrees, 2 minutes, 9-11 minutes, 5 minutes cooling).",
                        "estimated_completeness": {
                            "ingredients": "complete",
                            "instructions": "complete",
                            "timing": "complete",
                            "measurements": "complete"
                        }
                    }"""
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        title = "Homemade Chocolate Chip Cookies"
        transcript = """
        Preheat oven to 375 degrees. In a large bowl, cream together 1 cup butter and 
        3/4 cup brown sugar for 2 minutes. Add 2 large eggs and 1 teaspoon vanilla extract.
        In separate bowl, whisk 2 1/4 cups all-purpose flour, 1 teaspoon baking soda, 
        and 1 teaspoon salt. Gradually mix dry ingredients into wet ingredients.
        Fold in 2 cups chocolate chips. Drop rounded tablespoons onto baking sheet.
        Bake for 9 to 11 minutes until golden brown. Cool on wire rack for 5 minutes.
        """
        
        result = self.analyzer.analyze_sufficiency(title, transcript)
        
        assert result.is_sufficient is True
        assert result.confidence_score >= 0.9
        assert all(status == "complete" for status in result.estimated_completeness.values())
        mock_client.chat.completions.create.assert_called_once() 
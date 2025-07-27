import pytest
from marshmallow import ValidationError
from schemas.recipe import RecipeSchema, validate_recipe_json, get_recipe_schema_example

class TestRecipeSchema:
    
    def test_valid_recipe_schema(self):
        """Test that a valid recipe passes schema validation"""
        valid_recipe = {
            "title": "Test Recipe",
            "description": "A test recipe",
            "ingredients": [
                {
                    "name": "test ingredient",
                    "quantity": "1 cup"
                }
            ],
            "instructions": [
                "This is a test instruction"
            ],
            "prep_time": 5,
            "cook_time": 15,
            "servings": 4,
            "difficulty": 2,
            "tags": ["test", "quick"],
            "nutrition": {},
            "source_url": "https://test.com",
            "tiktok_author": "test_author",
            "is_public": True,
            "user_id": "",
            "created_at": None,
            "updated_at": None,
            "video_thumbnail": "",
            "saved_by": []
        }
        
        schema = RecipeSchema()
        result = schema.load(valid_recipe)
        assert result["title"] == "Test Recipe"
        assert len(result["ingredients"]) == 1
        assert len(result["instructions"]) == 1
    
    def test_missing_required_fields(self):
        """Test that missing required fields raise validation errors"""
        invalid_recipe = {
            "title": "Test Recipe",
            # Missing ingredients and steps
        }
        
        schema = RecipeSchema()
        with pytest.raises(ValidationError):
            schema.load(invalid_recipe)
    
    def test_invalid_ingredient_schema(self):
        """Test that invalid ingredient data raises validation errors"""
        invalid_recipe = {
            "title": "Test Recipe",
            "ingredients": [
                {
                    "name": "",  # Empty name should fail
                    "quantity": "1 cup"
                }
            ],
            "instructions": [
                "This is a test instruction"
            ]
        }
        
        schema = RecipeSchema()
        with pytest.raises(ValidationError):
            schema.load(invalid_recipe)
    
    def test_invalid_instruction_schema(self):
        """Test that invalid instruction data raises validation errors"""
        invalid_recipe = {
            "title": "Test Recipe",
            "ingredients": [
                {
                    "name": "test ingredient",
                    "quantity": "1 cup"
                }
            ],
            "instructions": [
                ""  # Empty instruction should fail
            ]
        }
        
        schema = RecipeSchema()
        with pytest.raises(ValidationError):
            schema.load(invalid_recipe)
    
    def test_validate_recipe_json_function(self):
        """Test the validate_recipe_json helper function"""
        valid_recipe = {
            "title": "Test Recipe",
            "ingredients": [
                {
                    "name": "test ingredient",
                    "quantity": "1 cup"
                }
            ],
            "instructions": [
                "This is a test instruction"
            ]
        }
        
        result = validate_recipe_json(valid_recipe)
        assert result["title"] == "Test Recipe"
    
    def test_validate_recipe_json_invalid(self):
        """Test that validate_recipe_json raises ValidationError for invalid data"""
        invalid_recipe = {
            "title": "Test Recipe",
            # Missing required fields
        }
        
        with pytest.raises(ValidationError):
            validate_recipe_json(invalid_recipe)
    
    def test_get_recipe_schema_example(self):
        """Test that the example recipe is valid"""
        example = get_recipe_schema_example()
        result = validate_recipe_json(example)
        assert result["title"] == "Caramelized Onion and Garlic Spaghetti"
        assert len(result["ingredients"]) > 0
        assert len(result["instructions"]) > 0 
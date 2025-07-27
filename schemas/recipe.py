from marshmallow import Schema, fields, validate, ValidationError
from typing import List, Dict, Any, Optional

class IngredientSchema(Schema):
    """Schema for individual ingredient"""
    name = fields.Str(required=True, validate=validate.Length(min=1))
    quantity = fields.Str(required=True, validate=validate.Length(min=1))

# No need for StepSchema since instructions are just strings

class RecipeSchema(Schema):
    """Schema for complete recipe JSON"""
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    description = fields.Str(load_default="")
    ingredients = fields.List(fields.Nested(IngredientSchema), required=True, validate=validate.Length(min=1))
    instructions = fields.List(fields.Str(validate=validate.Length(min=1)), required=True, validate=validate.Length(min=1))
    prep_time = fields.Int(load_default=None, validate=validate.Range(min=0))
    cook_time = fields.Int(load_default=None, validate=validate.Range(min=0))
    servings = fields.Int(load_default=None, validate=validate.Range(min=1))
    difficulty = fields.Int(load_default=None, validate=validate.Range(min=1, max=5))
    tags = fields.List(fields.Str(), load_default=[])
    nutrition = fields.Dict(load_default={})
    source_url = fields.Str(load_default="")
    tiktok_author = fields.Str(load_default="")
    is_public = fields.Bool(load_default=True)
    user_id = fields.Str(load_default="")
    created_at = fields.DateTime(load_default=None)
    updated_at = fields.DateTime(load_default=None)
    video_thumbnail = fields.Str(load_default="")
    saved_by = fields.List(fields.Str(), load_default=[])
    # Likes fields
    likes_count = fields.Int(load_default=0, validate=validate.Range(min=0))
    last_liked_by = fields.Str(allow_none=True, load_default=None)

def validate_recipe_json(recipe_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate recipe JSON against schema and return cleaned data
    Args:
        recipe_data: Raw recipe dictionary from LLM
    Returns:
        Validated and cleaned recipe dictionary
    Raises:
        ValidationError: If recipe data doesn't match schema
    """
    schema = RecipeSchema()
    try:
        validated_data = schema.load(recipe_data)
        return validated_data
    except ValidationError as e:
        raise ValidationError(f"Recipe validation failed: {e.messages}")

def get_recipe_schema_example() -> Dict[str, Any]:
    """Return an example recipe structure for LLM prompts"""
    return {
        "title": "Caramelized Onion and Garlic Spaghetti",
        "description": "A comforting pasta dish with sweet caramelized onions and aromatic garlic",
        "ingredients": [
            {
                "name": "large onion",
                "quantity": "1 large, thinly sliced"
            },
            {
                "name": "garlic cloves",
                "quantity": "4 cloves, minced"
            },
            {
                "name": "chili crisp",
                "quantity": "2 tbsp"
            },
            {
                "name": "cream",
                "quantity": "1 cup (or coconut milk, room temperature)"
            },
            {
                "name": "butter",
                "quantity": "2 tbsp"
            },
            {
                "name": "olive oil",
                "quantity": "1 tbsp"
            }
        ],
        "instructions": [
            "Slice onion thinly and mince garlic cloves. Measure out all seasonings.",
            "Heat butter and olive oil in large skillet over medium heat. Add onions and cook for 15-20 minutes until golden and caramelized.",
            "Add minced garlic and seasonings, cook for 1 minute until fragrant",
            "Add chili crisp and sauté for 1 minute",
            "Pour in cream and simmer for a few minutes",
            "Add grated Parmesan cheese and stir until melted",
            "Add cooked pasta and toss to coat with sauce",
            "Serve hot with extra chili crisp on top"
        ],
        "prep_time": 10,
        "cook_time": 25,
        "servings": 4,
        "difficulty": 2,
        "tags": ["pasta", "vegetarian", "comfort food", "italian"],
        "nutrition": {
            "calories": 450,
            "carbs": 55,
            "fat": 22,
            "protein": 12
        },
        "source_url": "https://www.tiktok.com/@recipeincaption/video/7519221347101199672",
        "tiktok_author": "recipeincaption",
        "is_public": True,
        "user_id": "",
        "created_at": None,
        "updated_at": None,
        "video_thumbnail": "",
        "saved_by": []
    } 
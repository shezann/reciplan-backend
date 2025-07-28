"""
Schemas for like/unlike operations
"""
from marshmallow import Schema, fields, validate


class LikeResponseSchema(Schema):
    """Schema for like/unlike response"""
    liked = fields.Bool(required=True)
    likes_count = fields.Int(required=True, validate=validate.Range(min=0))
    recipe_id = fields.Str(required=True)
    user_id = fields.Str(required=True)
    timestamp = fields.DateTime(required=True)


class LikeActionSchema(Schema):
    """Schema for validating like action (for explicit like requests with body)"""
    # This could be used if we want to support explicit like=true/false in request body
    # For now, we'll use HTTP methods (POST=like, DELETE=unlike) as the indicator
    pass


class LikeStatusSchema(Schema):
    """Schema for GET /recipes/{id}/liked response"""
    liked = fields.Bool(required=True)
    recipe_id = fields.Str(required=True)
    user_id = fields.Str(required=True) 
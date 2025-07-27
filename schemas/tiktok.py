from marshmallow import Schema, fields, validates, ValidationError
import re

class TikTokIngestRequestSchema(Schema):
    url = fields.Str(required=True)

    @validates('url')
    def validate_url(self, value):
        # Enhanced TikTok URL validation to support all TikTok domains
        # Supports: tiktok.com, www.tiktok.com, vm.tiktok.com, m.tiktok.com, vt.tiktok.com
        pattern = r"^https?://(www\.|vm\.|m\.|vt\.)?tiktok\.com/.+"
        if not re.match(pattern, value):
            raise ValidationError('Invalid TikTok URL. Please provide a valid TikTok link.')

class TikTokJobStatusResponseSchema(Schema):
    status = fields.Str(required=True)
    title = fields.Str(required=False, allow_none=True)
    transcript = fields.Str(required=False, allow_none=True)
    error_code = fields.Str(required=False, allow_none=True)
    # New LLM-related fields
    recipe_json = fields.Dict(required=False, allow_none=True)
    parse_errors = fields.Str(required=False, allow_none=True)
    llm_model_used = fields.Str(required=False, allow_none=True)
    llm_processing_time_seconds = fields.Float(required=False, allow_none=True)
    llm_processing_completed_at = fields.Str(required=False, allow_none=True)
    has_parse_errors = fields.Bool(required=False, allow_none=True)
    recipe_stats = fields.Dict(required=False, allow_none=True)
    llm_error_message = fields.Str(required=False, allow_none=True)
    # Recipe persistence fields
    recipe_id = fields.Str(required=False, allow_none=True)
    
    # OpenAI Data Sufficiency Analysis fields
    data_sufficiency_analysis = fields.Dict(required=False, allow_none=True)
    ocr_was_skipped = fields.Bool(required=False, allow_none=True)
    ocr_skip_reason = fields.Str(required=False, allow_none=True)
    ocr_confidence_score = fields.Float(required=False, allow_none=True)
    ocr_decision_factors = fields.Dict(required=False, allow_none=True)
    estimated_completeness = fields.Dict(required=False, allow_none=True)
    
    # Pipeline performance metrics
    pipeline_performance = fields.Dict(required=False, allow_none=True)
    total_duration_seconds = fields.Float(required=False, allow_none=True) 
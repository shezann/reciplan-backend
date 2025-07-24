from marshmallow import Schema, fields, validates, ValidationError
import re

class TikTokIngestRequestSchema(Schema):
    url = fields.Str(required=True)

    @validates('url')
    def validate_url(self, value):
        # Basic TikTok URL validation
        pattern = r"^https?://(www\.)?tiktok\.com/.+"
        if not re.match(pattern, value):
            raise ValidationError('Invalid TikTok URL.')

class TikTokJobStatusResponseSchema(Schema):
    status = fields.Str(required=True)
    title = fields.Str(required=False, allow_none=True)
    transcript = fields.Str(required=False, allow_none=True)
    error_code = fields.Str(required=False, allow_none=True) 
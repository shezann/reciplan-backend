from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from schemas.tiktok import TikTokIngestRequestSchema, TikTokJobStatusResponseSchema
from services.tiktok_ingest_service import TikTokIngestService

# Blueprint for TikTok ingestion

tiktok_bp = Blueprint('tiktok', __name__, url_prefix='/ingest')

# POST /ingest/tiktok
@tiktok_bp.route('/tiktok', methods=['POST'])
def ingest_tiktok():
    try:
        schema = TikTokIngestRequestSchema()
        data = schema.load(request.get_json())
        # Call service (mock)
        job_id, recipe_id, status = TikTokIngestService.mock_create_job(data['url'])
        response = {
            'job_id': job_id,
            'recipe_id': recipe_id,
            'status': status
        }
        return jsonify(response), 202
    except ValidationError as e:
        return jsonify({'error': 'Invalid request', 'details': e.messages}), 400

# GET /ingest/jobs/<job_id>
@tiktok_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    # Call service (mock)
    job_status = TikTokIngestService.mock_get_job_status(job_id)
    return jsonify(job_status), 200 
from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from schemas.tiktok import TikTokIngestRequestSchema, TikTokJobStatusResponseSchema
from services.tiktok_ingest_service import TikTokIngestService
from tasks.tiktok_tasks import ingest_tiktok as celery_ingest_tiktok
import uuid

# Blueprint for TikTok ingestion

tiktok_bp = Blueprint('tiktok', __name__, url_prefix='/ingest')

# POST /ingest/tiktok
@tiktok_bp.route('/tiktok', methods=['POST'])
def ingest_tiktok():
    try:
        schema = TikTokIngestRequestSchema()
        data = schema.load(request.get_json())
        # For now, mock owner_uid (in real app, get from auth)
        owner_uid = 'mock-user-uid'
        # Create job and recipe IDs, seed Firestore doc
        job_id, recipe_id, status = TikTokIngestService.mock_create_job(data['url'], owner_uid=owner_uid)
        # Enqueue Celery task
        celery_ingest_tiktok.delay(job_id, data['url'], owner_uid, recipe_id)
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
    try:
        # Read Firestore doc and return job status
        job_data = TikTokIngestService.mock_get_job_status(job_id)
        
        # Validate response using schema
        schema = TikTokJobStatusResponseSchema()
        validated_response = schema.load(job_data)
        
        return jsonify(validated_response), 200
    except ValidationError as e:
        # If schema validation fails, return raw data with warning
        print(f"Warning: Job status response validation failed: {e.messages}")
        return jsonify(job_data), 200
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve job status', 'details': str(e)}), 500 
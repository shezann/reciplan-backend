from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from schemas.tiktok import TikTokIngestRequestSchema, TikTokJobStatusResponseSchema
from services.tiktok_ingest_service import TikTokIngestService
from services.jwt_service import get_user_from_token
from tasks.tiktok_tasks import ingest_tiktok as celery_ingest_tiktok
from flask_jwt_extended import jwt_required, get_jwt_identity
import uuid

# Blueprint for TikTok ingestion

tiktok_bp = Blueprint('tiktok', __name__, url_prefix='/ingest')

# POST /ingest/tiktok
@tiktok_bp.route('/tiktok', methods=['POST'])
@jwt_required()
def ingest_tiktok():
    try:
        schema = TikTokIngestRequestSchema()
        data = schema.load(request.get_json())
        
        # Get the authenticated user's ID from JWT token
        owner_uid = get_jwt_identity()
        if not owner_uid:
            return jsonify({'error': 'Authentication required', 'message': 'Unable to identify user from token'}), 401
        
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
    except Exception as e:
        return jsonify({'error': 'Failed to start ingestion', 'details': str(e)}), 500

# GET /ingest/jobs/<job_id>
@tiktok_bp.route('/jobs/<job_id>', methods=['GET'])
@jwt_required()
def get_job_status(job_id):
    try:
        # Get the authenticated user's ID
        current_user_id = get_jwt_identity()
        if not current_user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Read Firestore doc and return job status
        job_data = TikTokIngestService.mock_get_job_status(job_id)
        
        # Check if the job belongs to the authenticated user
        if job_data.get('owner_uid') and job_data['owner_uid'] != current_user_id:
            return jsonify({'error': 'Access denied', 'message': 'You can only view your own jobs'}), 403
        
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
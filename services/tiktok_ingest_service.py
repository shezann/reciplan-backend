import uuid

class TikTokIngestService:
    @staticmethod
    def mock_create_job(url):
        # Return mock job_id, recipe_id, and status
        job_id = str(uuid.uuid4())
        recipe_id = str(uuid.uuid4())
        status = "QUEUED"
        return job_id, recipe_id, status

    @staticmethod
    def mock_get_job_status(job_id):
        # Return a mock job status response
        return {
            "status": "QUEUED",
            "title": None,
            "transcript": None,
            "error_code": None
        } 
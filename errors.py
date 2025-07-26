# errors.py
"""
Centralized error codes and messages for backend pipeline
"""

ERRORS = {
    "VIDEO_UNAVAILABLE": {
        "code": "VIDEO_UNAVAILABLE",
        "message": "The requested video is unavailable or private."
    },
    "AUDIO_EXTRACTION_FAILED": {
        "code": "AUDIO_EXTRACTION_FAILED", 
        "message": "Failed to extract audio from video."
    },
    "ASR_FAILED": {
        "code": "ASR_FAILED",
        "message": "Audio transcription failed."
    },
    "OCR_FAILED": {
        "code": "OCR_FAILED",
        "message": "On-screen text extraction failed."
    },
    "LLM_FAILED": {
        "code": "LLM_FAILED",
        "message": "Recipe structuring (LLM) failed."
    },
    "PERSIST_FAILED": {
        "code": "PERSIST_FAILED",
        "message": "Failed to persist recipe to database."
    },
    "DOWNLOAD_FAILED": {
        "code": "DOWNLOAD_FAILED",
        "message": "Failed to download video from source."
    },
    "FRAME_EXTRACTION_FAILED": {
        "code": "FRAME_EXTRACTION_FAILED",
        "message": "Failed to extract video frames for OCR."
    },
    "VALIDATION_FAILED": {
        "code": "VALIDATION_FAILED",
        "message": "Recipe validation failed."
    },
    "UNKNOWN_ERROR": {
        "code": "UNKNOWN_ERROR",
        "message": "An unknown error occurred."
    }
}

def get_error(code, details=None):
    """Get standardized error response"""
    err = ERRORS.get(code, ERRORS["UNKNOWN_ERROR"]).copy()
    if details:
        err["details"] = details
    return err

def log_stage_timing(stage_name, start_time, end_time=None):
    """Log timing for pipeline stages"""
    import time
    if end_time is None:
        end_time = time.time()
    duration = end_time - start_time
    print(f"[TIMING] {stage_name}: {duration:.2f}s")
    return duration 
from pathlib import Path
from openai import OpenAI
import os
import time

class TranscriptionError(Exception):
    pass

class TranscriptionService:
    @staticmethod
    def transcribe(audio_path: Path, max_retries: int = 2) -> str:
        """
        Transcribe the given audio file using OpenAI Whisper ASR and return the transcript as a string.
        Retries on HTTP 429 (rate limit) up to max_retries. Deletes audio after transcription (success or failure).
        Raises TranscriptionError on failure.
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise TranscriptionError("OPENAI_API_KEY not set in environment.")
        
        # Initialize OpenAI client (v1.0+ API)
        client = OpenAI(api_key=api_key)
        
        attempt = 0
        try:
            while attempt <= max_retries:
                try:
                    with open(audio_path, "rb") as audio_file:
                        response = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            response_format="text"
                        )
                    if not response or not isinstance(response, str):
                        raise TranscriptionError("No transcript returned from OpenAI.")
                    return response.strip()
                except Exception as e:
                    # Check for rate limit errors (HTTP 429)
                    if hasattr(e, 'status_code') and e.status_code == 429 or '429' in str(e):
                        attempt += 1
                        if attempt > max_retries:
                            raise TranscriptionError("ASR_FAILED: Rate limit exceeded after retries.")
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        raise TranscriptionError(f"ASR_FAILED: {e}")
        finally:
            # Always delete the audio file, even if transcription fails
            try:
                if audio_path and Path(audio_path).exists():
                    Path(audio_path).unlink()
            except Exception:
                pass  # Ignore errors during cleanup 
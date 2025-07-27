from tasks.celery_app import celery_app
from config.firebase_config import get_firestore_db
from datetime import datetime, timezone
import time
from utils.media_downloader import download_video, VideoUnavailableError, temp_job_dir
from utils.audio_extractor import extract_audio, AudioExtractionError
from services.transcription_service import TranscriptionService, TranscriptionError
from services.title_extractor import TitleExtractor
from utils.frame_extractor import extract_frames
from services.ocr_service import OCRService
from services.tiktok_ingest_service import TikTokIngestService
from services.llm_refine_service import LLMRefineService, LLMRefineError
from services.firestore_recipe_service import FirestoreRecipeService
from services.recipe_persist_service import RecipePersistService
from errors import get_error, log_stage_timing, PipelineStatus
import traceback


class PipelineContext:
    """Context object to manage pipeline state and reduce parameter passing"""
    def __init__(self, job_id: str, url: str, owner_uid: str, recipe_id: str):
        self.job_id = job_id
        self.url = url
        self.owner_uid = owner_uid
        self.recipe_id = recipe_id
        self.db = get_firestore_db()
        self.firestore_service = FirestoreRecipeService(self.db) if self.db else None
        self.recipe_persist_service = RecipePersistService() if self.db else None
        self.final_status = PipelineStatus.QUEUED
        self.saved_recipe_id = None
        self.thumbnail_url = None
        
    def update_status(self, status: str, extra_data: dict = None):
        """Update job status in Firestore"""
        if not self.db:
            return
            
        update_data = {
            "status": status,
            "updatedAt": datetime.now(timezone.utc).isoformat()
        }
        if extra_data:
            update_data.update(extra_data)
            
        try:
            self.db.collection("ingest_jobs").document(self.job_id).update(update_data)
        except Exception as e:
            print(f"[ERROR] Failed to update status to {status}: {e}")
    
    def update_recipe_status(self, status: str, extra_data: dict = None):
        """Update recipe status in Firestore"""
        if not self.db:
            return
            
        update_data = {
            "status": status,
            "updatedAt": datetime.now(timezone.utc).isoformat()
        }
        if extra_data:
            update_data.update(extra_data)
            
        try:
            self.db.collection("recipes").document(self.recipe_id).update(update_data)
        except Exception as e:
            print(f"[ERROR] Failed to update recipe status to {status}: {e}")
    
    def handle_error(self, error_type: str, exception: Exception, stage: str):
        """Centralized error handling"""
        error_info = get_error(error_type, str(exception))
        print(f"[ERROR] {stage} failed: {error_info}")
        
        self.update_status(PipelineStatus.FAILED, {
            "error_code": error_info["code"],
            "error_message": error_info["message"]
        })
        return error_info


@celery_app.task(bind=True, max_retries=1, autoretry_for=(Exception,), retry_backoff=True)
def ingest_tiktok(self, job_id: str, url: str, owner_uid: str, recipe_id: str):
    """
    Simplified TikTok ingestion task with improved error handling and reduced complexity
    """
    pipeline_start = time.time()
    ctx = PipelineContext(job_id, url, owner_uid, recipe_id)
    
    try:
        print(f"[TASK] Starting TikTok ingestion for job {job_id}")
        
        # Ensure ingest_jobs doc exists
        if ctx.db:
            job_ref = ctx.db.collection("ingest_jobs").document(job_id)
            if not job_ref.get().exists:
                now = datetime.now(timezone.utc).isoformat()
                job_ref.set({"status": PipelineStatus.QUEUED, "createdAt": now, "job_id": job_id})
        
        with temp_job_dir() as job_dir:
            # Stage 1: Download video
            video_path, metadata_title, thumbnail_url = _download_stage(ctx, url, job_dir, self)
            # Store thumbnail URL in context for later use
            ctx.thumbnail_url = thumbnail_url
            
            # Stage 2: Extract audio
            audio_path = _extract_audio_stage(ctx, video_path, job_dir, self)
            
            # Stage 3: Transcribe audio
            transcript = _transcription_stage(ctx, audio_path, self)
            
            # Stage 4: Extract title and update documents
            normalized_title = _title_extraction_stage(ctx, metadata_title, transcript)
            
            # Stage 5: OCR processing
            ocr_results = _ocr_stage(ctx, video_path, job_dir)
            
            # Stage 6: LLM refinement
            recipe_json = _llm_stage(ctx, normalized_title, transcript, ocr_results)
            
            # Stage 7: Recipe persistence
            if ctx.final_status in [PipelineStatus.DRAFT_PARSED, PipelineStatus.DRAFT_PARSED_WITH_ERRORS]:
                _persistence_stage(ctx, recipe_json)
        
        # Final status update
        log_stage_timing("TOTAL_PIPELINE", pipeline_start)
        ctx.update_status(ctx.final_status, {
            "pipeline_completed_at": datetime.now(timezone.utc).isoformat()
        })
        
        print(f"[TASK] Job {job_id} completed with status: {ctx.final_status}")
        return {"job_id": job_id, "status": ctx.final_status, "recipe_id": ctx.saved_recipe_id}
        
    except Exception as exc:
        log_stage_timing("TOTAL_PIPELINE", pipeline_start)
        error_info = get_error("UNKNOWN_ERROR", str(exc))
        print(f"[ERROR] Pipeline failed: {error_info}")
        traceback.print_exc()
        
        ctx.update_status(PipelineStatus.FAILED, {
            "error_code": error_info["code"],
            "error_message": error_info["message"]
        })
        
        raise self.retry(exc=exc)


def _download_stage(ctx: PipelineContext, url: str, job_dir, task_self):
    """Handle video download stage"""
    ctx.update_status(PipelineStatus.DOWNLOADING)
    download_start = time.time()
    
    try:
        print(f"[TASK] Downloading video from {url}")
        video_result = download_video(url, output_dir=job_dir)
        
        if isinstance(video_result, tuple) and len(video_result) == 3:
            video_path, metadata_title, thumbnail_url = video_result
        elif isinstance(video_result, tuple) and len(video_result) == 2:
            # Backward compatibility
            video_path, metadata_title = video_result
            thumbnail_url = None
        else:
            video_path = video_result
            metadata_title = None
            thumbnail_url = None
            
        log_stage_timing("DOWNLOAD", download_start)
        print(f"[TASK] Video downloaded successfully: {video_path}")
        if thumbnail_url:
            print(f"[TASK] Thumbnail URL extracted: {thumbnail_url}")
        return video_path, metadata_title, thumbnail_url
        
    except VideoUnavailableError as e:
        log_stage_timing("DOWNLOAD", download_start)
        ctx.handle_error("VIDEO_UNAVAILABLE", e, "Download")
        raise task_self.retry(exc=e)
    except Exception as e:
        log_stage_timing("DOWNLOAD", download_start)
        ctx.handle_error("DOWNLOAD_FAILED", e, "Download")
        raise task_self.retry(exc=e)


def _extract_audio_stage(ctx: PipelineContext, video_path, job_dir, task_self):
    """Handle audio extraction stage"""
    ctx.update_status(PipelineStatus.EXTRACTING)
    extract_start = time.time()
    
    try:
        print(f"[TASK] Extracting audio from video")
        audio_path = extract_audio(video_path, output_dir=job_dir)
        log_stage_timing("AUDIO_EXTRACTION", extract_start)
        print(f"[TASK] Audio extracted successfully: {audio_path}")
        return audio_path
        
    except AudioExtractionError as e:
        log_stage_timing("AUDIO_EXTRACTION", extract_start)
        ctx.handle_error("AUDIO_EXTRACTION_FAILED", e, "Audio extraction")
        raise task_self.retry(exc=e)


def _transcription_stage(ctx: PipelineContext, audio_path, task_self):
    """Handle transcription stage"""
    ctx.update_status(PipelineStatus.TRANSCRIBING)
    transcribe_start = time.time()
    
    try:
        print(f"[TASK] Transcribing audio using OpenAI ASR")
        transcript = TranscriptionService.transcribe(audio_path)
        log_stage_timing("TRANSCRIPTION", transcribe_start)
        print(f"[TASK] Transcription completed: {len(transcript)} characters")
        return transcript
        
    except TranscriptionError as e:
        log_stage_timing("TRANSCRIPTION", transcribe_start)
        ctx.handle_error("ASR_FAILED", e, "Transcription")
        raise task_self.retry(exc=e)


def _title_extraction_stage(ctx: PipelineContext, metadata_title, transcript):
    """Handle title extraction and document updates"""
    raw_title = TitleExtractor.from_metadata(metadata_title) or TitleExtractor.from_transcript(transcript)
    normalized_title = TitleExtractor.normalize_title(raw_title)
    
    # Update both collections with title and transcript
    ctx.update_status(PipelineStatus.DRAFT_TRANSCRIBED, {
        "transcript": transcript,
        "title": normalized_title
    })
    
    ctx.update_recipe_status(PipelineStatus.DRAFT_TRANSCRIBED, {
        "title": normalized_title,
        "transcript": transcript,
        "owner_uid": ctx.owner_uid
    })
    
    return normalized_title


def _ocr_stage(ctx: PipelineContext, video_path, job_dir):
    """Handle OCR processing stage"""
    ctx.update_status(PipelineStatus.OCRING)
    
    # Extract frames (optimized - max 8 frames)
    frame_extract_start = time.time()
    try:
        print(f"[TASK] Extracting video frames for OCR...")
        frames = extract_frames(video_path, job_dir / "frames", method="scene", fps=1.0, max_frames=8)
        log_stage_timing("FRAME_EXTRACTION", frame_extract_start)
        print(f"[TASK] Frame extraction completed: {len(frames)} frames")
    except Exception as e:
        log_stage_timing("FRAME_EXTRACTION", frame_extract_start)
        print(f"[ERROR] Frame extraction failed: {e}")
        frames = []
    
    # Run OCR
    ocr_service = OCRService()
    ocr_start = time.time()
    try:
        print(f"[TASK] Running OCR on {len(frames)} frames...")
        ocr_results = ocr_service.run_ocr_on_frames(frames)
        log_stage_timing("OCR_PROCESSING", ocr_start)
        
        # Process OCR results
        all_text_blocks = [tb for frame in ocr_results for tb in frame["text_blocks"]]
        deduped_blocks = ocr_service.dedupe_text_blocks(all_text_blocks)
        ingredient_candidates = ocr_service.extract_ingredient_candidates(deduped_blocks)
        
        # Persist OCR results
        TikTokIngestService.update_ocr_results(
            ctx.job_id,
            onscreen_text=ocr_results,
            ingredient_candidates=ingredient_candidates
        )
        
        ctx.update_status(PipelineStatus.OCR_DONE)
        print(f"[TASK] OCR processing completed")
        return ocr_results
        
    except Exception as e:
        log_stage_timing("OCR_PROCESSING", ocr_start)
        error_info = get_error("OCR_FAILED", str(e))
        print(f"[ERROR] OCR processing failed: {error_info}")
        
        # Don't fail the entire job, continue with empty OCR results
        ctx.update_status(PipelineStatus.OCR_FAILED_BUT_CONTINUED, {
            "error_code": error_info["code"],
            "error_message": error_info["message"]
        })
        return []


def _llm_stage(ctx: PipelineContext, normalized_title, transcript, ocr_results):
    """Handle LLM refinement stage"""
    ctx.update_status(PipelineStatus.LLM_REFINING)
    llm_start = time.time()
    
    try:
        print(f"[TASK] Starting LLM recipe refinement...")
        
        # Initialize LLM service
        llm_service = LLMRefineService()
        
        # Extract TikTok author from URL
        tiktok_author = ""
        if "@" in ctx.url:
            try:
                tiktok_author = ctx.url.split("@")[1].split("/")[0]
            except:
                pass
        
        # Refine recipe with validation retry
        recipe_json, parse_error = llm_service.refine_with_validation_retry(
            title=normalized_title,
            transcript=transcript,
            ocr_results=ocr_results,
            source_url=ctx.url,
            tiktok_author=tiktok_author,
            video_thumbnail=ctx.thumbnail_url or "",
            max_validation_retries=2
        )
        
        log_stage_timing("LLM_REFINEMENT", llm_start)
        
        # Determine final status
        if parse_error:
            ctx.final_status = PipelineStatus.DRAFT_PARSED_WITH_ERRORS
            print(f"[TASK] Recipe parsed with errors: {parse_error}")
        else:
            ctx.final_status = PipelineStatus.DRAFT_PARSED
            print(f"[TASK] Recipe parsed successfully")
        
        # Prepare LLM metadata
        llm_metadata = {
            "llm_model_used": llm_service.model,
            "llm_processing_time_seconds": round(time.time() - llm_start, 2),
            "llm_processing_completed_at": datetime.now(timezone.utc).isoformat(),
            "llm_validation_retries": 2,
            "ocr_frames_processed": len(ocr_results) if ocr_results else 0
        }
        
        # Update Firestore using the dedicated service
        if ctx.firestore_service:
            success = ctx.firestore_service.update_recipe_with_llm_results(
                job_id=ctx.job_id,
                recipe_id=ctx.recipe_id,
                recipe_json=recipe_json,
                llm_metadata=llm_metadata,
                parse_error=parse_error
            )
            
            if not success:
                print(f"[TASK] Warning: Firestore update failed for job {ctx.job_id}")
        
        return recipe_json
        
    except LLMRefineError as e:
        log_stage_timing("LLM_REFINEMENT", llm_start)
        error_info = get_error("LLM_FAILED", str(e))
        print(f"[ERROR] LLM refinement failed: {error_info}")
        
        # Update Firestore with LLM failure
        if ctx.firestore_service:
            ctx.firestore_service.update_recipe_llm_failure(
                job_id=ctx.job_id,
                recipe_id=ctx.recipe_id,
                error_message=str(e)
            )
        
        # Don't fail the entire job
        ctx.final_status = PipelineStatus.LLM_FAILED_BUT_CONTINUED
        return None


def _persistence_stage(ctx: PipelineContext, recipe_json):
    """Handle recipe persistence stage"""
    if not ctx.recipe_persist_service or not recipe_json:
        return
        
    persist_start = time.time()
    try:
        print(f"[TASK] Starting recipe persistence for job {ctx.job_id}")
        
        ctx.saved_recipe_id = ctx.recipe_persist_service.save_recipe_and_update_job(
            recipe_json=recipe_json,
            job_id=ctx.job_id,
            owner_uid=ctx.owner_uid,
            source_url=ctx.url,
            existing_recipe_id=ctx.recipe_id
        )
        
        log_stage_timing("RECIPE_PERSISTENCE", persist_start)
        
        if ctx.saved_recipe_id:
            print(f"[TASK] Successfully saved recipe {ctx.saved_recipe_id}")
            ctx.final_status = PipelineStatus.COMPLETED
        else:
            print(f"[TASK] Failed to save recipe for job {ctx.job_id}")
            
    except Exception as e:
        log_stage_timing("RECIPE_PERSISTENCE", persist_start)
        error_info = get_error("PERSIST_FAILED", str(e))
        print(f"[ERROR] Recipe persistence failed: {error_info}") 
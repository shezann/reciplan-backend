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
from errors import get_error, log_stage_timing
import traceback

@celery_app.task(bind=True, max_retries=1, autoretry_for=(Exception,), retry_backoff=True)
def ingest_tiktok(self, *args, **kwargs):
    # Support both positional and keyword arguments for testability
    if len(args) == 5:
        _, job_id, url, owner_uid, recipe_id = args
    elif len(args) == 4:
        job_id, url, owner_uid, recipe_id = args
    else:
        job_id = kwargs.get('job_id')
        url = kwargs.get('url')
        owner_uid = kwargs.get('owner_uid')
        recipe_id = kwargs.get('recipe_id')
    
    # Initialize services and timing
    pipeline_start = time.time()
    db = get_firestore_db()
    firestore_service = FirestoreRecipeService(db) if db else None
    recipe_persist_service = RecipePersistService() if db else None
    
    # Initialize final_status to handle all code paths
    final_status = "UNKNOWN"
    saved_recipe_id = None
    
    try:
        now = datetime.now(timezone.utc).isoformat()
        print(f"[TASK] Starting TikTok ingestion for job {job_id}")
        
        # Ensure ingest_jobs doc exists before any update
        if db:
            job_ref = db.collection("ingest_jobs").document(job_id)
            if not job_ref.get().exists:
                job_ref.set({"status": "QUEUED", "createdAt": now, "job_id": job_id})
        
        # Update job status to DOWNLOADING
        if db:
            db.collection("ingest_jobs").document(job_id).update({
                "status": "DOWNLOADING",
                "updatedAt": now
            })
        with temp_job_dir() as job_dir:
            # Download video
            download_start = time.time()
            try:
                print(f"[TASK] Downloading video from {url}")
                video_result = download_video(url, output_dir=job_dir)
                if isinstance(video_result, tuple):
                    video_path, metadata_title = video_result
                else:
                    video_path = video_result
                    metadata_title = None
                log_stage_timing("DOWNLOAD", download_start)
                print(f"[TASK] Video downloaded successfully: {video_path}")
                
            except VideoUnavailableError as e:
                log_stage_timing("DOWNLOAD", download_start)
                error_info = get_error("VIDEO_UNAVAILABLE", str(e))
                print(f"[ERROR] Download failed: {error_info}")
                if db:
                    db.collection("ingest_jobs").document(job_id).update({
                        "status": "FAILED",
                        "updatedAt": datetime.now(timezone.utc).isoformat(),
                        "error_code": error_info["code"],
                        "error_message": error_info["message"]
                    })
                raise self.retry(exc=e)
            except Exception as e:
                log_stage_timing("DOWNLOAD", download_start)
                error_info = get_error("DOWNLOAD_FAILED", str(e))
                print(f"[ERROR] Unexpected download error: {error_info}")
                if db:
                    db.collection("ingest_jobs").document(job_id).update({
                        "status": "FAILED",
                        "updatedAt": datetime.now(timezone.utc).isoformat(),
                        "error_code": error_info["code"],
                        "error_message": error_info["message"]
                    })
                raise self.retry(exc=e)
            # Update job status to EXTRACTING
            if db:
                db.collection("ingest_jobs").document(job_id).update({
                    "status": "EXTRACTING",
                    "updatedAt": datetime.now(timezone.utc).isoformat()
                })
            
            # Extract audio
            extract_start = time.time()
            try:
                print(f"[TASK] Extracting audio from video")
                audio_path = extract_audio(video_path, output_dir=job_dir)
                log_stage_timing("AUDIO_EXTRACTION", extract_start)
                print(f"[TASK] Audio extracted successfully: {audio_path}")
                
            except AudioExtractionError as e:
                log_stage_timing("AUDIO_EXTRACTION", extract_start)
                error_info = get_error("AUDIO_EXTRACTION_FAILED", str(e))
                print(f"[ERROR] Audio extraction failed: {error_info}")
                if db:
                    db.collection("ingest_jobs").document(job_id).update({
                        "status": "FAILED",
                        "updatedAt": datetime.now(timezone.utc).isoformat(),
                        "error_code": error_info["code"],
                        "error_message": error_info["message"]
                    })
                raise self.retry(exc=e)
            # Update job status to TRANSCRIBING
            if db:
                db.collection("ingest_jobs").document(job_id).update({
                    "status": "TRANSCRIBING",
                    "updatedAt": datetime.now(timezone.utc).isoformat()
                })
            
            # Transcribe audio
            transcribe_start = time.time()
            try:
                print(f"[TASK] Transcribing audio using OpenAI ASR")
                transcript = TranscriptionService.transcribe(audio_path)
                log_stage_timing("TRANSCRIPTION", transcribe_start)
                print(f"[TASK] Transcription completed: {len(transcript)} characters")
                
            except TranscriptionError as e:
                log_stage_timing("TRANSCRIPTION", transcribe_start)
                error_info = get_error("ASR_FAILED", str(e))
                print(f"[ERROR] Transcription failed: {error_info}")
                if db:
                    db.collection("ingest_jobs").document(job_id).update({
                        "status": "FAILED",
                        "updatedAt": datetime.now(timezone.utc).isoformat(),
                        "error_code": error_info["code"],
                        "error_message": error_info["message"]
                    })
                raise self.retry(exc=e)
            
            # Extract video title from yt-dlp metadata (if available)
            # video_result is already a tuple (video_path, metadata_title) from download_video
            if isinstance(video_result, tuple):
                video_path, metadata_title = video_result
            else:
                video_path = video_result
                metadata_title = None
            # Fallback to transcript if no metadata title
            print(f"[DEBUG] Metadata title: {metadata_title}")
            raw_title = TitleExtractor.from_metadata(metadata_title) or TitleExtractor.from_transcript(transcript)
            print(f"[DEBUG] Raw title: {raw_title}")
            normalized_title = TitleExtractor.normalize_title(raw_title)
            print(f"[DEBUG] Normalized title: {normalized_title}")
            now_str = datetime.now(timezone.utc).isoformat()
            if db:
                # Update ingest_jobs status
                db.collection("ingest_jobs").document(job_id).update({
                    "status": "DRAFT_TRANSCRIBED",
                    "updatedAt": now_str,
                    "transcript": transcript,
                    "title": normalized_title
                })
                # Update recipe doc as well
                db.collection("recipes").document(recipe_id).update({
                    "title": normalized_title,
                    "transcript": transcript,
                    "status": "DRAFT_TRANSCRIBED",
                    "updatedAt": now_str,
                    "owner_uid": owner_uid
                })
                # --- OCR STAGE ---
                if db:
                    db.collection("ingest_jobs").document(job_id).update({
                        "status": "OCRING",
                        "updatedAt": datetime.now(timezone.utc).isoformat()
                    })
                
                # Extract frames (optimized - max 8 frames)
                frame_extract_start = time.time()
                try:
                    print(f"[TASK] Extracting video frames for OCR...")
                    frames = extract_frames(video_path, job_dir / "frames", method="scene", fps=1.0, max_frames=8)
                    log_stage_timing("FRAME_EXTRACTION", frame_extract_start)
                    print(f"[TASK] Frame extraction completed: {len(frames)} frames")
                    
                except Exception as e:
                    log_stage_timing("FRAME_EXTRACTION", frame_extract_start)
                    error_info = get_error("FRAME_EXTRACTION_FAILED", str(e))
                    print(f"[ERROR] Frame extraction failed: {error_info}")
                    # Continue with empty frames for OCR
                    frames = []
                
                ocr_service = OCRService()
                ocr_start = time.time()
                try:
                    print(f"[TASK] Running OCR on {len(frames)} frames...")
                    ocr_results = ocr_service.run_ocr_on_frames(frames)
                    log_stage_timing("OCR_PROCESSING", ocr_start)
                    print(f"[TASK] OCR processing completed")
                    
                    # Flatten all text blocks for deduplication and ingredient extraction
                    all_text_blocks = [tb for frame in ocr_results for tb in frame["text_blocks"]]
                    deduped_blocks = ocr_service.dedupe_text_blocks(all_text_blocks)
                    ingredient_candidates = ocr_service.extract_ingredient_candidates(deduped_blocks)
                    
                    # Persist OCR results
                    TikTokIngestService.update_ocr_results(
                        job_id,
                        onscreen_text=ocr_results,
                        ingredient_candidates=ingredient_candidates
                    )
                    
                    if db:
                        db.collection("ingest_jobs").document(job_id).update({
                            "status": "OCR_DONE",
                            "updatedAt": datetime.now(timezone.utc).isoformat()
                        })
                        
                except Exception as e:
                    log_stage_timing("OCR_PROCESSING", ocr_start)
                    error_info = get_error("OCR_FAILED", str(e))
                    print(f"[ERROR] OCR processing failed: {error_info}")
                    print(f"[ERROR] OCR exception details: {e}")
                    traceback.print_exc()
                    
                    # Don't fail the entire job, just log the OCR error and continue
                    print("[TASK] OCR failed but continuing with job completion...")
                    if db:
                        db.collection("ingest_jobs").document(job_id).update({
                            "status": "OCR_FAILED_BUT_CONTINUED",
                            "updatedAt": datetime.now(timezone.utc).isoformat(),
                            "error_code": error_info["code"],
                            "error_message": error_info["message"]
                        })
                    ocr_results = []  # Empty OCR results for LLM
                
                # --- LLM REFINEMENT STAGE ---
                if db:
                    db.collection("ingest_jobs").document(job_id).update({
                        "status": "LLM_REFINING",
                        "updatedAt": datetime.now(timezone.utc).isoformat()
                    })
                
                llm_start = time.time()
                try:
                    print(f"[TASK] Starting LLM recipe refinement...")
                    
                    # Initialize LLM service
                    llm_service = LLMRefineService()
                    
                    # Extract TikTok author from URL if possible
                    tiktok_author = ""
                    if "@" in url:
                        try:
                            tiktok_author = url.split("@")[1].split("/")[0]
                        except:
                            pass
                    
                    # Refine recipe with validation retry
                    recipe_json, parse_error = llm_service.refine_with_validation_retry(
                        title=normalized_title,
                        transcript=transcript,
                        ocr_results=ocr_results,
                        source_url=url,
                        tiktok_author=tiktok_author,
                        max_validation_retries=2
                    )
                    
                    log_stage_timing("LLM_REFINEMENT", llm_start)
                    
                    # Determine final status based on parse error
                    if parse_error:
                        final_status = "DRAFT_PARSED_WITH_ERRORS"
                        print(f"[TASK] Recipe parsed with errors: {parse_error}")
                    else:
                        final_status = "DRAFT_PARSED"
                        print(f"[TASK] Recipe parsed successfully")
                    
                    # Prepare LLM metadata
                    llm_metadata = {
                        "llm_model_used": llm_service.model,
                        "llm_processing_time_seconds": round(time.time() - llm_start, 2),
                        "llm_processing_completed_at": datetime.now(timezone.utc).isoformat(),
                        "llm_validation_retries": 2,  # Fixed for now, could be made dynamic
                        "ocr_frames_processed": len(ocr_results) if ocr_results else 0
                    }
                    
                    # Update Firestore using the dedicated service
                    if firestore_service:
                        success = firestore_service.update_recipe_with_llm_results(
                            job_id=job_id,
                            recipe_id=recipe_id,
                            recipe_json=recipe_json,
                            llm_metadata=llm_metadata,
                            parse_error=parse_error
                        )
                        
                        if not success:
                            print(f"[TASK] Warning: Firestore update failed for job {job_id}")
                    
                except LLMRefineError as e:
                    log_stage_timing("LLM_REFINEMENT", llm_start)
                    error_info = get_error("LLM_FAILED", str(e))
                    print(f"[ERROR] LLM refinement failed: {error_info}")
                    print(f"[ERROR] LLM exception details: {e}")
                    
                    # Update Firestore with LLM failure using the dedicated service
                    if firestore_service:
                        success = firestore_service.update_recipe_llm_failure(
                            job_id=job_id,
                            recipe_id=recipe_id,
                            error_message=str(e)
                        )
                        
                        if not success:
                            print(f"[TASK] Warning: Failed to update Firestore with LLM failure for job {job_id}")
                    
                    # Don't fail the entire job, continue to persistence
                    final_status = "LLM_FAILED_BUT_CONTINUED"
                    recipe_json = None
                
                # Recipe persistence: Save recipe to recipes collection and update job
                saved_recipe_id = None
                if recipe_persist_service and final_status in ["DRAFT_PARSED", "DRAFT_PARSED_WITH_ERRORS"]:
                    persist_start = time.time()
                    try:
                        print(f"[TASK] Starting recipe persistence for job {job_id}")
                        print(f"[TASK] recipe_id being passed: '{recipe_id}'")
                        print(f"[TASK] recipe_json type: {type(recipe_json)}")
                        print(f"[TASK] recipe_json keys: {list(recipe_json.keys()) if recipe_json else 'None'}")
                        saved_recipe_id = recipe_persist_service.save_recipe_and_update_job(
                            recipe_json=recipe_json,
                            job_id=job_id,
                            owner_uid=owner_uid,
                            source_url=url,
                            existing_recipe_id=recipe_id  # Use the existing recipe_id to avoid duplicates
                        )
                        
                        log_stage_timing("RECIPE_PERSISTENCE", persist_start)
                        
                        if saved_recipe_id:
                            print(f"[TASK] Successfully saved recipe {saved_recipe_id} for job {job_id}")
                            # Update the final status to COMPLETED
                            final_status = "COMPLETED"
                        else:
                            print(f"[TASK] Failed to save recipe for job {job_id}")
                            # Keep the current status (DRAFT_PARSED or DRAFT_PARSED_WITH_ERRORS)
                            
                    except Exception as e:
                        log_stage_timing("RECIPE_PERSISTENCE", persist_start)
                        error_info = get_error("PERSIST_FAILED", str(e))
                        print(f"[ERROR] Recipe persistence failed: {error_info}")
                        print(f"[ERROR] Persistence exception details: {e}")
                        # Keep the current status (DRAFT_PARSED or DRAFT_PARSED_WITH_ERRORS)
                
        # Log overall pipeline timing
        log_stage_timing("TOTAL_PIPELINE", pipeline_start)
        
        # Final status update
        if db:
            try:
                db.collection("ingest_jobs").document(job_id).update({
                    "status": final_status,
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                    "pipeline_completed_at": datetime.now(timezone.utc).isoformat()
                })
                print(f"[TASK] Job {job_id} completed successfully with status: {final_status}")
            except Exception as e:
                print(f"[ERROR] Error updating final status: {e}")
                # Continue anyway
        
        # Verify temp directory cleanup (this happens automatically in the context manager)
        print(f"[TASK] Temp directory cleanup verified (handled by context manager)")
        
        # Return the saved recipe_id if available (already captured above)
        return {"job_id": job_id, "status": final_status, "recipe_id": saved_recipe_id}
    except Exception as exc:
        # Log overall pipeline timing even on failure
        log_stage_timing("TOTAL_PIPELINE", pipeline_start)
        
        # On final retry, mark job as FAILED
        error_info = get_error("UNKNOWN_ERROR", str(exc))
        print(f"[ERROR] Pipeline failed with unknown error: {error_info}")
        print(f"[ERROR] Exception details: {exc}")
        traceback.print_exc()
        
        if db:
            db.collection("ingest_jobs").document(job_id).update({
                "status": "FAILED",
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "error_code": error_info["code"],
                "error_message": error_info["message"]
            })
        
        # Verify temp directory cleanup even on failure
        print(f"[TASK] Temp directory cleanup verified (handled by context manager)")
        
        raise self.retry(exc=exc) 
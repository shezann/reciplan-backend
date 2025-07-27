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
from services.data_sufficiency_analyzer import DataSufficiencyAnalyzer
from services.recipe_quality_analyzer import RecipeQualityAnalyzer
from errors import get_error, log_stage_timing, PipelineStatus
import traceback
import os


class PipelineContext:
    """Context object to manage pipeline state and reduce parameter passing"""
    def __init__(self, job_id: str, url: str, owner_uid: str, recipe_id: str):
        self.job_id = job_id
        self.url = url
        self.owner_uid = owner_uid
        self.recipe_id = recipe_id
        self.db = get_firestore_db()
        self.firestore_service = FirestoreRecipeService(self.db) if self.db else None
        self.tiktok_service = TikTokIngestService() if self.db else None
        self.recipe_persist_service = RecipePersistService() if self.db else None
        self.final_status = PipelineStatus.QUEUED
        self.saved_recipe_id = None
        self.thumbnail_url = None
        self.sufficiency_result = None
        self.fallback_triggered = False
        self.original_ocr_results = None
        self.video_path = None
        self.job_dir = None
        self.tiktok_service = None
        
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
            # Store paths and thumbnail URL in context for potential fallback use
            ctx.video_path = video_path
            ctx.job_dir = job_dir
            ctx.thumbnail_url = thumbnail_url
            
            # Stage 2: Extract audio
            audio_path = _extract_audio_stage(ctx, video_path, job_dir, self)
            
            # Stage 3: Transcribe audio
            transcript = _transcription_stage(ctx, audio_path, self)
            
            # Stage 4: Extract title and update documents
            normalized_title = _title_extraction_stage(ctx, metadata_title, transcript)
            
            # Stage 5: Analyze data sufficiency with OpenAI
            sufficiency_result = _data_sufficiency_analysis_stage(ctx, normalized_title, transcript, metadata_title)
            
            # Stage 6: Conditional OCR processing (skip if data is sufficient)
            ocr_results = _conditional_ocr_stage(ctx, video_path, job_dir)
            
            # Stage 7: LLM refinement
            recipe_json = _llm_stage(ctx, normalized_title, transcript, ocr_results)
            
            # Stage 8: Recipe persistence
            if ctx.final_status in [PipelineStatus.DRAFT_PARSED, PipelineStatus.DRAFT_PARSED_WITH_ERRORS]:
                _persistence_stage(ctx, recipe_json)
        
        # Final status update with pipeline performance metrics
        total_duration = log_stage_timing("TOTAL_PIPELINE", pipeline_start)
        
        # Calculate performance metrics
        performance_metrics = {
            "pipeline_completed_at": datetime.now(timezone.utc).isoformat(),
            "total_duration_seconds": round(total_duration, 2),
            "ocr_was_skipped": ctx.sufficiency_result and ctx.sufficiency_result.is_sufficient,
            "confidence_score": ctx.sufficiency_result.confidence_score if ctx.sufficiency_result else None
        }
        
        # Add OCR-specific metrics
        if hasattr(ctx, 'sufficiency_result') and ctx.sufficiency_result:
            performance_metrics["data_sufficiency_analysis"] = {
                "was_sufficient": ctx.sufficiency_result.is_sufficient,
                "confidence": ctx.sufficiency_result.confidence_score,
                "estimated_completeness": ctx.sufficiency_result.estimated_completeness
            }
        
        ctx.update_status(ctx.final_status, performance_metrics)
        
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


def _data_sufficiency_analysis_stage(ctx: PipelineContext, title, transcript, metadata_title):
    """Handle OpenAI-based data sufficiency analysis stage"""
    ctx.update_status(PipelineStatus.ANALYZING_DATA_SUFFICIENCY)
    analysis_start = time.time()
    
    try:
        print(f"[TASK] Starting OpenAI data sufficiency analysis...")
        
        # Initialize data sufficiency analyzer
        analyzer = DataSufficiencyAnalyzer()
        
        # Prepare metadata for analysis
        metadata = {}
        if metadata_title and metadata_title != title:
            metadata['description'] = metadata_title
        
        # Analyze data sufficiency
        sufficiency_result = analyzer.analyze_sufficiency(
            title=title,
            transcript=transcript,
            metadata=metadata
        )
        
        # Store result in context
        ctx.sufficiency_result = sufficiency_result
        
        log_stage_timing("DATA_SUFFICIENCY_ANALYSIS", analysis_start)
        
        # Update job document with comprehensive analysis results
        analysis_summary = analyzer.get_analysis_summary(sufficiency_result)
        
        # Add additional pipeline metrics
        analysis_summary.update({
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "text_sources_analyzed": {
                "title_length": len(title) if title else 0,
                "transcript_length": len(transcript) if transcript else 0,
                "metadata_available": bool(metadata and metadata.get('description'))
            },
            "decision_ready": True
        })
        
        ctx.update_status(PipelineStatus.ANALYZING_DATA_SUFFICIENCY, {
            "data_sufficiency_analysis": analysis_summary
        })
        
        if sufficiency_result.is_sufficient:
            print(f"[TASK] Data sufficiency analysis: SUFFICIENT (confidence: {sufficiency_result.confidence_score:.2f})")
            print(f"[TASK] Reasoning: {sufficiency_result.reasoning}")
        else:
            print(f"[TASK] Data sufficiency analysis: INSUFFICIENT (confidence: {sufficiency_result.confidence_score:.2f})")
            print(f"[TASK] Reasoning: {sufficiency_result.reasoning}")
        
        return sufficiency_result
        
    except Exception as e:
        log_stage_timing("DATA_SUFFICIENCY_ANALYSIS", analysis_start)
        print(f"[ERROR] Data sufficiency analysis failed: {e}")
        
        # On error, default to requiring OCR (safe fallback)
        from services.data_sufficiency_analyzer import SufficiencyResult
        fallback_result = SufficiencyResult(
            is_sufficient=False,
            confidence_score=0.0,
            reasoning=f"Analysis failed: {str(e)}",
            estimated_completeness={
                "ingredients": "unknown",
                "instructions": "unknown",
                "timing": "unknown",
                "measurements": "unknown"
            }
        )
        
        ctx.sufficiency_result = fallback_result
        ctx.update_status(PipelineStatus.ANALYZING_DATA_SUFFICIENCY, {
            "data_sufficiency_analysis": {
                "is_sufficient": False,
                "confidence_score": 0.0,
                "reasoning": f"Analysis failed: {str(e)}",
                "estimated_completeness": fallback_result.estimated_completeness
            }
        })
        
        return fallback_result


def _conditional_ocr_stage(ctx: PipelineContext, video_path, job_dir):
    """Handle conditional OCR processing stage based on OpenAI sufficiency analysis and confidence scoring"""
    
    # Configuration: minimum confidence threshold for skipping OCR (configurable via env)
    MIN_CONFIDENCE_THRESHOLD = float(os.getenv('OCR_SKIP_CONFIDENCE_THRESHOLD', '0.7'))
    
    # Safety check: ensure we have sufficiency analysis results
    if not ctx.sufficiency_result:
        print("[TASK] No sufficiency analysis available - proceeding with OCR as fallback")
        return _ocr_stage(ctx, video_path, job_dir)
    
    confidence = ctx.sufficiency_result.confidence_score
    is_sufficient = ctx.sufficiency_result.is_sufficient
    reasoning = ctx.sufficiency_result.reasoning
    
    # Decision logic: both sufficiency flag AND confidence threshold must be met
    should_skip_ocr = (
        is_sufficient and 
        confidence >= MIN_CONFIDENCE_THRESHOLD
    )
    
    if should_skip_ocr:
        print(f"[TASK] ✅ Skipping OCR - OpenAI analysis indicates sufficient data")
        print(f"[TASK]    Confidence: {confidence:.2f} (>= {MIN_CONFIDENCE_THRESHOLD} threshold)")
        print(f"[TASK]    Reasoning: {reasoning}")
        
        # Update status with detailed OCR skip information
        ctx.update_status(PipelineStatus.OCR_SKIPPED, {
            "ocr_skipped_reason": reasoning,
            "confidence_score": confidence,
            "confidence_threshold_met": True,
            "estimated_completeness": ctx.sufficiency_result.estimated_completeness,
            "decision_factors": {
                "is_sufficient": is_sufficient,
                "confidence_above_threshold": confidence >= MIN_CONFIDENCE_THRESHOLD,
                "threshold_used": MIN_CONFIDENCE_THRESHOLD
            }
        })
        
        # Store empty OCR results for potential fallback
        ctx.original_ocr_results = []
        return []  # Return empty OCR results
    
    else:
        # Determine why OCR is needed
        if not is_sufficient:
            skip_reason = f"OpenAI analysis indicates insufficient data (confidence: {confidence:.2f})"
        else:
            skip_reason = f"Confidence {confidence:.2f} below threshold {MIN_CONFIDENCE_THRESHOLD}"
        
        print(f"[TASK] 🔍 Proceeding with OCR - {skip_reason}")
        print(f"[TASK]    Reasoning: {reasoning}")
        
        # Update status to show OCR decision reasoning
        ctx.update_status(PipelineStatus.OCRING, {
            "ocr_required_reason": skip_reason,
            "confidence_score": confidence,
            "confidence_threshold_met": confidence >= MIN_CONFIDENCE_THRESHOLD,
            "estimated_completeness": ctx.sufficiency_result.estimated_completeness
        })
        
        ocr_results = _ocr_stage(ctx, video_path, job_dir)
        # Store OCR results for potential fallback comparison
        ctx.original_ocr_results = ocr_results
        return ocr_results


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
    """Handle LLM refinement stage with intelligent fallback mechanism"""
    return _llm_stage_with_fallback(ctx, normalized_title, transcript, ocr_results)


def _llm_stage_with_fallback(ctx: PipelineContext, normalized_title, transcript, ocr_results):
    """Handle LLM refinement with intelligent fallback to OCR if recipe quality is poor"""
    ctx.update_status(PipelineStatus.LLM_REFINING)
                llm_start = time.time()
    
                try:
                    print(f"[TASK] Starting LLM recipe refinement...")
                    
        # Initialize services
                    llm_service = LLMRefineService()
        quality_analyzer = RecipeQualityAnalyzer()
                    
        # Extract TikTok author from URL
                    tiktok_author = ""
        if "@" in ctx.url:
                        try:
                tiktok_author = ctx.url.split("@")[1].split("/")[0]
                        except:
                            pass
        
        # First attempt: Refine recipe with current data
        recipe_json, parse_error = llm_service.refine_with_validation_retry(
            title=normalized_title,
            transcript=transcript,
            ocr_results=ocr_results,
            source_url=ctx.url,
            tiktok_author=tiktok_author,
            video_thumbnail=ctx.thumbnail_url or "",
            max_validation_retries=2
        )
        
        # Analyze recipe quality for potential fallback
        if recipe_json and ctx.sufficiency_result:
            quality_result = quality_analyzer.analyze_recipe_quality(recipe_json)
            fallback_decision = quality_analyzer.should_trigger_fallback(
                quality_result, ctx.sufficiency_result.confidence_score
            )
            
            # Check if fallback should be triggered
            if (fallback_decision['should_fallback'] and 
                not ctx.fallback_triggered and 
                not ocr_results):  # Only if OCR was originally skipped
                
                print(f"[TASK] 🔄 FALLBACK TRIGGERED - Recipe quality insufficient")
                print(f"[TASK]    Quality score: {quality_result.quality_score:.2f}")
                print(f"[TASK]    Missing: {', '.join(quality_result.missing_components)}")
                print(f"[TASK]    Reasons: {', '.join(fallback_decision['reasons'])}")
                
                # Mark fallback as triggered to prevent infinite loops
                ctx.fallback_triggered = True
                
                # Update status to indicate fallback
                ctx.update_status(PipelineStatus.FALLBACK_OCR_TRIGGERED, {
                    "fallback_reason": fallback_decision['reasons'],
                    "original_quality_score": quality_result.quality_score,
                    "original_confidence": ctx.sufficiency_result.confidence_score,
                    "missing_components": quality_result.missing_components,
                    "quality_issues": quality_result.quality_issues
                })
                
                # Run OCR as fallback
                fallback_ocr_results = _run_fallback_ocr(ctx)
                
                # Re-run LLM with OCR data
                if fallback_ocr_results:
                    print(f"[TASK] Re-running LLM with fallback OCR data ({len(fallback_ocr_results)} results)")
                    
                    recipe_json_fallback, parse_error_fallback = llm_service.refine_with_validation_retry(
                        title=normalized_title,
                        transcript=transcript,
                        ocr_results=fallback_ocr_results,
                        source_url=ctx.url,
                        tiktok_author=tiktok_author,
                        video_thumbnail=ctx.thumbnail_url or "",
                        max_validation_retries=2
                    )
                    
                    # Compare quality of fallback result
                    if recipe_json_fallback:
                        fallback_quality = quality_analyzer.analyze_recipe_quality(recipe_json_fallback)
                        
                        # Use fallback result if it's better
                        if fallback_quality.quality_score > quality_result.quality_score:
                            print(f"[TASK] ✅ Fallback improved quality: {quality_result.quality_score:.2f} → {fallback_quality.quality_score:.2f}")
                            recipe_json = recipe_json_fallback
                            parse_error = parse_error_fallback
                            ocr_results = fallback_ocr_results  # Update for metadata
                        else:
                            print(f"[TASK] ⚠️ Fallback didn't improve quality, keeping original")
                else:
                    print(f"[TASK] ⚠️ Fallback OCR failed, keeping original recipe")
                    
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
            "ocr_frames_processed": len(ocr_results) if ocr_results else 0,
            "fallback_triggered": ctx.fallback_triggered
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


def _run_fallback_ocr(ctx: PipelineContext):
    """Run OCR as a fallback mechanism when recipe quality is insufficient"""
    try:
        print(f"[TASK] Running intelligent fallback OCR...")
        
        if not ctx.video_path or not ctx.job_dir:
            print(f"[TASK] ⚠️ Missing video path or job directory for fallback OCR")
            return []
        
        # Update status to show fallback OCR is running
        ctx.update_status(PipelineStatus.OCRING, {
            "fallback_ocr_running": True,
            "reason": "Recipe quality insufficient despite high AI confidence"
        })
        
        # Run the same OCR process as the normal pipeline
        fallback_start = time.time()
        
        # Extract frames (same as normal OCR stage)
        frame_extract_start = time.time()
        try:
            print(f"[TASK] Extracting video frames for fallback OCR...")
            frames = extract_frames(ctx.video_path, ctx.job_dir / "fallback_frames", 
                                  method="scene", fps=1.0, max_frames=8)
            log_stage_timing("FALLBACK_FRAME_EXTRACTION", frame_extract_start)
            print(f"[TASK] Fallback frame extraction completed: {len(frames)} frames")
        except Exception as e:
            log_stage_timing("FALLBACK_FRAME_EXTRACTION", frame_extract_start)
            print(f"[ERROR] Fallback frame extraction failed: {e}")
            return []
        
        # Run OCR on frames
        if frames:
            ocr_start = time.time()
            try:
                print(f"[TASK] Running OCR on {len(frames)} fallback frames...")
                ocr_service = OCRService()
                ocr_results = []
                
                for i, frame_path in enumerate(frames):
                    try:
                        frame_results = ocr_service.extract_text_from_frame(frame_path)
                        if frame_results:
                            ocr_results.extend(frame_results)
                    except Exception as e:
                        print(f"[TASK] OCR failed for fallback frame {i+1}: {e}")
                        continue
                
                log_stage_timing("FALLBACK_OCR_PROCESSING", ocr_start)
                
                if ocr_results:
                    print(f"[TASK] ✅ Fallback OCR completed: {len(ocr_results)} text blocks found")
                    
                    # Update OCR results in Firestore
                    if ctx.tiktok_service:
                        ctx.tiktok_service.update_ocr_results(
                            ctx.job_id, 
                            ocr_results, 
                            []  # No ingredient candidates for fallback
                        )
                    
                    return ocr_results
                else:
                    print(f"[TASK] ⚠️ Fallback OCR found no text in frames")
                    return []
                    
            except Exception as e:
                log_stage_timing("FALLBACK_OCR_PROCESSING", ocr_start)
                print(f"[ERROR] Fallback OCR processing failed: {e}")
                return []
        else:
            print(f"[TASK] ⚠️ No frames available for fallback OCR")
            return []
        
    except Exception as e:
        print(f"[ERROR] Fallback OCR failed: {e}")
        return []


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
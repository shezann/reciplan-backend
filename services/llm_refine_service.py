import json
import os
import time
import hashlib
from typing import Dict, Any, Tuple, Optional
from openai import OpenAI
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

class LLMRefineError(Exception):
    """Custom exception for LLM refinement errors"""
    pass

class LLMRefineService:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM service with OpenAI client
        Args:
            api_key: OpenAI API key (optional, will use env var if not provided)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise LLMRefineError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"  # Use faster model for production
        self.prompt_template = self._load_prompt_template()
        
        logger.info(f"LLMRefineService initialized with model: {self.model}")

    @lru_cache(maxsize=1)
    def _load_prompt_template(self) -> str:
        """Load prompt template with caching for performance"""
        try:
            with open('prompts/recipe_refine_prompt.txt', 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error("Prompt template file not found: prompts/recipe_refine_prompt.txt")
            raise LLMRefineError("Prompt template file not found")

    def _create_content_hash(self, title: str, transcript: str, ocr_results: list) -> str:
        """Create hash of input content for caching"""
        content = f"{title}:{transcript}:{str(ocr_results)}"
        return hashlib.md5(content.encode()).hexdigest()

    def _prepare_ocr_text(self, ocr_results: list) -> str:
        """
        Prepare OCR text for LLM input with optimized processing
        Args:
            ocr_results: List of OCR results from frames
        Returns:
            Formatted OCR text string
        """
        if not ocr_results:
            return "No OCR text detected."
        
        # Optimize OCR text processing
        ocr_text_parts = []
        for frame_result in ocr_results:
            if frame_result.get("text_blocks"):
                # Filter out empty or whitespace-only text
                frame_texts = [block["text"].strip() for block in frame_result["text_blocks"] if block["text"].strip()]
                if frame_texts:
                    ocr_text_parts.append(f"Frame at {frame_result.get('timestamp', 0)}s: {' | '.join(frame_texts)}")
        
        return "\n".join(ocr_text_parts) if ocr_text_parts else "No readable text detected."

    def _extract_json_from_response(self, response: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Extract JSON from LLM response with improved error handling
        Args:
            response: Raw response from LLM
        Returns:
            Tuple of (parsed_json, error_message)
        """
        try:
            # Try to find JSON block
            json_start = response.find('```json')
            if json_start != -1:
                json_start = response.find('\n', json_start) + 1
                json_end = response.find('```', json_start)
                if json_end != -1:
                    json_str = response[json_start:json_end].strip()
                else:
                    json_str = response[json_start:].strip()
            else:
                # Try to find plain JSON
                json_str = response.strip()
            
            # Parse JSON
            parsed_json = json.loads(json_str)
            return parsed_json, None
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return None, f"Invalid JSON format: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {e}")
            return None, f"Unexpected error: {str(e)}"

    def _call_openai(self, messages: list, max_retries: int = 3) -> str:
        """
        Call OpenAI API with retry logic and optimized settings
        Args:
            messages: List of message dictionaries
            max_retries: Maximum number of retry attempts
        Returns:
            Response content from OpenAI
        """
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.1,  # Lower temperature for more consistent output
                    max_tokens=2000,  # Limit tokens for faster response
                    timeout=30  # Add timeout
                )
                return response.choices[0].message.content
                
            except Exception as e:
                logger.warning(f"OpenAI API call attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise LLMRefineError(f"OpenAI API call failed after {max_retries} attempts: {e}")
                time.sleep(1 * (attempt + 1))  # Exponential backoff

    def _validate_recipe_data(self, recipe_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate recipe data structure with improved validation
        Args:
            recipe_data: Parsed recipe data
        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = ['title', 'ingredients', 'instructions']
        for field in required_fields:
            if field not in recipe_data:
                return False, f"Missing required field: {field}"
        
        if not recipe_data.get('title', '').strip():
            return False, "Title cannot be empty"
        
        if not recipe_data.get('ingredients'):
            return False, "At least one ingredient is required"
        
        if not recipe_data.get('instructions'):
            return False, "At least one instruction is required"
        
        return True, None

    def _create_reprompt_message(self, original_error: str, original_response: str) -> str:
        """
        Create reprompt message for validation failures
        Args:
            original_error: Error from original response
            original_response: Original LLM response
        Returns:
            Reprompt message
        """
        return f"""Your previous response had an error: {original_error}

Original response:
{original_response}

Please fix the error and provide a valid JSON response that matches the schema exactly."""

    def refine_recipe(self, title: str, transcript: str, ocr_results: list, 
                     source_url: str = "", tiktok_author: str = "", video_thumbnail: str = "") -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Refine recipe using LLM with optimized processing
        Args:
            title: Recipe title
            transcript: Audio transcript
            ocr_results: OCR results from video frames
            source_url: Source URL
            tiktok_author: TikTok author username
            video_thumbnail: Video thumbnail URL
        Returns:
            Tuple of (recipe_json, parse_error)
        """
        try:
            # Prepare inputs
            ocr_text = self._prepare_ocr_text(ocr_results)
            
            # Create system message
            system_message = {
                "role": "system",
                "content": self.prompt_template
            }
            
            # Create user message
            user_message = {
                "role": "user",
                "content": f"""Title: {title}
Transcript: {transcript}
OCR Text: {ocr_text}
Source URL: {source_url}
TikTok Author: {tiktok_author}
Video Thumbnail: {video_thumbnail}"""
            }
            
            # Call OpenAI
            response = self._call_openai([system_message, user_message])
            
            # Parse response
            recipe_json, parse_error = self._extract_json_from_response(response)
            
            if recipe_json:
                # Validate recipe data
                is_valid, validation_error = self._validate_recipe_data(recipe_json)
                if not is_valid:
                    parse_error = validation_error
                    recipe_json = None
            
            # Add source metadata
            if recipe_json:
                recipe_json["source_url"] = source_url
                recipe_json["tiktok_author"] = tiktok_author
                recipe_json["is_public"] = True
                recipe_json["created_at"] = None
                recipe_json["updated_at"] = None
                recipe_json["video_thumbnail"] = video_thumbnail
                recipe_json["saved_by"] = []
                recipe_json["source_platform"] = "tiktok"
                recipe_json["original_job_id"] = ""
            
            return recipe_json, parse_error
            
        except Exception as e:
            logger.error(f"Error in refine_recipe: {e}")
            return None, f"LLM processing error: {str(e)}"

    def refine_with_validation_retry(self, title: str, transcript: str, ocr_results: list,
                                   source_url: str = "", tiktok_author: str = "", video_thumbnail: str = "",
                                   max_validation_retries: int = 2) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Refine recipe with validation retry logic
        Args:
            title: Recipe title
            transcript: Audio transcript
            ocr_results: OCR results from video frames
            source_url: Source URL
            tiktok_author: TikTok author username
            video_thumbnail: Video thumbnail URL
            max_validation_retries: Maximum validation retry attempts
        Returns:
            Tuple of (recipe_json, parse_error)
        """
        recipe_json, parse_error = self.refine_recipe(title, transcript, ocr_results, source_url, tiktok_author, video_thumbnail)
        
        # Retry on validation errors
        for attempt in range(max_validation_retries):
            if parse_error and "JSON" in parse_error:
                logger.info(f"Retrying due to JSON error (attempt {attempt + 1}/{max_validation_retries})")
                
                # Create reprompt
                reprompt_content = self._create_reprompt_message(parse_error, "")
                
                try:
                    # Call OpenAI with reprompt
                    response = self._call_openai([
                        {"role": "system", "content": self.prompt_template},
                        {"role": "user", "content": f"Title: {title}\nTranscript: {transcript}\nOCR Text: {self._prepare_ocr_text(ocr_results)}\nSource URL: {source_url}\nTikTok Author: {tiktok_author}\nVideo Thumbnail: {video_thumbnail}"},
                        {"role": "assistant", "content": "I'll provide a valid JSON response."},
                        {"role": "user", "content": reprompt_content}
                    ])
                    
                    # Parse new response
                    recipe_json, parse_error = self._extract_json_from_response(response)
                    
                    if recipe_json:
                        # Validate new recipe data
                        is_valid, validation_error = self._validate_recipe_data(recipe_json)
                        if not is_valid:
                            parse_error = validation_error
                            recipe_json = None
                        else:
                            # Add metadata to successful response
                            recipe_json["source_url"] = source_url
                            recipe_json["tiktok_author"] = tiktok_author
                            recipe_json["is_public"] = True
                            recipe_json["created_at"] = None
                            recipe_json["updated_at"] = None
                            recipe_json["video_thumbnail"] = video_thumbnail
                            recipe_json["saved_by"] = []
                            recipe_json["source_platform"] = "tiktok"
                            recipe_json["original_job_id"] = ""
                            break
                            
                except Exception as e:
                    logger.error(f"Retry attempt {attempt + 1} failed: {e}")
                    parse_error = f"Retry failed: {str(e)}"
        
        return recipe_json, parse_error

    def refine_with_retry(self, title: str, transcript: str, ocr_results: list,
                         source_url: str = "", tiktok_author: str = "",
                         max_retries: int = 2) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Refine recipe with general retry logic (deprecated, use refine_with_validation_retry)
        """
        logger.warning("refine_with_retry is deprecated, use refine_with_validation_retry")
        return self.refine_with_validation_retry(title, transcript, ocr_results, source_url, tiktok_author, max_retries) 
from pathlib import Path
from typing import List, Dict, Any, Tuple

from paddleocr import PaddleOCR
import re
from difflib import SequenceMatcher

class OCRService:
    _instance = None
    _ocr_instance = None
    
    def __new__(cls, lang: str = 'en'):
        if cls._instance is None:
            cls._instance = super(OCRService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, lang: str = 'en'):
        if not self._initialized:
            # Create singleton PaddleOCR instance
            if OCRService._ocr_instance is None:
                print("[OCRService] Initializing PaddleOCR (this may take a moment on first run)...")
                try:
                    OCRService._ocr_instance = PaddleOCR(
                        use_angle_cls=False,  # Disable angle classification for speed
                        lang=lang
                    )
                    print("[OCRService] PaddleOCR initialization complete!")
                except Exception as e:
                    print(f"[OCRService] Failed to initialize PaddleOCR: {e}")
                    raise
            self.ocr = OCRService._ocr_instance
            self._initialized = True
    
    @classmethod
    def get_instance(cls, lang: str = 'en'):
        """Get singleton instance of OCRService"""
        return cls(lang)

    def run_ocr_on_frames(self, frames: List[Tuple[Path, float]]) -> List[Dict[str, Any]]:
        """
        Run OCR on a list of frames.
        Args:
            frames: List of (frame_path, timestamp) tuples.
        Returns:
            List of dicts: {timestamp, text_blocks: [{text, bbox}]}
        """
        results = []
        print(f"[OCRService] Starting OCR on {len(frames)} frames")
        for frame_path, timestamp in frames:
            print(f"[OCRService] Processing frame: {frame_path}")
            try:
                ocr_result = self.ocr.ocr(str(frame_path))
                print(f"[OCRService] Raw OCR result type: {type(ocr_result)}")
                print(f"[OCRService] Raw OCR result: {ocr_result}")
            except Exception as e:
                print(f"[OCRService] Error processing frame {frame_path}: {e}")
                continue
            
            # Filter out low-confidence results
            text_blocks = []
            print(f"[OCRService] Processing OCR result: {type(ocr_result)}")
            
            # Handle new PaddleOCR format (dictionary with rec_texts and rec_scores)
            if ocr_result and isinstance(ocr_result[0], dict):
                ocr_data = ocr_result[0]
                rec_texts = ocr_data.get('rec_texts', [])
                rec_scores = ocr_data.get('rec_scores', [])
                rec_polys = ocr_data.get('rec_polys', [])
                
                print(f"[OCRService] Found {len(rec_texts)} text items in new format")
                
                for i, (text, confidence) in enumerate(zip(rec_texts, rec_scores)):
                    print(f"[OCRService] Processing text {i}: '{text}' (confidence: {confidence})")
                    
                    # Only include high-confidence text (score > 0.5) - lowered for better detection
                    if confidence > 0.5 and len(text.strip()) > 1:  # Minimum 2 characters
                        # Get bounding box if available
                        bbox = rec_polys[i] if i < len(rec_polys) else [[0, 0], [1, 0], [1, 1], [0, 1]]
                        block = {"text": text, "bbox": tolist_recursive(bbox), "score": confidence}
                        text_blocks.append(block)
                        print(f"[OCRService] Added text block: {block}")
                    else:
                        print(f"[OCRService] Skipped text due to low confidence or short length")
            
            # Handle old PaddleOCR format (list of [bbox, (text, confidence)] tuples)
            elif ocr_result and ocr_result[0] and isinstance(ocr_result[0], list):
                print(f"[OCRService] Found {len(ocr_result[0])} text lines in old format")
                for line in ocr_result[0]:  # Each line contains [bbox, (text, confidence)]
                    print(f"[OCRService] Processing line: {line}")
                    if len(line) >= 2:
                        bbox = line[0]  # Bounding box coordinates
                        text_info = line[1]  # (text, confidence) tuple
                        print(f"[OCRService] Bbox: {bbox}, Text info: {text_info}")
                        if len(text_info) >= 2:
                            text = text_info[0]
                            confidence = float(text_info[1])
                            print(f"[OCRService] Text: '{text}', Confidence: {confidence}")
                            # Only include high-confidence text (score > 0.5) - lowered for better detection
                            if confidence > 0.5 and len(text.strip()) > 1:  # Minimum 2 characters
                                block = {"text": text, "bbox": tolist_recursive(bbox), "score": confidence}
                                text_blocks.append(block)
                                print(f"[OCRService] Added text block: {block}")
                            else:
                                print(f"[OCRService] Skipped text due to low confidence or short length")
                        else:
                            print(f"[OCRService] Invalid text_info format: {text_info}")
                    else:
                        print(f"[OCRService] Invalid line format: {line}")
            else:
                print(f"[OCRService] No OCR result or empty result")
            
            if text_blocks:  # Only add frames with detected text
                results.append({
                    "timestamp": timestamp,
                    "text_blocks": text_blocks,
                    "frame_path": str(frame_path)
                })
                print(f"[OCRService] Found {len(text_blocks)} text blocks in {frame_path}")
            else:
                print(f"[OCRService] No text detected in {frame_path}")
        
        print(f"[OCRService] Final results: {len(results)} frames with text")
        for i, result in enumerate(results):
            print(f"[OCRService] Frame {i}: {len(result['text_blocks'])} text blocks")
        return results

    def extract_text(self, frames: List[Tuple[Path, float]]) -> List[Dict[str, Any]]:
        """
        Extract text from frames (alias for run_ocr_on_frames for compatibility)
        Args:
            frames: List of (frame_path, timestamp) tuples.
        Returns:
            List of dicts: {timestamp, text_blocks: [{text, bbox}]}
        """
        return self.run_ocr_on_frames(frames)

    @staticmethod
    def dedupe_text_blocks(text_blocks: List[Dict[str, any]], threshold: float = 0.85) -> List[Dict[str, any]]:
        """
        Merge near-duplicate text lines using fuzzy matching.
        Args:
            text_blocks: List of {text, bbox}
            threshold: Similarity threshold for merging
        Returns:
            Deduplicated list of text_blocks
        """
        deduped = []
        seen = []
        for block in text_blocks:
            text = block["text"].strip().lower()
            if any(SequenceMatcher(None, text, s).ratio() > threshold for s in seen):
                continue
            seen.append(text)
            deduped.append(block)
        return deduped

    @staticmethod
    def extract_ingredient_candidates(text_blocks: List[Dict[str, any]]) -> List[str]:
        """
        Identify ingredient-like lines using regex for quantity/units.
        Args:
            text_blocks: List of {text, bbox}
        Returns:
            List of ingredient candidate strings
        """
        ingredient_regex = re.compile(r"\b(\d+\s?(?:[\/\.]\d+)?\s?(?:cup|tbsp|tsp|g|kg|ml|l|oz|lb|teaspoon|tablespoon|gram|pound|ounce|pinch|clove|slice|can|package|stick|dash|handful|bunch|piece|quart|pint|liter|milliliter|milligram|mg|cm|mm|inch|drop)s?\b)", re.I)
        candidates = []
        for block in text_blocks:
            text = block["text"]
            if ingredient_regex.search(text):
                candidates.append(text)
        return candidates 

def tolist_recursive(x):
    if hasattr(x, 'tolist'):
        return tolist_recursive(x.tolist())
    elif isinstance(x, (list, tuple)):
        return [tolist_recursive(i) for i in x]
    elif hasattr(x, 'item'):
        return x.item()
    elif isinstance(x, (float, int, str)):
        return x
    else:
        try:
            return float(x)
        except Exception:
            return str(x) 
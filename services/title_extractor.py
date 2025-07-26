import re
from typing import List, Dict, Any

class TitleExtractor:
    @staticmethod
    def from_metadata(metadata_title: str | None) -> str | None:
        """
        Return the raw title from metadata if present and non-empty, else None.
        """
        print(f"[TitleExtractor] from_metadata called with: {metadata_title}")
        if metadata_title and metadata_title.strip():
            result = metadata_title.strip()
            print(f"[TitleExtractor] Returning metadata title: {result}")
            return result
        print(f"[TitleExtractor] No valid metadata title found")
        return None

    @staticmethod
    def from_transcript(transcript: str) -> str | None:
        """
        Fallback: Return the first non-empty sentence from the transcript.
        """
        print(f"[TitleExtractor] from_transcript called with transcript length: {len(transcript) if transcript else 0}")
        if not transcript:
            print(f"[TitleExtractor] No transcript provided")
            return None
        
        # Simple fallback: just return the first sentence
        sentences = re.split(r'[.!?\n]', transcript)
        print(f"[TitleExtractor] Found {len(sentences)} sentences")
        for i, sentence in enumerate(sentences):
            s = sentence.strip()
            if s and len(s) > 3:  # Only use sentences with meaningful content
                print(f"[TitleExtractor] Using sentence {i}: {s}")
                return s
        print(f"[TitleExtractor] No valid sentences found")
        return None

    @staticmethod
    def normalize_title(raw_title: str) -> str:
        """
        Normalize the title:
        - Keep emojis (preserve TikTok style)
        - Remove hashtags
        - Trim whitespace
        - Cap to 100 characters
        - Preserve original casing (don't force lowercase)
        """
        print(f"[TitleExtractor] normalize_title called with: {raw_title}")
        if not raw_title:
            print(f"[TitleExtractor] No raw title provided")
            return ""
        
        # Remove hashtags but keep emojis
        no_hashtags = re.sub(r'#\w+', '', raw_title)
        # Trim whitespace
        trimmed = no_hashtags.strip()
        # No character limit - keep the full title
        # TikTok creators often put full recipes in titles
        normalized = trimmed
        print(f"[TitleExtractor] Final normalized title: {normalized}")
        return normalized

    @staticmethod
    def from_ocr_text(ocr_results: List[Dict[str, any]]) -> str | None:
        """
        Extract title from OCR text blocks.
        Args:
            ocr_results: List of OCR frame results
        Returns:
            Potential title string or None
        """
        print(f"[TitleExtractor] from_ocr_text called with {len(ocr_results)} OCR frames")
        
        # Collect all text from OCR
        all_text = []
        for frame in ocr_results:
            if "text_blocks" in frame:
                for block in frame["text_blocks"]:
                    if "text" in block:
                        all_text.append(block["text"].strip())
        
        if not all_text:
            print(f"[TitleExtractor] No OCR text found")
            return None
        
        # Look for recipe title patterns in OCR text
        recipe_keywords = [
            "caramelized", "onion", "garlic", "spaghetti", "pasta", "sauce", "chicken", "beef", "pork",
            "salmon", "shrimp", "vegetables", "salad", "soup", "stew", "curry", "stir fry", "grilled",
            "baked", "fried", "roasted", "braised", "poached", "seared", "smoked", "pickled"
        ]
        
        # Try to find a combination of keywords that form a recipe title
        for i, text in enumerate(all_text):
            text_lower = text.lower()
            for keyword in recipe_keywords:
                if keyword in text_lower:
                    # Look for related keywords in nearby text blocks
                    title_parts = [text]
                    for j in range(max(0, i-2), min(len(all_text), i+3)):
                        if j != i:
                            nearby_text = all_text[j].lower()
                            # Check if nearby text contains related recipe keywords
                            for other_keyword in recipe_keywords:
                                if other_keyword in nearby_text and other_keyword != keyword:
                                    title_parts.append(all_text[j])
                                    break
                    
                    if len(title_parts) > 1:
                        title = " ".join(title_parts)  # No limit - keep all parts
                        print(f"[TitleExtractor] Found OCR title: {title}")
                        return title
        
        # Fallback: return the longest text block that looks like a recipe name
        longest_text = max(all_text, key=len) if all_text else ""
        if len(longest_text) > 5:
            print(f"[TitleExtractor] Using longest OCR text as title: {longest_text}")
            return longest_text
        
        print(f"[TitleExtractor] No suitable OCR title found")
        return None 
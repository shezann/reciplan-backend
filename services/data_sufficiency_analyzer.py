"""
Data Sufficiency Analyzer Service

This service uses OpenAI to evaluate whether the available data from title, transcript, 
and metadata is sufficient for LLM recipe refinement without requiring OCR processing.
"""

import logging
import json
from typing import Dict
from dataclasses import dataclass
from openai import OpenAI
import os

logger = logging.getLogger(__name__)

# Initialize OpenAI client (v1.0+ API)
api_key = os.getenv('OPENAI_API_KEY')
if api_key:
    client = OpenAI(api_key=api_key)
else:
    client = None
    logger.warning("OPENAI_API_KEY not set - data sufficiency analysis will be disabled")


@dataclass
class SufficiencyResult:
    """Result of data sufficiency analysis"""
    is_sufficient: bool
    confidence_score: float  # 0.0 to 1.0
    reasoning: str
    estimated_completeness: Dict[str, str]  # ingredients, instructions, timing, measurements


class DataSufficiencyAnalyzer:
    """
    Uses OpenAI to analyze recipe data completeness and determine if OCR is needed
    """
    
    def __init__(self):
        self.analysis_prompt = """
You are a recipe analysis expert. Your task is to evaluate whether the provided data contains enough information to create a complete recipe without needing additional visual text extraction (OCR).

Analyze the following data and determine if it's sufficient to create a structured recipe with:
- At least 3 ingredients with measurements
- At least 2 cooking instruction steps
- Basic timing information (prep/cook time)

Respond with a JSON object in this exact format:
{
    "is_sufficient": true/false,
    "confidence_score": 0.0-1.0,
    "reasoning": "Brief explanation of your decision",
    "estimated_completeness": {
        "ingredients": "complete/partial/missing",
        "instructions": "complete/partial/missing", 
        "timing": "complete/partial/missing",
        "measurements": "complete/partial/missing"
    }
}

Be conservative - only mark as sufficient if you're confident a good recipe can be created from the available data alone.
"""
    
    def analyze_sufficiency(self, title: str = "", transcript: str = "", 
                          metadata: Dict = None) -> SufficiencyResult:
        """
        Use OpenAI to analyze if the available data is sufficient for recipe refinement
        
        Args:
            title: Video title
            transcript: Audio transcript
            metadata: Additional metadata (description, etc.)
            
        Returns:
            SufficiencyResult with analysis details
        """
        try:
            # Combine all text sources
            combined_text = self._combine_text_sources(title, transcript, metadata)
            
            if not combined_text.strip():
                return SufficiencyResult(
                    is_sufficient=False,
                    confidence_score=0.0,
                    reasoning="No data provided for analysis",
                    estimated_completeness={
                        "ingredients": "missing",
                        "instructions": "missing",
                        "timing": "missing",
                        "measurements": "missing"
                    }
                )
            
            # Create user message with the data to analyze
            user_message = f"""
Title: {title}
Transcript: {transcript}
Description: {metadata.get('description', '') if metadata else ''}

Please analyze this data for recipe completeness.
"""
            
            # Call OpenAI for analysis
            response = self._call_openai_for_analysis(user_message)
            
            # Parse the response
            result = self._parse_analysis_response(response)
            
            logger.info(f"Data sufficiency analysis: sufficient={result.is_sufficient}, confidence={result.confidence_score:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"Error in sufficiency analysis: {e}")
            # Default to requiring OCR on error
            return SufficiencyResult(
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
    
    def _combine_text_sources(self, title: str, transcript: str, metadata: Dict = None) -> str:
        """Combine all available text sources"""
        text_parts = []
        
        if title:
            text_parts.append(f"Title: {title}")
        
        if transcript:
            text_parts.append(f"Transcript: {transcript}")
        
        if metadata:
            description = metadata.get('description', '')
            if description:
                text_parts.append(f"Description: {description}")
        
        return '\n'.join(text_parts)
    
    def _call_openai_for_analysis(self, user_message: str) -> str:
        """Call OpenAI API for sufficiency analysis"""
        if client is None:
            raise Exception("OpenAI client not initialized - OPENAI_API_KEY not set")
            
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": self.analysis_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1,  # Low temperature for consistent analysis
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise
    
    def _parse_analysis_response(self, response: str) -> SufficiencyResult:
        """Parse OpenAI response into SufficiencyResult"""
        try:
            # Try to extract JSON from the response
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:]
            if response_clean.endswith('```'):
                response_clean = response_clean[:-3]
            
            data = json.loads(response_clean)
            
            return SufficiencyResult(
                is_sufficient=data.get("is_sufficient", False),
                confidence_score=float(data.get("confidence_score", 0.0)),
                reasoning=data.get("reasoning", "No reasoning provided"),
                estimated_completeness=data.get("estimated_completeness", {
                    "ingredients": "unknown",
                    "instructions": "unknown",
                    "timing": "unknown",
                    "measurements": "unknown"
                })
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse OpenAI response: {e}")
            logger.error(f"Raw response: {response}")
            
            # Fallback: try to determine sufficiency from response text
            response_lower = response.lower()
            is_sufficient = "sufficient" in response_lower or "yes" in response_lower
            
            return SufficiencyResult(
                is_sufficient=is_sufficient,
                confidence_score=0.5 if is_sufficient else 0.0,
                reasoning=f"Parsed from text response: {response[:200]}...",
                estimated_completeness={
                    "ingredients": "unknown",
                    "instructions": "unknown", 
                    "timing": "unknown",
                    "measurements": "unknown"
                }
            )
    
    def get_analysis_summary(self, result: SufficiencyResult) -> Dict:
        """Get a summary suitable for API responses"""
        return {
            "is_sufficient": result.is_sufficient,
            "confidence_score": round(result.confidence_score, 2),
            "reasoning": result.reasoning,
            "estimated_completeness": result.estimated_completeness
        } 
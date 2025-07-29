"""
Recipe Quality Analyzer Service

Analyzes the quality and completeness of LLM-generated recipes to determine
if they meet minimum standards. Used for intelligent fallback decisions.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

@dataclass
class RecipeQualityResult:
    """Result of recipe quality analysis"""
    is_complete: bool
    quality_score: float  # 0.0 to 1.0
    missing_components: List[str]
    quality_issues: List[str]
    ingredient_count: int
    step_count: int
    has_measurements: bool
    has_timing: bool
    meets_minimum_standards: bool

class RecipeQualityAnalyzer:
    """Analyzes recipe completeness and quality for fallback decisions"""
    
    def __init__(self):
        # Minimum requirements for a complete recipe
        self.min_ingredients = 3
        self.min_steps = 2
        self.min_quality_score = 0.6
        
    def analyze_recipe_quality(self, recipe_json: Dict[str, Any]) -> RecipeQualityResult:
        """
        Analyze the quality and completeness of an LLM-generated recipe
        
        Args:
            recipe_json: The recipe data from LLM
            
        Returns:
            RecipeQualityResult with detailed analysis
        """
        try:
            if not recipe_json:
                return self._create_empty_result("Recipe JSON is None or empty")
            
            # Extract recipe components
            ingredients = recipe_json.get('ingredients', [])
            steps = recipe_json.get('instructions', [])  # Use 'instructions' field, not 'steps'
            title = recipe_json.get('title', '')
            
            # Analyze components
            ingredient_analysis = self._analyze_ingredients(ingredients)
            step_analysis = self._analyze_steps(steps)
            timing_analysis = self._analyze_timing(recipe_json, steps)
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(
                ingredient_analysis, step_analysis, timing_analysis, title
            )
            
            # Determine missing components
            missing_components = []
            quality_issues = []
            
            if len(ingredients) < self.min_ingredients:
                missing_components.append(f"ingredients (has {len(ingredients)}, need {self.min_ingredients})")
            
            if len(steps) < self.min_steps:
                missing_components.append(f"cooking steps (has {len(steps)}, need {self.min_steps})")
            
            if not ingredient_analysis['has_measurements']:
                missing_components.append("ingredient measurements")
                quality_issues.append("Most ingredients lack specific measurements")
            
            if not timing_analysis['has_timing']:
                quality_issues.append("No cooking times or temperatures specified")
            
            if not title.strip():
                quality_issues.append("Missing or empty recipe title")
            
            # Check for vague or incomplete steps
            vague_steps = [step for step in steps if len(step.strip()) < 10]
            if len(vague_steps) > 0:
                quality_issues.append(f"{len(vague_steps)} cooking steps are too vague or short")
            
            # Determine overall completeness
            is_complete = (
                len(ingredients) >= self.min_ingredients and
                len(steps) >= self.min_steps and
                ingredient_analysis['has_measurements'] and
                quality_score >= self.min_quality_score
            )
            
            meets_minimum_standards = (
                len(ingredients) >= self.min_ingredients and
                len(steps) >= self.min_steps
            )
            
            result = RecipeQualityResult(
                is_complete=is_complete,
                quality_score=quality_score,
                missing_components=missing_components,
                quality_issues=quality_issues,
                ingredient_count=len(ingredients),
                step_count=len(steps),
                has_measurements=ingredient_analysis['has_measurements'],
                has_timing=timing_analysis['has_timing'],
                meets_minimum_standards=meets_minimum_standards
            )
            
            logger.info(f"Recipe quality analysis: complete={is_complete}, score={quality_score:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing recipe quality: {e}")
            return self._create_empty_result(f"Analysis error: {str(e)}")
    
    def _analyze_ingredients(self, ingredients: List[Dict]) -> Dict:
        """Analyze ingredient quality and completeness"""
        if not ingredients:
            return {'has_measurements': False, 'measurement_ratio': 0.0}
        
        ingredients_with_measurements = 0
        
        for ingredient in ingredients:
            if isinstance(ingredient, dict):
                # Check for name and quantity fields (correct LLM schema)
                has_name = bool(ingredient.get('name', '').strip())
                has_quantity = bool(ingredient.get('quantity', '').strip())
                
                # Also check if quantity contains measurement patterns
                quantity = ingredient.get('quantity', '')
                import re
                measurement_pattern = r'\b\d+(?:\.\d+)?(?:\s*(?:cup|tbsp|tsp|oz|lb|g|kg|ml|l|pound|tablespoon|teaspoon|inch|large|medium|small|cloves?|bunch|bulbs?))\b'
                has_measurement = bool(re.search(measurement_pattern, quantity.lower())) if quantity else False
                
                if has_name and (has_quantity or has_measurement):
                    ingredients_with_measurements += 1
            elif isinstance(ingredient, str):
                # Check for measurement patterns in string format
                import re
                measurement_pattern = r'\b\d+(?:\.\d+)?\s*(?:cup|tbsp|tsp|oz|lb|g|kg|ml|l|pound|tablespoon|teaspoon)\b'
                if re.search(measurement_pattern, ingredient.lower()):
                    ingredients_with_measurements += 1
        
        measurement_ratio = ingredients_with_measurements / len(ingredients)
        has_measurements = measurement_ratio >= 0.7  # At least 70% have measurements
        
        return {
            'has_measurements': has_measurements,
            'measurement_ratio': measurement_ratio
        }
    
    def _analyze_steps(self, steps: List[str]) -> Dict:
        """Analyze cooking step quality"""
        if not steps:
            return {'avg_step_length': 0, 'has_detailed_steps': False}
        
        step_lengths = [len(step.strip()) for step in steps if isinstance(step, str)]
        avg_step_length = sum(step_lengths) / len(step_lengths) if step_lengths else 0
        
        # Consider steps detailed if average length > 20 characters
        has_detailed_steps = avg_step_length > 20
        
        return {
            'avg_step_length': avg_step_length,
            'has_detailed_steps': has_detailed_steps
        }
    
    def _analyze_timing(self, recipe_json: Dict, steps: List[str]) -> Dict:
        """Analyze timing information in recipe"""
        has_timing = False
        
        # Check for explicit timing fields
        if recipe_json.get('prep_time') or recipe_json.get('cook_time') or recipe_json.get('total_time'):
            has_timing = True
        
        # Check for timing in steps
        if not has_timing and steps:
            import re
            timing_pattern = r'\b\d+\s*(?:minute|min|hour|hr|second|sec)s?\b'
            for step in steps:
                if isinstance(step, str) and re.search(timing_pattern, step.lower()):
                    has_timing = True
                    break
        
        return {'has_timing': has_timing}
    
    def _calculate_quality_score(self, ingredient_analysis: Dict, step_analysis: Dict, 
                                timing_analysis: Dict, title: str) -> float:
        """Calculate overall recipe quality score (0.0 to 1.0)"""
        score = 0.0
        
        # Ingredient quality (40% of score)
        if ingredient_analysis['has_measurements']:
            score += 0.4 * ingredient_analysis['measurement_ratio']
        
        # Step quality (30% of score)
        if step_analysis['has_detailed_steps']:
            score += 0.3
        
        # Timing information (20% of score)
        if timing_analysis['has_timing']:
            score += 0.2
        
        # Title quality (10% of score)
        if title and len(title.strip()) > 5:
            score += 0.1
        
        return min(score, 1.0)
    
    def _create_empty_result(self, reason: str) -> RecipeQualityResult:
        """Create a result for empty/invalid recipes"""
        return RecipeQualityResult(
            is_complete=False,
            quality_score=0.0,
            missing_components=["all components"],
            quality_issues=[reason],
            ingredient_count=0,
            step_count=0,
            has_measurements=False,
            has_timing=False,
            meets_minimum_standards=False
        )
    
    def should_trigger_fallback(self, recipe_quality: RecipeQualityResult, 
                               original_confidence: float) -> Dict[str, Any]:
        """
        Determine if fallback OCR should be triggered based on recipe quality
        
        Args:
            recipe_quality: Result of recipe quality analysis
            original_confidence: Original OpenAI confidence score
            
        Returns:
            Dict with fallback decision and reasoning
        """
        should_fallback = False
        reasons = []
        
        # Trigger fallback if recipe doesn't meet minimum standards
        # but original confidence was high (indicating a potential false positive)
        if not recipe_quality.meets_minimum_standards and original_confidence > 0.7:
            should_fallback = True
            reasons.append(f"Recipe incomplete despite high AI confidence ({original_confidence:.2f})")
        
        # Trigger fallback if quality score is very low but confidence was high
        if recipe_quality.quality_score < 0.3 and original_confidence > 0.8:
            should_fallback = True
            reasons.append(f"Very low quality score ({recipe_quality.quality_score:.2f}) despite high confidence")
        
        # Trigger fallback if missing critical components
        if len(recipe_quality.missing_components) >= 2 and original_confidence > 0.75:
            should_fallback = True
            reasons.append(f"Missing {len(recipe_quality.missing_components)} critical components")
        
        return {
            'should_fallback': should_fallback,
            'reasons': reasons,
            'confidence_quality_mismatch': original_confidence > 0.7 and recipe_quality.quality_score < 0.5,
            'fallback_trigger_score': recipe_quality.quality_score,
            'original_confidence': original_confidence
        } 
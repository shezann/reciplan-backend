"""
Tests for RecipeQualityAnalyzer service (Task 10.7)
Tests recipe quality analysis and fallback decision logic
"""

import pytest
from services.recipe_quality_analyzer import RecipeQualityAnalyzer, RecipeQualityResult


class TestRecipeQualityAnalyzer:
    """Unit tests for recipe quality analysis"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = RecipeQualityAnalyzer()
    
    def test_high_quality_complete_recipe(self):
        """Test analysis of a high-quality, complete recipe"""
        recipe = {
            "title": "Delicious Homemade Chocolate Chip Cookies",
            "ingredients": [
                {"name": "butter", "amount": "1", "unit": "cup"},
                {"name": "brown sugar", "amount": "3/4", "unit": "cup"},
                {"name": "eggs", "amount": "2", "unit": "large"},
                {"name": "vanilla extract", "amount": "1", "unit": "teaspoon"},
                {"name": "all-purpose flour", "amount": "2 1/4", "unit": "cups"},
                {"name": "baking soda", "amount": "1", "unit": "teaspoon"},
                {"name": "salt", "amount": "1", "unit": "teaspoon"},
                {"name": "chocolate chips", "amount": "2", "unit": "cups"}
            ],
            "steps": [
                "Preheat oven to 375°F and line baking sheets with parchment paper",
                "In a large bowl, cream together butter and brown sugar until light and fluffy, about 3 minutes",
                "Beat in eggs one at a time, then add vanilla extract and mix well",
                "In a separate bowl, whisk together flour, baking soda, and salt",
                "Gradually mix the dry ingredients into the wet ingredients until just combined",
                "Fold in chocolate chips evenly throughout the dough",
                "Drop rounded tablespoons of dough onto prepared baking sheets, spacing 2 inches apart",
                "Bake for 9-11 minutes until edges are golden brown but centers still look slightly underdone",
                "Cool on baking sheet for 5 minutes before transferring to wire rack"
            ],
            "prep_time": "15 minutes",
            "cook_time": "10 minutes",
            "total_time": "25 minutes"
        }
        
        result = self.analyzer.analyze_recipe_quality(recipe)
        
        assert result.is_complete == True
        assert result.quality_score >= 0.9
        assert result.ingredient_count == 8
        assert result.step_count == 9
        assert result.has_measurements == True
        assert result.has_timing == True
        assert result.meets_minimum_standards == True
        assert len(result.missing_components) == 0
        assert len(result.quality_issues) == 0
    
    def test_low_quality_incomplete_recipe(self):
        """Test analysis of a low-quality, incomplete recipe"""
        recipe = {
            "title": "",
            "ingredients": [
                {"name": "chicken", "amount": "", "unit": ""},
                {"name": "sauce", "amount": "", "unit": ""}
            ],
            "steps": [
                "Cook chicken",
                "Add sauce"
            ]
        }
        
        result = self.analyzer.analyze_recipe_quality(recipe)
        
        assert result.is_complete == False
        assert result.quality_score < 0.3
        assert result.ingredient_count == 2
        assert result.step_count == 2
        assert result.has_measurements == False
        assert result.has_timing == False
        assert result.meets_minimum_standards == True  # Meets minimum count requirements
        assert "ingredient measurements" in result.missing_components
        assert len(result.quality_issues) > 0
    
    def test_borderline_quality_recipe(self):
        """Test analysis of a borderline quality recipe"""
        recipe = {
            "title": "Simple Pasta",
            "ingredients": [
                {"name": "pasta", "amount": "1", "unit": "cup"},
                {"name": "olive oil", "amount": "2", "unit": "tablespoons"},
                {"name": "salt", "amount": "", "unit": ""},
                {"name": "pepper", "amount": "", "unit": ""}
            ],
            "steps": [
                "Boil water in a large pot",
                "Add pasta and cook according to package directions",
                "Drain pasta and toss with olive oil, salt, and pepper"
            ]
        }
        
        result = self.analyzer.analyze_recipe_quality(recipe)
        
        assert result.ingredient_count == 4
        assert result.step_count == 3
        assert result.meets_minimum_standards == True
        # Should have some measurements (2 out of 4 ingredients)
        assert result.has_measurements == False  # Less than 70% threshold
        assert 0.3 <= result.quality_score <= 0.7  # Borderline score
    
    def test_recipe_with_string_ingredients(self):
        """Test analysis of recipe with string-format ingredients"""
        recipe = {
            "title": "Traditional Bread Recipe",
            "ingredients": [
                "2 cups all-purpose flour",
                "1 tsp active dry yeast", 
                "1 tbsp sugar",
                "1 tsp salt",
                "3/4 cup warm water"
            ],
            "steps": [
                "Mix dry ingredients in a large bowl",
                "Add warm water and stir until dough forms",
                "Knead dough on floured surface for 8-10 minutes",
                "Place in greased bowl, cover, and let rise for 1 hour"
            ]
        }
        
        result = self.analyzer.analyze_recipe_quality(recipe)
        
        assert result.ingredient_count == 5
        assert result.step_count == 4
        assert result.has_measurements == True  # Should detect measurements in strings
        assert result.has_timing == True  # Should detect "8-10 minutes" and "1 hour"
        assert result.quality_score > 0.7
    
    def test_empty_or_none_recipe(self):
        """Test analysis of empty or None recipe"""
        # Test None recipe
        result = self.analyzer.analyze_recipe_quality(None)
        assert result.is_complete == False
        assert result.quality_score == 0.0
        assert result.ingredient_count == 0
        assert result.step_count == 0
        assert "Recipe JSON is None or empty" in result.quality_issues[0]
        
        # Test empty recipe
        result = self.analyzer.analyze_recipe_quality({})
        assert result.is_complete == False
        assert result.quality_score <= 0.1  # Only title component missing
        assert result.ingredient_count == 0
        assert result.step_count == 0
    
    def test_ingredient_analysis_edge_cases(self):
        """Test ingredient analysis with various edge cases"""
        # Test mixed format ingredients
        mixed_ingredients = [
            {"name": "flour", "amount": "2", "unit": "cups"},  # Complete
            {"name": "sugar", "amount": "1", "unit": ""},     # Missing unit
            {"name": "eggs", "amount": "", "unit": "large"},  # Missing amount
            {"name": "salt", "amount": "", "unit": ""},       # Missing both
            "1 tsp vanilla extract"  # String format with measurement
        ]
        
        analysis = self.analyzer._analyze_ingredients(mixed_ingredients)
        
        # Should detect 2 out of 5 ingredients with measurements (40%)
        assert analysis['measurement_ratio'] == 0.4
        assert analysis['has_measurements'] == False  # Below 70% threshold
        
        # Test all ingredients with measurements
        complete_ingredients = [
            {"name": "butter", "amount": "1", "unit": "cup"},
            {"name": "sugar", "amount": "2", "unit": "cups"},
            {"name": "eggs", "amount": "3", "unit": "large"}
        ]
        
        analysis = self.analyzer._analyze_ingredients(complete_ingredients)
        assert analysis['measurement_ratio'] == 1.0
        assert analysis['has_measurements'] == True
    
    def test_step_analysis_detail_levels(self):
        """Test step analysis with different detail levels"""
        # Test detailed steps
        detailed_steps = [
            "Preheat your oven to 350°F and grease a 9x13 inch baking dish with butter",
            "In a large mixing bowl, combine flour, sugar, and baking powder, whisking until well blended",
            "In a separate bowl, beat eggs and gradually add milk, melted butter, and vanilla extract"
        ]
        
        analysis = self.analyzer._analyze_steps(detailed_steps)
        assert analysis['has_detailed_steps'] == True
        assert analysis['avg_step_length'] > 50
        
        # Test vague steps
        vague_steps = [
            "Mix ingredients",
            "Cook",
            "Serve"
        ]
        
        analysis = self.analyzer._analyze_steps(vague_steps)
        assert analysis['has_detailed_steps'] == False
        assert analysis['avg_step_length'] < 15
    
    def test_timing_analysis_detection(self):
        """Test timing detection in various locations"""
        # Test explicit timing fields
        recipe_with_times = {
            "prep_time": "15 minutes",
            "cook_time": "30 minutes"
        }
        
        analysis = self.analyzer._analyze_timing(recipe_with_times, [])
        assert analysis['has_timing'] == True
        
        # Test timing in steps
        steps_with_timing = [
            "Bake for 25-30 minutes until golden brown",
            "Let cool for 5 minutes before serving",
            "Marinate chicken for 2 hours in refrigerator"
        ]
        
        analysis = self.analyzer._analyze_timing({}, steps_with_timing)
        assert analysis['has_timing'] == True
        
        # Test no timing
        analysis = self.analyzer._analyze_timing({}, ["Cook until done", "Serve immediately"])
        assert analysis['has_timing'] == False
    
    def test_quality_score_calculation_components(self):
        """Test individual components of quality score calculation"""
        # Perfect components
        perfect_ingredient = {'has_measurements': True, 'measurement_ratio': 1.0}
        perfect_step = {'has_detailed_steps': True, 'avg_step_length': 50}
        perfect_timing = {'has_timing': True}
        perfect_title = "Delicious Homemade Recipe"
        
        score = self.analyzer._calculate_quality_score(
            perfect_ingredient, perfect_step, perfect_timing, perfect_title
        )
        assert score == 1.0
        
        # Test individual component contributions
        # Only ingredients (40% of score)
        score = self.analyzer._calculate_quality_score(
            perfect_ingredient, 
            {'has_detailed_steps': False}, 
            {'has_timing': False}, 
            ""
        )
        assert score == 0.4
        
        # Only steps (30% of score)
        score = self.analyzer._calculate_quality_score(
            {'has_measurements': False, 'measurement_ratio': 0.0},
            perfect_step,
            {'has_timing': False},
            ""
        )
        assert score == 0.3
    
    def test_fallback_decision_logic_scenarios(self):
        """Test fallback decision logic with various scenarios"""
        # Scenario 1: High confidence, poor quality → Should trigger
        poor_quality = RecipeQualityResult(
            is_complete=False,
            quality_score=0.2,
            missing_components=["measurements", "steps"],
            quality_issues=["Vague instructions"],
            ingredient_count=2,
            step_count=1,
            has_measurements=False,
            has_timing=False,
            meets_minimum_standards=False
        )
        
        decision = self.analyzer.should_trigger_fallback(poor_quality, 0.85)
        assert decision['should_fallback'] == True
        assert len(decision['reasons']) > 0
        assert decision['confidence_quality_mismatch'] == True
        
        # Scenario 2: Low confidence, poor quality → Should not trigger
        decision = self.analyzer.should_trigger_fallback(poor_quality, 0.4)
        assert decision['should_fallback'] == False
        assert decision['confidence_quality_mismatch'] == False
        
        # Scenario 3: High confidence, high quality → Should not trigger
        good_quality = RecipeQualityResult(
            is_complete=True,
            quality_score=0.9,
            missing_components=[],
            quality_issues=[],
            ingredient_count=5,
            step_count=4,
            has_measurements=True,
            has_timing=True,
            meets_minimum_standards=True
        )
        
        decision = self.analyzer.should_trigger_fallback(good_quality, 0.9)
        assert decision['should_fallback'] == False
        assert decision['confidence_quality_mismatch'] == False
        
        # Scenario 4: Very low quality score with high confidence → Should trigger
        very_poor_quality = RecipeQualityResult(
            is_complete=False,
            quality_score=0.1,
            missing_components=["everything"],
            quality_issues=["Completely inadequate"],
            ingredient_count=1,
            step_count=1,
            has_measurements=False,
            has_timing=False,
            meets_minimum_standards=True
        )
        
        decision = self.analyzer.should_trigger_fallback(very_poor_quality, 0.85)
        assert decision['should_fallback'] == True
        assert "Very low quality score" in decision['reasons'][0]
    
    def test_missing_component_detection(self):
        """Test detection of missing recipe components"""
        # Recipe missing ingredients
        recipe_missing_ingredients = {
            "title": "Test Recipe",
            "ingredients": [{"name": "salt", "amount": "", "unit": ""}],  # Only 1 ingredient, no measurements
            "steps": ["Step 1", "Step 2", "Step 3"]
        }
        
        result = self.analyzer.analyze_recipe_quality(recipe_missing_ingredients)
        assert any("ingredients" in component for component in result.missing_components)
        assert "ingredient measurements" in result.missing_components
        
        # Recipe missing steps
        recipe_missing_steps = {
            "title": "Test Recipe",
            "ingredients": [
                {"name": "flour", "amount": "2", "unit": "cups"},
                {"name": "sugar", "amount": "1", "unit": "cup"},
                {"name": "eggs", "amount": "2", "unit": "large"}
            ],
            "steps": ["Mix everything"]  # Only 1 step
        }
        
        result = self.analyzer.analyze_recipe_quality(recipe_missing_steps)
        assert any("cooking steps" in component for component in result.missing_components)
    
    def test_quality_issues_identification(self):
        """Test identification of specific quality issues"""
        recipe_with_issues = {
            "title": "",  # Empty title
            "ingredients": [
                {"name": "flour", "amount": "2", "unit": "cups"},
                {"name": "sugar", "amount": "", "unit": ""},  # No measurement
                {"name": "eggs", "amount": "", "unit": ""}   # No measurement
            ],
            "steps": [
                "Mix",  # Too short
                "Bake until done",  # Vague
                "This is a proper detailed cooking instruction with sufficient length"
            ]
        }
        
        result = self.analyzer.analyze_recipe_quality(recipe_with_issues)
        
        # Should identify various quality issues
        issues = result.quality_issues
        assert any("title" in issue.lower() for issue in issues)
        assert any("measurements" in issue.lower() for issue in issues)
        assert any("vague" in issue.lower() or "short" in issue.lower() for issue in issues)
    
    def test_minimum_standards_vs_completeness(self):
        """Test distinction between minimum standards and completeness"""
        # Recipe that meets minimum standards but isn't complete
        minimal_recipe = {
            "title": "Basic Recipe",
            "ingredients": [
                {"name": "ingredient1", "amount": "", "unit": ""},
                {"name": "ingredient2", "amount": "", "unit": ""},
                {"name": "ingredient3", "amount": "", "unit": ""}
            ],
            "steps": [
                "Step 1",
                "Step 2"
            ]
        }
        
        result = self.analyzer.analyze_recipe_quality(minimal_recipe)
        
        # Should meet minimum standards (3+ ingredients, 2+ steps)
        assert result.meets_minimum_standards == True
        # But should not be complete (lacks measurements, quality is low)
        assert result.is_complete == False
        assert result.quality_score < 0.6


if __name__ == "__main__":
    # Run the tests
    test_instance = TestRecipeQualityAnalyzer()
    test_methods = [method for method in dir(test_instance) if method.startswith('test_')]
    
    print("🧪 Running Recipe Quality Analyzer Tests (Task 10.7)")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for method_name in test_methods:
        try:
            test_instance.setup_method()
            test_method = getattr(test_instance, method_name)
            test_method()
            print(f"✅ {method_name}")
            passed += 1
        except Exception as e:
            print(f"❌ {method_name} FAILED: {e}")
            failed += 1
    
    print(f"\n📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 All recipe quality analyzer tests passed!")
    else:
        print(f"\n⚠️ {failed} tests failed. Please review the failures above.") 
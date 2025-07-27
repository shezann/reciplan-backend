"""
Integration tests for conditional OCR pipeline (Task 10.7)
Tests the complete pipeline with OpenAI analysis, conditional OCR, and fallback mechanisms
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from pathlib import Path

from tasks.tiktok_tasks import PipelineContext, _data_sufficiency_analysis_stage, _conditional_ocr_stage, _llm_stage_with_fallback
from services.data_sufficiency_analyzer import DataSufficiencyAnalyzer, SufficiencyResult
from services.recipe_quality_analyzer import RecipeQualityAnalyzer, RecipeQualityResult
from errors import PipelineStatus


class TestConditionalOCRIntegration:
    """Integration tests for the complete conditional OCR pipeline"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_ctx = self._create_mock_context()
    
    def _create_mock_context(self):
        """Create a mock pipeline context for testing"""
        ctx = Mock(spec=PipelineContext)
        ctx.job_id = "test-job-123"
        ctx.recipe_id = "test-recipe-456"
        ctx.url = "https://tiktok.com/@user/video/123"
        ctx.owner_uid = "test-user-789"
        ctx.db = Mock()
        ctx.firestore_service = Mock()
        ctx.tiktok_service = Mock()
        ctx.sufficiency_result = None
        ctx.fallback_triggered = False
        ctx.original_ocr_results = None
        ctx.video_path = Path("/tmp/test_video.mp4")
        ctx.job_dir = Path("/tmp/test_job")
        ctx.thumbnail_url = "https://example.com/thumb.jpg"
        ctx.status_updates = []
        
        def mock_update_status(status, data=None):
            ctx.status_updates.append({"status": status, "data": data or {}})
        
        ctx.update_status = mock_update_status
        return ctx

    @patch('services.data_sufficiency_analyzer.client')
    def test_high_confidence_sufficient_data_skips_ocr(self, mock_openai):
        """Test: High confidence + sufficient data → OCR skipped"""
        print("\n=== Test: High Confidence Sufficient Data ===")
        
        # Mock OpenAI response: high confidence, sufficient data
        mock_openai.return_value = {
            "choices": [{
                "message": {
                    "content": """{
                        "is_sufficient": true,
                        "confidence_score": 0.92,
                        "reasoning": "Complete recipe with detailed ingredients and measurements",
                        "estimated_completeness": {
                            "ingredients": "complete",
                            "instructions": "complete",
                            "timing": "complete",
                            "measurements": "complete"
                        }
                    }"""
                }
            }]
        }
        
        # Stage 1: Data sufficiency analysis
        title = "Perfect Chicken Stir Fry Recipe"
        transcript = "Heat 2 tbsp oil, add 1 lb chicken, cook 5 min, add vegetables, stir-fry 3 min, serve"
        metadata_title = "Cooking Tutorial"
        
        result = _data_sufficiency_analysis_stage(self.mock_ctx, title, transcript, metadata_title)
        
        # Verify analysis results
        assert result.is_sufficient == True
        assert result.confidence_score >= 0.9
        assert self.mock_ctx.sufficiency_result == result
        
        # Stage 2: Conditional OCR (should skip)
        with patch('tasks.tiktok_tasks._ocr_stage') as mock_ocr:
            ocr_results = _conditional_ocr_stage(self.mock_ctx, "video_path", "job_dir")
        
        # Verify OCR was skipped
        assert ocr_results == []
        mock_ocr.assert_not_called()
        assert self.mock_ctx.original_ocr_results == []
        
        # Verify status updates
        status_updates = [update["status"] for update in self.mock_ctx.status_updates]
        assert PipelineStatus.ANALYZING_DATA_SUFFICIENCY in status_updates
        assert PipelineStatus.OCR_SKIPPED in status_updates
        
        print("✅ High confidence sufficient data correctly skipped OCR")

    @patch('services.data_sufficiency_analyzer.client')
    def test_low_confidence_insufficient_data_runs_ocr(self, mock_openai):
        """Test: Low confidence + insufficient data → OCR runs"""
        print("\n=== Test: Low Confidence Insufficient Data ===")
        
        # Mock OpenAI response: low confidence, insufficient data
        mock_openai.return_value = {
            "choices": [{
                "message": {
                    "content": """{
                        "is_sufficient": false,
                        "confidence_score": 0.25,
                        "reasoning": "Very limited information, missing ingredients and measurements",
                        "estimated_completeness": {
                            "ingredients": "missing",
                            "instructions": "partial",
                            "timing": "missing",
                            "measurements": "missing"
                        }
                    }"""
                }
            }]
        }
        
        # Stage 1: Data sufficiency analysis
        title = "Cooking Video"
        transcript = "Hey everyone, today I'm making something delicious!"
        metadata_title = ""
        
        result = _data_sufficiency_analysis_stage(self.mock_ctx, title, transcript, metadata_title)
        
        # Verify analysis results
        assert result.is_sufficient == False
        assert result.confidence_score < 0.5
        
        # Stage 2: Conditional OCR (should run)
        mock_ocr_results = [{"text": "2 cups flour", "confidence": 0.9}]
        with patch('tasks.tiktok_tasks._ocr_stage', return_value=mock_ocr_results) as mock_ocr:
            ocr_results = _conditional_ocr_stage(self.mock_ctx, "video_path", "job_dir")
        
        # Verify OCR was run
        assert ocr_results == mock_ocr_results
        mock_ocr.assert_called_once()
        assert self.mock_ctx.original_ocr_results == mock_ocr_results
        
        # Verify status updates
        status_updates = [update["status"] for update in self.mock_ctx.status_updates]
        assert PipelineStatus.ANALYZING_DATA_SUFFICIENCY in status_updates
        assert PipelineStatus.OCRING in status_updates
        
        print("✅ Low confidence insufficient data correctly ran OCR")

    @patch('services.data_sufficiency_analyzer.client')
    def test_borderline_confidence_threshold_enforcement(self, mock_openai):
        """Test: Confidence threshold enforcement at borderline values"""
        print("\n=== Test: Borderline Confidence Threshold ===")
        
        # Test scenarios around the 0.7 threshold
        scenarios = [
            {"confidence": 0.69, "sufficient": True, "should_skip": False, "name": "Just below threshold"},
            {"confidence": 0.70, "sufficient": True, "should_skip": True, "name": "At threshold"},
            {"confidence": 0.71, "sufficient": True, "should_skip": True, "name": "Just above threshold"}
        ]
        
        for scenario in scenarios:
            print(f"\n--- {scenario['name']} (confidence: {scenario['confidence']}) ---")
            
            # Reset context
            self.mock_ctx.status_updates = []
            self.mock_ctx.sufficiency_result = None
            
            # Mock OpenAI response
            mock_openai.return_value = {
                "choices": [{
                    "message": {
                        "content": f"""{{
                            "is_sufficient": {str(scenario['sufficient']).lower()},
                            "confidence_score": {scenario['confidence']},
                            "reasoning": "Test scenario for threshold enforcement",
                            "estimated_completeness": {{
                                "ingredients": "complete",
                                "instructions": "complete",
                                "timing": "partial",
                                "measurements": "complete"
                            }}
                        }}"""
                    }
                }]
            }
            
            # Run analysis and conditional OCR
            _data_sufficiency_analysis_stage(self.mock_ctx, "Test Recipe", "Test transcript", "")
            
            with patch('tasks.tiktok_tasks._ocr_stage', return_value=["mock_ocr"]) as mock_ocr:
                ocr_results = _conditional_ocr_stage(self.mock_ctx, "video_path", "job_dir")
            
            # Verify threshold enforcement
            if scenario['should_skip']:
                assert ocr_results == []
                mock_ocr.assert_not_called()
                print(f"✅ Confidence {scenario['confidence']} correctly skipped OCR")
            else:
                assert ocr_results == ["mock_ocr"]
                mock_ocr.assert_called_once()
                print(f"✅ Confidence {scenario['confidence']} correctly ran OCR")

    @patch('services.data_sufficiency_analyzer.client')
    @patch('services.llm_refine_service.LLMRefineService')
    @patch('services.recipe_quality_analyzer.RecipeQualityAnalyzer')
    def test_fallback_mechanism_triggered(self, mock_quality_analyzer_class, mock_llm_service_class, mock_openai):
        """Test: Fallback mechanism triggered when recipe quality is poor despite high confidence"""
        print("\n=== Test: Fallback Mechanism Triggered ===")
        
        # Mock OpenAI sufficiency analysis (high confidence)
        mock_openai.return_value = {
            "choices": [{
                "message": {
                    "content": """{
                        "is_sufficient": true,
                        "confidence_score": 0.85,
                        "reasoning": "Appears to have sufficient data",
                        "estimated_completeness": {
                            "ingredients": "complete",
                            "instructions": "complete",
                            "timing": "complete",
                            "measurements": "complete"
                        }
                    }"""
                }
            }]
        }
        
        # Set up sufficiency result (high confidence)
        self.mock_ctx.sufficiency_result = SufficiencyResult(
            is_sufficient=True,
            confidence_score=0.85,
            reasoning="High confidence analysis",
            estimated_completeness={"ingredients": "complete", "instructions": "complete", "timing": "complete", "measurements": "complete"}
        )
        
        # Mock LLM service (returns poor quality recipe)
        mock_llm = Mock()
        mock_llm.model = "gpt-3.5-turbo"
        mock_llm.refine_with_validation_retry.return_value = (
            {  # Poor quality recipe
                "title": "Recipe",
                "ingredients": [{"name": "stuff", "amount": "", "unit": ""}],
                "steps": ["Cook it"]
            },
            None  # No parse error
        )
        mock_llm_service_class.return_value = mock_llm
        
        # Mock quality analyzer (detects poor quality, triggers fallback)
        mock_quality_analyzer = Mock()
        mock_quality_result = RecipeQualityResult(
            is_complete=False,
            quality_score=0.2,
            missing_components=["ingredient measurements", "detailed steps"],
            quality_issues=["Vague instructions"],
            ingredient_count=1,
            step_count=1,
            has_measurements=False,
            has_timing=False,
            meets_minimum_standards=False
        )
        mock_quality_analyzer.analyze_recipe_quality.return_value = mock_quality_result
        mock_quality_analyzer.should_trigger_fallback.return_value = {
            'should_fallback': True,
            'reasons': ['Recipe incomplete despite high AI confidence (0.85)'],
            'confidence_quality_mismatch': True,
            'fallback_trigger_score': 0.2,
            'original_confidence': 0.85
        }
        mock_quality_analyzer_class.return_value = mock_quality_analyzer
        
        # Mock fallback OCR
        with patch('tasks.tiktok_tasks._run_fallback_ocr', return_value=[{"text": "2 cups flour", "confidence": 0.9}]) as mock_fallback_ocr:
            # Run LLM stage with fallback
            result = _llm_stage_with_fallback(
                self.mock_ctx, 
                "Test Recipe", 
                "Test transcript", 
                []  # No initial OCR results (was skipped)
            )
        
        # Verify fallback was triggered
        assert self.mock_ctx.fallback_triggered == True
        mock_fallback_ocr.assert_called_once()
        
        # Verify LLM was called twice (initial + fallback)
        assert mock_llm.refine_with_validation_retry.call_count == 2
        
        # Verify status updates include fallback
        status_updates = [update["status"] for update in self.mock_ctx.status_updates]
        assert PipelineStatus.FALLBACK_OCR_TRIGGERED in status_updates
        
        print("✅ Fallback mechanism correctly triggered for poor quality recipe")

    @patch('services.data_sufficiency_analyzer.client')
    def test_api_error_handling_fallback_to_ocr(self, mock_openai):
        """Test: API errors cause fallback to running OCR (safe default)"""
        print("\n=== Test: API Error Handling ===")
        
        # Mock OpenAI API failure
        mock_client.chat.completions.create.side_effect = Exception("OpenAI API error")
        
        # Stage 1: Data sufficiency analysis (should handle error)
        result = _data_sufficiency_analysis_stage(self.mock_ctx, "Test Recipe", "Test transcript", "")
        
        # Verify safe fallback behavior
        assert result.is_sufficient == False  # Safe default
        assert result.confidence_score == 0.0
        assert "Analysis failed" in result.reasoning
        
        # Stage 2: Conditional OCR (should run due to error)
        with patch('tasks.tiktok_tasks._ocr_stage', return_value=["fallback_ocr"]) as mock_ocr:
            ocr_results = _conditional_ocr_stage(self.mock_ctx, "video_path", "job_dir")
        
        # Verify OCR was run as fallback
        assert ocr_results == ["fallback_ocr"]
        mock_ocr.assert_called_once()
        
        print("✅ API error correctly handled with safe OCR fallback")

    def test_pipeline_performance_metrics_tracking(self):
        """Test: Performance metrics are properly tracked throughout pipeline"""
        print("\n=== Test: Performance Metrics Tracking ===")
        
        # Mock sufficiency result
        self.mock_ctx.sufficiency_result = SufficiencyResult(
            is_sufficient=True,
            confidence_score=0.8,
            reasoning="Good data",
            estimated_completeness={"ingredients": "complete", "instructions": "complete", "timing": "complete", "measurements": "complete"}
        )
        
        # Run conditional OCR stage
        with patch('tasks.tiktok_tasks._ocr_stage') as mock_ocr:
            _conditional_ocr_stage(self.mock_ctx, "video_path", "job_dir")
        
        # Verify performance metrics in status updates
        ocr_skip_update = None
        for update in self.mock_ctx.status_updates:
            if update["status"] == PipelineStatus.OCR_SKIPPED:
                ocr_skip_update = update
                break
        
        assert ocr_skip_update is not None
        assert "confidence_score" in ocr_skip_update["data"]
        assert "decision_factors" in ocr_skip_update["data"]
        assert "estimated_completeness" in ocr_skip_update["data"]
        assert ocr_skip_update["data"]["confidence_score"] == 0.8
        
        print("✅ Performance metrics correctly tracked")

    @patch('services.data_sufficiency_analyzer.client')
    def test_metadata_integration_improves_analysis(self, mock_openai):
        """Test: Additional metadata improves sufficiency analysis"""
        print("\n=== Test: Metadata Integration ===")
        
        # Mock OpenAI response that uses metadata
        mock_openai.return_value = {
            "choices": [{
                "message": {
                    "content": """{
                        "is_sufficient": true,
                        "confidence_score": 0.78,
                        "reasoning": "Title and description provide recipe details",
                        "estimated_completeness": {
                            "ingredients": "complete",
                            "instructions": "partial",
                            "timing": "complete",
                            "measurements": "complete"
                        }
                    }"""
                }
            }]
        }
        
        # Test with metadata that should improve analysis
        title = "Cooking Video"
        transcript = "Making something tasty today"
        metadata_title = "Easy Pasta Recipe: 1 cup pasta, 2 tbsp oil, cook 10 minutes"
        
        result = _data_sufficiency_analysis_stage(self.mock_ctx, title, transcript, metadata_title)
        
        # Verify metadata was considered
        assert result.is_sufficient == True
        assert result.confidence_score > 0.7
        
        # Verify OpenAI was called with metadata
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_openai.call_args
        user_message = call_args[1]['messages'][1]['content']
        assert "Description:" in user_message
        assert metadata_title in user_message
        
        print("✅ Metadata integration correctly improves analysis")

    def test_complete_pipeline_flow_ocr_skipped(self):
        """Test: Complete pipeline flow when OCR is skipped"""
        print("\n=== Test: Complete Pipeline Flow - OCR Skipped ===")
        
        with patch('services.data_sufficiency_analyzer.client') as mock_client:
            # Mock high confidence response
            mock_openai.return_value = {
                "choices": [{
                    "message": {
                        "content": """{
                            "is_sufficient": true,
                            "confidence_score": 0.9,
                            "reasoning": "Excellent recipe data",
                            "estimated_completeness": {
                                "ingredients": "complete",
                                "instructions": "complete",
                                "timing": "complete",
                                "measurements": "complete"
                            }
                        }"""
                    }
                }]
            }
            
            # Stage 1: Data sufficiency analysis
            result = _data_sufficiency_analysis_stage(self.mock_ctx, "Perfect Recipe", "Detailed transcript", "")
            
            # Stage 2: Conditional OCR
            with patch('tasks.tiktok_tasks._ocr_stage') as mock_ocr:
                ocr_results = _conditional_ocr_stage(self.mock_ctx, "video_path", "job_dir")
        
        # Verify complete flow
        assert result.is_sufficient == True
        assert result.confidence_score == 0.9
        assert ocr_results == []
        mock_ocr.assert_not_called()
        
        # Verify all expected status updates
        expected_statuses = [
            PipelineStatus.ANALYZING_DATA_SUFFICIENCY,
            PipelineStatus.OCR_SKIPPED
        ]
        
        actual_statuses = [update["status"] for update in self.mock_ctx.status_updates]
        for status in expected_statuses:
            assert status in actual_statuses
        
        print("✅ Complete pipeline flow for OCR skipped scenario")

    def test_complete_pipeline_flow_ocr_run(self):
        """Test: Complete pipeline flow when OCR is run"""
        print("\n=== Test: Complete Pipeline Flow - OCR Run ===")
        
        with patch('services.data_sufficiency_analyzer.client') as mock_client:
            # Mock low confidence response
            mock_openai.return_value = {
                "choices": [{
                    "message": {
                        "content": """{
                            "is_sufficient": false,
                            "confidence_score": 0.3,
                            "reasoning": "Insufficient recipe data",
                            "estimated_completeness": {
                                "ingredients": "missing",
                                "instructions": "partial",
                                "timing": "missing",
                                "measurements": "missing"
                            }
                        }"""
                    }
                }]
            }
            
            # Stage 1: Data sufficiency analysis
            result = _data_sufficiency_analysis_stage(self.mock_ctx, "Basic Video", "Short transcript", "")
            
            # Stage 2: Conditional OCR
            mock_ocr_results = [{"text": "Recipe ingredients", "confidence": 0.8}]
            with patch('tasks.tiktok_tasks._ocr_stage', return_value=mock_ocr_results) as mock_ocr:
                ocr_results = _conditional_ocr_stage(self.mock_ctx, "video_path", "job_dir")
        
        # Verify complete flow
        assert result.is_sufficient == False
        assert result.confidence_score == 0.3
        assert ocr_results == mock_ocr_results
        mock_ocr.assert_called_once()
        
        # Verify all expected status updates
        expected_statuses = [
            PipelineStatus.ANALYZING_DATA_SUFFICIENCY,
            PipelineStatus.OCRING
        ]
        
        actual_statuses = [update["status"] for update in self.mock_ctx.status_updates]
        for status in expected_statuses:
            assert status in actual_statuses
        
        print("✅ Complete pipeline flow for OCR run scenario")


if __name__ == "__main__":
    # Run the tests
    test_instance = TestConditionalOCRIntegration()
    test_methods = [method for method in dir(test_instance) if method.startswith('test_')]
    
    print("🧪 Running Conditional OCR Integration Tests (Task 10.7)")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for method_name in test_methods:
        try:
            test_instance.setup_method()
            test_method = getattr(test_instance, method_name)
            test_method()
            passed += 1
        except Exception as e:
            print(f"\n❌ {method_name} FAILED: {e}")
            failed += 1
    
    print(f"\n📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 All integration tests passed! Conditional OCR pipeline is working correctly.")
    else:
        print(f"\n⚠️ {failed} tests failed. Please review the failures above.") 
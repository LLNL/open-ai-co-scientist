#!/usr/bin/env python3
"""
Test script for LLM call tracking and analytics functionality
"""

import sys
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import database
import models
import utils
import model_pricing

# Use the imported modules directly
DatabaseManager = database.DatabaseManager
ResearchGoal = models.ResearchGoal
ContextMemory = models.ContextMemory

class TestLLMTracking(unittest.TestCase):
    """Test cases for LLM call tracking and analytics"""
    
    def setUp(self):
        """Set up test database"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        self.db_manager = DatabaseManager(self.test_db.name)
        
        # Create test session
        research_goal = ResearchGoal(description="LLM tracking test")
        self.session_id = self.db_manager.create_session(research_goal)
        
        # Initialize some test model pricing
        self.db_manager.save_model_pricing(
            model_name="test-model",
            provider="test-provider",
            prompt_price_per_1k=0.001,
            completion_price_per_1k=0.002,
            context_window=4096,
            max_output_tokens=2048
        )
    
    def tearDown(self):
        """Clean up test database"""
        os.unlink(self.test_db.name)
    
    def test_save_llm_call(self):
        """Test saving LLM call data"""
        call_id = self.db_manager.save_llm_call(
            session_id=self.session_id,
            call_type="generation",
            model_name="test-model",
            prompt="Test prompt",
            response="Test response",
            temperature=0.7,
            prompt_tokens=100,
            completion_tokens=50,
            response_time_ms=1234.5,
            success=True,
            retry_count=0
        )
        
        self.assertIsInstance(call_id, int)
        self.assertGreater(call_id, 0)
        
        # Verify the call was saved
        analytics = self.db_manager.get_session_llm_analytics(self.session_id)
        self.assertEqual(len(analytics['recent_calls']), 1)
        self.assertEqual(analytics['recent_calls'][0]['call_type'], 'generation')
        self.assertEqual(analytics['recent_calls'][0]['model_name'], 'test-model')
        self.assertTrue(analytics['recent_calls'][0]['success'])
    
    def test_performance_metrics_aggregation(self):
        """Test that performance metrics are correctly aggregated"""
        # Save multiple LLM calls
        calls_data = [
            {"call_type": "generation", "success": True, "response_time_ms": 1000, "total_tokens": 150},
            {"call_type": "generation", "success": True, "response_time_ms": 1200, "total_tokens": 120},
            {"call_type": "generation", "success": False, "response_time_ms": 500, "total_tokens": 0},
            {"call_type": "reflection", "success": True, "response_time_ms": 800, "total_tokens": 100},
        ]
        
        for call_data in calls_data:
            self.db_manager.save_llm_call(
                session_id=self.session_id,
                call_type=call_data["call_type"],
                model_name="test-model",
                prompt="Test prompt",
                response="Test response" if call_data["success"] else None,
                temperature=0.7,
                prompt_tokens=call_data["total_tokens"] // 2 if call_data["total_tokens"] > 0 else 0,
                completion_tokens=call_data["total_tokens"] // 2 if call_data["total_tokens"] > 0 else 0,
                response_time_ms=call_data["response_time_ms"],
                success=call_data["success"],
                error_message="Test error" if not call_data["success"] else None
            )
        
        analytics = self.db_manager.get_session_llm_analytics(self.session_id)
        
        # Check totals
        self.assertEqual(analytics['total_calls'], 4)
        self.assertGreater(analytics['total_cost'], 0)  # Should have some cost calculated
        
        # Check performance metrics
        performance_metrics = analytics['performance_metrics']
        self.assertGreater(len(performance_metrics), 0)
        
        # Find generation metrics
        gen_metrics = [pm for pm in performance_metrics if pm['call_type'] == 'generation'][0]
        self.assertEqual(gen_metrics['total_calls'], 3)
        self.assertEqual(gen_metrics['successful_calls'], 2)
        self.assertEqual(gen_metrics['failed_calls'], 1)
    
    def test_cost_calculation(self):
        """Test that API costs are calculated correctly"""
        # Save a call with known token counts
        prompt_tokens = 100
        completion_tokens = 50
        expected_cost = (prompt_tokens / 1000.0 * 0.001) + (completion_tokens / 1000.0 * 0.002)
        
        self.db_manager.save_llm_call(
            session_id=self.session_id,
            call_type="generation",
            model_name="test-model",
            prompt="Test prompt",
            response="Test response",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            success=True
        )
        
        analytics = self.db_manager.get_session_llm_analytics(self.session_id)
        actual_cost = analytics['cost_breakdown'][0]['total_cost']
        
        self.assertAlmostEqual(actual_cost, expected_cost, places=6)
    
    def test_error_analysis(self):
        """Test error analysis functionality"""
        # Save some failed calls with different error messages
        errors = ["Rate limit exceeded", "Model timeout", "Rate limit exceeded"]
        
        for error in errors:
            self.db_manager.save_llm_call(
                session_id=self.session_id,
                call_type="generation",
                model_name="test-model",
                prompt="Test prompt",
                success=False,
                error_message=error
            )
        
        analytics = self.db_manager.get_session_llm_analytics(self.session_id)
        error_analysis = analytics['error_analysis']
        
        # Should have rate limit error appearing twice
        rate_limit_errors = [ea for ea in error_analysis if ea['error_message'] == 'Rate limit exceeded']
        self.assertEqual(len(rate_limit_errors), 1)
        self.assertEqual(rate_limit_errors[0]['error_count'], 2)

class TestLLMCallIntegration(unittest.TestCase):
    """Test LLM call function integration with database logging"""
    
    def setUp(self):
        """Set up test database"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        self.db_manager = DatabaseManager(self.test_db.name)
        
        # Create test session
        research_goal = ResearchGoal(description="LLM integration test")
        self.session_id = self.db_manager.create_session(research_goal)
        
        # Initialize test model pricing
        self.db_manager.save_model_pricing(
            model_name="test-model",
            provider="test-provider",
            prompt_price_per_1k=0.001,
            completion_price_per_1k=0.002
        )
    
    def tearDown(self):
        """Clean up test database"""
        os.unlink(self.test_db.name)
    
    @patch('utils.config')
    @patch('utils.OpenAI')
    def test_call_llm_with_tracking(self, mock_openai_class, mock_config):
        """Test that call_llm logs to database when session_id is provided"""
        # Mock config
        mock_config.get.side_effect = lambda key, default=None: {
            'openrouter_base_url': 'https://test.api',
            'llm_model': 'test-model',
            'max_retries': 1,
            'initial_retry_delay': 0.1
        }.get(key, default)
        
        # Mock OpenAI client and response
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.api_key = "test-key"
        
        # Mock successful completion
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Test response"
        mock_completion.usage.prompt_tokens = 100
        mock_completion.usage.completion_tokens = 50
        mock_completion.id = "test-request-id"
        mock_client.chat.completions.create.return_value = mock_completion
        
        # Mock environment variable
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test-key'}):
            # Call LLM with session tracking
            response = utils.call_llm(
                prompt="Test prompt",
                temperature=0.7,
                call_type="test",
                session_id=self.session_id
            )
        
        # Verify response
        self.assertEqual(response, "Test response")
        
        # Verify database logging
        analytics = self.db_manager.get_session_llm_analytics(self.session_id)
        self.assertEqual(len(analytics['recent_calls']), 1)
        
        call = analytics['recent_calls'][0]
        self.assertEqual(call['call_type'], 'test')
        self.assertEqual(call['model_name'], 'test-model')
        self.assertTrue(call['success'])
        self.assertEqual(call['total_tokens'], 150)
    
    @patch('utils.config')
    @patch('utils.OpenAI')
    def test_call_llm_error_tracking(self, mock_openai_class, mock_config):
        """Test that call_llm logs errors to database"""
        # Mock config
        mock_config.get.side_effect = lambda key, default=None: {
            'openrouter_base_url': 'https://test.api',
            'llm_model': 'test-model',
            'max_retries': 1,
            'initial_retry_delay': 0.1
        }.get(key, default)
        
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.api_key = "test-key"
        
        # Mock API error
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        # Mock environment variable
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test-key'}):
            # Call LLM with session tracking
            response = utils.call_llm(
                prompt="Test prompt",
                call_type="test",
                session_id=self.session_id
            )
        
        # Verify error response
        self.assertTrue(response.startswith("Error:"))
        
        # Verify database logging
        analytics = self.db_manager.get_session_llm_analytics(self.session_id)
        self.assertEqual(len(analytics['recent_calls']), 1)
        
        call = analytics['recent_calls'][0]
        self.assertEqual(call['call_type'], 'test')
        self.assertFalse(call['success'])
        self.assertIsNotNone(call['error_message'])

class TestModelPricing(unittest.TestCase):
    """Test model pricing functionality"""
    
    def setUp(self):
        """Set up test database"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        self.db_manager = DatabaseManager(self.test_db.name)
    
    def tearDown(self):
        """Clean up test database"""
        os.unlink(self.test_db.name)
    
    def test_save_model_pricing(self):
        """Test saving model pricing data"""
        self.db_manager.save_model_pricing(
            model_name="test-model",
            provider="test-provider",
            prompt_price_per_1k=0.001,
            completion_price_per_1k=0.002,
            context_window=4096,
            max_output_tokens=2048
        )
        
        # Verify pricing was saved by calculating cost
        cost = self.db_manager._calculate_api_cost("test-model", 100, 50)
        expected_cost = (100 / 1000.0 * 0.001) + (50 / 1000.0 * 0.002)
        self.assertAlmostEqual(cost, expected_cost, places=6)
    
    def test_default_pricing_initialization(self):
        """Test that default pricing can be initialized"""
        # This is a simple test to ensure the function doesn't crash
        # In a real scenario, we'd mock the database operations
        try:
            # Just test that the DEFAULT_MODEL_PRICING constant exists and is valid
            self.assertIsInstance(model_pricing.DEFAULT_MODEL_PRICING, dict)
            self.assertGreater(len(model_pricing.DEFAULT_MODEL_PRICING), 0)
            
            # Test that each entry has required fields
            for model_name, pricing in model_pricing.DEFAULT_MODEL_PRICING.items():
                self.assertIn("provider", pricing)
                self.assertIn("prompt_price_per_1k", pricing)
                self.assertIn("completion_price_per_1k", pricing)
                self.assertIsInstance(pricing["prompt_price_per_1k"], (int, float))
                self.assertIsInstance(pricing["completion_price_per_1k"], (int, float))
        except Exception as e:
            self.fail(f"Default pricing initialization failed: {e}")

if __name__ == '__main__':
    print("🧪 Running LLM tracking and analytics tests...")
    unittest.main(verbosity=2)
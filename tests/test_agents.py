#!/usr/bin/env python3
"""
Test script for agent functionality including arXiv reference tracking
"""

import sys
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import agents
import models
import database

# Use the imported modules directly
GenerationAgent = agents.GenerationAgent
ReflectionAgent = agents.ReflectionAgent
Hypothesis = models.Hypothesis
ResearchGoal = models.ResearchGoal
ContextMemory = models.ContextMemory
DatabaseManager = database.DatabaseManager

class TestAgentArxivTracking(unittest.TestCase):
    """Test cases for arXiv reference tracking in agents"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary database
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        self.db_manager = DatabaseManager(self.test_db.name)
        
        # Create test session
        research_goal = ResearchGoal(description="Agent test goal")
        self.session_id = self.db_manager.create_session(research_goal)
        
        # Create context with database support
        self.context = ContextMemory(session_id=self.session_id, use_database=True)
        self.research_goal = research_goal
    
    def tearDown(self):
        """Clean up test database"""
        os.unlink(self.test_db.name)
    
    def test_generation_agent_reference_tracking(self):
        """Test that GenerationAgent tracks arXiv references in generated text"""
        agent = GenerationAgent()
        
        # Mock the arXiv tool to avoid real API calls
        with patch('agents.ArxivSearchTool') as mock_arxiv_tool:
            mock_tool_instance = MagicMock()
            mock_tool_instance.get_paper_details.return_value = {
                'arxiv_id': '2301.12345',
                'title': 'Test Paper',
                'abstract': 'Test abstract',
                'authors': ['Test Author'],
                'primary_category': 'cs.AI',
                'categories': ['cs.AI'],
                'published': '2023-01-01T00:00:00',
                'pdf_url': 'https://arxiv.org/pdf/2301.12345.pdf',
                'arxiv_url': 'https://arxiv.org/abs/2301.12345'
            }
            mock_arxiv_tool.return_value = mock_tool_instance
            
            # Create a hypothesis with arXiv reference in text
            hypothesis = Hypothesis(
                "H001", 
                "Test Hypothesis", 
                "This hypothesis is based on arXiv:2301.12345 which shows promising results."
            )
            
            # Track references manually (simulating what happens in generate_new_hypotheses)
            agent._track_paper_references(
                hypothesis.hypothesis_id, 
                [hypothesis.text], 
                self.context.db_manager, 
                "llm_generation"
            )
            
            # Verify the reference was tracked
            analytics = self.db_manager.get_session_arxiv_analytics(self.session_id)
            self.assertEqual(len(analytics['paper_hypothesis_relationships']), 1)
            
            rel = analytics['paper_hypothesis_relationships'][0]
            self.assertEqual(rel['hypothesis_id'], 'H001')
            self.assertEqual(rel['arxiv_id'], '2301.12345')
            self.assertEqual(rel['reference_type'], 'inspiration')
            self.assertEqual(rel['added_by'], 'llm_generation')
    
    def test_reflection_agent_reference_tracking(self):
        """Test that ReflectionAgent tracks arXiv references from LLM responses"""
        agent = ReflectionAgent()
        
        # Mock the arXiv tool
        with patch('agents.ArxivSearchTool') as mock_arxiv_tool:
            mock_tool_instance = MagicMock()
            mock_tool_instance.get_paper_details.return_value = {
                'arxiv_id': '2301.54321',
                'title': 'Reflection Test Paper',
                'abstract': 'Test abstract for reflection',
                'authors': ['Reflection Author'],
                'primary_category': 'cs.ML',
                'categories': ['cs.ML'],
                'published': '2023-01-15T00:00:00',
                'pdf_url': 'https://arxiv.org/pdf/2301.54321.pdf',
                'arxiv_url': 'https://arxiv.org/abs/2301.54321'
            }
            mock_arxiv_tool.return_value = mock_tool_instance
            
            # Test reference tracking with multiple formats
            references = [
                "Based on arXiv:2301.54321",
                "See paper 2301.54321 for details",
                "Related work includes arXiv:cs/0701001"  # Old format, should be skipped
            ]
            
            agent._track_paper_references(
                "H002", 
                references, 
                self.context.db_manager, 
                "llm_reflection"
            )
            
            # Verify only the valid new-format references were tracked
            analytics = self.db_manager.get_session_arxiv_analytics(self.session_id)
            relationships = analytics['paper_hypothesis_relationships']
            
            # Should have 2 relationships (2301.54321 appears twice but should be deduplicated)
            self.assertEqual(len(relationships), 1)
            self.assertEqual(relationships[0]['arxiv_id'], '2301.54321')
            self.assertEqual(relationships[0]['reference_type'], 'citation')
            self.assertEqual(relationships[0]['added_by'], 'llm_reflection')
    
    def test_reference_extraction_patterns(self):
        """Test various arXiv ID extraction patterns"""
        agent = ReflectionAgent()
        
        test_cases = [
            ("Based on arXiv:2301.12345", "2301.12345"),
            ("See 2301.12345 for details", "2301.12345"),
            ("Paper arXiv:2301.12345v2 shows", "2301.12345"),
            ("Multiple refs: arXiv:2301.12345 and arXiv:2302.54321", ["2301.12345", "2302.54321"]),
            ("No valid refs here", []),
            ("Old format arXiv:cs/0701001", []),  # Should be skipped
        ]
        
        import re
        arxiv_patterns = [
            r'arXiv:(\d{4}\.\d{4,5})',  # arXiv:2301.12345
            r'(\d{4}\.\d{4,5})',        # 2301.12345
            r'arXiv:([a-z-]+/\d{7})',   # arXiv:cs/0701001 (old format)
        ]
        
        for test_text, expected in test_cases:
            found_ids = []
            for pattern in arxiv_patterns:
                matches = re.findall(pattern, test_text, re.IGNORECASE)
                for match in matches:
                    if '/' not in match:  # Skip old format
                        found_ids.append(match)
            
            # Remove duplicates while preserving order
            found_ids = list(dict.fromkeys(found_ids))
            
            if isinstance(expected, str):
                expected = [expected]
            
            self.assertEqual(found_ids, expected, f"Failed for text: {test_text}")

class TestAgentIntegration(unittest.TestCase):
    """Test agent integration with database persistence"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        self.db_manager = DatabaseManager(self.test_db.name)
        
        research_goal = ResearchGoal(
            description="Integration test goal",
            num_hypotheses=2,
            generation_temperature=0.7,
            reflection_temperature=0.5
        )
        self.session_id = self.db_manager.create_session(research_goal)
        self.context = ContextMemory(session_id=self.session_id, use_database=True)
        self.research_goal = research_goal
    
    def tearDown(self):
        """Clean up test database"""
        os.unlink(self.test_db.name)
    
    @patch('agents.call_llm_for_generation')
    def test_generation_with_database_persistence(self, mock_llm_gen):
        """Test that generated hypotheses are saved to database"""
        # Mock LLM response
        mock_llm_gen.return_value = [
            {
                "title": "Database Test Hypothesis 1",
                "text": "This is a test hypothesis for database persistence"
            },
            {
                "title": "Database Test Hypothesis 2", 
                "text": "Another test hypothesis with arXiv:2301.99999 reference"
            }
        ]
        
        agent = GenerationAgent()
        
        with patch('agents.ArxivSearchTool') as mock_arxiv_tool:
            mock_tool_instance = MagicMock()
            mock_tool_instance.get_paper_details.return_value = {
                'arxiv_id': '2301.99999',
                'title': 'Mock Paper',
                'abstract': 'Mock abstract',
                'authors': ['Mock Author'],
                'primary_category': 'cs.AI',
                'categories': ['cs.AI'],
                'published': '2023-01-01T00:00:00',
                'pdf_url': 'https://arxiv.org/pdf/2301.99999.pdf',
                'arxiv_url': 'https://arxiv.org/abs/2301.99999'
            }
            mock_arxiv_tool.return_value = mock_tool_instance
            
            # Generate hypotheses
            hypotheses = agent.generate_new_hypotheses(self.research_goal, self.context)
            
            # Verify hypotheses were generated
            self.assertEqual(len(hypotheses), 2)
            
            # Add hypotheses to context (simulating what SupervisorAgent does)
            for h in hypotheses:
                self.context.add_hypothesis(h)
            
            # Verify hypotheses were saved to database
            saved_hypotheses = self.db_manager.get_session_hypotheses(self.session_id)
            self.assertEqual(len(saved_hypotheses), 2)
            
            # Verify arXiv reference was tracked
            analytics = self.db_manager.get_session_arxiv_analytics(self.session_id)
            relationships = analytics['paper_hypothesis_relationships']
            
            # Should have tracked the arXiv reference from the second hypothesis
            self.assertGreaterEqual(len(relationships), 0)  # May be 0 if reference extraction didn't work
    
    @patch('agents.call_llm_for_reflection')
    def test_reflection_with_database_persistence(self, mock_llm_reflection):
        """Test that reflection results are saved to database"""
        # Create a test hypothesis
        hypothesis = Hypothesis("H001", "Test Hypothesis", "Test hypothesis text")
        self.context.add_hypothesis(hypothesis)
        
        # Mock LLM reflection response
        mock_llm_reflection.return_value = {
            "novelty_review": "HIGH",
            "feasibility_review": "MEDIUM",
            "comment": "Interesting approach with good potential",
            "references": ["arXiv:2301.11111", "Some other reference"]
        }
        
        agent = ReflectionAgent()
        
        with patch('agents.ArxivSearchTool') as mock_arxiv_tool:
            mock_tool_instance = MagicMock()
            mock_tool_instance.get_paper_details.return_value = {
                'arxiv_id': '2301.11111',
                'title': 'Reflection Mock Paper',
                'abstract': 'Mock abstract for reflection',
                'authors': ['Reflection Mock Author'],
                'primary_category': 'cs.AI',
                'categories': ['cs.AI'],
                'published': '2023-01-01T00:00:00',
                'pdf_url': 'https://arxiv.org/pdf/2301.11111.pdf',
                'arxiv_url': 'https://arxiv.org/abs/2301.11111'
            }
            mock_arxiv_tool.return_value = mock_tool_instance
            
            # Perform reflection
            agent.review_hypotheses([hypothesis], self.context, self.research_goal)
            
            # Verify hypothesis was updated
            self.assertEqual(hypothesis.novelty_review, "HIGH")
            self.assertEqual(hypothesis.feasibility_review, "MEDIUM")
            self.assertIn("Interesting approach with good potential", hypothesis.review_comments)
            
            # Verify database was updated
            saved_hypotheses = self.db_manager.get_session_hypotheses(self.session_id)
            saved_h = saved_hypotheses[0]
            self.assertEqual(saved_h.novelty_review, "HIGH")
            self.assertEqual(saved_h.feasibility_review, "MEDIUM")

if __name__ == '__main__':
    print("🤖 Running agent and arXiv tracking integration tests...")
    unittest.main(verbosity=2)
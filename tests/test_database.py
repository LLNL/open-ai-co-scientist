#!/usr/bin/env python3
"""
Test script for database functionality including arXiv tracking
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

# Use the imported modules directly
DatabaseManager = database.DatabaseManager
Hypothesis = models.Hypothesis
ResearchGoal = models.ResearchGoal

class TestDatabaseManager(unittest.TestCase):
    """Test cases for DatabaseManager"""
    
    def setUp(self):
        """Set up test database"""
        # Use temporary file for test database
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        self.db_manager = DatabaseManager(self.test_db.name)
    
    def tearDown(self):
        """Clean up test database"""
        os.unlink(self.test_db.name)
    
    def test_database_initialization(self):
        """Test that database tables are created correctly"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check that all tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = [
                'research_sessions', 'hypotheses', 'tournament_results',
                'meta_reviews', 'system_logs', 'arxiv_papers',
                'arxiv_searches', 'hypothesis_paper_references',
                'arxiv_search_results'
            ]
            
            for table in expected_tables:
                self.assertIn(table, tables, f"Table {table} not found in database")
    
    def test_create_session(self):
        """Test creating a research session"""
        research_goal = ResearchGoal(
            description="Test research goal",
            constraints={"test": "constraint"}
        )
        
        session_id = self.db_manager.create_session(research_goal)
        self.assertTrue(session_id.startswith("session_"))
        
        # Verify session was saved
        session_info = self.db_manager.get_session_info(session_id)
        self.assertIsNotNone(session_info)
        self.assertEqual(session_info['research_goal'], "Test research goal")
    
    def test_save_hypothesis(self):
        """Test saving a hypothesis"""
        research_goal = ResearchGoal(description="Test goal")
        session_id = self.db_manager.create_session(research_goal)
        
        hypothesis = Hypothesis("H001", "Test Hypothesis", "This is a test hypothesis")
        hypothesis.novelty_review = "HIGH"
        hypothesis.feasibility_review = "MEDIUM"
        
        self.db_manager.save_hypothesis(hypothesis, session_id)
        
        # Verify hypothesis was saved
        hypotheses = self.db_manager.get_session_hypotheses(session_id)
        self.assertEqual(len(hypotheses), 1)
        self.assertEqual(hypotheses[0].hypothesis_id, "H001")
        self.assertEqual(hypotheses[0].novelty_review, "HIGH")
    
    def test_save_arxiv_paper(self):
        """Test saving arXiv paper data"""
        paper_data = {
            'arxiv_id': '2301.12345',
            'title': 'Test Paper',
            'abstract': 'This is a test paper',
            'authors': ['Author One', 'Author Two'],
            'primary_category': 'cs.AI',
            'categories': ['cs.AI', 'cs.LG'],
            'published': '2023-01-01T00:00:00',
            'pdf_url': 'https://arxiv.org/pdf/2301.12345.pdf',
            'arxiv_url': 'https://arxiv.org/abs/2301.12345'
        }
        
        arxiv_id = self.db_manager.save_arxiv_paper(paper_data)
        self.assertEqual(arxiv_id, '2301.12345')
        
        # Test accessing the same paper again (should increment access count)
        arxiv_id2 = self.db_manager.save_arxiv_paper(paper_data)
        self.assertEqual(arxiv_id2, '2301.12345')
        
        # Verify access count was incremented
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT access_count FROM arxiv_papers WHERE arxiv_id = ?', (arxiv_id,))
            access_count = cursor.fetchone()[0]
            self.assertEqual(access_count, 2)
    
    def test_save_arxiv_search(self):
        """Test saving arXiv search data"""
        research_goal = ResearchGoal(description="Test goal")
        session_id = self.db_manager.create_session(research_goal)
        
        search_params = {
            'max_results': 10,
            'categories': ['cs.AI'],
            'sort_by': 'relevance'
        }
        
        search_id = self.db_manager.save_arxiv_search(
            session_id=session_id,
            query="machine learning",
            search_type="manual",
            search_params=search_params,
            results_count=5,
            search_time_ms=123.45
        )
        
        self.assertIsInstance(search_id, int)
        self.assertGreater(search_id, 0)
    
    def test_hypothesis_paper_reference(self):
        """Test linking papers to hypotheses"""
        research_goal = ResearchGoal(description="Test goal")
        session_id = self.db_manager.create_session(research_goal)
        
        # Create hypothesis
        hypothesis = Hypothesis("H001", "Test Hypothesis", "This is a test hypothesis")
        self.db_manager.save_hypothesis(hypothesis, session_id)
        
        # Create paper
        paper_data = {
            'arxiv_id': '2301.12345',
            'title': 'Test Paper',
            'abstract': 'This is a test paper',
            'authors': ['Author One'],
            'primary_category': 'cs.AI',
            'categories': ['cs.AI'],
            'published': '2023-01-01T00:00:00',
            'pdf_url': 'https://arxiv.org/pdf/2301.12345.pdf',
            'arxiv_url': 'https://arxiv.org/abs/2301.12345'
        }
        self.db_manager.save_arxiv_paper(paper_data)
        
        # Link paper to hypothesis
        self.db_manager.save_hypothesis_paper_reference(
            hypothesis_id="H001",
            arxiv_id="2301.12345",
            reference_type="citation",
            added_by="test",
            relevance_score=0.8
        )
        
        # Verify relationship was saved
        analytics = self.db_manager.get_session_arxiv_analytics(session_id)
        self.assertEqual(len(analytics['paper_hypothesis_relationships']), 1)
        self.assertEqual(analytics['paper_hypothesis_relationships'][0]['arxiv_id'], '2301.12345')
        self.assertEqual(analytics['paper_hypothesis_relationships'][0]['hypothesis_id'], 'H001')
    
    def test_export_session_data(self):
        """Test exporting complete session data"""
        research_goal = ResearchGoal(description="Test export goal")
        session_id = self.db_manager.create_session(research_goal)
        
        # Add some data
        hypothesis = Hypothesis("H001", "Test Hypothesis", "Export test")
        self.db_manager.save_hypothesis(hypothesis, session_id)
        
        # Export data
        export_data = self.db_manager.export_session_data(session_id)
        
        self.assertIsNotNone(export_data)
        self.assertIn('session', export_data)
        self.assertIn('hypotheses', export_data)
        self.assertIn('arxiv_analytics', export_data)
        
        self.assertEqual(len(export_data['hypotheses']), 1)
        self.assertEqual(export_data['hypotheses'][0]['id'], 'H001')

class TestArxivTracking(unittest.TestCase):
    """Test cases specifically for arXiv tracking functionality"""
    
    def setUp(self):
        """Set up test database"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        self.db_manager = DatabaseManager(self.test_db.name)
        
        # Create a test session
        research_goal = ResearchGoal(description="arXiv tracking test")
        self.session_id = self.db_manager.create_session(research_goal)
    
    def tearDown(self):
        """Clean up test database"""
        os.unlink(self.test_db.name)
    
    def test_arxiv_analytics_empty_session(self):
        """Test analytics for session with no arXiv activity"""
        analytics = self.db_manager.get_session_arxiv_analytics(self.session_id)
        
        self.assertEqual(analytics['search_statistics'], [])
        self.assertEqual(analytics['top_accessed_papers'], [])
        self.assertEqual(analytics['paper_hypothesis_relationships'], [])
        self.assertEqual(analytics['category_distribution'], [])
        self.assertEqual(analytics['total_unique_papers'], 0)
    
    def test_full_arxiv_workflow(self):
        """Test complete arXiv tracking workflow"""
        # 1. Perform a search
        search_params = {'max_results': 5, 'categories': ['cs.AI']}
        search_id = self.db_manager.save_arxiv_search(
            session_id=self.session_id,
            query="neural networks",
            search_type="manual",
            search_params=search_params,
            results_count=3,
            search_time_ms=234.56
        )
        
        # 2. Save some papers from the search
        papers = [
            {
                'arxiv_id': '2301.01001',
                'title': 'Neural Network Paper 1',
                'abstract': 'Abstract 1',
                'authors': ['Author A'],
                'primary_category': 'cs.AI',
                'categories': ['cs.AI'],
                'published': '2023-01-01T00:00:00',
                'pdf_url': 'https://arxiv.org/pdf/2301.01001.pdf',
                'arxiv_url': 'https://arxiv.org/abs/2301.01001'
            },
            {
                'arxiv_id': '2301.01002',
                'title': 'Neural Network Paper 2',
                'abstract': 'Abstract 2',
                'authors': ['Author B'],
                'primary_category': 'cs.LG',
                'categories': ['cs.LG', 'cs.AI'],
                'published': '2023-01-02T00:00:00',
                'pdf_url': 'https://arxiv.org/pdf/2301.01002.pdf',
                'arxiv_url': 'https://arxiv.org/abs/2301.01002'
            }
        ]
        
        self.db_manager.save_arxiv_search_results(search_id, papers)
        
        # 3. Create a hypothesis and link it to a paper
        hypothesis = Hypothesis("H001", "NN Hypothesis", "Based on recent neural network research")
        self.db_manager.save_hypothesis(hypothesis, self.session_id)
        
        self.db_manager.save_hypothesis_paper_reference(
            hypothesis_id="H001",
            arxiv_id="2301.01001",
            reference_type="inspiration",
            added_by="llm_generation",
            relevance_score=0.9
        )
        
        # 4. Get analytics and verify everything is tracked
        analytics = self.db_manager.get_session_arxiv_analytics(self.session_id)
        
        # Check search statistics
        self.assertEqual(len(analytics['search_statistics']), 1)
        search_stat = analytics['search_statistics'][0]
        self.assertEqual(search_stat['search_count'], 1)
        self.assertEqual(search_stat['total_papers_found'], 3)
        self.assertEqual(search_stat['search_type'], 'manual')
        
        # Check papers
        self.assertEqual(len(analytics['top_accessed_papers']), 2)
        
        # Check relationships
        self.assertEqual(len(analytics['paper_hypothesis_relationships']), 1)
        rel = analytics['paper_hypothesis_relationships'][0]
        self.assertEqual(rel['hypothesis_id'], 'H001')
        self.assertEqual(rel['arxiv_id'], '2301.01001')
        self.assertEqual(rel['reference_type'], 'inspiration')
        
        # Check categories
        self.assertEqual(len(analytics['category_distribution']), 2)
        categories = {cat['primary_category']: cat['count'] for cat in analytics['category_distribution']}
        self.assertEqual(categories['cs.AI'], 1)
        self.assertEqual(categories['cs.LG'], 1)

if __name__ == '__main__':
    print("🧪 Running database and arXiv tracking tests...")
    unittest.main(verbosity=2)
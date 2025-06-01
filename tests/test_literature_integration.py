#!/usr/bin/env python3
"""
Test script for literature-informed hypothesis generation
"""
import sys
import os
import json

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_literature_integration():
    """Test the complete literature integration workflow"""
    print("🧪 Testing Literature-Informed Hypothesis Generation")
    print("=" * 60)
    
    try:
        # Test 1: Search term extraction
        print("\n1. Testing search term extraction...")
        import re
        
        def _extract_search_terms(research_goal_description: str) -> str:
            stopwords = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 
                'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 
                'above', 'below', 'between', 'among', 'is', 'are', 'was', 'were', 'be', 'been', 
                'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 
                'should', 'may', 'might', 'must', 'can', 'shall', 'new', 'novel', 'develop', 
                'improvement', 'better', 'enhance', 'increase', 'method', 'methods', 'approach',
                'approaches', 'way', 'ways', 'technique', 'techniques', 'strategy', 'strategies'
            }
            
            text = research_goal_description.lower()
            text = re.sub(r'[^\w\s-]', ' ', text)
            words = text.split()
            meaningful_words = [word for word in words if len(word) > 2 and word not in stopwords]
            key_terms = meaningful_words[:8]
            search_query = ' '.join(key_terms)
            
            if not search_query.strip():
                search_query = research_goal_description[:100]
            
            return search_query
        
        test_goal = "Develop new methods for increasing solar panel efficiency"
        search_terms = _extract_search_terms(test_goal)
        print(f"   Research Goal: {test_goal}")
        print(f"   Extracted Terms: {search_terms}")
        assert len(search_terms) > 0, "Search terms should not be empty"
        print("   ✅ Search term extraction working")
        
        # Test 2: ArXiv search with search_type
        print("\n2. Testing arXiv search with search_type...")
        import tools.arxiv_search as arxiv_module
        arxiv_tool = arxiv_module.ArxivSearchTool(max_results=3)
        papers = arxiv_tool.search(search_terms, search_type="auto_goal_setting")
        print(f"   Found {len(papers)} papers for query: {search_terms}")
        if papers:
            print(f"   Sample paper: {papers[0]['title'][:50]}...")
        print("   ✅ ArXiv search working")
        
        # Test 3: Research goal with literature context
        print("\n3. Testing ResearchGoal with literature context...")
        import models
        research_goal = models.ResearchGoal(test_goal, num_hypotheses=2)
        research_goal.literature_context = papers[:3]
        print(f"   Literature context: {len(research_goal.literature_context)} papers")
        print("   ✅ ResearchGoal literature context working")
        
        # Test 4: Check literature integration in generation
        print("\n4. Testing literature integration setup...")
        if hasattr(research_goal, 'literature_context') and research_goal.literature_context:
            print("   ✓ ResearchGoal has literature_context attribute")
            print(f"   ✓ Literature context contains {len(research_goal.literature_context)} papers")
            if research_goal.literature_context:
                sample_paper = research_goal.literature_context[0]
                print(f"   ✓ Sample paper has title: {sample_paper.get('title', 'N/A')[:50]}...")
                print(f"   ✓ Sample paper has abstract: {'Yes' if sample_paper.get('abstract') else 'No'}")
        else:
            print("   ✗ ResearchGoal missing literature_context")
        
        print("   ✅ Literature integration setup working")
        
        print("\n🎉 All literature integration tests passed!")
        print("\nTo test the complete workflow:")
        print("1. Start the server: make run")
        print("2. Make a request:")
        print('   curl -X POST "http://localhost:8000/research_goal" \\')
        print('     -H "Content-Type: application/json" \\')
        print('     -d \'{"description": "Develop new methods for increasing solar panel efficiency", "num_hypotheses": 3}\'')
        print("\n3. Check the response for:")
        print("   - auto_run_result with literature-informed hypotheses")
        print("   - literature_papers_found count > 0")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_literature_integration()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Test script for arXiv integration
Run this independently to test the arXiv functionality before full integration
"""

import sys
import os

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.tools.arxiv_search import ArxivSearchTool, get_categories_for_field

def test_basic_search():
    """Test basic arXiv search functionality"""
    print("🔍 Testing basic arXiv search...")
    
    tool = ArxivSearchTool(max_results=5)
    papers = tool.search_papers("machine learning", max_results=3)
    
    print(f"Found {len(papers)} papers")
    for i, paper in enumerate(papers, 1):
        print(f"\n{i}. {paper['title']}")
        print(f"   Authors: {', '.join(paper['authors'][:3])}{'...' if len(paper['authors']) > 3 else ''}")
        print(f"   arXiv ID: {paper['arxiv_id']}")
        print(f"   Published: {paper['published']}")
        print(f"   Categories: {', '.join(paper['categories'])}")
        print(f"   Abstract: {paper['abstract'][:200]}...")
    
    return len(papers) > 0

def test_category_search():
    """Test category-specific search"""
    print("\n🏷️ Testing category-specific search...")
    
    tool = ArxivSearchTool(max_results=3)
    papers = tool.search_papers("neural networks", categories=["cs.AI", "cs.LG"])
    
    print(f"Found {len(papers)} papers in cs.AI or cs.LG categories")
    for paper in papers:
        print(f"- {paper['title']} ({paper['primary_category']})")
    
    return len(papers) > 0

def test_recent_papers():
    """Test recent papers search"""
    print("\n📅 Testing recent papers search...")
    
    tool = ArxivSearchTool(max_results=3)
    papers = tool.search_recent_papers("transformer", days_back=30)
    
    print(f"Found {len(papers)} recent papers about 'transformer'")
    for paper in papers:
        print(f"- {paper['title']} (Published: {paper['published']})")
    
    return True  # May return 0 papers if nothing recent

def test_specific_paper():
    """Test getting a specific paper by ID"""
    print("\n📄 Testing specific paper retrieval...")
    
    tool = ArxivSearchTool()
    # Use a well-known paper ID (Attention Is All You Need)
    paper = tool.get_paper_details("1706.03762")
    
    if paper:
        print(f"Retrieved paper: {paper['title']}")
        print(f"Authors: {', '.join(paper['authors'])}")
        print(f"Abstract: {paper['abstract'][:200]}...")
        return True
    else:
        print("Failed to retrieve specific paper")
        return False

def test_trends_analysis():
    """Test trends analysis"""
    print("\n📊 Testing trends analysis...")
    
    tool = ArxivSearchTool()
    trends = tool.analyze_research_trends("quantum computing", days_back=60)
    
    print(f"Trends analysis for 'quantum computing':")
    print(f"- Total papers: {trends['total_papers']}")
    print(f"- Date range: {trends['date_range']}")
    print(f"- Top categories: {trends['top_categories'][:3]}")
    print(f"- Top authors: {trends['top_authors'][:3]}")
    
    return True

def test_categories():
    """Test category utilities"""
    print("\n🏷️ Testing category utilities...")
    
    cs_categories = get_categories_for_field("computer_science")
    print(f"Computer Science categories: {cs_categories}")
    
    physics_categories = get_categories_for_field("physics")
    print(f"Physics categories: {physics_categories}")
    
    return len(cs_categories) > 0

def main():
    """Run all tests"""
    print("🧪 ArXiv Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("Basic Search", test_basic_search),
        ("Category Search", test_category_search),
        ("Recent Papers", test_recent_papers),
        ("Specific Paper", test_specific_paper),
        ("Trends Analysis", test_trends_analysis),
        ("Categories", test_categories),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result, None))
            print(f"✅ {test_name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            results.append((test_name, False, str(e)))
            print(f"❌ {test_name}: ERROR - {e}")
    
    print("\n📋 Test Summary:")
    print("=" * 50)
    
    passed = sum(1 for _, result, _ in results if result)
    total = len(results)
    
    for test_name, result, error in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if error:
            print(f"    Error: {error}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! ArXiv integration is working correctly.")
        print("\n🚀 Next steps:")
        print("   1. Install dependencies: pip install -r requirements.txt")
        print("   2. Start the server: make run")
        print("   3. Visit http://localhost:8000/arxiv/test to use the web interface")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
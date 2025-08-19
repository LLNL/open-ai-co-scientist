# Literature Integration Implementation Plan

## Overview
Integration strategy for arXiv and Google Scholar to enhance hypothesis generation with real scientific literature.

## Phase 1: arXiv Integration (Week 1)

### Dependencies
```bash
pip install arxiv feedparser python-dateutil
```

### Implementation: `app/tools/literature.py`

```python
import arxiv
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

class ArxivSearchTool:
    def __init__(self, max_results: int = 10):
        self.max_results = max_results
        self.client = arxiv.Client()
    
    def search_papers(self, query: str, categories: List[str] = None) -> List[Dict]:
        """Search arXiv for papers matching query"""
        search = arxiv.Search(
            query=query,
            max_results=self.max_results,
            sort_by=arxiv.SortCriterion.Relevance,
            sort_order=arxiv.SortOrder.Descending
        )
        
        papers = []
        for paper in self.client.results(search):
            papers.append({
                'id': paper.entry_id,
                'title': paper.title,
                'abstract': paper.summary,
                'authors': [str(author) for author in paper.authors],
                'published': paper.published,
                'categories': paper.categories,
                'pdf_url': paper.pdf_url,
                'arxiv_id': paper.get_short_id()
            })
        return papers
    
    def get_recent_papers(self, category: str, days_back: int = 7) -> List[Dict]:
        """Get recent papers in a specific category"""
        start_date = datetime.now() - timedelta(days=days_back)
        query = f"cat:{category} AND submittedDate:[{start_date.strftime('%Y%m%d')} TO *]"
        return self.search_papers(query)
```

### Integration Points

1. **Generation Agent Enhancement**:
```python
# In app/agents.py - GenerationAgent
async def generate_literature_grounded_hypotheses(self, research_goal: ResearchGoal, context: ContextMemory) -> List[Hypothesis]:
    """Generate hypotheses based on recent literature"""
    arxiv_tool = ArxivSearchTool()
    
    # Search for relevant papers
    papers = arxiv_tool.search_papers(research_goal.description)
    
    # Create literature-aware prompt
    literature_context = "\n".join([
        f"Paper: {p['title']}\nAbstract: {p['abstract'][:500]}..."
        for p in papers[:3]
    ])
    
    prompt = f"""
    Research Goal: {research_goal.description}
    
    Recent Literature Context:
    {literature_context}
    
    Based on the research goal and recent literature, generate novel hypotheses that:
    1. Build upon or challenge existing findings
    2. Address gaps identified in the literature
    3. Propose new experimental approaches
    
    Ensure hypotheses are grounded in scientific literature but offer novel insights.
    """
    
    return await self.generate_with_prompt(prompt, research_goal)
```

2. **Reflection Agent Enhancement**:
```python
# Enhanced novelty checking
async def literature_novelty_check(self, hypothesis: Hypothesis) -> Dict:
    """Check hypothesis novelty against existing literature"""
    arxiv_tool = ArxivSearchTool()
    
    # Search for papers related to hypothesis
    papers = arxiv_tool.search_papers(hypothesis.text[:200])
    
    if not papers:
        return {"novelty_score": "HIGH", "similar_papers": []}
    
    # Analyze similarity with existing work
    prompt = f"""
    Hypothesis: {hypothesis.text}
    
    Existing Literature:
    {chr(10).join([f"- {p['title']}: {p['abstract'][:300]}" for p in papers[:5]])}
    
    Assess novelty (HIGH/MEDIUM/LOW) and explain how this hypothesis differs from existing work.
    """
    
    # ... LLM call logic
```

## Phase 2: Google Scholar Integration (Week 2)

### Option A: Using `scholarly` (Free)
```python
pip install scholarly
```

```python
from scholarly import scholarly, ProxyGenerator

class GoogleScholarTool:
    def __init__(self):
        # Optional: Use proxy for rate limiting
        pg = ProxyGenerator()
        pg.FreeProxies()
        scholarly.use_proxy(pg)
    
    def search_papers(self, query: str, num_results: int = 10) -> List[Dict]:
        search_query = scholarly.search_pubs(query)
        papers = []
        
        for i, paper in enumerate(search_query):
            if i >= num_results:
                break
            papers.append({
                'title': paper.get('title'),
                'abstract': paper.get('abstract'),
                'authors': paper.get('author'),
                'year': paper.get('pub_year'),
                'citations': paper.get('num_citations'),
                'url': paper.get('pub_url')
            })
        return papers
```

### Option B: Using SerpAPI (Paid but Reliable)
```python
pip install google-search-results
```

```python
from serpapi import GoogleSearch

class GoogleScholarSerpTool:
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def search_papers(self, query: str, num_results: int = 10) -> List[Dict]:
        params = {
            "engine": "google_scholar",
            "q": query,
            "api_key": self.api_key,
            "num": num_results
        }
        
        search = GoogleSearch(params)
        results = search.get_dict()
        
        papers = []
        for result in results.get("organic_results", []):
            papers.append({
                'title': result.get('title'),
                'abstract': result.get('snippet'),
                'authors': result.get('publication_info', {}).get('authors'),
                'year': result.get('publication_info', {}).get('year'),
                'citations': result.get('inline_links', {}).get('cited_by', {}).get('total'),
                'pdf_link': result.get('resources', [{}])[0].get('link') if result.get('resources') else None
            })
        return papers
```

## Phase 3: Unified Literature Tool (Week 3)

### Combined Search Interface
```python
class LiteratureSearchTool:
    def __init__(self, config: Dict):
        self.arxiv_tool = ArxivSearchTool()
        self.scholar_tool = self._init_scholar_tool(config)
    
    def comprehensive_search(self, query: str, max_results: int = 20) -> Dict:
        """Search both arXiv and Google Scholar"""
        results = {
            'arxiv_papers': self.arxiv_tool.search_papers(query, max_results//2),
            'scholar_papers': self.scholar_tool.search_papers(query, max_results//2),
            'total_found': 0
        }
        results['total_found'] = len(results['arxiv_papers']) + len(results['scholar_papers'])
        return results
    
    def analyze_literature_gap(self, research_goal: str) -> Dict:
        """Identify gaps in current literature"""
        papers = self.comprehensive_search(research_goal)
        
        # Use LLM to analyze gaps
        prompt = f"""
        Research Goal: {research_goal}
        
        Recent Literature Found:
        {self._format_papers_for_analysis(papers)}
        
        Identify:
        1. Key themes in current research
        2. Gaps or unexplored areas
        3. Conflicting findings that need resolution
        4. Opportunities for novel approaches
        """
        
        # ... LLM analysis
```

## Configuration Updates

### Add to `config.yaml`:
```yaml
literature_search:
  arxiv:
    max_results: 10
    categories: ["cs.AI", "cs.LG", "cs.CL"]  # Customize based on domain
  
  google_scholar:
    method: "scholarly"  # or "serpapi"
    serpapi_key: ""  # If using SerpAPI
    max_results: 10
    rate_limit_delay: 2  # seconds between requests
  
  analysis:
    similarity_threshold: 0.7
    max_papers_per_analysis: 5
```

## Integration with Existing Agents

### 1. Update Generation Agent:
```python
# Add literature-grounded generation method
self.literature_tool = LiteratureSearchTool(config['literature_search'])

async def generate_with_literature(self, research_goal: ResearchGoal) -> List[Hypothesis]:
    # Search literature
    literature = self.literature_tool.comprehensive_search(research_goal.description)
    
    # Generate context-aware hypotheses
    return await self.generate_literature_grounded_hypotheses(research_goal, literature)
```

### 2. Enhance Reflection Agent:
```python
async def deep_literature_review(self, hypothesis: Hypothesis) -> Dict:
    # Check against existing literature
    similar_papers = self.literature_tool.find_similar_work(hypothesis.text)
    
    # Assess novelty and feasibility with literature context
    return await self.literature_informed_review(hypothesis, similar_papers)
```

## Testing Strategy

### Unit Tests:
```python
# tests/test_literature_tools.py
def test_arxiv_search():
    tool = ArxivSearchTool()
    papers = tool.search_papers("machine learning")
    assert len(papers) > 0
    assert 'title' in papers[0]

def test_literature_integration():
    # Test full integration with agents
    pass
```

## Performance Considerations

1. **Caching**: Cache literature search results for 24 hours
2. **Rate Limiting**: Respect API limits (arXiv: none, Scholar: 1 req/sec)
3. **Async Processing**: Make literature searches non-blocking
4. **Storage**: Store relevant papers in database for future reference

## Expected Impact

- **Hypothesis Quality**: 40-60% improvement in scientific grounding
- **Novelty Assessment**: More accurate literature-based validation
- **Research Gaps**: Automatic identification of unexplored areas
- **Citation Integration**: Proper attribution and reference tracking

This implementation provides a solid foundation for literature-integrated hypothesis generation while being scalable and maintainable.
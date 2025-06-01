# API Documentation

The AI Co-Scientist system provides REST API endpoints for all functionality, including new database and analytics features.

## Base URL
```
http://localhost:8000
```

## Core Research Endpoints

### POST /research_goal
Set a new research goal and initialize a session.

**Request Body:**
```json
{
  "description": "Develop new methods for increasing solar panel efficiency",
  "constraints": {},
  "llm_model": "google/gemini-2.0-flash-001",
  "num_hypotheses": 6,
  "generation_temperature": 0.7,
  "reflection_temperature": 0.5,
  "elo_k_factor": 32,
  "top_k_hypotheses": 2
}
```

**Response:**
```json
{
  "message": "Research goal set successfully",
  "session_id": "session_20250531_174002",
  "auto_run_result": {
    "iteration": 1,
    "meta_review_critique": ["Initial hypotheses show good diversity"],
    "top_hypotheses": [...],
    "suggested_next_steps": [...]
  }
}
```

### POST /run_cycle
Execute a research cycle on the current session.

**Response:**
```json
{
  "iteration": 2,
  "meta_review_critique": ["Hypotheses are improving"],
  "top_hypotheses": [
    {
      "id": "G1234",
      "title": "Nanomaterial Enhancement",
      "text": "Explore quantum dots for light absorption",
      "novelty_review": "HIGH",
      "feasibility_review": "MEDIUM",
      "elo_score": 1250.5,
      "review_comments": [...],
      "references": [...],
      "is_active": true
    }
  ],
  "suggested_next_steps": [...],
  "proximity_data": {
    "nodes": [...],
    "edges": [...]
  }
}
```

### GET /hypotheses
Get all active hypotheses for the current session.

**Response:**
```json
[
  {
    "id": "G1234",
    "title": "Nanomaterial Enhancement",
    "text": "Explore quantum dots for light absorption",
    "novelty_review": "HIGH",
    "feasibility_review": "MEDIUM",
    "elo_score": 1250.5,
    "review_comments": [...],
    "references": [...],
    "is_active": true
  }
]
```

## ArXiv Integration Endpoints

### POST /arxiv/search
Search arXiv for research papers.

**Request Body:**
```json
{
  "query": "machine learning neural networks",
  "max_results": 10,
  "categories": ["cs.LG", "cs.AI"],
  "sort_by": "relevance",
  "days_back": 30
}
```

**Response:**
```json
{
  "query": "machine learning neural networks",
  "total_results": 150,
  "papers": [
    {
      "arxiv_id": "2301.12345",
      "entry_id": "http://arxiv.org/abs/2301.12345v1",
      "title": "Advanced Neural Network Architectures",
      "abstract": "This paper presents novel approaches...",
      "authors": ["John Doe", "Jane Smith"],
      "primary_category": "cs.LG",
      "categories": ["cs.LG", "cs.AI"],
      "published": "2023-01-15",
      "updated": "2023-01-20",
      "doi": "10.1000/182",
      "pdf_url": "http://arxiv.org/pdf/2301.12345v1.pdf",
      "arxiv_url": "http://arxiv.org/abs/2301.12345v1",
      "comment": "Accepted at NeurIPS 2023",
      "journal_ref": null,
      "source": "arxiv"
    }
  ],
  "search_time_ms": 1250.5
}
```

### GET /arxiv/paper/{arxiv_id}
Get detailed information about a specific arXiv paper.

**Parameters:**
- `arxiv_id`: ArXiv paper ID (e.g., "2301.12345")

**Response:**
```json
{
  "arxiv_id": "2301.12345",
  "title": "Advanced Neural Network Architectures",
  "abstract": "This paper presents novel approaches...",
  "authors": ["John Doe", "Jane Smith"],
  "primary_category": "cs.LG",
  "categories": ["cs.LG", "cs.AI"],
  "published": "2023-01-15",
  "updated": "2023-01-20",
  "access_count": 5,
  "first_accessed": "2025-05-31T17:40:14",
  "last_accessed": "2025-05-31T18:30:22"
}
```

### GET /arxiv/categories
Get available arXiv subject categories.

**Response:**
```json
{
  "categories": [
    {
      "id": "cs.AI",
      "name": "Artificial Intelligence",
      "description": "Covers all areas of AI except Vision, Robotics, Machine Learning, Multiagent Systems, and Computation and Language"
    },
    {
      "id": "cs.LG", 
      "name": "Machine Learning",
      "description": "Papers on all aspects of machine learning research"
    }
  ]
}
```

### POST /arxiv/trends
Get trending papers in specific categories.

**Request Body:**
```json
{
  "categories": ["cs.AI", "cs.LG"],
  "days_back": 7,
  "max_results": 20
}
```

**Response:**
```json
{
  "query": "Recent trends in cs.AI, cs.LG",
  "total_papers": 45,
  "date_range": "2025-05-24 to 2025-05-31",
  "top_categories": [
    ["cs.LG", 25],
    ["cs.AI", 20]
  ],
  "top_authors": [
    ["John Doe", 3],
    ["Jane Smith", 2]
  ],
  "papers": [...]
}
```

### GET /arxiv/test
Testing interface for arXiv integration.

**Response:**
```html
<!-- HTML testing interface -->
```

## Dashboard and Analytics Endpoints

### GET /dashboard
Main analytics dashboard interface.

**Response:**
```html
<!-- HTML dashboard interface -->
```

### GET /dashboard/sessions
Research sessions browser interface.

**Response:**
```html
<!-- HTML sessions browser interface -->
```

### GET /api/sessions/recent
Get recent research sessions.

**Query Parameters:**
- `limit`: Maximum number of sessions to return (default: 10)

**Response:**
```json
[
  {
    "session_id": "session_20250531_174002",
    "research_goal": "Develop new solar panel technologies",
    "created_at": "2025-05-31T17:40:02",
    "is_active": true
  }
]
```

### GET /api/sessions/{session_id}/info
Get detailed information about a specific session.

**Response:**
```json
{
  "session_id": "session_20250531_174002",
  "research_goal": "Develop new solar panel technologies",
  "constraints": {},
  "settings": {
    "llm_model": "google/gemini-2.0-flash-001",
    "num_hypotheses": 6,
    "generation_temperature": 0.7,
    "reflection_temperature": 0.5,
    "elo_k_factor": 32,
    "top_k_hypotheses": 2
  },
  "created_at": "2025-05-31T17:40:02",
  "updated_at": "2025-05-31T18:30:15",
  "is_active": true
}
```

### GET /api/sessions/{session_id}/hypotheses
Get all hypotheses for a specific session.

**Query Parameters:**
- `active_only`: Whether to return only active hypotheses (default: true)

**Response:**
```json
[
  {
    "id": "G1234",
    "title": "Nanomaterial Enhancement",
    "text": "Explore quantum dots for light absorption",
    "novelty_review": "HIGH",
    "feasibility_review": "MEDIUM",
    "elo_score": 1250.5,
    "review_comments": [...],
    "references": [...],
    "is_active": true,
    "created_at": "2025-05-31T17:45:12",
    "updated_at": "2025-05-31T18:30:15"
  }
]
```

### GET /api/sessions/{session_id}/arxiv-analytics
Get arXiv usage analytics for a session.

**Response:**
```json
{
  "search_statistics": [
    {
      "search_count": 5,
      "total_papers_found": 25,
      "avg_search_time": 1250.5,
      "search_type": "auto_generation"
    }
  ],
  "top_accessed_papers": [
    {
      "arxiv_id": "2301.12345",
      "title": "Advanced Neural Networks",
      "authors": "[\"John Doe\", \"Jane Smith\"]",
      "access_count": 3,
      "primary_category": "cs.LG",
      "published_date": "2023-01-15"
    }
  ],
  "paper_hypothesis_relationships": [
    {
      "hypothesis_id": "G1234",
      "arxiv_id": "2301.12345",
      "reference_type": "inspiration",
      "added_by": "llm_generation",
      "title": "Advanced Neural Networks",
      "hypothesis_title": "Nanomaterial Enhancement"
    }
  ],
  "category_distribution": [
    {
      "primary_category": "cs.LG",
      "count": 15
    },
    {
      "primary_category": "cs.AI",
      "count": 10
    }
  ],
  "total_unique_papers": 25
}
```

### GET /api/sessions/{session_id}/llm-analytics
Get LLM usage analytics for a session.

**Response:**
```json
{
  "performance_metrics": [
    {
      "model_name": "google/gemini-2.0-flash-001",
      "call_type": "generation",
      "total_calls": 15,
      "successful_calls": 14,
      "failed_calls": 1,
      "retry_calls": 2,
      "rate_limited_calls": 0,
      "total_tokens": 12500,
      "total_cost_usd": 0.125,
      "avg_response_time_ms": 1850.5,
      "min_response_time_ms": 950.2,
      "max_response_time_ms": 3200.8
    }
  ],
  "recent_calls": [
    {
      "call_type": "generation",
      "model_name": "google/gemini-2.0-flash-001",
      "success": true,
      "response_time_ms": 1850.5,
      "total_tokens": 450,
      "api_cost_usd": 0.0045,
      "timestamp": "2025-05-31T18:30:15",
      "error_message": null,
      "retry_count": 0
    }
  ],
  "cost_breakdown": [
    {
      "model_name": "google/gemini-2.0-flash-001",
      "total_cost": 0.125,
      "call_count": 15,
      "total_tokens": 12500
    }
  ],
  "error_analysis": [
    {
      "error_message": "Rate limit exceeded",
      "error_count": 1
    }
  ],
  "total_calls": 15,
  "total_cost": 0.125,
  "total_tokens": 12500
}
```

### GET /api/sessions/{session_id}/export
Export complete session data.

**Response:**
```json
{
  "session": {
    "session_id": "session_20250531_174002",
    "research_goal": "Develop new solar panel technologies",
    "settings": {...},
    "created_at": "2025-05-31T17:40:02"
  },
  "hypotheses": [...],
  "tournament_results": [...],
  "meta_reviews": [...],
  "logs": [...],
  "arxiv_analytics": {...},
  "llm_analytics": {...}
}
```

## Utility Endpoints

### POST /log_frontend_error
Log frontend errors for debugging.

**Request Body:**
```json
{
  "error": "ReferenceError: variable is not defined",
  "context": "arxiv_search_widget",
  "url": "http://localhost:8000/",
  "userAgent": "Mozilla/5.0...",
  "timestamp": "2025-05-31T18:30:15"
}
```

**Response:**
```json
{
  "status": "logged"
}
```

### GET /models
Get available LLM models from OpenRouter.

**Response:**
```json
{
  "models": [
    {
      "id": "google/gemini-2.0-flash-001",
      "name": "Gemini 2.0 Flash",
      "provider": "Google",
      "context_length": 1000000,
      "pricing": {
        "prompt": 0.000075,
        "completion": 0.0003
      }
    }
  ]
}
```

## Error Responses

All endpoints may return error responses in the following format:

**4xx Client Errors:**
```json
{
  "error": "Invalid request",
  "detail": "Missing required field 'query'",
  "status_code": 400
}
```

**5xx Server Errors:**
```json
{
  "error": "Internal server error", 
  "detail": "Database connection failed",
  "status_code": 500
}
```

## Authentication

Currently, the API uses OpenRouter API key authentication for LLM calls:
- Set `OPENROUTER_API_KEY` environment variable
- No user authentication required for local development

## Rate Limiting

- ArXiv API calls are rate-limited to respect arXiv.org policies
- LLM API calls are subject to OpenRouter rate limits
- Dashboard endpoints have no rate limiting

## CORS

CORS is enabled for all origins in development mode. For production deployment, configure appropriate CORS settings.

## WebSocket Support

Currently, the API does not support WebSocket connections. All interactions are via HTTP requests.

## Data Formats

### Timestamps
All timestamps are in ISO 8601 format: `"2025-05-31T17:40:02"`

### Currency
All cost values are in USD with 4-6 decimal precision: `0.001234`

### IDs
- Session IDs: `"session_YYYYMMDD_HHMMSS"`
- Hypothesis IDs: `"G1234"` (Generated), `"E5678"` (Evolved), `"H9012"` (Default)
- ArXiv IDs: `"2301.12345"` (standard arXiv format)

## Example Usage

### Complete Research Workflow

```python
import requests

base_url = "http://localhost:8000"

# 1. Set research goal
response = requests.post(f"{base_url}/research_goal", json={
    "description": "Improve renewable energy storage efficiency",
    "num_hypotheses": 4
})
session_data = response.json()
session_id = session_data["session_id"]

# 2. Run additional cycles
for i in range(3):
    response = requests.post(f"{base_url}/run_cycle")
    cycle_data = response.json()
    print(f"Cycle {cycle_data['iteration']} completed")

# 3. Get final hypotheses
response = requests.get(f"{base_url}/hypotheses")
hypotheses = response.json()

# 4. Search related papers
response = requests.post(f"{base_url}/arxiv/search", json={
    "query": "renewable energy storage battery",
    "max_results": 10
})
papers = response.json()

# 5. Get session analytics
response = requests.get(f"{base_url}/api/sessions/{session_id}/llm-analytics")
llm_analytics = response.json()

response = requests.get(f"{base_url}/api/sessions/{session_id}/arxiv-analytics")
arxiv_analytics = response.json()

print(f"Session used {llm_analytics['total_tokens']} tokens")
print(f"Session cost: ${llm_analytics['total_cost']:.4f}")
print(f"Papers discovered: {arxiv_analytics['total_unique_papers']}")
```
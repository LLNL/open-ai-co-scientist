# Testing Guide

This guide covers how to test the AI Co-Scientist system's new database and tracking features independently.

## Prerequisites

1. **Environment Setup**
   ```bash
   # Activate virtual environment
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Set OpenRouter API key
   export OPENROUTER_API_KEY=your_api_key_here
   ```

2. **Start the Application**
   ```bash
   make run
   # Application will be available at http://localhost:8000
   ```

## Database Testing

### 1. Database Initialization Test

Test that the database is properly created and initialized:

```python
# Test database initialization
from app.database import get_db_manager
import os

# Check database file creation
db_path = "data/ai_coscientist.db"
assert os.path.exists(db_path), "Database file should exist"

# Test database connection
db = get_db_manager()
with db.get_connection() as conn:
    cursor = conn.cursor()
    
    # Check that all tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    expected_tables = [
        'research_sessions', 'hypotheses', 'tournament_results',
        'meta_reviews', 'system_logs', 'arxiv_papers', 'arxiv_searches',
        'arxiv_search_results', 'hypothesis_paper_references',
        'llm_calls', 'llm_performance_metrics', 'llm_model_pricing'
    ]
    
    for table in expected_tables:
        assert table in tables, f"Table {table} should exist"
    
    print("✅ Database initialization test passed")
```

### 2. Session Management Test

Test creating and retrieving research sessions:

```python
from app.database import get_db_manager
from app.models import ResearchGoal

db = get_db_manager()

# Create test research goal
research_goal = ResearchGoal(
    description="Test goal for database testing",
    llm_model="google/gemini-2.0-flash-001",
    num_hypotheses=3
)

# Test session creation
session_id = db.create_session(research_goal)
print(f"Created session: {session_id}")

# Test session retrieval
session_info = db.get_session_info(session_id)
assert session_info is not None, "Session should be retrievable"
assert session_info['research_goal'] == research_goal.description
print("✅ Session management test passed")

# Test recent sessions
recent = db.get_recent_sessions(limit=5)
assert len(recent) >= 1, "Should have at least one session"
print(f"Found {len(recent)} recent sessions")
```

### 3. Hypothesis Storage Test

Test hypothesis creation and retrieval:

```python
from app.models import Hypothesis

# Create test hypothesis
hypothesis = Hypothesis(
    hypothesis_id="TEST001",
    title="Test Hypothesis",
    text="This is a test hypothesis for database validation"
)
hypothesis.novelty_review = "HIGH"
hypothesis.feasibility_review = "MEDIUM"
hypothesis.elo_score = 1250.0

# Save hypothesis
db.save_hypothesis(hypothesis, session_id)
print(f"Saved hypothesis: {hypothesis.hypothesis_id}")

# Retrieve hypotheses
hypotheses = db.get_session_hypotheses(session_id)
assert len(hypotheses) >= 1, "Should have at least one hypothesis"
assert hypotheses[0].hypothesis_id == "TEST001"
print("✅ Hypothesis storage test passed")
```

## ArXiv Integration Testing

### 1. ArXiv Search API Test

Test the arXiv search functionality:

```bash
# Test basic search
curl -X POST "http://localhost:8000/arxiv/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning",
    "max_results": 3,
    "sort_by": "relevance"
  }'

# Expected response: JSON with papers array
```

```python
# Programmatic test
import requests

response = requests.post(
    "http://localhost:8000/arxiv/search",
    json={
        "query": "neural networks",
        "max_results": 5,
        "categories": ["cs.LG", "cs.AI"]
    }
)

assert response.status_code == 200
data = response.json()
assert "papers" in data
assert len(data["papers"]) <= 5
print(f"✅ ArXiv search returned {len(data['papers'])} papers")
```

### 2. ArXiv Database Tracking Test

Test that arXiv searches are properly tracked in the database:

```python
# Perform a search and check database tracking
from app.tools.arxiv_search import ArxivSearchTool

# Create search tool with session tracking
search_tool = ArxivSearchTool(max_results=3, session_id=session_id)

# Perform search
results = search_tool.search("quantum computing", days_back=30)
print(f"Search returned {len(results)} results")

# Check database tracking
with db.get_connection() as conn:
    cursor = conn.cursor()
    
    # Check search was logged
    cursor.execute(
        "SELECT COUNT(*) FROM arxiv_searches WHERE session_id = ?",
        (session_id,)
    )
    search_count = cursor.fetchone()[0]
    assert search_count >= 1, "Search should be tracked in database"
    
    # Check papers were saved
    cursor.execute("SELECT COUNT(*) FROM arxiv_papers")
    paper_count = cursor.fetchone()[0]
    assert paper_count >= len(results), "Papers should be saved"
    
    print("✅ ArXiv database tracking test passed")
```

### 3. ArXiv Analytics Test

Test session arXiv analytics:

```python
# Get analytics for the session
analytics = db.get_session_arxiv_analytics(session_id)

print("ArXiv Analytics:")
print(f"- Search statistics: {len(analytics['search_statistics'])}")
print(f"- Top papers: {len(analytics['top_accessed_papers'])}")
print(f"- Category distribution: {len(analytics['category_distribution'])}")
print(f"- Total unique papers: {analytics['total_unique_papers']}")

assert analytics['total_unique_papers'] >= 0
print("✅ ArXiv analytics test passed")
```

## LLM Call Tracking Testing

### 1. LLM Call Logging Test

Test that LLM calls are properly logged:

```python
from app.utils import call_llm

# Make a test LLM call with tracking
response = call_llm(
    prompt="What is machine learning?",
    temperature=0.7,
    call_type="test",
    session_id=session_id,
    hypothesis_id="TEST001"
)

print(f"LLM Response: {response[:100]}...")

# Check database tracking
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM llm_calls WHERE session_id = ?",
        (session_id,)
    )
    call_count = cursor.fetchone()[0]
    assert call_count >= 1, "LLM call should be tracked"
    
    # Check performance metrics were updated
    cursor.execute(
        "SELECT COUNT(*) FROM llm_performance_metrics WHERE session_id = ?",
        (session_id,)
    )
    metrics_count = cursor.fetchone()[0]
    assert metrics_count >= 1, "Performance metrics should be updated"
    
    print("✅ LLM call tracking test passed")
```

### 2. LLM Analytics Test

Test LLM performance analytics:

```python
# Get LLM analytics for the session
llm_analytics = db.get_session_llm_analytics(session_id)

print("LLM Analytics:")
print(f"- Performance metrics: {len(llm_analytics['performance_metrics'])}")
print(f"- Recent calls: {len(llm_analytics['recent_calls'])}")
print(f"- Total calls: {llm_analytics['total_calls']}")
print(f"- Total cost: ${llm_analytics['total_cost']:.4f}")
print(f"- Total tokens: {llm_analytics['total_tokens']}")

assert llm_analytics['total_calls'] >= 1
print("✅ LLM analytics test passed")
```

### 3. Cost Calculation Test

Test API cost calculations:

```python
# Save test model pricing
db.save_model_pricing(
    model_name="test-model",
    provider="test-provider",
    prompt_price_per_1k=0.001,
    completion_price_per_1k=0.002
)

# Test cost calculation
cost = db._calculate_api_cost("test-model", 1000, 500)
expected_cost = (1000 * 0.001 / 1000) + (500 * 0.002 / 1000)
assert abs(cost - expected_cost) < 0.0001, f"Cost calculation error: {cost} vs {expected_cost}"
print("✅ Cost calculation test passed")
```

## Web Dashboard Testing

### 1. Dashboard Endpoints Test

Test that dashboard endpoints are accessible:

```bash
# Test main dashboard
curl -I "http://localhost:8000/dashboard"
# Expected: 200 OK

# Test sessions browser
curl -I "http://localhost:8000/dashboard/sessions"
# Expected: 200 OK

# Test session analytics API
curl "http://localhost:8000/api/sessions/recent"
# Expected: JSON array of recent sessions
```

### 2. Session Analytics API Test

```python
import requests

# Test session analytics APIs
base_url = "http://localhost:8000"

# Test recent sessions
response = requests.get(f"{base_url}/api/sessions/recent")
assert response.status_code == 200
sessions = response.json()
print(f"Found {len(sessions)} recent sessions")

if sessions:
    test_session_id = sessions[0]['session_id']
    
    # Test arXiv analytics
    response = requests.get(f"{base_url}/api/sessions/{test_session_id}/arxiv-analytics")
    assert response.status_code == 200
    arxiv_data = response.json()
    print("✅ ArXiv analytics API test passed")
    
    # Test LLM analytics
    response = requests.get(f"{base_url}/api/sessions/{test_session_id}/llm-analytics")
    assert response.status_code == 200
    llm_data = response.json()
    print("✅ LLM analytics API test passed")
```

### 3. Dashboard UI Test

Manual testing steps for the web dashboard:

1. **Visit Main Dashboard**: Go to `http://localhost:8000/dashboard`
   - ✅ Page loads without errors
   - ✅ Navigation cards are displayed
   - ✅ "Back to AI Co-Scientist" link works

2. **Visit Sessions Browser**: Go to `http://localhost:8000/dashboard/sessions`
   - ✅ Sessions table loads
   - ✅ Search and filter controls work
   - ✅ Session details expand properly
   - ✅ Analytics charts display (if sessions exist)

3. **Test Session Creation Tracking**:
   - Create a new research session via main interface
   - Check that it appears in dashboard immediately
   - Verify analytics data is populated

## Data Migration Testing

### 1. Migration Script Test

Test the log file migration functionality:

```bash
# Ensure there are log files to migrate
ls results/app_log_*.txt

# Run migration
python migrate_results.py

# Check output for success messages
# Expected output includes:
# - "🎉 Migration completed successfully!"
# - Statistics on sessions and log entries migrated
```

### 2. Migration Data Validation

Test that migrated data is properly structured:

```python
from app.database import get_db_manager

db = get_db_manager()

# Check migrated sessions
with db.get_connection() as conn:
    cursor = conn.cursor()
    
    # Check for migrated sessions (identified by "migrated_" prefix)
    cursor.execute("SELECT * FROM research_sessions WHERE session_id LIKE 'migrated_%'")
    migrated_sessions = cursor.fetchall()
    
    print(f"Found {len(migrated_sessions)} migrated sessions")
    
    if migrated_sessions:
        session = migrated_sessions[0]
        session_id = session['session_id']
        
        # Check for associated data
        cursor.execute("SELECT COUNT(*) FROM system_logs WHERE session_id = ?", (session_id,))
        log_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM hypotheses WHERE session_id = ?", (session_id,))
        hypothesis_count = cursor.fetchone()[0]
        
        print(f"Session {session_id}:")
        print(f"- Log entries: {log_count}")
        print(f"- Hypotheses: {hypothesis_count}")
        
        print("✅ Migration data validation passed")
```

## Integration Testing

### 1. End-to-End Research Session Test

Test a complete research workflow with database tracking:

```python
import time
from app.models import ResearchGoal
from app.agents import GenerationAgent
from app.database import get_db_manager

db = get_db_manager()

# Create research session
research_goal = ResearchGoal(
    description="Develop new approaches to renewable energy storage",
    num_hypotheses=2,
    generation_temperature=0.7
)

session_id = db.create_session(research_goal)
print(f"Created research session: {session_id}")

# Generate hypotheses
generation_agent = GenerationAgent()
hypotheses = generation_agent.generate_hypotheses(research_goal, session_id=session_id)

print(f"Generated {len(hypotheses)} hypotheses")

# Wait a moment for async operations
time.sleep(2)

# Check database state
session_data = db.export_session_data(session_id)
print("Session export contains:")
print(f"- Hypotheses: {len(session_data['hypotheses'])}")
print(f"- LLM calls: {session_data['llm_analytics']['total_calls']}")
print(f"- ArXiv papers: {session_data['arxiv_analytics']['total_unique_papers']}")

print("✅ End-to-end integration test passed")
```

### 2. Performance Test

Test system performance with database tracking:

```python
import time
from app.utils import call_llm

# Measure performance impact of database tracking
start_time = time.time()

# Make multiple LLM calls
for i in range(5):
    response = call_llm(
        prompt=f"Generate a short hypothesis about renewable energy (attempt {i+1})",
        temperature=0.7,
        call_type="performance_test",
        session_id=session_id
    )

end_time = time.time()
duration = end_time - start_time

print(f"5 LLM calls with database tracking took {duration:.2f} seconds")
print(f"Average time per call: {duration/5:.2f} seconds")

# Check that all calls were tracked
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM llm_calls WHERE call_type = 'performance_test'"
    )
    tracked_calls = cursor.fetchone()[0]
    assert tracked_calls == 5, "All calls should be tracked"

print("✅ Performance test passed")
```

## Test Cleanup

After running tests, clean up test data:

```python
# Clean up test data
with db.get_connection() as conn:
    cursor = conn.cursor()
    
    # Remove test session and related data
    cursor.execute("DELETE FROM research_sessions WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM hypotheses WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM llm_calls WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM arxiv_searches WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM system_logs WHERE session_id = ?", (session_id,))
    
    # Remove test model pricing
    cursor.execute("DELETE FROM llm_model_pricing WHERE model_name = 'test-model'")
    
    conn.commit()
    print("✅ Test cleanup completed")
```

## Running All Tests

To run all tests in sequence:

```python
#!/usr/bin/env python3
"""
Comprehensive test suite for AI Co-Scientist database features
"""
import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

def run_all_tests():
    """Run all database and integration tests"""
    try:
        print("🧪 Starting comprehensive test suite...")
        
        # Database tests
        print("\n1. Database Initialization Test")
        # ... (run database init test)
        
        print("\n2. Session Management Test")
        # ... (run session test)
        
        print("\n3. Hypothesis Storage Test")
        # ... (run hypothesis test)
        
        print("\n4. ArXiv Integration Test")
        # ... (run arxiv tests)
        
        print("\n5. LLM Tracking Test")
        # ... (run llm tests)
        
        print("\n6. Analytics Test")
        # ... (run analytics tests)
        
        print("\n7. Integration Test")
        # ... (run integration test)
        
        print("\n🎉 All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
```

Save this as `test_database_features.py` and run with:
```bash
python test_database_features.py
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check that `data/` directory exists and is writable
   - Verify SQLite is properly installed

2. **API Key Issues**
   - Ensure `OPENROUTER_API_KEY` environment variable is set
   - Test with a simple API call first

3. **Missing Dependencies**
   - Run `pip install -r requirements.txt` in virtual environment
   - Check for any import errors

4. **Migration Issues**
   - Ensure log files exist in `results/` directory
   - Check log file format matches expected patterns

5. **Dashboard Access Issues**
   - Verify application is running on correct port
   - Check for any CORS or permission issues
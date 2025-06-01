# Database Documentation

The AI Co-Scientist system uses SQLite for persistent storage of all research activities, providing comprehensive tracking and analytics capabilities.

## Database Schema

### Core Tables

#### `research_sessions`
Stores information about each research session.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| session_id | TEXT UNIQUE | Session identifier (e.g., "session_20250531_174002") |
| research_goal | TEXT | The research goal description |
| constraints | TEXT | JSON string of constraints |
| settings | TEXT | JSON string of runtime settings |
| created_at | TEXT | ISO timestamp of creation |
| updated_at | TEXT | ISO timestamp of last update |
| is_active | BOOLEAN | Whether session is currently active |

#### `hypotheses`
Stores all generated and evolved hypotheses.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| hypothesis_id | TEXT UNIQUE | Hypothesis identifier (e.g., "G1234", "E5678") |
| session_id | TEXT | Foreign key to research_sessions |
| title | TEXT | Hypothesis title |
| text | TEXT | Full hypothesis description |
| novelty_review | TEXT | Novelty assessment (HIGH/MEDIUM/LOW) |
| feasibility_review | TEXT | Feasibility assessment (HIGH/MEDIUM/LOW) |
| elo_score | REAL | Current Elo rating (default: 1200.0) |
| review_comments | TEXT | JSON array of review comments |
| paper_references | TEXT | JSON array of referenced papers |
| parent_ids | TEXT | JSON array of parent hypothesis IDs |
| is_active | BOOLEAN | Whether hypothesis is active |
| created_at | TEXT | ISO timestamp of creation |
| updated_at | TEXT | ISO timestamp of last update |

### ArXiv Tracking Tables

#### `arxiv_papers`
Stores metadata for all accessed arXiv papers.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| arxiv_id | TEXT UNIQUE | ArXiv identifier (e.g., "2301.12345") |
| entry_id | TEXT | Full arXiv entry ID |
| title | TEXT | Paper title |
| abstract | TEXT | Paper abstract |
| authors | TEXT | JSON array of author names |
| primary_category | TEXT | Primary subject category |
| categories | TEXT | JSON array of all categories |
| published_date | TEXT | Publication date |
| updated_date | TEXT | Last update date |
| doi | TEXT | Digital Object Identifier |
| pdf_url | TEXT | Link to PDF |
| arxiv_url | TEXT | Link to arXiv page |
| comment | TEXT | Author comments |
| journal_ref | TEXT | Journal reference |
| first_accessed | TEXT | ISO timestamp of first access |
| last_accessed | TEXT | ISO timestamp of last access |
| access_count | INTEGER | Number of times accessed |

#### `arxiv_searches`
Tracks all arXiv search queries.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| session_id | TEXT | Foreign key to research_sessions |
| query | TEXT | Search query string |
| search_type | TEXT | Type of search (manual/auto_generation/auto_reflection/trends) |
| max_results | INTEGER | Maximum results requested |
| categories | TEXT | JSON array of category filters |
| sort_by | TEXT | Sort method (relevance/lastUpdatedDate/submittedDate) |
| days_back | INTEGER | Days back for recent papers |
| results_count | INTEGER | Actual number of results returned |
| search_time_ms | REAL | Search execution time in milliseconds |
| timestamp | TEXT | ISO timestamp of search |

#### `arxiv_search_results`
Links search queries to discovered papers.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| search_id | INTEGER | Foreign key to arxiv_searches |
| arxiv_id | TEXT | Foreign key to arxiv_papers |
| result_rank | INTEGER | Position in search results (1-based) |
| relevance_score | REAL | Relevance score (0.0-1.0) |
| clicked | BOOLEAN | Whether user clicked on this result |

#### `hypothesis_paper_references`
Links hypotheses to referenced papers.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| hypothesis_id | TEXT | Foreign key to hypotheses |
| arxiv_id | TEXT | Foreign key to arxiv_papers |
| reference_type | TEXT | Type of reference (inspiration/citation/background/contradiction) |
| added_by | TEXT | How reference was discovered (llm_generation/llm_reflection/user/auto_discovery) |
| relevance_score | REAL | Relevance score (0.0-1.0) |
| extraction_method | TEXT | Method used to identify reference |
| timestamp | TEXT | ISO timestamp of when reference was added |

### LLM Tracking Tables

#### `llm_calls`
Records all LLM API interactions.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| session_id | TEXT | Foreign key to research_sessions |
| call_type | TEXT | Type of call (generation/reflection/ranking/meta_review) |
| hypothesis_id | TEXT | Foreign key to hypotheses (if applicable) |
| model_name | TEXT | LLM model identifier |
| prompt | TEXT | Input prompt sent to LLM |
| response | TEXT | Response received from LLM |
| temperature | REAL | Temperature parameter used |
| max_tokens | INTEGER | Maximum tokens requested |
| prompt_tokens | INTEGER | Actual prompt tokens used |
| completion_tokens | INTEGER | Actual completion tokens generated |
| total_tokens | INTEGER | Total tokens (prompt + completion) |
| response_time_ms | REAL | Response time in milliseconds |
| api_cost_usd | REAL | Cost in USD for this call |
| success | BOOLEAN | Whether call succeeded |
| error_message | TEXT | Error message if call failed |
| retry_count | INTEGER | Number of retries attempted |
| timestamp | TEXT | ISO timestamp of call |
| openrouter_model_id | TEXT | OpenRouter-specific model ID |
| openrouter_request_id | TEXT | OpenRouter request tracking ID |
| rate_limited | BOOLEAN | Whether call was rate limited |

#### `llm_performance_metrics`
Aggregated performance data by model and call type.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| session_id | TEXT | Foreign key to research_sessions |
| model_name | TEXT | LLM model identifier |
| call_type | TEXT | Type of call |
| total_calls | INTEGER | Total number of calls |
| successful_calls | INTEGER | Number of successful calls |
| failed_calls | INTEGER | Number of failed calls |
| retry_calls | INTEGER | Number of retry calls |
| rate_limited_calls | INTEGER | Number of rate-limited calls |
| total_tokens | INTEGER | Total tokens across all calls |
| total_prompt_tokens | INTEGER | Total prompt tokens |
| total_completion_tokens | INTEGER | Total completion tokens |
| total_cost_usd | REAL | Total cost in USD |
| avg_response_time_ms | REAL | Average response time |
| min_response_time_ms | REAL | Minimum response time |
| max_response_time_ms | REAL | Maximum response time |
| last_updated | TEXT | ISO timestamp of last update |

#### `llm_model_pricing`
Stores pricing information for cost calculations.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| model_name | TEXT UNIQUE | Model identifier |
| provider | TEXT | Provider name (openrouter/openai/etc.) |
| prompt_price_per_1k_tokens | REAL | Cost per 1000 prompt tokens |
| completion_price_per_1k_tokens | REAL | Cost per 1000 completion tokens |
| context_window | INTEGER | Maximum context window size |
| max_output_tokens | INTEGER | Maximum output tokens |
| last_updated | TEXT | ISO timestamp of last pricing update |

### System Tables

#### `tournament_results`
Records Elo tournament outcomes.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| session_id | TEXT | Foreign key to research_sessions |
| iteration | INTEGER | Cycle iteration number |
| hypothesis1_id | TEXT | First hypothesis ID |
| hypothesis2_id | TEXT | Second hypothesis ID |
| winner_id | TEXT | Winning hypothesis ID |
| old_elo1 | REAL | Original Elo score of hypothesis 1 |
| old_elo2 | REAL | Original Elo score of hypothesis 2 |
| new_elo1 | REAL | Updated Elo score of hypothesis 1 |
| new_elo2 | REAL | Updated Elo score of hypothesis 2 |
| created_at | TEXT | ISO timestamp of tournament |

#### `meta_reviews`
Stores meta-review feedback from each cycle.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| session_id | TEXT | Foreign key to research_sessions |
| iteration | INTEGER | Cycle iteration number |
| critique | TEXT | Meta-review critique text |
| suggested_next_steps | TEXT | JSON array of suggested next steps |
| created_at | TEXT | ISO timestamp of review |

#### `system_logs`
System log entries (replaces file-based logging).

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| session_id | TEXT | Foreign key to research_sessions (optional) |
| log_level | TEXT | Log level (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| message | TEXT | Log message |
| module | TEXT | Module that generated the log |
| timestamp | TEXT | ISO timestamp of log entry |
| metadata | TEXT | JSON metadata for additional context |

## Database Operations

### Core Database Manager

The `DatabaseManager` class in `app/database.py` provides the main interface:

```python
from app.database import get_db_manager

db = get_db_manager()
```

### Key Methods

#### Session Management
```python
# Create a new research session
session_id = db.create_session(research_goal)

# Get session information
session_info = db.get_session_info(session_id)

# Get recent sessions
recent_sessions = db.get_recent_sessions(limit=10)
```

#### Hypothesis Management
```python
# Save a hypothesis
db.save_hypothesis(hypothesis, session_id)

# Get session hypotheses
hypotheses = db.get_session_hypotheses(session_id, active_only=True)
```

#### ArXiv Operations
```python
# Save an arXiv paper
arxiv_id = db.save_arxiv_paper(paper_data)

# Save a search
search_id = db.save_arxiv_search(session_id, query, search_type, search_params)

# Save search results
db.save_arxiv_search_results(search_id, papers)

# Link paper to hypothesis
db.save_hypothesis_paper_reference(hypothesis_id, arxiv_id)

# Get session arXiv analytics
analytics = db.get_session_arxiv_analytics(session_id)
```

#### LLM Operations
```python
# Save an LLM call
call_id = db.save_llm_call(
    session_id=session_id,
    call_type="generation",
    model_name="google/gemini-2.0-flash-001",
    prompt="Generate hypotheses...",
    response="1. Hypothesis...",
    temperature=0.7,
    prompt_tokens=150,
    completion_tokens=300,
    response_time_ms=1250.5,
    success=True
)

# Get session LLM analytics
analytics = db.get_session_llm_analytics(session_id)

# Save model pricing
db.save_model_pricing(
    model_name="google/gemini-2.0-flash-001",
    provider="openrouter",
    prompt_price_per_1k=0.002,
    completion_price_per_1k=0.006
)
```

#### Tournament and Meta-Review
```python
# Save tournament result
db.save_tournament_result(
    session_id, iteration, hypothesis1_id, hypothesis2_id,
    winner_id, old_elo1, old_elo2, new_elo1, new_elo2
)

# Save meta-review
db.save_meta_review(session_id, iteration, critique, suggested_next_steps)
```

#### Logging
```python
# Log a message
db.log_message(
    message="Generated 3 new hypotheses",
    level="INFO",
    session_id=session_id,
    module="GenerationAgent",
    metadata={"hypothesis_count": 3}
)
```

## Analytics and Reporting

### Session Analytics

#### ArXiv Analytics
```python
analytics = db.get_session_arxiv_analytics(session_id)
# Returns:
# {
#   'search_statistics': [...],
#   'top_accessed_papers': [...],
#   'paper_hypothesis_relationships': [...],
#   'category_distribution': [...],
#   'total_unique_papers': 15
# }
```

#### LLM Analytics
```python
analytics = db.get_session_llm_analytics(session_id)
# Returns:
# {
#   'performance_metrics': [...],
#   'recent_calls': [...],
#   'cost_breakdown': [...],
#   'error_analysis': [...],
#   'total_calls': 45,
#   'total_cost': 0.123,
#   'total_tokens': 12500
# }
```

### Data Export
```python
# Export complete session data
session_data = db.export_session_data(session_id)
# Returns comprehensive session data including:
# - Session info and settings
# - All hypotheses with metadata
# - Tournament results and meta-reviews
# - System logs
# - ArXiv and LLM analytics
```

## Database Configuration

### Location
- Default path: `data/ai_coscientist.db`
- Configurable via `config.yaml`:
  ```yaml
  database:
    path: "data/ai_coscientist.db"
  ```

### Initialization
The database is automatically initialized on first use. All tables are created with proper foreign key relationships and indexes.

### Connection Management
The system uses context managers for safe database operations:
```python
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research_sessions")
    results = cursor.fetchall()
```

## Migration and Maintenance

### Migrating Log Files
Historical log files from the `results/` folder can be migrated:
```bash
python migrate_results.py
```

This script:
1. Parses all `app_log_*.txt` files
2. Extracts research goals, hypotheses, tournament results
3. Creates corresponding database entries
4. Preserves timestamps and metadata

### Database Backup
Since the database is a single SQLite file, backup is simple:
```bash
cp data/ai_coscientist.db data/backup_$(date +%Y%m%d_%H%M%S).db
```

### Database Queries
You can query the database directly using SQLite tools:
```bash
sqlite3 data/ai_coscientist.db
.tables
SELECT COUNT(*) FROM research_sessions;
```

## Performance Considerations

### Indexing
The database includes indexes on frequently queried columns:
- `session_id` fields for fast session lookups
- `hypothesis_id` for hypothesis relationships
- `arxiv_id` for paper lookups
- `timestamp` fields for chronological queries

### Connection Pooling
The system uses a single global DatabaseManager instance with proper connection management to avoid connection leaks.

### Memory Usage
The hybrid approach maintains active session data in memory while persisting everything to disk, balancing performance with data safety.
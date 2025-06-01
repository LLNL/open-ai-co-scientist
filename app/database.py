import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager
import os

try:
    from .models import Hypothesis, ResearchGoal
    from .config import config
except ImportError:
    # Handle case when imported directly
    from models import Hypothesis, ResearchGoal
    from config import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = config.get('database', {}).get('path', 'data/ai_coscientist.db')
        self.db_path = db_path
        
        # Ensure database directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Research sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS research_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    research_goal TEXT NOT NULL,
                    constraints TEXT,  -- JSON
                    settings TEXT,     -- JSON (llm_model, temperatures, etc.)
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            # Hypotheses table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hypotheses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hypothesis_id TEXT UNIQUE NOT NULL,
                    session_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    novelty_review TEXT,
                    feasibility_review TEXT,
                    elo_score REAL DEFAULT 1200.0,
                    review_comments TEXT,  -- JSON array
                    paper_references TEXT,       -- JSON array
                    parent_ids TEXT,       -- JSON array
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES research_sessions (session_id)
                )
            ''')
            
            # Tournament results table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tournament_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    iteration INTEGER NOT NULL,
                    hypothesis1_id TEXT NOT NULL,
                    hypothesis2_id TEXT NOT NULL,
                    winner_id TEXT NOT NULL,
                    old_elo1 REAL NOT NULL,
                    old_elo2 REAL NOT NULL,
                    new_elo1 REAL NOT NULL,
                    new_elo2 REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES research_sessions (session_id),
                    FOREIGN KEY (hypothesis1_id) REFERENCES hypotheses (hypothesis_id),
                    FOREIGN KEY (hypothesis2_id) REFERENCES hypotheses (hypothesis_id),
                    FOREIGN KEY (winner_id) REFERENCES hypotheses (hypothesis_id)
                )
            ''')
            
            # Meta-review feedback table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS meta_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    iteration INTEGER NOT NULL,
                    critique TEXT NOT NULL,
                    suggested_next_steps TEXT,  -- JSON array
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES research_sessions (session_id)
                )
            ''')
            
            # System logs table (to replace results folder)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    log_level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    module TEXT,
                    timestamp TEXT NOT NULL,
                    metadata TEXT  -- JSON for additional context
                )
            ''')
            
            # arXiv papers table - stores accessed papers
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS arxiv_papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    arxiv_id TEXT UNIQUE NOT NULL,
                    entry_id TEXT,
                    title TEXT NOT NULL,
                    abstract TEXT,
                    authors TEXT,  -- JSON array
                    primary_category TEXT,
                    categories TEXT,  -- JSON array
                    published_date TEXT,
                    updated_date TEXT,
                    doi TEXT,
                    pdf_url TEXT,
                    arxiv_url TEXT,
                    comment TEXT,
                    journal_ref TEXT,
                    first_accessed TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    access_count INTEGER DEFAULT 1
                )
            ''')
            
            # arXiv searches table - tracks search queries
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS arxiv_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    query TEXT NOT NULL,
                    search_type TEXT,  -- 'manual', 'auto_generation', 'auto_reflection', 'trends'
                    max_results INTEGER,
                    categories TEXT,  -- JSON array
                    sort_by TEXT,
                    days_back INTEGER,
                    results_count INTEGER,
                    search_time_ms REAL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES research_sessions (session_id)
                )
            ''')
            
            # Hypothesis-paper relationships table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hypothesis_paper_references (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hypothesis_id TEXT NOT NULL,
                    arxiv_id TEXT NOT NULL,
                    reference_type TEXT,  -- 'inspiration', 'citation', 'background', 'contradiction'
                    added_by TEXT,  -- 'llm_generation', 'llm_reflection', 'user', 'auto_discovery'
                    relevance_score REAL,  -- 0.0 to 1.0
                    extraction_method TEXT,  -- how the reference was identified
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (hypothesis_id) REFERENCES hypotheses (hypothesis_id),
                    FOREIGN KEY (arxiv_id) REFERENCES arxiv_papers (arxiv_id)
                )
            ''')
            
            # arXiv search results table - links searches to papers found
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS arxiv_search_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_id INTEGER NOT NULL,
                    arxiv_id TEXT NOT NULL,
                    result_rank INTEGER,  -- position in search results
                    relevance_score REAL,
                    clicked BOOLEAN DEFAULT 0,
                    FOREIGN KEY (search_id) REFERENCES arxiv_searches (id),
                    FOREIGN KEY (arxiv_id) REFERENCES arxiv_papers (arxiv_id)
                )
            ''')
            
            # LLM calls table - tracks all LLM API interactions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS llm_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    call_type TEXT NOT NULL,  -- 'generation', 'reflection', 'ranking', 'meta_review'
                    hypothesis_id TEXT,  -- if call is related to specific hypothesis
                    model_name TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    response TEXT,
                    temperature REAL,
                    max_tokens INTEGER,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    response_time_ms REAL,
                    api_cost_usd REAL,
                    success BOOLEAN DEFAULT 1,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    timestamp TEXT NOT NULL,
                    openrouter_model_id TEXT,
                    openrouter_request_id TEXT,
                    rate_limited BOOLEAN DEFAULT 0,
                    FOREIGN KEY (session_id) REFERENCES research_sessions (session_id),
                    FOREIGN KEY (hypothesis_id) REFERENCES hypotheses (hypothesis_id)
                )
            ''')
            
            # LLM performance metrics table - aggregated performance data
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS llm_performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    model_name TEXT NOT NULL,
                    call_type TEXT NOT NULL,
                    total_calls INTEGER DEFAULT 0,
                    successful_calls INTEGER DEFAULT 0,
                    failed_calls INTEGER DEFAULT 0,
                    retry_calls INTEGER DEFAULT 0,
                    rate_limited_calls INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    total_prompt_tokens INTEGER DEFAULT 0,
                    total_completion_tokens INTEGER DEFAULT 0,
                    total_cost_usd REAL DEFAULT 0.0,
                    avg_response_time_ms REAL DEFAULT 0.0,
                    min_response_time_ms REAL,
                    max_response_time_ms REAL,
                    last_updated TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES research_sessions (session_id)
                )
            ''')
            
            # LLM model pricing table - for cost calculations
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS llm_model_pricing (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT UNIQUE NOT NULL,
                    provider TEXT NOT NULL,  -- 'openrouter', 'openai', etc.
                    prompt_price_per_1k_tokens REAL NOT NULL,
                    completion_price_per_1k_tokens REAL NOT NULL,
                    context_window INTEGER,
                    max_output_tokens INTEGER,
                    last_updated TEXT NOT NULL
                )
            ''')
            
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
    
    def create_session(self, research_goal: ResearchGoal) -> str:
        """Create a new research session"""
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.now().isoformat()
        
        settings = {
            'llm_model': research_goal.llm_model,
            'num_hypotheses': research_goal.num_hypotheses,
            'generation_temperature': research_goal.generation_temperature,
            'reflection_temperature': research_goal.reflection_temperature,
            'elo_k_factor': research_goal.elo_k_factor,
            'top_k_hypotheses': research_goal.top_k_hypotheses
        }
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO research_sessions 
                (session_id, research_goal, constraints, settings, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                research_goal.description,
                json.dumps(research_goal.constraints),
                json.dumps(settings),
                timestamp,
                timestamp
            ))
            conn.commit()
        
        logger.info(f"Created research session: {session_id}")
        return session_id
    
    def save_hypothesis(self, hypothesis: Hypothesis, session_id: str):
        """Save or update a hypothesis"""
        timestamp = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if hypothesis exists
            cursor.execute('SELECT id FROM hypotheses WHERE hypothesis_id = ?', (hypothesis.hypothesis_id,))
            exists = cursor.fetchone()
            
            if exists:
                # Update existing
                cursor.execute('''
                    UPDATE hypotheses SET
                        title = ?, text = ?, novelty_review = ?, feasibility_review = ?,
                        elo_score = ?, review_comments = ?, paper_references = ?, parent_ids = ?,
                        is_active = ?, updated_at = ?
                    WHERE hypothesis_id = ?
                ''', (
                    hypothesis.title, hypothesis.text, hypothesis.novelty_review,
                    hypothesis.feasibility_review, hypothesis.elo_score,
                    json.dumps(hypothesis.review_comments), json.dumps(hypothesis.references),
                    json.dumps(hypothesis.parent_ids), hypothesis.is_active,
                    timestamp, hypothesis.hypothesis_id
                ))
            else:
                # Insert new
                cursor.execute('''
                    INSERT INTO hypotheses 
                    (hypothesis_id, session_id, title, text, novelty_review, feasibility_review,
                     elo_score, review_comments, paper_references, parent_ids, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    hypothesis.hypothesis_id, session_id, hypothesis.title, hypothesis.text,
                    hypothesis.novelty_review, hypothesis.feasibility_review, hypothesis.elo_score,
                    json.dumps(hypothesis.review_comments), json.dumps(hypothesis.references),
                    json.dumps(hypothesis.parent_ids), hypothesis.is_active,
                    timestamp, timestamp
                ))
            
            conn.commit()
    
    def get_session_hypotheses(self, session_id: str, active_only: bool = True) -> List[Hypothesis]:
        """Retrieve hypotheses for a session"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM hypotheses WHERE session_id = ?'
            params = [session_id]
            
            if active_only:
                query += ' AND is_active = 1'
            
            query += ' ORDER BY created_at DESC'
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            hypotheses = []
            for row in rows:
                hypothesis = Hypothesis(
                    hypothesis_id=row['hypothesis_id'],
                    title=row['title'],
                    text=row['text']
                )
                hypothesis.novelty_review = row['novelty_review']
                hypothesis.feasibility_review = row['feasibility_review']
                hypothesis.elo_score = row['elo_score']
                hypothesis.review_comments = json.loads(row['review_comments'] or '[]')
                hypothesis.references = json.loads(row['paper_references'] or '[]')
                hypothesis.parent_ids = json.loads(row['parent_ids'] or '[]')
                hypothesis.is_active = bool(row['is_active'])
                hypotheses.append(hypothesis)
            
            return hypotheses
    
    def save_tournament_result(self, session_id: str, iteration: int, 
                             hypothesis1_id: str, hypothesis2_id: str, winner_id: str,
                             old_elo1: float, old_elo2: float, new_elo1: float, new_elo2: float):
        """Save tournament result"""
        timestamp = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tournament_results 
                (session_id, iteration, hypothesis1_id, hypothesis2_id, winner_id,
                 old_elo1, old_elo2, new_elo1, new_elo2, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, iteration, hypothesis1_id, hypothesis2_id, winner_id,
                old_elo1, old_elo2, new_elo1, new_elo2, timestamp
            ))
            conn.commit()
    
    def save_meta_review(self, session_id: str, iteration: int, critique: str, 
                        suggested_next_steps: List[str]):
        """Save meta-review feedback"""
        timestamp = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO meta_reviews 
                (session_id, iteration, critique, suggested_next_steps, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                session_id, iteration, critique, json.dumps(suggested_next_steps), timestamp
            ))
            conn.commit()
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get session information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM research_sessions WHERE session_id = ?', (session_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'session_id': row['session_id'],
                    'research_goal': row['research_goal'],
                    'constraints': json.loads(row['constraints'] or '{}'),
                    'settings': json.loads(row['settings'] or '{}'),
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'is_active': bool(row['is_active'])
                }
            return None
    
    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """Get recent research sessions"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT session_id, research_goal, created_at, is_active
                FROM research_sessions 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def log_message(self, message: str, level: str = "INFO", session_id: str = None, 
                   module: str = None, metadata: Dict = None):
        """Log a message to the database (replaces file logging)"""
        timestamp = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO system_logs 
                (session_id, log_level, message, module, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session_id, level, message, module, timestamp,
                json.dumps(metadata) if metadata else None
            ))
            conn.commit()
    
    def save_arxiv_paper(self, paper_data: Dict) -> str:
        """Save or update an arXiv paper record"""
        timestamp = datetime.now().isoformat()
        arxiv_id = paper_data['arxiv_id']
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if paper exists
            cursor.execute('SELECT access_count FROM arxiv_papers WHERE arxiv_id = ?', (arxiv_id,))
            existing = cursor.fetchone()
            
            if existing:
                # Update access count and last accessed time
                cursor.execute('''
                    UPDATE arxiv_papers SET
                        last_accessed = ?, access_count = access_count + 1
                    WHERE arxiv_id = ?
                ''', (timestamp, arxiv_id))
            else:
                # Insert new paper
                cursor.execute('''
                    INSERT INTO arxiv_papers 
                    (arxiv_id, entry_id, title, abstract, authors, primary_category, categories,
                     published_date, updated_date, doi, pdf_url, arxiv_url, comment, journal_ref,
                     first_accessed, last_accessed, access_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    arxiv_id, paper_data.get('entry_id'), paper_data['title'], 
                    paper_data.get('abstract'), json.dumps(paper_data.get('authors', [])),
                    paper_data.get('primary_category'), json.dumps(paper_data.get('categories', [])),
                    paper_data.get('published'), paper_data.get('updated'),
                    paper_data.get('doi'), paper_data.get('pdf_url'), paper_data.get('arxiv_url'),
                    paper_data.get('comment'), paper_data.get('journal_ref'),
                    timestamp, timestamp, 1
                ))
            
            conn.commit()
        
        return arxiv_id
    
    def save_arxiv_search(self, session_id: str, query: str, search_type: str = "manual",
                         search_params: Dict = None, results_count: int = 0, 
                         search_time_ms: float = None) -> int:
        """Save an arXiv search record"""
        timestamp = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO arxiv_searches 
                (session_id, query, search_type, max_results, categories, sort_by, 
                 days_back, results_count, search_time_ms, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, query, search_type,
                search_params.get('max_results') if search_params else None,
                json.dumps(search_params.get('categories', [])) if search_params else None,
                search_params.get('sort_by') if search_params else None,
                search_params.get('days_back') if search_params else None,
                results_count, search_time_ms, timestamp
            ))
            
            search_id = cursor.lastrowid
            conn.commit()
        
        return search_id
    
    def save_arxiv_search_results(self, search_id: int, papers: List[Dict]):
        """Save papers found in a search"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for rank, paper in enumerate(papers, 1):
                arxiv_id = self.save_arxiv_paper(paper)
                
                cursor.execute('''
                    INSERT INTO arxiv_search_results 
                    (search_id, arxiv_id, result_rank, relevance_score)
                    VALUES (?, ?, ?, ?)
                ''', (search_id, arxiv_id, rank, paper.get('relevance_score', 0.0)))
            
            conn.commit()
    
    def save_hypothesis_paper_reference(self, hypothesis_id: str, arxiv_id: str, 
                                      reference_type: str = "citation", added_by: str = "llm_reflection",
                                      relevance_score: float = None, extraction_method: str = None):
        """Link a paper to a hypothesis"""
        timestamp = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if relationship already exists
            cursor.execute('''
                SELECT id FROM hypothesis_paper_references 
                WHERE hypothesis_id = ? AND arxiv_id = ?
            ''', (hypothesis_id, arxiv_id))
            
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO hypothesis_paper_references 
                    (hypothesis_id, arxiv_id, reference_type, added_by, relevance_score, 
                     extraction_method, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (hypothesis_id, arxiv_id, reference_type, added_by, relevance_score, 
                      extraction_method, timestamp))
                
                conn.commit()
    
    def get_session_arxiv_analytics(self, session_id: str) -> Dict:
        """Get arXiv usage analytics for a session"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get search statistics
            cursor.execute('''
                SELECT COUNT(*) as search_count, 
                       SUM(results_count) as total_papers_found,
                       AVG(search_time_ms) as avg_search_time,
                       search_type
                FROM arxiv_searches 
                WHERE session_id = ?
                GROUP BY search_type
            ''', (session_id,))
            search_stats = [dict(row) for row in cursor.fetchall()]
            
            # Get most accessed papers
            cursor.execute('''
                SELECT ap.arxiv_id, ap.title, ap.authors, ap.access_count,
                       ap.primary_category, ap.published_date
                FROM arxiv_papers ap
                JOIN arxiv_search_results asr ON ap.arxiv_id = asr.arxiv_id
                JOIN arxiv_searches as_tbl ON asr.search_id = as_tbl.id
                WHERE as_tbl.session_id = ?
                ORDER BY ap.access_count DESC
                LIMIT 10
            ''', (session_id,))
            top_papers = [dict(row) for row in cursor.fetchall()]
            
            # Get hypothesis-paper relationships
            cursor.execute('''
                SELECT hpr.hypothesis_id, hpr.arxiv_id, hpr.reference_type, 
                       hpr.added_by, ap.title, h.title as hypothesis_title
                FROM hypothesis_paper_references hpr
                JOIN arxiv_papers ap ON hpr.arxiv_id = ap.arxiv_id
                JOIN hypotheses h ON hpr.hypothesis_id = h.hypothesis_id
                WHERE h.session_id = ?
                ORDER BY hpr.timestamp DESC
            ''', (session_id,))
            paper_relationships = [dict(row) for row in cursor.fetchall()]
            
            # Get category distribution
            cursor.execute('''
                SELECT ap.primary_category, COUNT(*) as count
                FROM arxiv_papers ap
                JOIN arxiv_search_results asr ON ap.arxiv_id = asr.arxiv_id
                JOIN arxiv_searches as_tbl ON asr.search_id = as_tbl.id
                WHERE as_tbl.session_id = ?
                GROUP BY ap.primary_category
                ORDER BY count DESC
            ''', (session_id,))
            category_distribution = [dict(row) for row in cursor.fetchall()]
            
            return {
                'search_statistics': search_stats,
                'top_accessed_papers': top_papers,
                'paper_hypothesis_relationships': paper_relationships,
                'category_distribution': category_distribution,
                'total_unique_papers': len(top_papers)
            }
    
    def save_llm_call(self, session_id: str, call_type: str, model_name: str, 
                     prompt: str, response: str = None, temperature: float = None,
                     prompt_tokens: int = None, completion_tokens: int = None,
                     response_time_ms: float = None, success: bool = True,
                     error_message: str = None, retry_count: int = 0,
                     hypothesis_id: str = None, **kwargs) -> int:
        """Save an LLM API call record"""
        timestamp = datetime.now().isoformat()
        
        # Calculate total tokens and cost
        total_tokens = None
        if prompt_tokens and completion_tokens:
            total_tokens = prompt_tokens + completion_tokens
        
        api_cost_usd = self._calculate_api_cost(model_name, prompt_tokens, completion_tokens)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO llm_calls 
                (session_id, call_type, hypothesis_id, model_name, prompt, response,
                 temperature, prompt_tokens, completion_tokens, total_tokens,
                 response_time_ms, api_cost_usd, success, error_message, retry_count,
                 timestamp, openrouter_model_id, openrouter_request_id, rate_limited)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, call_type, hypothesis_id, model_name, prompt, response,
                temperature, prompt_tokens, completion_tokens, total_tokens,
                response_time_ms, api_cost_usd, success, error_message, retry_count,
                timestamp, kwargs.get('openrouter_model_id'), 
                kwargs.get('openrouter_request_id'), 
                kwargs.get('rate_limited', False)
            ))
            
            call_id = cursor.lastrowid
            conn.commit()
        
        # Update performance metrics
        self._update_performance_metrics(session_id, model_name, call_type, 
                                       success, retry_count > 0, 
                                       kwargs.get('rate_limited', False),
                                       total_tokens or 0, prompt_tokens or 0, 
                                       completion_tokens or 0, api_cost_usd or 0.0,
                                       response_time_ms or 0.0)
        
        return call_id
    
    def _calculate_api_cost(self, model_name: str, prompt_tokens: int = None, 
                          completion_tokens: int = None) -> float:
        """Calculate API cost based on model pricing"""
        if not prompt_tokens or not completion_tokens:
            return 0.0
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT prompt_price_per_1k_tokens, completion_price_per_1k_tokens
                FROM llm_model_pricing WHERE model_name = ?
            ''', (model_name,))
            
            pricing = cursor.fetchone()
            if pricing:
                prompt_cost = (prompt_tokens / 1000.0) * pricing[0]
                completion_cost = (completion_tokens / 1000.0) * pricing[1]
                return prompt_cost + completion_cost
        
        return 0.0
    
    def _update_performance_metrics(self, session_id: str, model_name: str, call_type: str,
                                  success: bool, was_retry: bool, was_rate_limited: bool,
                                  total_tokens: int, prompt_tokens: int, completion_tokens: int,
                                  cost_usd: float, response_time_ms: float):
        """Update aggregated performance metrics"""
        timestamp = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if metrics record exists
            cursor.execute('''
                SELECT id, total_calls, successful_calls, failed_calls, retry_calls,
                       rate_limited_calls, total_tokens, total_prompt_tokens,
                       total_completion_tokens, total_cost_usd, avg_response_time_ms,
                       min_response_time_ms, max_response_time_ms
                FROM llm_performance_metrics 
                WHERE session_id = ? AND model_name = ? AND call_type = ?
            ''', (session_id, model_name, call_type))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing metrics
                record_id = existing[0]
                total_calls = existing[1] + 1
                successful_calls = existing[2] + (1 if success else 0)
                failed_calls = existing[3] + (0 if success else 1)
                retry_calls = existing[4] + (1 if was_retry else 0)
                rate_limited_calls = existing[5] + (1 if was_rate_limited else 0)
                
                new_total_tokens = existing[6] + total_tokens
                new_total_prompt_tokens = existing[7] + prompt_tokens
                new_total_completion_tokens = existing[8] + completion_tokens
                new_total_cost = existing[9] + cost_usd
                
                # Calculate new average response time
                old_avg = existing[10] or 0.0
                new_avg = ((old_avg * (total_calls - 1)) + response_time_ms) / total_calls
                
                # Update min/max response times
                min_time = existing[11]
                max_time = existing[12]
                if min_time is None or response_time_ms < min_time:
                    min_time = response_time_ms
                if max_time is None or response_time_ms > max_time:
                    max_time = response_time_ms
                
                cursor.execute('''
                    UPDATE llm_performance_metrics SET
                        total_calls = ?, successful_calls = ?, failed_calls = ?,
                        retry_calls = ?, rate_limited_calls = ?, total_tokens = ?,
                        total_prompt_tokens = ?, total_completion_tokens = ?,
                        total_cost_usd = ?, avg_response_time_ms = ?,
                        min_response_time_ms = ?, max_response_time_ms = ?,
                        last_updated = ?
                    WHERE id = ?
                ''', (total_calls, successful_calls, failed_calls, retry_calls,
                      rate_limited_calls, new_total_tokens, new_total_prompt_tokens,
                      new_total_completion_tokens, new_total_cost, new_avg,
                      min_time, max_time, timestamp, record_id))
            else:
                # Create new metrics record
                cursor.execute('''
                    INSERT INTO llm_performance_metrics
                    (session_id, model_name, call_type, total_calls, successful_calls,
                     failed_calls, retry_calls, rate_limited_calls, total_tokens,
                     total_prompt_tokens, total_completion_tokens, total_cost_usd,
                     avg_response_time_ms, min_response_time_ms, max_response_time_ms,
                     last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (session_id, model_name, call_type, 1, 
                      1 if success else 0, 0 if success else 1,
                      1 if was_retry else 0, 1 if was_rate_limited else 0,
                      total_tokens, prompt_tokens, completion_tokens, cost_usd,
                      response_time_ms, response_time_ms, response_time_ms, timestamp))
            
            conn.commit()
    
    def save_model_pricing(self, model_name: str, provider: str,
                          prompt_price_per_1k: float, completion_price_per_1k: float,
                          context_window: int = None, max_output_tokens: int = None):
        """Save or update model pricing information"""
        timestamp = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO llm_model_pricing
                (model_name, provider, prompt_price_per_1k_tokens, completion_price_per_1k_tokens,
                 context_window, max_output_tokens, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (model_name, provider, prompt_price_per_1k, completion_price_per_1k,
                  context_window, max_output_tokens, timestamp))
            conn.commit()
    
    def get_session_llm_analytics(self, session_id: str) -> Dict:
        """Get LLM usage analytics for a session"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get performance metrics by model and call type
            cursor.execute('''
                SELECT model_name, call_type, total_calls, successful_calls, failed_calls,
                       retry_calls, rate_limited_calls, total_tokens, total_cost_usd,
                       avg_response_time_ms, min_response_time_ms, max_response_time_ms
                FROM llm_performance_metrics 
                WHERE session_id = ?
                ORDER BY model_name, call_type
            ''', (session_id,))
            performance_metrics = [dict(zip([col[0] for col in cursor.description], row)) 
                                 for row in cursor.fetchall()]
            
            # Get recent LLM calls
            cursor.execute('''
                SELECT call_type, model_name, success, response_time_ms, total_tokens,
                       api_cost_usd, timestamp, error_message, retry_count
                FROM llm_calls 
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT 50
            ''', (session_id,))
            recent_calls = [dict(zip([col[0] for col in cursor.description], row)) 
                          for row in cursor.fetchall()]
            
            # Get cost breakdown by model
            cursor.execute('''
                SELECT model_name, SUM(api_cost_usd) as total_cost, 
                       COUNT(*) as call_count, SUM(total_tokens) as total_tokens
                FROM llm_calls 
                WHERE session_id = ? AND success = 1
                GROUP BY model_name
                ORDER BY total_cost DESC
            ''', (session_id,))
            cost_breakdown = [dict(zip([col[0] for col in cursor.description], row)) 
                            for row in cursor.fetchall()]
            
            # Get error analysis
            cursor.execute('''
                SELECT error_message, COUNT(*) as error_count
                FROM llm_calls 
                WHERE session_id = ? AND success = 0
                GROUP BY error_message
                ORDER BY error_count DESC
            ''', (session_id,))
            error_analysis = [dict(zip([col[0] for col in cursor.description], row)) 
                            for row in cursor.fetchall()]
            
            return {
                'performance_metrics': performance_metrics,
                'recent_calls': recent_calls,
                'cost_breakdown': cost_breakdown,
                'error_analysis': error_analysis,
                'total_calls': sum(pm['total_calls'] for pm in performance_metrics),
                'total_cost': sum(cb['total_cost'] for cb in cost_breakdown),
                'total_tokens': sum(cb['total_tokens'] for cb in cost_breakdown)
            }
    
    def export_session_data(self, session_id: str) -> Dict:
        """Export all data for a session"""
        session_info = self.get_session_info(session_id)
        if not session_info:
            return None
        
        hypotheses = self.get_session_hypotheses(session_id, active_only=False)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get tournament results
            cursor.execute('''
                SELECT * FROM tournament_results WHERE session_id = ?
                ORDER BY iteration, created_at
            ''', (session_id,))
            tournaments = [dict(row) for row in cursor.fetchall()]
            
            # Get meta-reviews
            cursor.execute('''
                SELECT * FROM meta_reviews WHERE session_id = ?
                ORDER BY iteration
            ''', (session_id,))
            meta_reviews = [dict(row) for row in cursor.fetchall()]
            
            # Get logs
            cursor.execute('''
                SELECT * FROM system_logs WHERE session_id = ?
                ORDER BY timestamp
            ''', (session_id,))
            logs = [dict(row) for row in cursor.fetchall()]
            
            # Get arXiv data
            arxiv_analytics = self.get_session_arxiv_analytics(session_id)
            
            # Get LLM analytics
            llm_analytics = self.get_session_llm_analytics(session_id)
        
        return {
            'session': session_info,
            'hypotheses': [h.to_dict() for h in hypotheses],
            'tournament_results': tournaments,
            'meta_reviews': meta_reviews,
            'logs': logs,
            'arxiv_analytics': arxiv_analytics,
            'llm_analytics': llm_analytics
        }

# Global database instance
db_manager = None

def get_db_manager() -> DatabaseManager:
    """Get or create the global database manager instance"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager
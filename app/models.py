import logging
from typing import List, Dict, Optional
from pydantic import BaseModel

# Assuming logger is configured elsewhere or passed in if needed within methods
# If models need logging, consider passing a logger instance during initialization
# or using a globally accessible logger configured in utils.py or config.py.
# For simplicity, direct logging calls are removed from models for now.
# logger = logging.getLogger(__name__) # Example if models needed their own logger

###############################################################################
# Data Models
###############################################################################

class Hypothesis:
    def __init__(self, hypothesis_id: str, title: str, text: str):
        self.hypothesis_id = hypothesis_id
        self.title = title
        self.text = text
        self.novelty_review: Optional[str] = None   # "HIGH", "MEDIUM", "LOW"
        self.feasibility_review: Optional[str] = None
        self.elo_score: float = 1200.0      # initial Elo score
        self.review_comments: List[str] = []
        self.references: List[str] = []
        self.is_active: bool = True
        self.parent_ids: List[str] = []  # Store IDs of parent hypotheses

    def to_dict(self) -> dict:
        return {
            "id": self.hypothesis_id,
            "title": self.title,
            "text": self.text,
            "novelty_review": self.novelty_review,
            "feasibility_review": self.feasibility_review,
            "elo_score": self.elo_score,
            "review_comments": self.review_comments,
            "references": self.references,
            "is_active": self.is_active,
            "parent_ids": self.parent_ids,  # Include parent IDs
        }

# Import config to access defaults easily
try:
    from .config import config
except ImportError:
    from config import config

class ResearchGoal:
    def __init__(self,
                 description: str,
                 constraints: Optional[Dict] = None,
                 llm_model: Optional[str] = None,
                 num_hypotheses: Optional[int] = None,
                 generation_temperature: Optional[float] = None,
                 reflection_temperature: Optional[float] = None,
                 elo_k_factor: Optional[int] = None,
                 top_k_hypotheses: Optional[int] = None):
        self.description = description
        self.constraints = constraints if constraints else {}
        # Store runtime settings, falling back to config defaults if not provided
        self.llm_model = llm_model if llm_model else config.get('llm_model', 'google/gemini-flash-1.5') # Example default
        self.num_hypotheses = num_hypotheses if num_hypotheses is not None else config.get('num_hypotheses', 3)
        self.generation_temperature = generation_temperature if generation_temperature is not None else config.get('step_temperatures', {}).get('generation', 0.7)
        self.reflection_temperature = reflection_temperature if reflection_temperature is not None else config.get('step_temperatures', {}).get('reflection', 0.5)
        self.elo_k_factor = elo_k_factor if elo_k_factor is not None else config.get('elo_k_factor', 32)
        self.top_k_hypotheses = top_k_hypotheses if top_k_hypotheses is not None else config.get('top_k_hypotheses', 2)
        
        # Literature context for hypothesis generation
        self.literature_context: List[Dict] = []  # Will be populated with relevant papers


class ContextMemory:
    """
    A hybrid context storage that supports both in-memory and persistent database storage.
    """
    def __init__(self, session_id: str = None, use_database: bool = True):
        self.session_id = session_id
        self.use_database = use_database
        self.hypotheses: Dict[str, Hypothesis] = {}  # key: hypothesis_id
        self.tournament_results: List[Dict] = []
        self.meta_review_feedback: List[Dict] = []
        self.iteration_number: int = 0
        
        if self.use_database:
            from .database import get_db_manager
            self.db_manager = get_db_manager()
            if session_id:
                self._load_session_data()

    def _load_session_data(self):
        """Load session data from database"""
        if not self.use_database or not self.session_id:
            return
        
        hypotheses = self.db_manager.get_session_hypotheses(self.session_id, active_only=False)
        for hypothesis in hypotheses:
            self.hypotheses[hypothesis.hypothesis_id] = hypothesis

    def add_hypothesis(self, hypothesis: Hypothesis):
        self.hypotheses[hypothesis.hypothesis_id] = hypothesis
        
        if self.use_database and self.session_id:
            self.db_manager.save_hypothesis(hypothesis, self.session_id)

    def get_active_hypotheses(self) -> List[Hypothesis]:
        return [h for h in self.hypotheses.values() if h.is_active]
    
    def save_tournament_result(self, hypothesis1_id: str, hypothesis2_id: str, winner_id: str,
                              old_elo1: float, old_elo2: float, new_elo1: float, new_elo2: float):
        """Save tournament result to memory and database"""
        result = {
            'hypothesis1_id': hypothesis1_id,
            'hypothesis2_id': hypothesis2_id,
            'winner_id': winner_id,
            'old_elo1': old_elo1,
            'old_elo2': old_elo2,
            'new_elo1': new_elo1,
            'new_elo2': new_elo2,
            'iteration': self.iteration_number
        }
        self.tournament_results.append(result)
        
        if self.use_database and self.session_id:
            self.db_manager.save_tournament_result(
                self.session_id, self.iteration_number, hypothesis1_id, hypothesis2_id,
                winner_id, old_elo1, old_elo2, new_elo1, new_elo2
            )
    
    def save_meta_review(self, critique: str, suggested_next_steps: List[str]):
        """Save meta-review feedback to memory and database"""
        review = {
            'critique': critique,
            'suggested_next_steps': suggested_next_steps,
            'iteration': self.iteration_number
        }
        self.meta_review_feedback.append(review)
        
        if self.use_database and self.session_id:
            self.db_manager.save_meta_review(
                self.session_id, self.iteration_number, critique, suggested_next_steps
            )


###############################################################################
# Pydantic Schemas for API
###############################################################################

class ResearchGoalRequest(BaseModel):
    description: str
    constraints: Optional[Dict] = {}
    # Add optional fields for advanced settings
    llm_model: Optional[str] = None
    num_hypotheses: Optional[int] = None
    generation_temperature: Optional[float] = None
    reflection_temperature: Optional[float] = None
    elo_k_factor: Optional[int] = None
    top_k_hypotheses: Optional[int] = None


class HypothesisResponse(BaseModel):
    id: str
    title: str
    text: str
    novelty_review: Optional[str]
    feasibility_review: Optional[str]
    elo_score: float
    review_comments: List[str]
    references: List[str]
    is_active: bool
    # parent_ids: List[str] # Add if needed in API response

class OverviewResponse(BaseModel):
    iteration: int
    meta_review_critique: List[str]
    top_hypotheses: List[HypothesisResponse]
    suggested_next_steps: List[str]

###############################################################################
# ArXiv Search Models
###############################################################################

class ArxivSearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 10
    categories: Optional[List[str]] = None
    sort_by: Optional[str] = "relevance"  # relevance, lastUpdatedDate, submittedDate
    days_back: Optional[int] = None  # For recent papers search

class ArxivPaper(BaseModel):
    arxiv_id: str
    entry_id: str
    title: str
    abstract: str
    authors: List[str]
    primary_category: str
    categories: List[str]
    published: Optional[str]
    updated: Optional[str]
    doi: Optional[str]
    pdf_url: str
    arxiv_url: str
    comment: Optional[str]
    journal_ref: Optional[str]
    source: str = "arxiv"

class ArxivSearchResponse(BaseModel):
    query: str
    total_results: int
    papers: List[ArxivPaper]
    search_time_ms: Optional[float]

class ArxivTrendsResponse(BaseModel):
    query: str
    total_papers: int
    date_range: str
    top_categories: List[tuple]
    top_authors: List[tuple]
    papers: List[ArxivPaper]

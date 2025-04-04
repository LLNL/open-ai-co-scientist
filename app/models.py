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

class ResearchGoal:
    def __init__(self, description: str, constraints: Dict = None):
        self.description = description
        self.constraints = constraints if constraints else {}

class ContextMemory:
    """
    A simple in-memory context storage.
    """
    def __init__(self):
        self.hypotheses: Dict[str, Hypothesis] = {}  # key: hypothesis_id
        self.tournament_results: List[Dict] = []
        self.meta_review_feedback: List[Dict] = []
        self.iteration_number: int = 0

    def add_hypothesis(self, hypothesis: Hypothesis):
        self.hypotheses[hypothesis.hypothesis_id] = hypothesis
        # Consider moving logging out of the model if possible
        # logger.info(f"Added hypothesis {hypothesis.hypothesis_id}")

    def get_active_hypotheses(self) -> List[Hypothesis]:
        return [h for h in self.hypotheses.values() if h.is_active]


###############################################################################
# Pydantic Schemas for API
###############################################################################

class ResearchGoalRequest(BaseModel):
    description: str
    constraints: Optional[Dict] = {}

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

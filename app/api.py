import datetime
import json
import logging
import os
import requests # Import requests
from typing import List, Optional, Dict

from fastapi import FastAPI, HTTPException, responses
from fastapi.staticfiles import StaticFiles

# Import components from other modules in the package
from .models import (
    ContextMemory, ResearchGoal, ResearchGoalRequest,
    HypothesisResponse, Hypothesis, # Hypothesis needed by ContextMemory
    ArxivSearchRequest, ArxivSearchResponse, ArxivPaper, ArxivTrendsResponse
)
from .agents import SupervisorAgent
from .utils import logger # Use the configured logger
from .tools.arxiv_search import ArxivSearchTool, get_categories_for_field
from .data_migration import migrate_results_folder
from .config import config

###############################################################################
# FastAPI Application Setup
###############################################################################

app = FastAPI(title="AI Co-Scientist - Hypothesis Evolution System", version="1.0")

# --- Global State (Consider alternatives for production) ---
global_context = ContextMemory()
supervisor = SupervisorAgent()
current_research_goal: Optional[ResearchGoal] = None
current_session_id: Optional[str] = None
available_models: List[str] = [] # Global list to store model IDs

# --- Startup Event ---
@app.on_event("startup")
async def fetch_available_models():
    """Fetches available models from OpenRouter on startup."""
    global available_models
    logger.info("Fetching available models from OpenRouter...")
    try:
        response = requests.get("https://openrouter.ai/api/v1/models", timeout=10) # Added timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        models_data = response.json().get("data", [])
        # Extract model IDs, maybe filter/sort later
        # For now, just get all IDs
        available_models = sorted([model.get("id") for model in models_data if model.get("id")])
        logger.info(f"Successfully fetched {len(available_models)} models.")
        # Log the actual list for confirmation
        logger.info(f"Available models list (first 10): {available_models[:10]}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch models from OpenRouter: {e}")
        available_models = [] # Ensure it's an empty list on failure
    except Exception as e:
        logger.error(f"An unexpected error occurred during model fetching: {e}", exc_info=True)
        available_models = []


# --- Static Files ---
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("Mounted static files directory.")
except RuntimeError as e:
     logger.warning(f"Could not mount static directory (may not exist): {e}")


###############################################################################
# Helper Functions
###############################################################################

def _extract_search_terms(research_goal_description: str) -> str:
    """Extract key terms from research goal description for arXiv search"""
    import re
    
    # Remove common stopwords and extract meaningful terms
    stopwords = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 
        'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 
        'above', 'below', 'between', 'among', 'is', 'are', 'was', 'were', 'be', 'been', 
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 
        'should', 'may', 'might', 'must', 'can', 'shall', 'new', 'novel', 'develop', 
        'improvement', 'better', 'enhance', 'increase', 'method', 'methods', 'approach',
        'approaches', 'way', 'ways', 'technique', 'techniques', 'strategy', 'strategies'
    }
    
    # Clean and normalize the text
    text = research_goal_description.lower()
    # Remove punctuation except hyphens in compound words
    text = re.sub(r'[^\w\s-]', ' ', text)
    # Split into words
    words = text.split()
    
    # Filter out stopwords and short words
    meaningful_words = [word for word in words if len(word) > 2 and word not in stopwords]
    
    # Take the most important terms (limit to avoid overly long queries)
    key_terms = meaningful_words[:8]  # Limit to 8 most relevant terms
    
    # Join terms for search query
    search_query = ' '.join(key_terms)
    
    # If no meaningful terms found, use the original description truncated
    if not search_query.strip():
        search_query = research_goal_description[:100]
    
    return search_query

###############################################################################
# API Endpoints
###############################################################################

@app.post("/research_goal", response_model=dict)
def set_research_goal(goal: ResearchGoalRequest):
    """Sets the research goal and resets the context."""
    global current_research_goal, global_context, current_session_id
    from .database import get_db_manager
    logger.info("--- Endpoint /research_goal START ---")
    logger.info(f"Received new research goal description: {goal.description}")
    logger.info(f"Received constraints: {goal.constraints}")
    logger.info(f"Received advanced settings: llm_model={goal.llm_model}, num_hypotheses={goal.num_hypotheses}, etc.") # Log received settings
    try:
        # Pass all settings from the request to the ResearchGoal constructor
        current_research_goal = ResearchGoal(
            description=goal.description,
            constraints=goal.constraints,
            llm_model=goal.llm_model,
            num_hypotheses=goal.num_hypotheses,
            generation_temperature=goal.generation_temperature,
            reflection_temperature=goal.reflection_temperature,
            elo_k_factor=goal.elo_k_factor,
            top_k_hypotheses=goal.top_k_hypotheses
        )
        logger.info(f"ResearchGoal object created with effective settings: model={current_research_goal.llm_model}, num={current_research_goal.num_hypotheses}, gen_temp={current_research_goal.generation_temperature}, etc.") # Log effective settings
        
        # Create new session in database
        db_manager = get_db_manager()
        current_session_id = db_manager.create_session(current_research_goal)
        
        # Create context with database integration
        global_context = ContextMemory(session_id=current_session_id, use_database=True)
        
        # Perform automatic literature search based on research goal
        try:
            logger.info("Performing automatic literature search for research goal...")
            from .tools.arxiv_search import ArxivSearchTool
            
            arxiv_tool = ArxivSearchTool(max_results=10, session_id=current_session_id)
            
            # Extract key terms from research goal for search
            search_query = _extract_search_terms(goal.description)
            logger.info(f"Extracted search terms: {search_query}")
            
            # Search for relevant papers
            papers = arxiv_tool.search(search_query, search_type="auto_goal_setting")
            logger.info(f"Found {len(papers)} relevant papers for research goal")
            
            # Store literature context in the research goal for use in generation
            current_research_goal.literature_context = papers[:5]  # Top 5 most relevant papers
            
        except Exception as lit_e:
            logger.warning(f"Failed to perform automatic literature search: {lit_e}")
            current_research_goal.literature_context = []  # Empty list on failure
        
        logger.info(f"Global context reset successfully. Session ID: {current_session_id}")
    except Exception as e:
        logger.error(f"Error processing research goal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error setting research goal: {e}")

    # --- Setup Timestamped File Logging ---
    try:
        # Get the specific logger instance used by the app
        app_logger = logging.getLogger("aicoscientist") # Match the name used in utils.py

        # Remove existing FileHandlers to avoid duplicates
        for handler in app_logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                logger.info(f"Removing existing file handler: {handler.baseFilename}")
                app_logger.removeHandler(handler)
                handler.close() # Close the handler

        # Create a new timestamped log file name
        log_dir = "results" # Assuming logs go in 'results' directory at project root
        os.makedirs(log_dir, exist_ok=True) # Ensure directory exists
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # Use the log file name base from config if available
        log_file_base = "app_log" # Default base name
        # TODO: Access config safely if needed: from .config import config; log_file_base = config.get('log_file_name', 'app_log')
        log_filename = os.path.join(log_dir, f"{log_file_base}_{timestamp}.txt")

        # Create and add the new file handler
        file_handler = logging.FileHandler(log_filename)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s") # Consistent format
        file_handler.setFormatter(formatter)
        app_logger.addHandler(file_handler)
        logger.info(f"Logging for this goal directed to: {log_filename}")

    except Exception as log_e:
        logger.error(f"Failed to set up file logging: {log_e}", exc_info=True)
        # Decide if this should be a fatal error for the request
        # raise HTTPException(status_code=500, detail=f"Failed to setup logging: {log_e}")

    logger.info(f"Logging setup complete. File: {log_filename}, Database: Session {current_session_id}")
    
    # Auto-run first cycle with literature-informed generation
    auto_run_result = None
    try:
        logger.info("Auto-running first cycle with literature context...")
        from .agents import SupervisorAgent
        supervisor = SupervisorAgent()
        auto_run_result = supervisor.run_cycle(current_research_goal, global_context)
        logger.info("Auto-run cycle completed successfully")
    except Exception as auto_e:
        logger.error(f"Auto-run cycle failed: {auto_e}", exc_info=True)
        auto_run_result = {"error": f"Auto-run failed: {auto_e}"}
    
    logger.info("--- Endpoint /research_goal END ---")
    
    response = {
        "message": "Research goal successfully set with literature search and auto-run cycle.",
        "session_id": current_session_id,
        "literature_papers_found": len(current_research_goal.literature_context)
    }
    
    if auto_run_result:
        response["auto_run_result"] = auto_run_result
    
    return response

@app.post("/run_cycle", response_model=Dict)
def run_cycle_endpoint():
    """Runs a single cycle of the AI Co-Scientist workflow."""
    global current_research_goal, global_context, supervisor
    logger.info("--- Endpoint /run_cycle START ---")
    if not current_research_goal:
        logger.error("Run cycle called but current_research_goal is not set.")
        raise HTTPException(status_code=400, detail="No research goal set. Please POST to /research_goal first.")

    iteration = global_context.iteration_number + 1
    logger.info(f"Attempting to run cycle {iteration} for goal: {current_research_goal.description}")
    try:
        logger.info("Calling supervisor.run_cycle...")
        cycle_details = supervisor.run_cycle(current_research_goal, global_context)
        logger.info(f"Supervisor run_cycle completed for iteration {global_context.iteration_number}.")
        logger.info("--- Endpoint /run_cycle END (Success) ---")
        return cycle_details
    except Exception as e:
        logger.error(f"Error during cycle {iteration} execution: {e}", exc_info=True)
        logger.info("--- Endpoint /run_cycle END (Error) ---")
        raise HTTPException(status_code=500, detail=f"An internal error occurred during cycle execution: {e}")


@app.get("/hypotheses", response_model=List[HypothesisResponse])
def list_hypotheses_endpoint():
    """Retrieves a list of all currently active hypotheses."""
    global global_context
    active_hypotheses = global_context.get_active_hypotheses()
    logger.info(f"Retrieving {len(active_hypotheses)} active hypotheses.")
    return [HypothesisResponse(**h.to_dict()) for h in active_hypotheses]

@app.post("/log_frontend_error")
def log_frontend_error(log_data: Dict):
    """Logs frontend errors and information to the backend log."""
    try:
        level = log_data.get('level', 'INFO').upper()
        message = log_data.get('message', 'No message provided')
        timestamp = log_data.get('timestamp', '')
        data = log_data.get('data', {})
        
        # Format the log message
        log_message = f"[FRONTEND-{level}] {message}"
        if data:
            log_message += f" | Data: {data}"
        if timestamp:
            log_message += f" | Client Time: {timestamp}"
        
        # Log at appropriate level
        if level == 'ERROR':
            logger.error(log_message)
        elif level == 'WARNING':
            logger.warning(log_message)
        else:
            logger.info(log_message)
        
        # Also log to database if session is available
        if current_session_id:
            try:
                from .database import get_db_manager
                db_manager = get_db_manager()
                db_manager.log_message(
                    message=f"[FRONTEND] {message}",
                    level=level,
                    session_id=current_session_id,
                    module="frontend",
                    metadata={
                        "client_timestamp": timestamp,
                        "data": data
                    }
                )
            except Exception as db_e:
                logger.error(f"Failed to log frontend message to database: {db_e}")
        
        return {"status": "logged", "level": level}
        
    except Exception as e:
        logger.error(f"Error logging frontend message: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

###############################################################################
# ArXiv Search Endpoints
###############################################################################

@app.post("/arxiv/search", response_model=ArxivSearchResponse)
def search_arxiv_papers(search_request: ArxivSearchRequest):
    """Search arXiv for papers based on query and filters."""
    import time
    start_time = time.time()
    
    try:
        # Initialize arXiv tool with session tracking if available
        arxiv_tool = ArxivSearchTool(
            max_results=search_request.max_results or 10,
            session_id=current_session_id
        )
        
        if search_request.days_back:
            # Search recent papers
            papers = arxiv_tool.search_recent_papers(
                query=search_request.query,
                days_back=search_request.days_back,
                max_results=search_request.max_results
            )
        else:
            # Regular search
            papers = arxiv_tool.search_papers(
                query=search_request.query,
                max_results=search_request.max_results,
                categories=search_request.categories,
                sort_by=search_request.sort_by or "relevance"
            )
        
        search_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Convert to Pydantic models
        arxiv_papers = [ArxivPaper(**paper) for paper in papers]
        
        logger.info(f"ArXiv search for '{search_request.query}' returned {len(papers)} papers in {search_time:.2f}ms")
        
        return ArxivSearchResponse(
            query=search_request.query,
            total_results=len(papers),
            papers=arxiv_papers,
            search_time_ms=search_time
        )
        
    except Exception as e:
        logger.error(f"Error in arXiv search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"ArXiv search failed: {str(e)}")

@app.get("/arxiv/paper/{arxiv_id}", response_model=ArxivPaper)
def get_arxiv_paper(arxiv_id: str):
    """Get detailed information for a specific arXiv paper."""
    try:
        arxiv_tool = ArxivSearchTool()
        paper = arxiv_tool.get_paper_details(arxiv_id)
        
        if not paper:
            raise HTTPException(status_code=404, detail=f"Paper with arXiv ID '{arxiv_id}' not found")
        
        logger.info(f"Retrieved arXiv paper: {arxiv_id}")
        return ArxivPaper(**paper)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving arXiv paper {arxiv_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve paper: {str(e)}")

@app.get("/arxiv/trends/{query}", response_model=ArxivTrendsResponse)
def analyze_arxiv_trends(query: str, days_back: int = 30):
    """Analyze research trends for a given topic."""
    try:
        arxiv_tool = ArxivSearchTool()
        trends = arxiv_tool.analyze_research_trends(query, days_back)
        
        # Convert papers to Pydantic models
        arxiv_papers = [ArxivPaper(**paper) for paper in trends['papers']]
        
        logger.info(f"ArXiv trends analysis for '{query}' found {trends['total_papers']} papers")
        
        return ArxivTrendsResponse(
            query=query,
            total_papers=trends['total_papers'],
            date_range=trends['date_range'],
            top_categories=trends['top_categories'],
            top_authors=trends['top_authors'],
            papers=arxiv_papers
        )
        
    except Exception as e:
        logger.error(f"Error in arXiv trends analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Trends analysis failed: {str(e)}")

@app.get("/arxiv/categories")
def get_arxiv_categories():
    """Get available arXiv categories by field."""
    from .tools.arxiv_search import ARXIV_CATEGORIES
    return {
        "categories_by_field": ARXIV_CATEGORIES,
        "all_categories": [cat for cats in ARXIV_CATEGORIES.values() for cat in cats]
    }

@app.get("/arxiv/test")
async def arxiv_test_page():
    """Serves the arXiv testing interface."""
    html_content = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>ArXiv Search Testing Interface</title>
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 20px; 
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 { 
                color: #2c3e50; 
                text-align: center;
                margin-bottom: 30px;
            }
            .search-form {
                background-color: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 30px;
            }
            .form-group {
                margin-bottom: 15px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
                color: #34495e;
            }
            input, select, textarea {
                width: 100%;
                padding: 8px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
                box-sizing: border-box;
            }
            textarea {
                height: 80px;
                resize: vertical;
            }
            .form-row {
                display: flex;
                gap: 15px;
            }
            .form-row .form-group {
                flex: 1;
            }
            button {
                background-color: #3498db;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                margin-right: 10px;
                margin-top: 10px;
            }
            button:hover {
                background-color: #2980b9;
            }
            .secondary-btn {
                background-color: #95a5a6;
            }
            .secondary-btn:hover {
                background-color: #7f8c8d;
            }
            #results {
                margin-top: 30px;
            }
            .paper {
                border: 1px solid #ddd;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 8px;
                background-color: #fff;
            }
            .paper-title {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }
            .paper-meta {
                color: #7f8c8d;
                font-size: 14px;
                margin-bottom: 10px;
            }
            .paper-abstract {
                line-height: 1.5;
                margin-bottom: 15px;
                text-align: justify;
            }
            .paper-links a {
                color: #3498db;
                text-decoration: none;
                margin-right: 15px;
            }
            .paper-links a:hover {
                text-decoration: underline;
            }
            .stats {
                background-color: #ecf0f1;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
            .error {
                color: #e74c3c;
                background-color: #fdf2f2;
                padding: 15px;
                border-radius: 8px;
                border-left: 4px solid #e74c3c;
                margin-bottom: 20px;
            }
            .loading {
                text-align: center;
                padding: 40px;
                color: #7f8c8d;
            }
            .categories {
                display: flex;
                flex-wrap: wrap;
                gap: 5px;
                margin-bottom: 10px;
            }
            .category-tag {
                background-color: #3498db;
                color: white;
                padding: 2px 8px;
                border-radius: 12px;
                font-size: 12px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔬 ArXiv Search Testing Interface</h1>
            
            <div class="search-form">
                <div class="form-group">
                    <label for="query">Search Query:</label>
                    <textarea id="query" placeholder="Enter your search query (e.g., 'machine learning', 'neural networks', 'quantum computing')">machine learning</textarea>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label for="maxResults">Max Results:</label>
                        <input type="number" id="maxResults" value="10" min="1" max="50">
                    </div>
                    <div class="form-group">
                        <label for="sortBy">Sort By:</label>
                        <select id="sortBy">
                            <option value="relevance">Relevance</option>
                            <option value="lastUpdatedDate">Last Updated</option>
                            <option value="submittedDate">Submitted Date</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="daysBack">Recent Papers (days):</label>
                        <input type="number" id="daysBack" placeholder="Leave empty for all time" min="1" max="365">
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="categories">Categories (optional):</label>
                    <select id="categories" multiple style="height: 100px;">
                        <optgroup label="Computer Science">
                            <option value="cs.AI">cs.AI - Artificial Intelligence</option>
                            <option value="cs.LG">cs.LG - Machine Learning</option>
                            <option value="cs.CL">cs.CL - Computation and Language</option>
                            <option value="cs.CV">cs.CV - Computer Vision</option>
                            <option value="cs.RO">cs.RO - Robotics</option>
                            <option value="cs.NE">cs.NE - Neural and Evolutionary Computing</option>
                        </optgroup>
                        <optgroup label="Physics">
                            <option value="physics.data-an">physics.data-an - Data Analysis</option>
                            <option value="physics.comp-ph">physics.comp-ph - Computational Physics</option>
                        </optgroup>
                        <optgroup label="Mathematics">
                            <option value="math.ST">math.ST - Statistics Theory</option>
                            <option value="math.OC">math.OC - Optimization and Control</option>
                        </optgroup>
                    </select>
                    <small style="color: #7f8c8d;">Hold Ctrl/Cmd to select multiple categories</small>
                </div>
                
                <button onclick="searchPapers()">🔍 Search Papers</button>
                <button onclick="analyzeOptions()" class="secondary-btn">📊 Analyze Options</button>
                <button onclick="clearResults()" class="secondary-btn">🗑️ Clear Results</button>
            </div>
            
            <div id="results"></div>
        </div>

        <script>
            let isSearching = false;

            async function searchPapers() {
                if (isSearching) return;
                
                const query = document.getElementById('query').value.trim();
                if (!query) {
                    alert('Please enter a search query');
                    return;
                }
                
                isSearching = true;
                const resultsDiv = document.getElementById('results');
                resultsDiv.innerHTML = '<div class="loading">🔄 Searching arXiv...</div>';
                
                try {
                    const searchData = {
                        query: query,
                        max_results: parseInt(document.getElementById('maxResults').value),
                        sort_by: document.getElementById('sortBy').value
                    };
                    
                    const daysBack = document.getElementById('daysBack').value;
                    if (daysBack) {
                        searchData.days_back = parseInt(daysBack);
                    }
                    
                    const categoriesSelect = document.getElementById('categories');
                    const selectedCategories = Array.from(categoriesSelect.selectedOptions).map(option => option.value);
                    if (selectedCategories.length > 0) {
                        searchData.categories = selectedCategories;
                    }
                    
                    const response = await fetch('/arxiv/search', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(searchData)
                    });
                    
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || `HTTP ${response.status}`);
                    }
                    
                    const data = await response.json();
                    displayResults(data);
                    
                } catch (error) {
                    resultsDiv.innerHTML = `<div class="error">❌ Error: ${error.message}</div>`;
                } finally {
                    isSearching = false;
                }
            }
            
            function displayResults(data) {
                const resultsDiv = document.getElementById('results');
                
                if (data.papers.length === 0) {
                    resultsDiv.innerHTML = '<div class="stats">No papers found for your query.</div>';
                    return;
                }
                
                let html = `
                    <div class="stats">
                        <strong>📈 Search Results:</strong> Found ${data.total_results} papers for "${data.query}"
                        ${data.search_time_ms ? ` in ${data.search_time_ms.toFixed(2)}ms` : ''}
                    </div>
                `;
                
                data.papers.forEach((paper, index) => {
                    const publishedDate = paper.published ? new Date(paper.published).toLocaleDateString() : 'Unknown';
                    const categoriesHtml = paper.categories.map(cat => `<span class="category-tag">${cat}</span>`).join('');
                    
                    html += `
                        <div class="paper">
                            <div class="paper-title">${paper.title}</div>
                            <div class="paper-meta">
                                <strong>Authors:</strong> ${paper.authors.join(', ')}<br>
                                <strong>Published:</strong> ${publishedDate} | 
                                <strong>Primary Category:</strong> ${paper.primary_category} |
                                <strong>arXiv ID:</strong> ${paper.arxiv_id}
                            </div>
                            <div class="categories">${categoriesHtml}</div>
                            <div class="paper-abstract">${paper.abstract}</div>
                            <div class="paper-links">
                                <a href="${paper.arxiv_url}" target="_blank">📄 View on arXiv</a>
                                <a href="${paper.pdf_url}" target="_blank">📁 Download PDF</a>
                                ${paper.doi ? `<a href="https://doi.org/${paper.doi}" target="_blank">🔗 DOI</a>` : ''}
                            </div>
                        </div>
                    `;
                });
                
                resultsDiv.innerHTML = html;
            }
            
            function analyzeOptions() {
                const options = `
                    <div class="stats">
                        <h3>🛠️ Additional Analysis Options</h3>
                        <p><strong>Trends Analysis:</strong> Use <code>/arxiv/trends/{query}</code> to analyze research trends</p>
                        <p><strong>Specific Paper:</strong> Use <code>/arxiv/paper/{arxiv_id}</code> to get details for a specific paper</p>
                        <p><strong>Categories:</strong> Use <code>/arxiv/categories</code> to see all available categories</p>
                        <p><strong>Recent Papers:</strong> Set "Recent Papers (days)" to filter by submission date</p>
                        <p><strong>API Integration:</strong> All endpoints are available for programmatic access</p>
                    </div>
                `;
                document.getElementById('results').innerHTML = options;
            }
            
            function clearResults() {
                document.getElementById('results').innerHTML = '';
            }
            
            // Allow Enter key to search
            document.getElementById('query').addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    searchPapers();
                }
            });
        </script>
    </body>
    </html>
    '''
    return responses.HTMLResponse(content=html_content)

@app.get("/")
async def root_endpoint():
    """Serves the main HTML page, injecting available models."""
    global available_models
    logger.debug("Serving root HTML page.")
    # Pass the models list to the template (will be used by JS)
    # Need json import here
    import json
    # Ensure models_json is treated as a raw string suitable for JS assignment
    models_json_string = json.dumps(available_models)
    
    # Get config values for Advanced Settings defaults
    config_num_hypotheses = config.get('num_hypotheses', 3)
    config_gen_temp = config.get('step_temperatures', {}).get('generation', 0.7)
    config_ref_temp = config.get('step_temperatures', {}).get('reflection', 0.5)
    config_elo_k = config.get('elo_k_factor', 32)
    config_top_k = config.get('top_k_hypotheses', 2)
    config_llm_model = config.get('llm_model', 'google/gemini-flash-1.5')

    # Use regular string concatenation or triple quotes, NOT f-string for the large HTML block
    # Add a placeholder like ###MODELS_JSON### where the data should go
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Co-Scientist</title>
        <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <style>
            body { font-family: sans-serif; margin: 20px; }
            textarea { width: 90%; }
            button { margin-top: 10px; padding: 8px 15px; }
            #results { margin-top: 20px; border-top: 1px solid #eee; padding-top: 20px; }
            #errors { color: red; margin-top: 10px; }
            #references { margin-top: 20px; border-top: 1px solid #eee; padding-top: 20px; }
            h2, h3, h4, h5 { margin-top: 1.5em; }
            ul { padding-left: 20px; }
            li { margin-bottom: 10px; }
            .reference-paper {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 15px;
                background-color: #fafafa;
            }
            .reference-title {
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 8px;
                font-size: 16px;
            }
            .reference-authors {
                color: #7f8c8d;
                font-size: 14px;
                margin-bottom: 8px;
            }
            .reference-meta {
                color: #95a5a6;
                font-size: 12px;
                margin-bottom: 10px;
            }
            .reference-abstract {
                color: #34495e;
                font-size: 14px;
                line-height: 1.4;
                margin-bottom: 10px;
            }
            .reference-links a {
                color: #3498db;
                text-decoration: none;
                margin-right: 15px;
                font-size: 14px;
            }
            .reference-links a:hover {
                text-decoration: underline;
            }
            .reference-category {
                display: inline-block;
                background-color: #3498db;
                color: white;
                padding: 2px 6px;
                border-radius: 10px;
                font-size: 11px;
                margin-right: 5px;
                margin-bottom: 5px;
            }
            #mynetwork {
                width: 100%;
                height: 500px; /* Explicit height */
                border: 1px solid lightgray;
                margin-bottom: 10px;
            }
            .graph-explanation p {
                 margin-top: 0;
                 margin-bottom: 20px;
                 font-size: 0.9em;
                 color: #555;
            }
        </style>
    </head>
    <body>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding: 10px; background: #f8f9fa; border-radius: 5px;">
            <div>
                <h1 style="margin: 0;">Welcome to the AI Co-Scientist System</h1>
                <p style="margin: 5px 0 0 0;">Set your research goal and run cycles to generate hypotheses.</p>
            </div>
            <div>
                <a href="/dashboard" style="background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    🗄️ Database Dashboard
                </a>
            </div>
        </div>

        <label for="researchGoal">Research Goal:</label><br>
        <textarea id="researchGoal" name="researchGoal" rows="4" cols="50"></textarea><br><br>

        <details style="margin-top: 15px; margin-bottom: 15px; border: 1px solid #eee; padding: 10px; border-radius: 5px;">
            <summary style="cursor: pointer; font-weight: bold;">Advanced Settings</summary>
            <div style="margin-top: 10px;">
                <label for="llm_model">LLM Model:</label><br>
                <select id="llm_model" name="llm_model" style="width: 90%; margin-bottom: 10px;">
                    <!-- Options will be populated by JavaScript -->
                    <option value="">-- Select Model --</option>
                </select><br>

                <label for="num_hypotheses">Number of Hypotheses per Cycle:</label>
                <input type="number" id="num_hypotheses" name="num_hypotheses" min="1" max="10" placeholder="###CONFIG_NUM_HYPOTHESES###" style="width: 50px; margin-bottom: 10px;"><br>

                <label for="generation_temperature">Generation Temperature (Creativity):</label>
                <input type="range" id="generation_temperature" name="generation_temperature" min="0.1" max="1.0" step="0.1" value="###CONFIG_GEN_TEMP###" style="width: 90%; margin-bottom: 5px;" oninput="this.nextElementSibling.value = this.value">
                <output>###CONFIG_GEN_TEMP###</output><br>

                <label for="reflection_temperature">Reflection Temperature (Analysis):</label>
                <input type="range" id="reflection_temperature" name="reflection_temperature" min="0.1" max="1.0" step="0.1" value="###CONFIG_REF_TEMP###" style="width: 90%; margin-bottom: 5px;" oninput="this.nextElementSibling.value = this.value">
                <output>###CONFIG_REF_TEMP###</output><br>

                <label for="elo_k_factor">Elo K-Factor (Ranking Sensitivity):</label>
                <input type="number" id="elo_k_factor" name="elo_k_factor" min="1" max="100" placeholder="###CONFIG_ELO_K###" style="width: 50px; margin-bottom: 10px;"><br>

                <label for="top_k_hypotheses">Top K for Evolution:</label>
                <input type="number" id="top_k_hypotheses" name="top_k_hypotheses" min="2" max="5" placeholder="###CONFIG_TOP_K###" style="width: 50px; margin-bottom: 10px;"><br>
            </div>
        </details>

        <button onclick="submitResearchGoal()">Submit Research Goal</button>
        <button onclick="runCycle()">Run Next Cycle</button> <!-- Added manual run button -->

        <p style="margin-top: 20px; margin-bottom: 20px; display: block; font-size: 0.9em; color: #333;">
            <em>Instructions:</em> Enter a research goal and click "Submit Research Goal" to start a new process.
            Click "Run Next Cycle" to perform another iteration on the current set of hypotheses.
        </p>
        <p id="initial-prompt" style="color: #555;">Submit a research goal to begin.</p>

        <h2>Results</h2>
        <div id="results"></div> <!-- Removed initial text -->

        <h2>References</h2>
        <div id="references">
            <p style="color: #7f8c8d; font-style: italic;">arXiv papers related to generated hypotheses will appear here.</p>
        </div>

        <h2>Errors</h2>
        <div id="errors"></div>

        <script>
            // Inject the models list from the backend - Placeholder will be replaced
            const availableModels = ###MODELS_JSON###;
            const defaultModel = "###CONFIG_LLM_MODEL###";
            console.log("Available models received from backend:", availableModels); // Log received models

            let currentIteration = 0;
            let isRunning = false;

            // Function to safely escape HTML characters
            function escapeHTML(str) {
                if (!str) return "";
                // Correctly replace & first, then other characters
                return str.replace(/&/g, '&').replace(/</g, '<').replace(/>/g, '>').replace(/"/g, '"').replace(/'/g, '&#039;');
            }

            async function submitResearchGoal() {
                if (isRunning) {
                    console.log("submitResearchGoal: Already running, exiting.");
                    return;
                }
                const researchGoal = document.getElementById('researchGoal').value;
                if (!researchGoal.trim()) {
                    document.getElementById('errors').innerHTML = '<p>Please enter a research goal.</p>';
                    return;
                }
                // Clear initial prompt and show status
                const initialPrompt = document.getElementById('initial-prompt');
                if (initialPrompt) initialPrompt.style.display = 'none';
                document.getElementById('results').innerHTML = '<p>Setting research goal...</p>';
                document.getElementById('errors').innerHTML = '';
                currentIteration = 0;
                    console.log("Submitting research goal:", researchGoal);

                // Read advanced settings (read from select for llm_model)
                const settings = {
                    description: researchGoal,
                    constraints: {}, // Add constraints input if needed later
                    llm_model: document.getElementById('llm_model').value || null, // Read from select
                    num_hypotheses: parseInt(document.getElementById('num_hypotheses').value) || null,
                    generation_temperature: parseFloat(document.getElementById('generation_temperature').value) || null,
                    reflection_temperature: parseFloat(document.getElementById('reflection_temperature').value) || null,
                    elo_k_factor: parseInt(document.getElementById('elo_k_factor').value) || null,
                    top_k_hypotheses: parseInt(document.getElementById('top_k_hypotheses').value) || null,
                };
                // Remove null values so backend uses defaults from ResearchGoal class
                Object.keys(settings).forEach(key => (settings[key] == null || settings[key] === '' || isNaN(settings[key])) && delete settings[key]);
                // Ensure description is always present
                settings.description = researchGoal;

                console.log("Submitting with settings:", settings);


                try {
                    isRunning = true;
                    console.log("Fetching /research_goal...");
                    const response = await fetch('/research_goal', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(settings) // Send all settings
                    });
                    console.log("Response status from /research_goal:", response.status);

                    if (!response.ok) {
                        let errorMsg = `HTTP error! status: ${response.status}`;
                        try {
                            const errorData = await response.json();
                            errorMsg = errorData.detail || JSON.stringify(errorData);
                        } catch (e) { errorMsg = response.statusText || errorMsg; }
                        console.error("Error response from /research_goal:", errorMsg);
                        throw new Error(errorMsg);
                    }

                    const data = await response.json();
                    console.log("Response data from /research_goal:", data);
                    document.getElementById('results').innerHTML = '<p>' + escapeHTML(data.message) + '</p><p>Running first cycle...</p>';
                    setTimeout(runCycle, 100);
                } catch (error) {
                    console.error('Error in submitResearchGoal:', error);
                    document.getElementById('errors').innerHTML = '<p>Error setting goal: ' + escapeHTML(error.message) + '</p>';
                    document.getElementById('results').innerHTML = ''; // Clear results on error
                    // Restore initial prompt on error if needed
                    // const initialPrompt = document.getElementById('initial-prompt');
                    // if (initialPrompt) initialPrompt.style.display = 'block';
                } finally {
                    isRunning = false;
                    console.log("submitResearchGoal: isRunning set to false.");
                }
            }

            async function runCycle() {
                 if (isRunning) {
                    console.log("runCycle: Already running, exiting.");
                    return;
                }
                console.log(`Attempting to run cycle ${currentIteration + 1}`);
                document.getElementById('errors').innerHTML = '';
                const resultsDiv = document.getElementById('results');
                // Clear initial prompt if it's still visible
                const initialPrompt = document.getElementById('initial-prompt');
                if (initialPrompt) initialPrompt.style.display = 'none';
                // Add status message
                const statusDiv = document.createElement('p');
                statusDiv.id = `cycle-status-${currentIteration + 1}`;
                statusDiv.textContent = `Running cycle ${currentIteration + 1}...`;
                resultsDiv.appendChild(statusDiv);

                try {
                    isRunning = true;
                    console.log("Fetching /run_cycle...");
                    const response = await fetch('/run_cycle', { method: 'POST' });
                    console.log("Response status from /run_cycle:", response.status);

                    const currentStatusDiv = document.getElementById(statusDiv.id);
                    if (currentStatusDiv) {
                        resultsDiv.removeChild(currentStatusDiv);
                    }

                    if (!response.ok) {
                         let errorMsg = `HTTP error! status: ${response.status}`;
                        try {
                            const errorData = await response.json();
                            errorMsg = errorData.detail || JSON.stringify(errorData);
                        } catch (e) { errorMsg = response.statusText || errorMsg; }
                        console.error("Error response from /run_cycle:", errorMsg);
                        throw new Error(errorMsg);
                    }

                    const data = await response.json();
                    console.log("Response data from /run_cycle:", data);
                    currentIteration = data.iteration;

                    let resultsHTML = '<h3>Iteration: ' + data.iteration + '</h3>';
                    let graphData = null;

                    for (const stepName in data.steps) {
                        if (data.steps.hasOwnProperty(stepName)) {
                            const step = data.steps[stepName];
                            resultsHTML += '<h4>Step: ' + escapeHTML(stepName) + '</h4>';

                            if (step.hypotheses && step.hypotheses.length > 0) {
                                resultsHTML += '<h5>Hypotheses:</h5><ul>';
                                step.hypotheses.sort((a, b) => b.elo_score - a.elo_score).forEach(hypo => {
                                    resultsHTML += '<li>';
                                    resultsHTML += '<strong>' + escapeHTML(hypo.title) + '</strong>';
                                    resultsHTML += ' (ID: ' + escapeHTML(hypo.id) + ', Elo: ' + hypo.elo_score.toFixed(2) + ')<br>';
                                    if (hypo.parent_ids && hypo.parent_ids.length > 0) {
                                        resultsHTML += '<em>Parents: ' + escapeHTML(hypo.parent_ids.join(', ')) + '</em><br>';
                                    }
                                    resultsHTML += '<p>' + escapeHTML(hypo.text) + '</p>'; // Use escaped text
                                    if (hypo.novelty_review) { resultsHTML += '<p>Novelty: ' + escapeHTML(hypo.novelty_review) + '</p>'; }
                                    if (hypo.feasibility_review){ resultsHTML += '<p>Feasibility: ' + escapeHTML(hypo.feasibility_review) + '</p>'; }
                                    resultsHTML += '</li>';
                                });
                                resultsHTML += '</ul>';
                            } else if (step.hypotheses) {
                                 resultsHTML += '<p>No hypotheses generated or active in this step.</p>';
                            }

                            if (stepName === "proximity" && step.nodes_str && step.edges_str) {
                                resultsHTML += '<h5>Hypothesis Similarity Graph:</h5>';
                                resultsHTML += '<div id="mynetwork"></div>';
                                resultsHTML += '<div class="graph-explanation"><p><b>How to read:</b> Nodes are hypotheses. Edges show similarity > 0.2.</p></div>';
                                graphData = { nodesStr: step.nodes_str, edgesStr: step.edges_str };
                            } else if (stepName === "proximity" && step.adjacency_graph) {
                                 resultsHTML += '<p>Adjacency Graph (raw): ' + escapeHTML(JSON.stringify(step.adjacency_graph)) + '</p>';
                            }
                        }
                    }

                    if (data.meta_review) {
                         resultsHTML += '<h4>Meta-Review:</h4>';
                         if (data.meta_review.meta_review_critique && data.meta_review.meta_review_critique.length > 0) {
                              resultsHTML += '<h5>Critique:</h5><ul>' + data.meta_review.meta_review_critique.map(item => '<li>' + escapeHTML(item) + '</li>').join('') + '</ul>';
                         }
                         if (data.meta_review.research_overview && data.meta_review.research_overview.suggested_next_steps.length > 0) {
                              resultsHTML += '<h5>Suggested Next Steps:</h5><ul>' + data.meta_review.research_overview.suggested_next_steps.map(item => '<li>' + escapeHTML(item) + '</li>').join('') + '</ul>';
                         }
                    }

                    resultsDiv.innerHTML = resultsHTML;

                    // Extract and display references
                    await updateReferences(data);

                    if (graphData) {
                        initializeGraph(graphData.nodesStr, graphData.edgesStr);
                    }

                } catch (error) {
                    console.error('Error in runCycle:', error);
                    document.getElementById('errors').innerHTML = '<p>Error during cycle ' + currentIteration + ': ' + escapeHTML(error.message) + '</p>';
                } finally {
                    isRunning = false;
                    console.log("runCycle: isRunning set to false.");
                }
            }

            // Function to log messages to backend for debugging
            async function logToBackend(level, message, data = null) {
                try {
                    const logData = {
                        level: level,
                        message: message,
                        timestamp: new Date().toISOString(),
                        data: data
                    };
                    
                    // Send log to backend endpoint (we'll create this)
                    await fetch('/log_frontend_error', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(logData)
                    });
                } catch (e) {
                    console.error('Failed to send log to backend:', e);
                }
            }

            // Function to update references section with arXiv papers
            async function updateReferences(data) {
                console.log("Updating references section...");
                await logToBackend('INFO', 'Starting references section update');
                
                const referencesDiv = document.getElementById('references');
                
                // Collect all unique reference IDs from hypotheses
                const allReferences = new Set();
                const researchGoal = document.getElementById('researchGoal').value.trim();
                
                await logToBackend('INFO', 'Extracting references from hypotheses', {
                    researchGoal: researchGoal,
                    hasSteps: !!data.steps
                });
                
                // Extract references from all hypotheses in all steps
                if (data.steps) {
                    Object.values(data.steps).forEach(step => {
                        if (step.hypotheses) {
                            step.hypotheses.forEach(hypo => {
                                if (hypo.references && Array.isArray(hypo.references)) {
                                    hypo.references.forEach(ref => allReferences.add(ref));
                                }
                            });
                        }
                    });
                }
                
                await logToBackend('INFO', 'References extraction complete', {
                    totalReferences: allReferences.size,
                    references: Array.from(allReferences)
                });
                
                // If we have references or a research goal, try to find related arXiv papers
                if (allReferences.size > 0 || researchGoal) {
                    try {
                        // Search for arXiv papers related to the research goal
                        let arxivPapers = [];
                        if (researchGoal) {
                            await logToBackend('INFO', 'Starting arXiv search', { query: researchGoal });
                            
                            const searchResponse = await fetch('/arxiv/search', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    query: researchGoal,
                                    max_results: 5,
                                    sort_by: 'relevance'
                                })
                            });
                            
                            await logToBackend('INFO', 'arXiv search response received', {
                                status: searchResponse.status,
                                ok: searchResponse.ok
                            });
                            
                            if (searchResponse.ok) {
                                const searchData = await searchResponse.json();
                                arxivPapers = searchData.papers || [];
                                console.log(`Found ${arxivPapers.length} related arXiv papers`);
                                await logToBackend('INFO', 'arXiv papers found', {
                                    count: arxivPapers.length,
                                    paperTitles: arxivPapers.map(p => p.title)
                                });
                            } else {
                                const errorText = await searchResponse.text();
                                await logToBackend('ERROR', 'arXiv search failed', {
                                    status: searchResponse.status,
                                    error: errorText
                                });
                            }
                        }
                        
                        // Display the references
                        await logToBackend('INFO', 'Calling displayReferences function');
                        await displayReferences(arxivPapers, Array.from(allReferences));
                        await logToBackend('INFO', 'References section update completed successfully');
                        
                    } catch (error) {
                        console.error('Error fetching arXiv papers:', error);
                        await logToBackend('ERROR', 'Error in updateReferences function', {
                            errorMessage: error.message,
                            errorStack: error.stack,
                            errorName: error.name
                        });
                        referencesDiv.innerHTML = '<p style="color: #e74c3c;">Error loading references: ' + escapeHTML(error.message) + '</p>';
                    }
                } else {
                    await logToBackend('INFO', 'No references or research goal found');
                    referencesDiv.innerHTML = '<p style="color: #7f8c8d; font-style: italic;">No references found in generated hypotheses.</p>';
                }
            }
            
            // Function to display references in a formatted way
            async function displayReferences(arxivPapers, additionalReferences) {
                try {
                    await logToBackend('INFO', 'Starting displayReferences function', {
                        arxivPapersCount: arxivPapers ? arxivPapers.length : 0,
                        additionalReferencesCount: additionalReferences ? additionalReferences.length : 0
                    });
                    
                    const referencesDiv = document.getElementById('references');
                    let referencesHTML = '';
                    
                    // Display arXiv papers
                    if (arxivPapers && arxivPapers.length > 0) {
                        await logToBackend('INFO', 'Processing arXiv papers for display');
                        referencesHTML += '<h3>Related arXiv Papers</h3>';
                        
                        arxivPapers.forEach((paper, index) => {
                            try {
                                const publishedDate = paper.published ? new Date(paper.published).toLocaleDateString() : 'Unknown';
                                const categoriesHTML = paper.categories ? paper.categories.slice(0, 3).map(cat => 
                                    `<span class="reference-category">${escapeHTML(cat)}</span>`).join('') : '';
                                
                                referencesHTML += `
                                    <div class="reference-paper">
                                        <div class="reference-title">${escapeHTML(paper.title)}</div>
                                        <div class="reference-authors">
                                            <strong>Authors:</strong> ${escapeHTML(paper.authors.slice(0, 5).join(', '))}${paper.authors.length > 5 ? ' et al.' : ''}
                                        </div>
                                        <div class="reference-meta">
                                            <strong>Published:</strong> ${publishedDate} | 
                                            <strong>arXiv ID:</strong> ${escapeHTML(paper.arxiv_id)}
                                        </div>
                                        <div style="margin-bottom: 8px;">${categoriesHTML}</div>
                                        <div class="reference-abstract">
                                            ${escapeHTML(paper.abstract.length > 300 ? paper.abstract.substring(0, 300) + '...' : paper.abstract)}
                                        </div>
                                        <div class="reference-links">
                                            <a href="${escapeHTML(paper.arxiv_url)}" target="_blank">📄 View on arXiv</a>
                                            <a href="${escapeHTML(paper.pdf_url)}" target="_blank">📁 Download PDF</a>
                                            ${paper.doi ? `<a href="https://doi.org/${escapeHTML(paper.doi)}" target="_blank">🔗 DOI</a>` : ''}
                                        </div>
                                    </div>
                                `;
                            } catch (paperError) {
                                logToBackend('ERROR', `Error processing arXiv paper ${index}`, {
                                    error: paperError.message,
                                    paperData: paper
                                });
                            }
                        });
                        
                        await logToBackend('INFO', 'arXiv papers HTML generation completed');
                    }
                
                    // Display additional references if any
                    if (additionalReferences && additionalReferences.length > 0) {
                        await logToBackend('INFO', 'Processing additional references', {
                            count: additionalReferences.length,
                            references: additionalReferences
                        });
                        
                        referencesHTML += '<h3>Additional References</h3>';
                        referencesHTML += '<div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px;">';
                        referencesHTML += '<p><strong>References mentioned in hypothesis reviews:</strong></p>';
                        referencesHTML += '<ul>';
                        
                        additionalReferences.forEach((ref, index) => {
                            try {
                                const refStr = escapeHTML(ref);
                                
                                // Detect arXiv ID (format: YYMM.NNNNN or starts with arXiv:)
                                const isArxivId = /^\\d{4}\\.\\d{4,5}(v\\d+)?$/.test(ref);
                                if (isArxivId || ref.toLowerCase().startsWith('arxiv:')) {
                                    const arxivId = ref.toLowerCase().startsWith('arxiv:') ? ref.substring(6) : ref;
                                    referencesHTML += '<li><strong>arXiv:</strong> <a href="https://arxiv.org/abs/' + arxivId + '" target="_blank">' + refStr + '</a></li>';
                                }
                                // Detect DOI (starts with 10. or doi:)
                                else if (ref.startsWith('10.') || ref.toLowerCase().startsWith('doi:')) {
                                    const doiId = ref.toLowerCase().startsWith('doi:') ? ref.substring(4) : ref;
                                    referencesHTML += '<li><strong>DOI:</strong> <a href="https://doi.org/' + doiId + '" target="_blank">' + refStr + '</a></li>';
                                }
                                // Pure numbers might be PMIDs (but warn for CS topics)
                                else if (/^\\d{8,}$/.test(ref)) {
                                    referencesHTML += '<li><strong>PubMed ID:</strong> <a href="https://pubmed.ncbi.nlm.nih.gov/' + refStr + '/" target="_blank">' + refStr + '</a> <span style="color: #e74c3c; font-size: 12px;">(⚠️ Note: PubMed is primarily for biomedical literature)</span></li>';
                                }
                                // Everything else as generic reference
                                else {
                                    referencesHTML += '<li><strong>Reference:</strong> ' + refStr + '</li>';
                                }
                            } catch (refError) {
                                logToBackend('ERROR', `Error processing additional reference ${index}`, {
                                    error: refError.message,
                                    reference: ref
                                });
                            }
                        });
                        
                        referencesHTML += '</ul>';
                        referencesHTML += '</div>';
                        
                        await logToBackend('INFO', 'Additional references processing completed');
                    }
                    
                    if (!referencesHTML) {
                        referencesHTML = '<p style="color: #7f8c8d; font-style: italic;">No references available for this research session.</p>';
                    }
                    
                    referencesDiv.innerHTML = referencesHTML;
                    await logToBackend('INFO', 'displayReferences function completed successfully');
                    
                } catch (error) {
                    await logToBackend('ERROR', 'Error in displayReferences function', {
                        errorMessage: error.message,
                        errorStack: error.stack,
                        errorName: error.name
                    });
                    const referencesDiv = document.getElementById('references');
                    referencesDiv.innerHTML = '<p style="color: #e74c3c;">Error displaying references: ' + escapeHTML(error.message) + '</p>';
                }
            }

            // Function to populate the model dropdown
            function populateModelDropdown() {
                console.log("Populating model dropdown..."); // Log function start
                const selectElement = document.getElementById('llm_model');
                if (!selectElement) {
                    console.error("LLM model select element not found!");
                    return;
                }

                // Clear existing options except the placeholder
                selectElement.innerHTML = '<option value="">-- Select Model --</option>';

                console.log("Type of availableModels:", typeof availableModels, "Is Array:", Array.isArray(availableModels), "Length:", availableModels ? availableModels.length : 'N/A');

                if (availableModels && Array.isArray(availableModels) && availableModels.length > 0) {
                    availableModels.forEach(modelId => {
                        console.log("Adding model to dropdown:", modelId); // Log each model
                        const option = document.createElement('option');
                        option.value = modelId;
                        option.textContent = modelId;
                        // Try to pre-select the default model
                        if (modelId === defaultModel) {
                            option.selected = true;
                        }
                        selectElement.appendChild(option);
                    });
                } else {
                    // Optionally add a default or indicate loading failed
                     const option = document.createElement('option');
                     option.value = defaultModel; // Fallback to a known default
                     option.textContent = defaultModel + " (Default - List unavailable)";
                     option.selected = true;
                     selectElement.appendChild(option);
                     console.warn("Available models list is empty, using default.");
                }
            }

            // Populate dropdown when the page loads
            document.addEventListener('DOMContentLoaded', populateModelDropdown);


            function initializeGraph(nodesStr, edgesStr) {
                if (typeof vis === 'undefined') {
                    console.error("Vis.js library not loaded!");
                    document.getElementById('errors').innerHTML += '<p>Error: Vis.js library failed to load.</p>';
                    return;
                }
                 const container = document.getElementById('mynetwork');
                 if (!container) {
                     console.error("Graph container #mynetwork not found in DOM!");
                     return;
                 }

                try {
                    const nodesArray = nodesStr ? new Function('return [' + nodesStr + ']')() : [];
                    const edgesArray = edgesStr ? new Function('return [' + edgesStr + ']')() : [];

                    var nodes = new vis.DataSet(nodesArray);
                    var edges = new vis.DataSet(edgesArray);

                    var data = { nodes: nodes, edges: edges };
                    var options = {
                         edges: {
                            smooth: { enabled: true, type: "dynamic" },
                            font: { size: 12, align: 'middle' }
                        },
                        nodes: {
                            shape: 'circle',
                            font: { size: 14 }
                        },
                        physics: {
                            stabilization: true,
                            barnesHut: { gravitationalConstant: -2000, centralGravity: 0.3, springLength: 150, springConstant: 0.04 }
                        }
                    };
                    var network = new vis.Network(container, data, options);
                } catch (e) {
                    console.error("Error initializing Vis.js graph:", e);
                    document.getElementById('errors').innerHTML += '<p>Error initializing graph: ' + escapeHTML(e.message) + '</p>';
                    container.innerHTML = '<p style="color:red;">Could not render graph.</p>';
                }
            }
        </script>
    </body>
    </html>
    """
    # Replace placeholders with actual values before returning
    html_content = html_content.replace("###MODELS_JSON###", models_json_string)
    html_content = html_content.replace("###CONFIG_NUM_HYPOTHESES###", str(config_num_hypotheses))
    html_content = html_content.replace("###CONFIG_GEN_TEMP###", str(config_gen_temp))
    html_content = html_content.replace("###CONFIG_REF_TEMP###", str(config_ref_temp))
    html_content = html_content.replace("###CONFIG_ELO_K###", str(config_elo_k))
    html_content = html_content.replace("###CONFIG_TOP_K###", str(config_top_k))
    html_content = html_content.replace("###CONFIG_LLM_MODEL###", config_llm_model)
    return responses.HTMLResponse(content=html_content)

###############################################################################
# ArXiv Analytics and Tracking Endpoints
###############################################################################

@app.get("/sessions/{session_id}/arxiv/analytics")
def get_session_arxiv_analytics(session_id: str):
    """Returns arXiv usage analytics for a session."""
    try:
        from .database import get_db_manager
        db_manager = get_db_manager()
        
        # Verify session exists
        session_info = db_manager.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        analytics = db_manager.get_session_arxiv_analytics(session_id)
        logger.info(f"Retrieved arXiv analytics for session {session_id}")
        
        return {
            "session_id": session_id,
            "analytics": analytics
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving arXiv analytics for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve analytics: {str(e)}")

@app.get("/arxiv/papers/{arxiv_id}/usage")
def get_paper_usage_statistics(arxiv_id: str):
    """Shows usage statistics for a specific paper across all sessions."""
    try:
        from .database import get_db_manager
        db_manager = get_db_manager()
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get paper details and access count
            cursor.execute('''
                SELECT arxiv_id, title, authors, primary_category, published_date,
                       access_count, first_accessed, last_accessed
                FROM arxiv_papers 
                WHERE arxiv_id = ?
            ''', (arxiv_id,))
            paper_row = cursor.fetchone()
            
            if not paper_row:
                raise HTTPException(status_code=404, detail=f"Paper with arXiv ID '{arxiv_id}' not found in database")
            
            paper_data = dict(paper_row)
            paper_data['authors'] = json.loads(paper_data['authors'] or '[]')
            
            # Get search results where this paper appeared
            cursor.execute('''
                SELECT s.session_id, s.query, s.search_type, s.timestamp, sr.result_rank
                FROM arxiv_search_results sr
                JOIN arxiv_searches s ON sr.search_id = s.id
                WHERE sr.arxiv_id = ?
                ORDER BY s.timestamp DESC
            ''', (arxiv_id,))
            search_appearances = [dict(row) for row in cursor.fetchall()]
            
            # Get hypothesis relationships
            cursor.execute('''
                SELECT hpr.hypothesis_id, hpr.reference_type, hpr.added_by, 
                       hpr.relevance_score, h.title as hypothesis_title, h.session_id
                FROM hypothesis_paper_references hpr
                JOIN hypotheses h ON hpr.hypothesis_id = h.hypothesis_id
                WHERE hpr.arxiv_id = ?
                ORDER BY hpr.timestamp DESC
            ''', (arxiv_id,))
            hypothesis_relationships = [dict(row) for row in cursor.fetchall()]
            
            # Get sessions where this paper was accessed
            cursor.execute('''
                SELECT DISTINCT s.session_id, COUNT(*) as appearances
                FROM arxiv_search_results sr
                JOIN arxiv_searches s ON sr.search_id = s.id
                WHERE sr.arxiv_id = ?
                GROUP BY s.session_id
                ORDER BY appearances DESC
            ''', (arxiv_id,))
            session_usage = [dict(row) for row in cursor.fetchall()]
        
        logger.info(f"Retrieved usage statistics for arXiv paper: {arxiv_id}")
        
        return {
            "arxiv_id": arxiv_id,
            "paper_details": paper_data,
            "usage_statistics": {
                "total_access_count": paper_data['access_count'],
                "sessions_accessed": len(session_usage),
                "search_appearances": len(search_appearances),
                "hypothesis_relationships": len(hypothesis_relationships)
            },
            "search_appearances": search_appearances,
            "hypothesis_relationships": hypothesis_relationships,
            "session_usage": session_usage
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving usage statistics for paper {arxiv_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve paper usage statistics: {str(e)}")

@app.post("/arxiv/papers/{arxiv_id}/access")
def log_paper_access(arxiv_id: str):
    """Manually log that a paper was accessed (for tracking clicks from frontend)."""
    try:
        from .database import get_db_manager
        db_manager = get_db_manager()
        
        # First try to get paper details from arXiv if not in database
        paper_data = None
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT arxiv_id FROM arxiv_papers WHERE arxiv_id = ?', (arxiv_id,))
            exists = cursor.fetchone()
        
        if not exists:
            # Try to fetch paper details from arXiv API
            try:
                from .tools.arxiv_search import ArxivSearchTool
                arxiv_tool = ArxivSearchTool()
                paper_details = arxiv_tool.get_paper_details(arxiv_id)
                
                if paper_details:
                    paper_data = paper_details
                else:
                    # Create minimal paper record
                    paper_data = {
                        'arxiv_id': arxiv_id,
                        'title': f'arXiv:{arxiv_id}',
                        'abstract': '',
                        'authors': [],
                        'categories': [],
                        'primary_category': 'unknown',
                        'published': None,
                        'pdf_url': f'https://arxiv.org/pdf/{arxiv_id}.pdf',
                        'arxiv_url': f'https://arxiv.org/abs/{arxiv_id}'
                    }
            except Exception as fetch_error:
                logger.warning(f"Could not fetch details for paper {arxiv_id}: {fetch_error}")
                # Create minimal paper record
                paper_data = {
                    'arxiv_id': arxiv_id,
                    'title': f'arXiv:{arxiv_id}',
                    'abstract': '',
                    'authors': [],
                    'categories': [],
                    'primary_category': 'unknown',
                    'published': None,
                    'pdf_url': f'https://arxiv.org/pdf/{arxiv_id}.pdf',
                    'arxiv_url': f'https://arxiv.org/abs/{arxiv_id}'
                }
        else:
            # Paper already exists, just need to update access count
            paper_data = {'arxiv_id': arxiv_id}
        
        # Save/update paper and increment access count
        saved_arxiv_id = db_manager.save_arxiv_paper(paper_data)
        
        # Log the access event if we have a current session
        if current_session_id:
            db_manager.log_message(
                message=f"Manual paper access logged: {arxiv_id}",
                level="INFO",
                session_id=current_session_id,
                module="frontend",
                metadata={
                    "arxiv_id": arxiv_id,
                    "access_type": "manual_click"
                }
            )
        
        logger.info(f"Logged access for arXiv paper: {arxiv_id}")
        
        return {
            "message": "Paper access logged successfully",
            "arxiv_id": saved_arxiv_id,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error logging access for paper {arxiv_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to log paper access: {str(e)}")

@app.get("/arxiv/search-history/{session_id}")
def get_arxiv_search_history(session_id: str):
    """Shows search history for a session."""
    try:
        from .database import get_db_manager
        db_manager = get_db_manager()
        
        # Verify session exists
        session_info = db_manager.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get search history
            cursor.execute('''
                SELECT id, query, search_type, max_results, categories, sort_by, 
                       days_back, results_count, search_time_ms, timestamp
                FROM arxiv_searches 
                WHERE session_id = ?
                ORDER BY timestamp DESC
            ''', (session_id,))
            searches = []
            
            for row in cursor.fetchall():
                search_data = dict(row)
                search_data['categories'] = json.loads(search_data['categories'] or '[]')
                
                # Get papers found in this search
                cursor.execute('''
                    SELECT sr.arxiv_id, sr.result_rank, sr.clicked, ap.title, ap.authors
                    FROM arxiv_search_results sr
                    JOIN arxiv_papers ap ON sr.arxiv_id = ap.arxiv_id
                    WHERE sr.search_id = ?
                    ORDER BY sr.result_rank
                ''', (search_data['id'],))
                
                papers = []
                for paper_row in cursor.fetchall():
                    paper_data = dict(paper_row)
                    paper_data['authors'] = json.loads(paper_data['authors'] or '[]')
                    papers.append(paper_data)
                
                search_data['papers_found'] = papers
                searches.append(search_data)
        
        logger.info(f"Retrieved search history for session {session_id}: {len(searches)} searches")
        
        return {
            "session_id": session_id,
            "search_history": searches,
            "total_searches": len(searches)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving search history for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve search history: {str(e)}")

@app.put("/sessions/{session_id}/hypotheses/{hypothesis_id}/papers/{arxiv_id}")
def link_paper_to_hypothesis(session_id: str, hypothesis_id: str, arxiv_id: str, 
                           reference_type: str = "citation", relevance_score: Optional[float] = None):
    """Manually link a paper to a hypothesis with metadata."""
    try:
        from .database import get_db_manager
        db_manager = get_db_manager()
        
        # Verify session exists
        session_info = db_manager.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        # Verify hypothesis exists and belongs to the session
        hypotheses = db_manager.get_session_hypotheses(session_id, active_only=False)
        hypothesis_exists = any(h.hypothesis_id == hypothesis_id for h in hypotheses)
        
        if not hypothesis_exists:
            raise HTTPException(status_code=404, detail=f"Hypothesis '{hypothesis_id}' not found in session '{session_id}'")
        
        # Validate reference_type
        valid_types = ["inspiration", "citation", "background", "contradiction"]
        if reference_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"Invalid reference_type. Must be one of: {valid_types}")
        
        # Validate relevance_score if provided
        if relevance_score is not None and (relevance_score < 0.0 or relevance_score > 1.0):
            raise HTTPException(status_code=400, detail="relevance_score must be between 0.0 and 1.0")
        
        # Check if paper exists in database, if not try to fetch it
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT arxiv_id FROM arxiv_papers WHERE arxiv_id = ?', (arxiv_id,))
            paper_exists = cursor.fetchone()
        
        if not paper_exists:
            # Try to fetch paper details from arXiv
            try:
                from .tools.arxiv_search import ArxivSearchTool
                arxiv_tool = ArxivSearchTool()
                paper_details = arxiv_tool.get_paper_details(arxiv_id)
                
                if paper_details:
                    db_manager.save_arxiv_paper(paper_details)
                else:
                    # Create minimal paper record
                    minimal_paper = {
                        'arxiv_id': arxiv_id,
                        'title': f'arXiv:{arxiv_id}',
                        'abstract': '',
                        'authors': [],
                        'categories': [],
                        'primary_category': 'unknown',
                        'published': None,
                        'pdf_url': f'https://arxiv.org/pdf/{arxiv_id}.pdf',
                        'arxiv_url': f'https://arxiv.org/abs/{arxiv_id}'
                    }
                    db_manager.save_arxiv_paper(minimal_paper)
            except Exception as fetch_error:
                logger.warning(f"Could not fetch details for paper {arxiv_id}: {fetch_error}")
                # Create minimal paper record anyway
                minimal_paper = {
                    'arxiv_id': arxiv_id,
                    'title': f'arXiv:{arxiv_id}',
                    'abstract': '',
                    'authors': [],
                    'categories': [],
                    'primary_category': 'unknown',
                    'published': None,
                    'pdf_url': f'https://arxiv.org/pdf/{arxiv_id}.pdf',
                    'arxiv_url': f'https://arxiv.org/abs/{arxiv_id}'
                }
                db_manager.save_arxiv_paper(minimal_paper)
        
        # Create the relationship
        db_manager.save_hypothesis_paper_reference(
            hypothesis_id=hypothesis_id,
            arxiv_id=arxiv_id,
            reference_type=reference_type,
            added_by="user",
            relevance_score=relevance_score,
            extraction_method="manual_link"
        )
        
        # Log the action
        db_manager.log_message(
            message=f"Paper {arxiv_id} linked to hypothesis {hypothesis_id} as {reference_type}",
            level="INFO",
            session_id=session_id,
            module="api",
            metadata={
                "hypothesis_id": hypothesis_id,
                "arxiv_id": arxiv_id,
                "reference_type": reference_type,
                "relevance_score": relevance_score,
                "action": "manual_link"
            }
        )
        
        logger.info(f"Linked paper {arxiv_id} to hypothesis {hypothesis_id} in session {session_id}")
        
        return {
            "message": "Paper successfully linked to hypothesis",
            "session_id": session_id,
            "hypothesis_id": hypothesis_id,
            "arxiv_id": arxiv_id,
            "reference_type": reference_type,
            "relevance_score": relevance_score,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking paper {arxiv_id} to hypothesis {hypothesis_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to link paper to hypothesis: {str(e)}")

###############################################################################
# Database Management Endpoints
###############################################################################

@app.post("/migrate/results")
def migrate_results_endpoint():
    """Migrates data from results folder to database."""
    try:
        logger.info("Starting results folder migration to database")
        migrate_results_folder("results")
        logger.info("Results folder migration completed successfully")
        return {"message": "Results folder successfully migrated to database"}
    except Exception as e:
        logger.error(f"Error during results migration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")

@app.get("/sessions")
def list_recent_sessions():
    """Lists recent research sessions from the database."""
    try:
        from .database import get_db_manager
        db_manager = get_db_manager()
        sessions = db_manager.get_recent_sessions()
        logger.info(f"Retrieved {len(sessions)} recent sessions")
        return {"sessions": sessions}
    except Exception as e:
        logger.error(f"Error retrieving recent sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve sessions: {str(e)}")

@app.get("/sessions/{session_id}")
def get_session_details(session_id: str):
    """Gets detailed information for a specific session."""
    try:
        from .database import get_db_manager
        db_manager = get_db_manager()
        
        # Get session info
        session_info = db_manager.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        # Get session hypotheses
        hypotheses = db_manager.get_session_hypotheses(session_id)
        
        # Convert hypotheses to dict format for JSON serialization
        hypotheses_dict = [h.to_dict() for h in hypotheses]
        
        logger.info(f"Retrieved details for session {session_id}: {len(hypotheses)} hypotheses")
        return {
            "session_info": session_info,
            "hypotheses": hypotheses_dict,
            "total_hypotheses": len(hypotheses)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session details for {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve session details: {str(e)}")

@app.get("/sessions/{session_id}/export")
def export_session_data(session_id: str):
    """Exports all data for a specific session."""
    try:
        from .database import get_db_manager
        db_manager = get_db_manager()
        
        # Check if session exists
        session_info = db_manager.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        # Export session data
        export_data = db_manager.export_session_data(session_id)
        
        logger.info(f"Exported data for session {session_id}")
        return export_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting session data for {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export session data: {str(e)}")

###############################################################################
# LLM Analytics API Endpoints
###############################################################################

@app.get("/sessions/{session_id}/llm/analytics")
def get_session_llm_analytics(session_id: str):
    """Returns LLM usage analytics for a session."""
    try:
        from .database import get_db_manager
        db_manager = get_db_manager()
        
        # Verify session exists
        session_info = db_manager.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        
        analytics = db_manager.get_session_llm_analytics(session_id)
        logger.info(f"Retrieved LLM analytics for session {session_id}")
        
        return {
            "session_id": session_id,
            "analytics": analytics
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving LLM analytics for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve LLM analytics: {str(e)}")

@app.get("/llm/models")
def get_all_models_with_pricing():
    """Lists all available models with pricing information from the database."""
    try:
        from .database import get_db_manager
        db_manager = get_db_manager()
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT model_name, provider, prompt_price_per_1k_tokens, 
                       completion_price_per_1k_tokens, context_window, 
                       max_output_tokens, last_updated
                FROM llm_model_pricing
                ORDER BY provider, model_name
            ''')
            
            models = []
            for row in cursor.fetchall():
                model_data = dict(row)
                models.append(model_data)
        
        logger.info(f"Retrieved {len(models)} models with pricing information")
        
        return {
            "models": models,
            "total_models": len(models)
        }
        
    except Exception as e:
        logger.error(f"Error retrieving models with pricing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve models: {str(e)}")

@app.post("/llm/models/{model_name}/pricing")
def update_model_pricing(model_name: str, pricing_data: Dict):
    """Updates pricing for a specific model."""
    try:
        from .database import get_db_manager
        
        # Validate required fields
        required_fields = ["prompt_price_per_1k", "completion_price_per_1k"]
        for field in required_fields:
            if field not in pricing_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate pricing values
        if pricing_data["prompt_price_per_1k"] < 0 or pricing_data["completion_price_per_1k"] < 0:
            raise HTTPException(status_code=400, detail="Pricing values must be non-negative")
        
        # Extract pricing parameters
        prompt_price = float(pricing_data["prompt_price_per_1k"])
        completion_price = float(pricing_data["completion_price_per_1k"])
        provider = pricing_data.get("provider", "openrouter")
        context_window = pricing_data.get("context_window")
        max_output_tokens = pricing_data.get("max_output_tokens")
        
        # Convert to int if provided
        if context_window is not None:
            context_window = int(context_window)
        if max_output_tokens is not None:
            max_output_tokens = int(max_output_tokens)
        
        # Update pricing using the model_pricing module function
        db_manager = get_db_manager()
        db_manager.save_model_pricing(
            model_name=model_name,
            provider=provider,
            prompt_price_per_1k=prompt_price,
            completion_price_per_1k=completion_price,
            context_window=context_window,
            max_output_tokens=max_output_tokens
        )
        
        logger.info(f"Updated pricing for model {model_name}")
        
        return {
            "message": f"Pricing for model '{model_name}' updated successfully",
            "model_name": model_name,
            "pricing": {
                "provider": provider,
                "prompt_price_per_1k": prompt_price,
                "completion_price_per_1k": completion_price,
                "context_window": context_window,
                "max_output_tokens": max_output_tokens
            },
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid pricing data: {str(e)}")
    except Exception as e:
        logger.error(f"Error updating pricing for model {model_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update model pricing: {str(e)}")

@app.get("/llm/performance")
def get_overall_llm_performance():
    """Gets overall LLM performance metrics across all sessions."""
    try:
        from .database import get_db_manager
        db_manager = get_db_manager()
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get overall performance metrics across all sessions
            cursor.execute('''
                SELECT model_name, call_type,
                       SUM(total_calls) as total_calls,
                       SUM(successful_calls) as successful_calls,
                       SUM(failed_calls) as failed_calls,
                       SUM(retry_calls) as retry_calls,
                       SUM(rate_limited_calls) as rate_limited_calls,
                       SUM(total_tokens) as total_tokens,
                       SUM(total_cost_usd) as total_cost_usd,
                       AVG(avg_response_time_ms) as avg_response_time_ms,
                       MIN(min_response_time_ms) as min_response_time_ms,
                       MAX(max_response_time_ms) as max_response_time_ms
                FROM llm_performance_metrics
                GROUP BY model_name, call_type
                ORDER BY total_calls DESC
            ''')
            performance_metrics = [dict(row) for row in cursor.fetchall()]
            
            # Get cost breakdown by model across all sessions
            cursor.execute('''
                SELECT model_name, 
                       SUM(api_cost_usd) as total_cost,
                       COUNT(*) as total_calls,
                       SUM(total_tokens) as total_tokens,
                       AVG(response_time_ms) as avg_response_time,
                       COUNT(DISTINCT session_id) as sessions_used
                FROM llm_calls
                WHERE success = 1
                GROUP BY model_name
                ORDER BY total_cost DESC
            ''')
            cost_breakdown = [dict(row) for row in cursor.fetchall()]
            
            # Get error analysis across all sessions
            cursor.execute('''
                SELECT model_name, error_message, COUNT(*) as error_count
                FROM llm_calls
                WHERE success = 0
                GROUP BY model_name, error_message
                ORDER BY error_count DESC
                LIMIT 20
            ''')
            error_analysis = [dict(row) for row in cursor.fetchall()]
            
            # Get daily usage trends (last 30 days)
            cursor.execute('''
                SELECT DATE(timestamp) as date,
                       COUNT(*) as total_calls,
                       SUM(api_cost_usd) as daily_cost,
                       SUM(total_tokens) as daily_tokens
                FROM llm_calls
                WHERE timestamp >= date('now', '-30 days')
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            ''')
            daily_trends = [dict(row) for row in cursor.fetchall()]
            
            # Calculate summary statistics
            total_calls = sum(pm['total_calls'] for pm in performance_metrics)
            total_cost = sum(cb['total_cost'] for cb in cost_breakdown)
            total_tokens = sum(cb['total_tokens'] for cb in cost_breakdown)
            total_sessions = len(set(cb['sessions_used'] for cb in cost_breakdown))
            
            # Get top performing models by success rate
            cursor.execute('''
                SELECT model_name,
                       SUM(successful_calls) * 100.0 / SUM(total_calls) as success_rate,
                       SUM(total_calls) as total_calls
                FROM llm_performance_metrics
                WHERE total_calls > 0
                GROUP BY model_name
                HAVING total_calls >= 10
                ORDER BY success_rate DESC, total_calls DESC
                LIMIT 10
            ''')
            top_models = [dict(row) for row in cursor.fetchall()]
        
        logger.info("Retrieved overall LLM performance metrics")
        
        return {
            "summary": {
                "total_calls": total_calls,
                "total_cost_usd": total_cost,
                "total_tokens": total_tokens,
                "unique_sessions": total_sessions,
                "unique_models": len(cost_breakdown)
            },
            "performance_metrics": performance_metrics,
            "cost_breakdown": cost_breakdown,
            "error_analysis": error_analysis,
            "daily_trends": daily_trends,
            "top_performing_models": top_models
        }
        
    except Exception as e:
        logger.error(f"Error retrieving overall LLM performance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve LLM performance metrics: {str(e)}")

@app.post("/llm/initialize-pricing")
def initialize_default_pricing():
    """Initializes default model pricing in the database."""
    try:
        from .model_pricing import initialize_model_pricing, DEFAULT_MODEL_PRICING
        
        # Use the initialize function from model_pricing module
        initialize_model_pricing()
        
        logger.info(f"Initialized default pricing for {len(DEFAULT_MODEL_PRICING)} models")
        
        return {
            "message": f"Successfully initialized default pricing for {len(DEFAULT_MODEL_PRICING)} models",
            "models_initialized": list(DEFAULT_MODEL_PRICING.keys()),
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error initializing default pricing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to initialize default pricing: {str(e)}")

###############################################################################
# Database Browser Web Interface
###############################################################################

@app.get("/dashboard")
async def database_dashboard():
    """Main database dashboard - browse all stored information"""
    html_content = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Co-Scientist Database Dashboard</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: #333;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.95);
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                backdrop-filter: blur(10px);
            }
            .header {
                text-align: center;
                margin-bottom: 40px;
                padding-bottom: 20px;
                border-bottom: 3px solid #667eea;
            }
            .header h1 {
                color: #2c3e50;
                margin: 0;
                font-size: 2.5em;
                font-weight: 300;
            }
            .header p {
                color: #7f8c8d;
                font-size: 1.1em;
                margin: 10px 0 0 0;
            }
            .nav-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 25px;
                margin-bottom: 40px;
            }
            .nav-card {
                background: white;
                padding: 25px;
                border-radius: 12px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                transition: all 0.3s ease;
                cursor: pointer;
                border: 2px solid transparent;
            }
            .nav-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                border-color: #667eea;
            }
            .nav-card h3 {
                color: #2c3e50;
                margin: 0 0 10px 0;
                font-size: 1.3em;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .nav-card p {
                color: #7f8c8d;
                margin: 0 0 15px 0;
                line-height: 1.5;
            }
            .nav-card .features {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            .nav-card .features li {
                color: #27ae60;
                margin: 5px 0;
                padding-left: 20px;
                position: relative;
            }
            .nav-card .features li:before {
                content: "✓";
                position: absolute;
                left: 0;
                color: #27ae60;
                font-weight: bold;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .stat-card {
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            }
            .stat-number {
                font-size: 2em;
                font-weight: bold;
                margin: 10px 0;
            }
            .stat-label {
                font-size: 0.9em;
                opacity: 0.9;
            }
            .quick-access {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                margin-top: 30px;
            }
            .quick-access h3 {
                margin: 0 0 15px 0;
                color: #2c3e50;
            }
            .quick-links {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
            }
            .quick-link {
                background: #3498db;
                color: white;
                padding: 8px 15px;
                border-radius: 20px;
                text-decoration: none;
                font-size: 0.9em;
                transition: background 0.3s ease;
            }
            .quick-link:hover {
                background: #2980b9;
                text-decoration: none;
                color: white;
            }
            .loading {
                text-align: center;
                padding: 20px;
                color: #7f8c8d;
            }
            @media (max-width: 768px) {
                .container { padding: 15px; }
                .nav-grid { grid-template-columns: 1fr; }
                .stats-grid { grid-template-columns: repeat(2, 1fr); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🗄️ AI Co-Scientist Database Dashboard</h1>
                <p>Browse and analyze all stored research data, sessions, and performance metrics</p>
            </div>
            
            <div id="stats-container" class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" id="total-sessions">-</div>
                    <div class="stat-label">Research Sessions</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="total-hypotheses">-</div>
                    <div class="stat-label">Hypotheses Generated</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="total-papers">-</div>
                    <div class="stat-label">arXiv Papers Accessed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="total-llm-calls">-</div>
                    <div class="stat-label">LLM API Calls</div>
                </div>
            </div>
            
            <div class="nav-grid">
                <div class="nav-card" onclick="window.location.href='/dashboard/sessions'">
                    <h3>📊 Research Sessions</h3>
                    <p>Browse all research sessions with detailed analytics and export capabilities</p>
                    <ul class="features">
                        <li>Session timeline and progress</li>
                        <li>Hypothesis evolution tracking</li>
                        <li>Performance metrics</li>
                        <li>Data export options</li>
                    </ul>
                </div>
                
                <div class="nav-card" onclick="window.location.href='/dashboard/hypotheses'">
                    <h3>💡 Hypothesis Explorer</h3>
                    <p>Explore all generated hypotheses with filtering and search capabilities</p>
                    <ul class="features">
                        <li>Advanced search and filtering</li>
                        <li>ELO score rankings</li>
                        <li>Reference tracking</li>
                        <li>Evolution relationships</li>
                    </ul>
                </div>
                
                <div class="nav-card" onclick="window.location.href='/dashboard/arxiv'">
                    <h3>📚 arXiv Analytics</h3>
                    <p>Comprehensive analysis of literature integration and paper usage</p>
                    <ul class="features">
                        <li>Paper access statistics</li>
                        <li>Search pattern analysis</li>
                        <li>Category distribution</li>
                        <li>Citation relationships</li>
                    </ul>
                </div>
                
                <div class="nav-card" onclick="window.location.href='/dashboard/llm'">
                    <h3>🤖 LLM Performance</h3>
                    <p>Monitor LLM API usage, costs, and performance across all models</p>
                    <ul class="features">
                        <li>Cost analysis and tracking</li>
                        <li>Response time monitoring</li>
                        <li>Error rate analysis</li>
                        <li>Token usage optimization</li>
                    </ul>
                </div>
                
                <div class="nav-card" onclick="window.location.href='/dashboard/tournaments'">
                    <h3>⚔️ Tournament Results</h3>
                    <p>Analyze hypothesis ranking battles and ELO score evolution</p>
                    <ul class="features">
                        <li>ELO score trends</li>
                        <li>Tournament history</li>
                        <li>Ranking analytics</li>
                        <li>Performance comparisons</li>
                    </ul>
                </div>
                
                <div class="nav-card" onclick="window.location.href='/dashboard/system'">
                    <h3>⚙️ System Analytics</h3>
                    <p>System-wide performance monitoring and health metrics</p>
                    <ul class="features">
                        <li>System logs analysis</li>
                        <li>Performance trends</li>
                        <li>Error monitoring</li>
                        <li>Usage statistics</li>
                    </ul>
                </div>
            </div>
            
            <div class="quick-access">
                <h3>🚀 Quick Access</h3>
                <div class="quick-links">
                    <a href="/sessions" class="quick-link">API: List Sessions</a>
                    <a href="/llm/models" class="quick-link">API: Model Pricing</a>
                    <a href="/arxiv/test" class="quick-link">arXiv Search Test</a>
                    <a href="/migrate/results" class="quick-link">Migrate Results</a>
                    <a href="/llm/initialize-pricing" class="quick-link">Initialize Pricing</a>
                    <a href="/dashboard/export" class="quick-link">Export All Data</a>
                </div>
            </div>
        </div>

        <script>
            async function loadDashboardStats() {
                try {
                    // Load basic statistics
                    const [sessionsResp, llmResp] = await Promise.all([
                        fetch('/sessions'),
                        fetch('/llm/performance')
                    ]);
                    
                    if (sessionsResp.ok) {
                        const sessionsData = await sessionsResp.json();
                        document.getElementById('total-sessions').textContent = sessionsData.sessions.length;
                    }
                    
                    if (llmResp.ok) {
                        const llmData = await llmResp.json();
                        document.getElementById('total-llm-calls').textContent = llmData.summary.total_calls.toLocaleString();
                        document.getElementById('total-hypotheses').textContent = llmData.summary.total_sessions * 5; // Estimate
                        document.getElementById('total-papers').textContent = '1000+'; // Placeholder
                    }
                } catch (error) {
                    console.error('Error loading dashboard stats:', error);
                    // Leave placeholders as is
                }
            }
            
            // Load stats when page loads
            loadDashboardStats();
        </script>
    </body>
    </html>
    '''
    return responses.HTMLResponse(content=html_content)

@app.get("/dashboard/sessions")
async def sessions_dashboard():
    """Comprehensive sessions browser dashboard with filtering, search, and analytics"""
    html_content = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Research Sessions Browser - AI Co-Scientist</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: #333;
            }
            .container {
                max-width: 1600px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.95);
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                backdrop-filter: blur(10px);
            }
            .header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 3px solid #667eea;
            }
            .header-left h1 {
                color: #2c3e50;
                margin: 0;
                font-size: 2.2em;
                font-weight: 300;
            }
            .header-left p {
                color: #7f8c8d;
                margin: 5px 0 0 0;
                font-size: 1.1em;
            }
            .back-btn {
                background: #3498db;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                text-decoration: none;
                font-size: 0.9em;
                transition: background 0.3s ease;
                cursor: pointer;
            }
            .back-btn:hover {
                background: #2980b9;
                text-decoration: none;
                color: white;
            }
            .filters-section {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 25px;
                display: flex;
                flex-wrap: wrap;
                gap: 15px;
                align-items: center;
            }
            .filter-group {
                display: flex;
                flex-direction: column;
                gap: 5px;
            }
            .filter-group label {
                font-size: 0.9em;
                color: #555;
                font-weight: 500;
            }
            .filter-group input, .filter-group select {
                padding: 8px 12px;
                border: 1px solid #ddd;
                border-radius: 6px;
                font-size: 0.9em;
                min-width: 150px;
            }
            .search-input {
                min-width: 250px !important;
            }
            .filter-actions {
                margin-left: auto;
                display: flex;
                gap: 10px;
            }
            .btn {
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 0.9em;
                transition: all 0.3s ease;
                text-decoration: none;
                display: inline-block;
                text-align: center;
            }
            .btn-primary { background: #3498db; color: white; }
            .btn-primary:hover { background: #2980b9; }
            .btn-secondary { background: #95a5a6; color: white; }
            .btn-secondary:hover { background: #7f8c8d; }
            .btn-success { background: #27ae60; color: white; }
            .btn-success:hover { background: #229954; }
            .btn-danger { background: #e74c3c; color: white; }
            .btn-danger:hover { background: #c0392b; }
            .btn-sm {
                padding: 6px 12px;
                font-size: 0.8em;
            }
            .stats-bar {
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                padding: 15px 20px;
                border-radius: 8px;
                margin-bottom: 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .stats-item {
                text-align: center;
            }
            .stats-number {
                font-size: 1.5em;
                font-weight: bold;
                margin-bottom: 5px;
            }
            .stats-label {
                font-size: 0.9em;
                opacity: 0.9;
            }
            .sessions-table {
                background: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }
            .table-header {
                background: #34495e;
                color: white;
                padding: 15px 20px;
                font-weight: 600;
                display: grid;
                grid-template-columns: 150px 1fr 120px 100px 100px 120px 180px;
                gap: 15px;
                align-items: center;
            }
            .table-row {
                padding: 15px 20px;
                border-bottom: 1px solid #eee;
                display: grid;
                grid-template-columns: 150px 1fr 120px 100px 100px 120px 180px;
                gap: 15px;
                align-items: center;
                transition: background 0.2s ease;
            }
            .table-row:hover {
                background: #f8f9fa;
            }
            .table-row:last-child {
                border-bottom: none;
            }
            .session-id {
                font-family: monospace;
                background: #ecf0f1;
                padding: 4px 8px;
                border-radius: 4px;
                cursor: pointer;
                color: #3498db;
                text-decoration: none;
                font-size: 0.9em;
            }
            .session-id:hover {
                background: #d5dbdb;
                text-decoration: none;
                color: #2980b9;
            }
            .goal-description {
                font-size: 0.9em;
                line-height: 1.4;
                max-height: 40px;
                overflow: hidden;
                text-overflow: ellipsis;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
            }
            .status-badge {
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 0.8em;
                font-weight: 500;
                text-align: center;
            }
            .status-active {
                background: #d5f4e6;
                color: #27ae60;
            }
            .status-completed {
                background: #dae8fc;
                color: #3498db;
            }
            .status-inactive {
                background: #f8d7da;
                color: #e74c3c;
            }
            .cost-display {
                font-family: monospace;
                font-size: 0.9em;
                color: #27ae60;
                font-weight: 500;
            }
            .actions-cell {
                display: flex;
                gap: 5px;
                flex-wrap: wrap;
            }
            .loading-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.5);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 1000;
            }
            .loading-spinner {
                background: white;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
            }
            .spinner {
                border: 4px solid #f3f3f3;
                border-top: 4px solid #3498db;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 0 auto 10px;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .error-message {
                background: #f8d7da;
                color: #721c24;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                border: 1px solid #f5c6cb;
            }
            .empty-state {
                text-align: center;
                padding: 50px 20px;
                color: #7f8c8d;
            }
            .empty-state h3 {
                margin-bottom: 10px;
                font-size: 1.3em;
            }
            @media (max-width: 1200px) {
                .table-header, .table-row {
                    grid-template-columns: 120px 1fr 100px 80px 80px 100px 150px;
                    gap: 10px;
                }
                .filters-section {
                    flex-direction: column;
                    align-items: stretch;
                }
                .filter-actions {
                    margin-left: 0;
                    margin-top: 10px;
                }
            }
            @media (max-width: 768px) {
                .container { padding: 15px; }
                .header { flex-direction: column; gap: 15px; }
                .stats-bar { flex-direction: column; gap: 15px; }
                .table-header, .table-row {
                    grid-template-columns: 1fr;
                    gap: 5px;
                    text-align: left;
                }
                .actions-cell {
                    justify-content: flex-start;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <h1>📊 Research Sessions Browser</h1>
                    <p>Browse, filter, and analyze all research sessions with comprehensive analytics</p>
                </div>
                <a href="/dashboard" class="back-btn">← Back to Dashboard</a>
            </div>
            
            <div class="filters-section">
                <div class="filter-group">
                    <label for="search-input">Search Sessions</label>
                    <input type="text" id="search-input" class="search-input" placeholder="Search by research goal description...">
                </div>
                <div class="filter-group">
                    <label for="date-from">Date From</label>
                    <input type="date" id="date-from">
                </div>
                <div class="filter-group">
                    <label for="date-to">Date To</label>
                    <input type="date" id="date-to">
                </div>
                <div class="filter-group">
                    <label for="status-filter">Status</label>
                    <select id="status-filter">
                        <option value="">All Statuses</option>
                        <option value="active">Active</option>
                        <option value="completed">Completed</option>
                        <option value="inactive">Inactive</option>
                    </select>
                </div>
                <div class="filter-actions">
                    <button class="btn btn-primary" onclick="applyFilters()">Apply Filters</button>
                    <button class="btn btn-secondary" onclick="clearFilters()">Clear</button>
                    <button class="btn btn-success" onclick="exportAllSessions()">Export All</button>
                </div>
            </div>
            
            <div class="stats-bar" id="stats-bar">
                <div class="stats-item">
                    <div class="stats-number" id="total-sessions-count">-</div>
                    <div class="stats-label">Total Sessions</div>
                </div>
                <div class="stats-item">
                    <div class="stats-number" id="filtered-sessions-count">-</div>
                    <div class="stats-label">Filtered Sessions</div>
                </div>
                <div class="stats-item">
                    <div class="stats-number" id="total-hypotheses-count">-</div>
                    <div class="stats-label">Total Hypotheses</div>
                </div>
                <div class="stats-item">
                    <div class="stats-number" id="total-cost">-</div>
                    <div class="stats-label">Total Cost</div>
                </div>
                <div class="stats-item">
                    <div class="stats-number" id="avg-session-cost">-</div>
                    <div class="stats-label">Avg Session Cost</div>
                </div>
            </div>
            
            <div class="sessions-table">
                <div class="table-header">
                    <div>Session ID</div>
                    <div>Research Goal</div>
                    <div>Created Date</div>
                    <div>Hypotheses</div>
                    <div>Status</div>
                    <div>Total Cost</div>
                    <div>Actions</div>
                </div>
                <div id="sessions-tbody">
                    <!-- Sessions will be loaded here -->
                </div>
            </div>
        </div>
        
        <div id="loading-overlay" class="loading-overlay" style="display: none;">
            <div class="loading-spinner">
                <div class="spinner"></div>
                <p>Loading sessions data...</p>
            </div>
        </div>

        <script>
            let allSessions = [];
            let filteredSessions = [];
            let sessionAnalytics = {};

            async function loadSessionsData() {
                showLoading(true);
                try {
                    // Load sessions list
                    const sessionsResponse = await fetch('/sessions');
                    if (!sessionsResponse.ok) {
                        throw new Error(`Failed to load sessions: ${sessionsResponse.status}`);
                    }
                    const sessionsData = await sessionsResponse.json();
                    allSessions = sessionsData.sessions || [];
                    
                    // Load analytics for each session
                    await loadSessionAnalytics();
                    
                    // Apply initial filters and render
                    applyFilters();
                    
                } catch (error) {
                    console.error('Error loading sessions:', error);
                    showError('Failed to load sessions data. Please try again.');
                } finally {
                    showLoading(false);
                }
            }

            async function loadSessionAnalytics() {
                const analyticsPromises = allSessions.map(async session => {
                    try {
                        const response = await fetch(`/sessions/${session.session_id}/llm/analytics`);
                        if (response.ok) {
                            const data = await response.json();
                            sessionAnalytics[session.session_id] = data.analytics;
                        }
                    } catch (error) {
                        console.error(`Failed to load analytics for session ${session.session_id}:`, error);
                    }
                });
                
                await Promise.all(analyticsPromises);
            }

            function applyFilters() {
                const searchTerm = document.getElementById('search-input').value.toLowerCase();
                const dateFrom = document.getElementById('date-from').value;
                const dateTo = document.getElementById('date-to').value;
                const statusFilter = document.getElementById('status-filter').value;
                
                filteredSessions = allSessions.filter(session => {
                    // Search filter
                    if (searchTerm && !session.research_goal.toLowerCase().includes(searchTerm)) {
                        return false;
                    }
                    
                    // Date filters
                    const sessionDate = new Date(session.created_at).toISOString().split('T')[0];
                    if (dateFrom && sessionDate < dateFrom) return false;
                    if (dateTo && sessionDate > dateTo) return false;
                    
                    // Status filter
                    if (statusFilter) {
                        const sessionStatus = determineSessionStatus(session);
                        if (sessionStatus !== statusFilter) return false;
                    }
                    
                    return true;
                });
                
                renderSessions();
                updateStats();
            }

            function clearFilters() {
                document.getElementById('search-input').value = '';
                document.getElementById('date-from').value = '';
                document.getElementById('date-to').value = '';
                document.getElementById('status-filter').value = '';
                applyFilters();
            }

            function renderSessions() {
                const tbody = document.getElementById('sessions-tbody');
                
                if (filteredSessions.length === 0) {
                    tbody.innerHTML = `
                        <div class="empty-state">
                            <h3>No sessions found</h3>
                            <p>Try adjusting your filters or search criteria.</p>
                        </div>
                    `;
                    return;
                }
                
                tbody.innerHTML = filteredSessions.map(session => {
                    const analytics = sessionAnalytics[session.session_id] || {};
                    const status = determineSessionStatus(session);
                    const statusClass = `status-${status}`;
                    const totalCost = analytics.total_cost || 0;
                    const hypothesesCount = session.hypothesis_count || 0;
                    
                    return `
                        <div class="table-row">
                            <div>
                                <a href="/sessions/${session.session_id}" class="session-id" title="View session details">
                                    ${session.session_id.substring(0, 12)}...
                                </a>
                            </div>
                            <div class="goal-description" title="${escapeHtml(session.research_goal)}">
                                ${escapeHtml(session.research_goal)}
                            </div>
                            <div>${formatDate(session.created_at)}</div>
                            <div>${hypothesesCount}</div>
                            <div>
                                <span class="status-badge ${statusClass}">
                                    ${status.charAt(0).toUpperCase() + status.slice(1)}
                                </span>
                            </div>
                            <div class="cost-display">$${totalCost.toFixed(4)}</div>
                            <div class="actions-cell">
                                <a href="/sessions/${session.session_id}" class="btn btn-primary btn-sm">Details</a>
                                <button class="btn btn-success btn-sm" onclick="exportSession('${session.session_id}')">Export</button>
                                <button class="btn btn-secondary btn-sm" onclick="viewAnalytics('${session.session_id}')">Analytics</button>
                            </div>
                        </div>
                    `;
                }).join('');
            }

            function updateStats() {
                const totalHypotheses = filteredSessions.reduce((sum, session) => 
                    sum + (session.hypothesis_count || 0), 0);
                const totalCost = filteredSessions.reduce((sum, session) => {
                    const analytics = sessionAnalytics[session.session_id] || {};
                    return sum + (analytics.total_cost || 0);
                }, 0);
                const avgCost = filteredSessions.length > 0 ? totalCost / filteredSessions.length : 0;
                
                document.getElementById('total-sessions-count').textContent = allSessions.length;
                document.getElementById('filtered-sessions-count').textContent = filteredSessions.length;
                document.getElementById('total-hypotheses-count').textContent = totalHypotheses;
                document.getElementById('total-cost').textContent = `$${totalCost.toFixed(4)}`;
                document.getElementById('avg-session-cost').textContent = `$${avgCost.toFixed(4)}`;
            }

            function determineSessionStatus(session) {
                // Simple status determination logic - can be enhanced
                const now = new Date();
                const sessionDate = new Date(session.created_at);
                const daysSinceCreated = (now - sessionDate) / (1000 * 60 * 60 * 24);
                
                if (session.session_id === getCurrentSessionId()) {
                    return 'active';
                } else if (daysSinceCreated < 1) {
                    return 'active';
                } else if (session.hypothesis_count > 0) {
                    return 'completed';
                } else {
                    return 'inactive';
                }
            }

            function getCurrentSessionId() {
                // This would need to be implemented based on your session tracking
                return null; // Placeholder
            }

            async function exportSession(sessionId) {
                try {
                    showLoading(true);
                    const response = await fetch(`/sessions/${sessionId}/export`);
                    if (!response.ok) {
                        throw new Error(`Export failed: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `session_${sessionId}_export.json`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    
                } catch (error) {
                    console.error('Export failed:', error);
                    showError('Failed to export session data.');
                } finally {
                    showLoading(false);
                }
            }

            async function exportAllSessions() {
                try {
                    showLoading(true);
                    const exportData = {
                        exported_at: new Date().toISOString(),
                        total_sessions: filteredSessions.length,
                        sessions: filteredSessions,
                        analytics: sessionAnalytics
                    };
                    
                    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `all_sessions_export_${new Date().toISOString().split('T')[0]}.json`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    
                } catch (error) {
                    console.error('Export failed:', error);
                    showError('Failed to export sessions data.');
                } finally {
                    showLoading(false);
                }
            }

            function viewAnalytics(sessionId) {
                // Open analytics in new window/tab
                window.open(`/sessions/${sessionId}/llm/analytics`, '_blank');
            }

            function formatDate(dateString) {
                const date = new Date(dateString);
                return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            }

            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }

            function showLoading(show) {
                document.getElementById('loading-overlay').style.display = show ? 'flex' : 'none';
            }

            function showError(message) {
                const container = document.querySelector('.container');
                const existingError = container.querySelector('.error-message');
                if (existingError) {
                    existingError.remove();
                }
                
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error-message';
                errorDiv.textContent = message;
                container.insertBefore(errorDiv, container.firstChild.nextSibling);
                
                // Auto-remove after 5 seconds
                setTimeout(() => {
                    if (errorDiv.parentNode) {
                        errorDiv.remove();
                    }
                }, 5000);
            }

            // Event listeners
            document.getElementById('search-input').addEventListener('input', 
                debounce(() => applyFilters(), 300));

            function debounce(func, wait) {
                let timeout;
                return function executedFunction(...args) {
                    const later = () => {
                        clearTimeout(timeout);
                        func(...args);
                    };
                    clearTimeout(timeout);
                    timeout = setTimeout(later, wait);
                };
            }

            // Initialize on page load
            window.addEventListener('load', loadSessionsData);
        </script>
    </body>
    </html>
    '''
    return responses.HTMLResponse(content=html_content)

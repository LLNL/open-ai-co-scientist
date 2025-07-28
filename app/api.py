import datetime
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
from .utils import logger, is_huggingface_space, get_deployment_environment # Use the configured logger
from .tools.arxiv_search import ArxivSearchTool, get_categories_for_field
# from .config import config # Config might be needed if endpoints use it directly

###############################################################################
# FastAPI Application Setup
###############################################################################

app = FastAPI(title="AI Co-Scientist - Hypothesis Evolution System", version="1.0")

# --- Global State (Consider alternatives for production) ---
global_context = ContextMemory()
supervisor = SupervisorAgent()
current_research_goal: Optional[ResearchGoal] = None
available_models: List[str] = [] # Global list to store model IDs

# --- Startup Event ---
@app.on_event("startup")
async def fetch_available_models():
    """Fetches available models from OpenRouter on startup."""
    global available_models
    
    # Detect deployment environment
    deployment_env = get_deployment_environment()
    is_hf_spaces = is_huggingface_space()
    
    logger.info(f"Detected deployment environment: {deployment_env}")
    logger.info(f"Is Hugging Face Spaces: {is_hf_spaces}")
    logger.info("Fetching available models from OpenRouter...")
    
    # Define cost-effective models for production deployment
    ALLOWED_MODELS_PRODUCTION = [
        "google/gemini-2.0-flash-001",
        "google/gemini-flash-1.5",
        "openai/gpt-3.5-turbo",
        "anthropic/claude-3-haiku",
        "meta-llama/llama-3.1-8b-instruct",
        "mistralai/mistral-7b-instruct",
        "microsoft/phi-3-mini-4k-instruct"
    ]
    
    try:
        response = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        response.raise_for_status()
        models_data = response.json().get("data", [])
        
        # Extract all model IDs
        all_models = sorted([model.get("id") for model in models_data if model.get("id")])
        
        # Apply filtering based on environment
        if is_hf_spaces:
            # Filter to only cost-effective models in HF Spaces
            available_models = [model for model in all_models if model in ALLOWED_MODELS_PRODUCTION]
            logger.info(f"Hugging Face Spaces: Filtered to {len(available_models)} cost-effective models")
            logger.info(f"Allowed models: {available_models}")
        else:
            # Use all models in local/development environment
            available_models = all_models
            logger.info(f"Local/Development: Using all {len(available_models)} models")
            logger.info(f"Available models list (first 10): {available_models[:10]}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch models from OpenRouter: {e}")
        # Fallback to safe defaults in production
        if is_hf_spaces:
            available_models = ALLOWED_MODELS_PRODUCTION
            logger.info(f"Using fallback production models: {available_models}")
        else:
            available_models = []
    except Exception as e:
        logger.error(f"An unexpected error occurred during model fetching: {e}", exc_info=True)
        available_models = ALLOWED_MODELS_PRODUCTION if is_hf_spaces else []


# --- Static Files ---
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("Mounted static files directory.")
except RuntimeError as e:
     logger.warning(f"Could not mount static directory (may not exist): {e}")


###############################################################################
# API Endpoints
###############################################################################

@app.post("/research_goal", response_model=dict)
def set_research_goal(goal: ResearchGoalRequest):
    """Sets the research goal and resets the context."""
    global current_research_goal, global_context
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
        global_context = ContextMemory()
        logger.info("Global context reset successfully.")
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

    logger.info("--- Endpoint /research_goal END ---")
    return {"message": "Research goal successfully set. Ready to run cycles."}

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

@app.get("/deployment_status")
def get_deployment_status():
    """Returns the current deployment environment status."""
    deployment_env = get_deployment_environment()
    is_hf_spaces = is_huggingface_space()
    
    return {
        "environment": deployment_env,
        "is_huggingface_spaces": is_hf_spaces,
        "models_filtered": is_hf_spaces,
        "available_models_count": len(available_models)
    }

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
        arxiv_tool = ArxivSearchTool(max_results=search_request.max_results or 10)
        
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
        <div id="deployment-status" style="background-color: #e8f4fd; border: 1px solid #bee5eb; padding: 10px; margin-bottom: 20px; border-radius: 5px; font-size: 14px;">
            <strong>🔧 Deployment Status:</strong> <span id="deployment-info">Loading...</span>
        </div>
        
        <h1>Welcome to the AI Co-Scientist System</h1>
        <p>Set your research goal and run cycles to generate hypotheses.</p>

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
                <input type="number" id="num_hypotheses" name="num_hypotheses" min="1" max="10" placeholder="3" style="width: 50px; margin-bottom: 10px;"><br>

                <label for="generation_temperature">Generation Temperature (Creativity):</label>
                <input type="range" id="generation_temperature" name="generation_temperature" min="0.1" max="1.0" step="0.1" value="0.7" style="width: 90%; margin-bottom: 5px;" oninput="this.nextElementSibling.value = this.value">
                <output>0.7</output><br>

                <label for="reflection_temperature">Reflection Temperature (Analysis):</label>
                <input type="range" id="reflection_temperature" name="reflection_temperature" min="0.1" max="1.0" step="0.1" value="0.5" style="width: 90%; margin-bottom: 5px;" oninput="this.nextElementSibling.value = this.value">
                <output>0.5</output><br>

                <label for="elo_k_factor">Elo K-Factor (Ranking Sensitivity):</label>
                <input type="number" id="elo_k_factor" name="elo_k_factor" min="1" max="100" placeholder="32" style="width: 50px; margin-bottom: 10px;"><br>

                <label for="top_k_hypotheses">Top K for Evolution:</label>
                <input type="number" id="top_k_hypotheses" name="top_k_hypotheses" min="2" max="5" placeholder="2" style="width: 50px; margin-bottom: 10px;"><br>
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
            const defaultModel = "google/gemini-flash-1.5"; // Or get from config if possible
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

            // Function to fetch and display deployment status
            async function fetchDeploymentStatus() {
                try {
                    const response = await fetch('/deployment_status');
                    if (response.ok) {
                        const status = await response.json();
                        const deploymentInfo = document.getElementById('deployment-info');
                        
                        let statusText = `Running in ${status.environment}`;
                        let statusColor = '#e8f4fd'; // Default blue
                        
                        if (status.is_huggingface_spaces) {
                            statusText += ` | Models filtered for cost control (${status.available_models_count} available)`;
                            statusColor = '#fff3cd'; // Yellow for production
                            document.getElementById('deployment-status').style.backgroundColor = statusColor;
                            document.getElementById('deployment-status').style.borderColor = '#ffeaa7';
                        } else {
                            statusText += ` | All models available (${status.available_models_count} total)`;
                            statusColor = '#d1ecf1'; // Light blue for development
                            document.getElementById('deployment-status').style.backgroundColor = statusColor;
                            document.getElementById('deployment-status').style.borderColor = '#bee5eb';
                        }
                        
                        deploymentInfo.textContent = statusText;
                        console.log('Deployment status loaded:', status);
                    } else {
                        document.getElementById('deployment-info').textContent = 'Unable to determine deployment status';
                    }
                } catch (error) {
                    console.error('Error fetching deployment status:', error);
                    document.getElementById('deployment-info').textContent = 'Error loading deployment status';
                }
            }

            // Populate dropdown and fetch deployment status when the page loads
            document.addEventListener('DOMContentLoaded', function() {
                populateModelDropdown();
                fetchDeploymentStatus();
            });


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
    # Replace the placeholder with the actual JSON string before returning
    html_content = html_content.replace("###MODELS_JSON###", models_json_string)
    return responses.HTMLResponse(content=html_content)

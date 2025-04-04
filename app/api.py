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
    HypothesisResponse, Hypothesis # Hypothesis needed by ContextMemory
)
from .agents import SupervisorAgent
from .utils import logger # Use the configured logger
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
            h2, h3, h4, h5 { margin-top: 1.5em; }
            ul { padding-left: 20px; }
            li { margin-bottom: 10px; }
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
    # Replace the placeholder with the actual JSON string before returning
    html_content = html_content.replace("###MODELS_JSON###", models_json_string)
    return responses.HTMLResponse(content=html_content)

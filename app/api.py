import datetime
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
# These globals make the app stateful, which can be problematic for scaling.
# For simple cases or demos, it might be acceptable.
# Alternatives: Dependency Injection with classes, external storage (DB, Redis).
global_context = ContextMemory()
supervisor = SupervisorAgent()
current_research_goal: Optional[ResearchGoal] = None

# --- Static Files ---
# Assuming a 'static' directory exists at the project root
# If it should be inside 'app', adjust the path: StaticFiles(directory="app/static")
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
    logger.info(f"Received new research goal: {goal.description}")
    current_research_goal = ResearchGoal(goal.description, goal.constraints)
    # Reset context for the new goal
    global_context = ContextMemory()
    logger.info("Global context reset for new research goal.")
    # Note: Logger setup per request might be better handled via middleware or dependency
    # timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # log_filename = f"log_{timestamp}.txt" # This will create many log files
    # setup_logger(log_filename) # Consider if logger needs reconfiguration per goal

    return {"message": "Research goal successfully set. Ready to run cycles."}

@app.post("/run_cycle", response_model=Dict) # Return type might be more specific, e.g., CycleResponse
def run_cycle_endpoint():
    """Runs a single cycle of the AI Co-Scientist workflow."""
    global current_research_goal, global_context, supervisor
    if not current_research_goal:
        logger.error("Run cycle called before setting research goal.")
        raise HTTPException(status_code=400, detail="No research goal set. Please POST to /research_goal first.")

    logger.info(f"Running cycle {global_context.iteration_number + 1} for goal: {current_research_goal.description}")
    try:
        # The supervisor agent now handles the full cycle logic
        cycle_details = supervisor.run_cycle(current_research_goal, global_context)
        logger.info(f"Cycle {global_context.iteration_number} complete.") # Iteration number was incremented in run_cycle
        return cycle_details
    except Exception as e:
        logger.error(f"Error during cycle execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal error occurred during cycle execution: {e}")


@app.get("/hypotheses", response_model=List[HypothesisResponse])
def list_hypotheses_endpoint():
    """Retrieves a list of all currently active hypotheses."""
    global global_context
    active_hypotheses = global_context.get_active_hypotheses()
    logger.info(f"Retrieving {len(active_hypotheses)} active hypotheses.")
    # Convert Hypothesis objects to dicts using .to_dict() before creating HypothesisResponse
    # Pydantic should handle the conversion if the fields match, but explicit is safer
    return [HypothesisResponse(**h.to_dict()) for h in active_hypotheses]

@app.get("/")
async def root_endpoint():
    """Serves the main HTML page."""
    logger.debug("Serving root HTML page.")
    # HTML content remains largely the same, ensure JS function names match
    return responses.HTMLResponse(content="""
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
        <button onclick="submitResearchGoal()">Submit Research Goal</button>
        <button onclick="runCycle()">Run Next Cycle</button> <!-- Added manual run button -->

        <h2>Results</h2>
        <div id="results"><p>Submit a research goal to begin.</p></div>

        <h2>Errors</h2>
        <div id="errors"></div>

        <script>
            let currentIteration = 0; // Keep track of the iteration

            async function submitResearchGoal() {
                const researchGoal = document.getElementById('researchGoal').value;
                if (!researchGoal.trim()) {
                    document.getElementById('errors').innerHTML = '<p>Please enter a research goal.</p>';
                    return;
                }
                document.getElementById('results').innerHTML = '<p>Setting research goal...</p>';
                document.getElementById('errors').innerHTML = '';
                currentIteration = 0; // Reset iteration count

                try {
                    const response = await fetch('/research_goal', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ description: researchGoal })
                    });

                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                    }

                    const data = await response.json();
                    document.getElementById('results').innerHTML = `<p>${data.message}</p><p>Running first cycle...</p>`;
                    runCycle(); // Automatically run the first cycle
                } catch (error) {
                    console.error('Error submitting research goal:', error);
                    document.getElementById('errors').innerHTML = `<p>Error: ${error.message}</p>`;
                    document.getElementById('results').innerHTML = ''; // Clear results area on error
                }
            }

            async function runCycle() {
                document.getElementById('errors').innerHTML = ''; // Clear previous errors
                const resultsDiv = document.getElementById('results');
                // Append status message if it's not the first auto-run
                if (currentIteration > 0 || !resultsDiv.innerHTML.includes("Running first cycle")) {
                     resultsDiv.innerHTML += `<p>Running cycle ${currentIteration + 1}...</p>`;
                }


                try {
                    const response = await fetch('/run_cycle', { method: 'POST' });

                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                    }

                    const data = await response.json();
                    currentIteration = data.iteration; // Update iteration count

                    let resultsHTML = `<h3>Iteration: ${data.iteration}</h3>`;
                    let graphData = null; // To store graph data for initialization later

                    const stepExplanations = { /* ... explanations ... */ }; // Keep explanations if desired

                    for (const stepName in data.steps) {
                        if (data.steps.hasOwnProperty(stepName)) {
                            const step = data.steps[stepName];
                            resultsHTML += `<h4>Step: ${stepName}</h4>`;
                            // Add explanation if available
                            // if (stepExplanations[stepName]) { resultsHTML += `<p>${stepExplanations[stepName]}</p>`; }

                            if (step.hypotheses && step.hypotheses.length > 0) {
                                resultsHTML += `<h5>Hypotheses:</h5><ul>`;
                                // Sort hypotheses by Elo score descending for display
                                step.hypotheses.sort((a, b) => b.elo_score - a.elo_score).forEach(hypo => {
                                    resultsHTML += \`<li>
                                        <strong>\${hypo.title}</strong> (ID: \${hypo.id}, Elo: \${hypo.elo_score.toFixed(2)})<br>\`;
                                    if (hypo.parent_ids && hypo.parent_ids.length > 0) {
                                        resultsHTML += \`<em>Parents: \${hypo.parent_ids.join(', ')}</em><br>\`;
                                    }
                                    resultsHTML += \`<p>\${hypo.text}</p>\`;
                                    if (hypo.novelty_review) { resultsHTML += \`<p>Novelty: \${hypo.novelty_review}</p>\`; }
                                    if (hypo.feasibility_review){ resultsHTML += \`<p>Feasibility: \${hypo.feasibility_review}</p>\`; }
                                    // Add comments and references if needed
                                    resultsHTML += \`</li>\`;
                                });
                                resultsHTML += `</ul>`;
                            } else if (step.hypotheses) {
                                 resultsHTML += `<p>No hypotheses generated or active in this step.</p>`;
                            }

                            // Handle graph data specifically from the 'proximity' step
                            if (stepName === "proximity" && step.nodes_str && step.edges_str) {
                                resultsHTML += \`<h5>Hypothesis Similarity Graph:</h5>\`;
                                resultsHTML += \`<div id="mynetwork"></div>\`; // Container for the graph
                                resultsHTML += \`<div class="graph-explanation"><p>
                                    <b>How to read:</b> Nodes are hypotheses. Edges show similarity > 0.2.
                                </p></div>\`;
                                // Store data for initialization after HTML is rendered
                                graphData = { nodesStr: step.nodes_str, edgesStr: step.edges_str };
                            } else if (stepName === "proximity" && step.adjacency_graph) {
                                 resultsHTML += \`<p>Adjacency Graph (raw): \${JSON.stringify(step.adjacency_graph)}</p>\`;
                            }
                        }
                    }

                    // Display meta-review
                    if (data.meta_review) {
                         resultsHTML += `<h4>Meta-Review:</h4>`;
                         if (data.meta_review.meta_review_critique && data.meta_review.meta_review_critique.length > 0) {
                              resultsHTML += `<h5>Critique:</h5><ul>\${data.meta_review.meta_review_critique.map(item => \`<li>\${item}</li>\`).join('')}</ul>`;
                         }
                         if (data.meta_review.research_overview && data.meta_review.research_overview.suggested_next_steps.length > 0) {
                              resultsHTML += `<h5>Suggested Next Steps:</h5><ul>\${data.meta_review.research_overview.suggested_next_steps.map(item => \`<li>\${item}</li>\`).join('')}</ul>`;
                         }
                    }

                    // Update the results div content
                    resultsDiv.innerHTML = resultsHTML;

                    // Initialize the graph *after* its container is in the DOM
                    if (graphData) {
                        initializeGraph(graphData.nodesStr, graphData.edgesStr);
                    }

                } catch (error) {
                    console.error('Error running cycle:', error);
                    document.getElementById('errors').innerHTML = `<p>Error during cycle ${currentIteration + 1}: ${error.message}</p>`;
                     // Optionally clear or update resultsDiv on error
                     resultsDiv.innerHTML += `<p>Cycle failed. See errors above.</p>`;
                }
            }

            // Function to initialize the Vis.js graph (remains the same)
            function initializeGraph(nodesStr, edgesStr) {
                // Check if vis is loaded
                if (typeof vis === 'undefined') {
                    console.error("Vis.js library not loaded!");
                    document.getElementById('errors').innerHTML += '<p>Error: Vis.js library failed to load.</p>';
                    return;
                }
                 const container = document.getElementById('mynetwork');
                 if (!container) {
                     console.error("Graph container #mynetwork not found in DOM!");
                     return; // Don't proceed if container doesn't exist
                 }

                try {
                    // Use Function constructor for safe parsing of JS object strings
                    const nodesArray = nodesStr ? new Function(\`return [\${nodesStr}]\`)() : [];
                    const edgesArray = edgesStr ? new Function(\`return [\${edgesStr}]\`)() : [];

                    var nodes = new vis.DataSet(nodesArray);
                    var edges = new vis.DataSet(edgesArray);

                    var data = { nodes: nodes, edges: edges };
                    var options = { /* ... vis options ... */
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
                    document.getElementById('errors').innerHTML += `<p>Error initializing graph: ${e.message}</p>`;
                    // Optionally clear the graph container on error
                    container.innerHTML = '<p style="color:red;">Could not render graph.</p>';
                }
            }
        </script>
    </body>
    </html>
    """)

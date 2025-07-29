import gradio as gr
import os
import json
import time
from typing import List, Dict, Optional, Tuple
import logging

# Import the existing app components
from app.models import ResearchGoal, ContextMemory
from app.agents import SupervisorAgent
from app.utils import logger, is_huggingface_space, get_deployment_environment, filter_free_models
from app.tools.arxiv_search import ArxivSearchTool
import requests

# Global state for the Gradio app
global_context = ContextMemory()
supervisor = SupervisorAgent()
current_research_goal: Optional[ResearchGoal] = None
available_models: List[str] = []

# Configure logging for Gradio
logging.basicConfig(level=logging.INFO)

def fetch_available_models():
    """Fetch available models from OpenRouter with environment-based filtering."""
    global available_models
    
    # Detect deployment environment
    deployment_env = get_deployment_environment()
    is_hf_spaces = is_huggingface_space()
    
    logger.info(f"Detected deployment environment: {deployment_env}")
    logger.info(f"Is Hugging Face Spaces: {is_hf_spaces}")
    
    try:
        response = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        response.raise_for_status()
        models_data = response.json().get("data", [])
        
        # Extract all model IDs
        all_models = sorted([model.get("id") for model in models_data if model.get("id")])
        
        # Create filtered free models list
        free_models = filter_free_models(all_models)
        
        # Apply filtering based on environment
        if is_hf_spaces:
            # Use only free models for Hugging Face Spaces
            available_models = free_models
            logger.info(f"Hugging Face Spaces: Filtered to {len(available_models)} free models")
        else:
            # Use all models in local/development environment
            available_models = all_models
            logger.info(f"Local/Development: Using all {len(available_models)} models")
            
    except Exception as e:
        logger.error(f"Failed to fetch models from OpenRouter: {e}")
        # Fallback to safe defaults
        if is_hf_spaces:
            # Use a known free model as fallback
            available_models = ["google/gemini-2.0-flash-001:free"]
        else:
            available_models = ["google/gemini-2.0-flash-001"]
    
    return available_models

def get_deployment_status():
    """Get deployment status information."""
    deployment_env = get_deployment_environment()
    is_hf_spaces = is_huggingface_space()
    
    if is_hf_spaces:
        status = f"🚀 Running in {deployment_env} | Models filtered for cost control ({len(available_models)} available)"
        color = "orange"
    else:
        status = f"💻 Running in {deployment_env} | All models available ({len(available_models)} total)"
        color = "blue"
    
    return status, color

def set_research_goal(
    description: str,
    llm_model: str = None,
    num_hypotheses: int = 3,
    generation_temperature: float = 0.7,
    reflection_temperature: float = 0.5,
    elo_k_factor: int = 32,
    top_k_hypotheses: int = 2
) -> Tuple[str, str]:
    """Set the research goal and initialize the system."""
    global current_research_goal, global_context
    
    if not description.strip():
        return "❌ Error: Please enter a research goal.", ""
    
    try:
        # Create research goal with settings
        current_research_goal = ResearchGoal(
            description=description.strip(),
            constraints={},
            llm_model=llm_model if llm_model and llm_model != "-- Select Model --" else None,
            num_hypotheses=num_hypotheses,
            generation_temperature=generation_temperature,
            reflection_temperature=reflection_temperature,
            elo_k_factor=elo_k_factor,
            top_k_hypotheses=top_k_hypotheses
        )
        
        # Reset context
        global_context = ContextMemory()
        
        logger.info(f"Research goal set: {description}")
        logger.info(f"Settings: model={current_research_goal.llm_model}, num={current_research_goal.num_hypotheses}")
        
        status_msg = f"✅ Research goal set successfully!\n\n**Goal:** {description}\n**Model:** {current_research_goal.llm_model or 'Default'}\n**Hypotheses per cycle:** {num_hypotheses}"
        
        return status_msg, "Ready to run first cycle. Click 'Run Cycle' to begin."
        
    except Exception as e:
        error_msg = f"❌ Error setting research goal: {str(e)}"
        logger.error(error_msg)
        return error_msg, ""

def run_cycle() -> Tuple[str, str, str]:
    """Run a single research cycle with detailed step logging for debugging."""
    import datetime

    global current_research_goal, global_context, supervisor

    if not current_research_goal:
        return "❌ Error: No research goal set. Please set a research goal first.", "", ""

    # Prepare log file
    log_dir = "results"
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(log_dir, f"app_log_{timestamp}.txt")
    with open(log_file, "w") as f:
        f.write(f"LOGGING FOR THIS GOAL: {current_research_goal.description}\n")
        f.write(f"--- Endpoint /run_cycle START ---\n")

    try:
        iteration = global_context.iteration_number + 1
        logger.info(f"Running cycle {iteration}")

        # Run the cycle
        cycle_details = supervisor.run_cycle(current_research_goal, global_context)

        # Log all steps and hypotheses
        steps = cycle_details.get("steps", {})
        with open(log_file, "a") as f:
            for step_name, step_data in steps.items():
                hypos = step_data.get("hypotheses", [])
                f.write(f"Step: {step_name} | {len(hypos)} hypotheses\n")
                for h in hypos:
                    f.write(f"  - ID: {h.get('id')} | Title: {h.get('title')} | Elo: {h.get('elo_score', 'N/A')}\n")

        # Format results for display (also logs final rankings)
        results_html = format_cycle_results(cycle_details, log_file=log_file)

        # Get references
        references_html = get_references_html(cycle_details)

        # Status message
        status_msg = f"✅ Cycle {iteration} completed successfully! Log: {log_file}"

        return status_msg, results_html, references_html

    except Exception as e:
        error_msg = f"❌ Error during cycle execution: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg, "", ""

def format_cycle_results(cycle_details: Dict, log_file: str = None) -> str:
    """Format cycle results as HTML with expandable sections. Optionally log final rankings to log_file."""
    html = f"<h2>🔬 Iteration {cycle_details.get('iteration', 'Unknown')}</h2>"
    
    # Process steps in order
    steps = cycle_details.get('steps', {})
    # Display steps in the order they appear in the steps dict (preserves backend execution order)
    for step_name, step_data in steps.items():
        step_title = {
            'generation': '🎯 Generation',
            'reflection': '🔍 Reflection',
            'ranking': '📊 Ranking',
            'evolution': '🧬 Evolution',
            'reflection_evolved': '🔍 Reflection (Evolved)',
            'ranking_final': '📊 Final Ranking',
            'proximity': '🔗 Proximity Analysis',
            'meta_review': '📋 Meta-Review'
        }.get(step_name, step_name.title())
        
        html += f"""
        <details style="margin: 15px 0; border: 1px solid #ddd; border-radius: 8px; padding: 10px;">
            <summary style="font-weight: bold; font-size: 1.1em; cursor: pointer; padding: 5px;">
                {step_title}
            </summary>
            <div style="margin-top: 10px; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
        """
        
        # Step-specific content
        if step_name == 'generation':
            hypotheses = step_data.get('hypotheses', [])
            html += f"<p><strong>Generated {len(hypotheses)} new hypotheses:</strong></p>"
            for i, hypo in enumerate(hypotheses):
                html += f"""
                <div style="border-left: 3px solid #28a745; padding-left: 10px; margin: 10px 0;">
                    <h5>#{i+1}: {hypo.get('title', 'Untitled')} (ID: {hypo.get('id', 'Unknown')})</h5>
                    <p>{hypo.get('text', 'No description')}</p>
                </div>
                """
                
        elif step_name in ['reflection', 'reflection_evolved']:
            hypotheses = step_data.get('hypotheses', [])
            html += f"<p><strong>Reviewed {len(hypotheses)} hypotheses:</strong></p>"
            for hypo in hypotheses:
                html += f"""
                <div style="border-left: 3px solid #17a2b8; padding-left: 10px; margin: 10px 0;">
                    <h5>{hypo.get('title', 'Untitled')} (ID: {hypo.get('id', 'Unknown')})</h5>
                    <p><strong>Novelty:</strong> {hypo.get('novelty_review', 'Not assessed')} | 
                       <strong>Feasibility:</strong> {hypo.get('feasibility_review', 'Not assessed')}</p>
                    {f"<p><strong>Comments:</strong> {hypo.get('comments', 'No comments')}</p>" if hypo.get('comments') else ""}
                </div>
                """
                
        elif step_name.startswith('ranking'):
            hypotheses = step_data.get('hypotheses', [])
            if hypotheses:
                # Sort by Elo score
                sorted_hypotheses = sorted(hypotheses, key=lambda h: h.get('elo_score', 0), reverse=True)
                html += f"<p><strong>Ranking results ({len(hypotheses)} hypotheses):</strong></p>"
                html += "<ol>"
                for hypo in sorted_hypotheses:
                    html += f"""
                    <li style="margin: 5px 0;">
                        <strong>{hypo.get('title', 'Untitled')}</strong> (ID: {hypo.get('id', 'Unknown')}) 
                        - Elo: {hypo.get('elo_score', 0):.2f}
                    </li>
                    """
                html += "</ol>"
                
        elif step_name == 'evolution':
            hypotheses = step_data.get('hypotheses', [])
            html += f"<p><strong>Evolved {len(hypotheses)} new hypotheses by combining top performers:</strong></p>"
            for hypo in hypotheses:
                html += f"""
                <div style="border-left: 3px solid #ffc107; padding-left: 10px; margin: 10px 0;">
                    <h5>{hypo.get('title', 'Untitled')} (ID: {hypo.get('id', 'Unknown')})</h5>
                    <p>{hypo.get('text', 'No description')}</p>
                </div>
                """
                
        elif step_name == 'proximity':
            adjacency_graph = step_data.get('adjacency_graph', {})
            nodes = step_data.get('nodes', [])
            edges = step_data.get('edges', [])
            
            # Debug logging
            logger.info(f"Proximity data - adjacency_graph keys: {list(adjacency_graph.keys()) if adjacency_graph else 'None'}")
            logger.info(f"Proximity data - nodes count: {len(nodes) if nodes else 0}")
            logger.info(f"Proximity data - edges count: {len(edges) if edges else 0}")
            
            if adjacency_graph:
                num_hypotheses = len(adjacency_graph)
                html += f"<p><strong>Similarity Analysis:</strong></p>"
                html += f"<p>Analyzed relationships between {num_hypotheses} hypotheses</p>"
                
                # Calculate and display average similarity
                all_similarities = []
                for hypo_id, connections in adjacency_graph.items():
                    for conn in connections:
                        all_similarities.append(conn.get('similarity', 0))
                
                if all_similarities:
                    avg_sim = sum(all_similarities) / len(all_similarities)
                    html += f"<p>Average similarity: {avg_sim:.3f}</p>"
                    html += f"<p>Total connections analyzed: {len(all_similarities)}</p>"
                
                # Show top similar pairs
                similarity_pairs = []
                for hypo_id, connections in adjacency_graph.items():
                    for conn in connections:
                        similarity_pairs.append((hypo_id, conn.get('other_id'), conn.get('similarity', 0)))
                
                # Sort by similarity and show top 5
                similarity_pairs.sort(key=lambda x: x[2], reverse=True)
                if similarity_pairs:
                    html += "<h6>Top Similar Hypothesis Pairs:</h6><ul>"
                    for i, (id1, id2, sim) in enumerate(similarity_pairs[:5]):
                        html += f"<li>{id1} ↔ {id2}: {sim:.3f}</li>"
                    html += "</ul>"
                else:
                    html += "<p>No proximity data available.</p>"
                    
        elif step_name == 'meta_review':
            # Debug: log the actual meta_review data structure
            import sys
            print("DEBUG: meta_review step_data =", step_data, file=sys.stderr)
            assert isinstance(step_data, dict), "meta_review step_data is not a dict"
            # Accept both direct dict or nested under 'meta_review'
            if "meta_review" in step_data and isinstance(step_data["meta_review"], dict):
                meta_review = step_data["meta_review"]
            else:
                meta_review = step_data
            assert "meta_review_critique" in meta_review, f"meta_review_critique missing in meta_review: {meta_review}"
            assert "research_overview" in meta_review, f"research_overview missing in meta_review: {meta_review}"
            # Critique section
            if meta_review.get('meta_review_critique'):
                html += "<h5>Critique:</h5><ul>"
                for critique in meta_review['meta_review_critique']:
                    html += f"<li>{critique}</li>"
                html += "</ul>"
            # Top ranked hypotheses section
            top_hypos = meta_review.get('research_overview', {}).get('top_ranked_hypotheses', [])
            assert isinstance(top_hypos, list), f"top_ranked_hypotheses is not a list: {top_hypos}"
            if top_hypos:
                html += "<h5>Top Ranked Hypotheses:</h5>"
                for i, hypo in enumerate(top_hypos):
                    html += f"""
                    <div style="border-left: 3px solid #28a745; padding-left: 10px; margin: 10px 0;">
                        <h6>#{i+1}: {hypo.get('title', 'Untitled')}</h6>
                        <p><strong>ID:</strong> {hypo.get('id', 'Unknown')} | 
                           <strong>Elo Score:</strong> {hypo.get('elo_score', 0):.2f}</p>
                        <p><strong>Description:</strong> {hypo.get('text', 'No description')}</p>
                        <p><strong>Novelty:</strong> {hypo.get('novelty_review', 'Not assessed')} | 
                           <strong>Feasibility:</strong> {hypo.get('feasibility_review', 'Not assessed')}</p>
                    </div>
                    """
            # Suggested next steps section
            if meta_review.get('research_overview', {}).get('suggested_next_steps'):
                html += "<h5>Suggested Next Steps:</h5><ul>"
                for step in meta_review['research_overview']['suggested_next_steps']:
                    html += f"<li>{step}</li>"
                html += "</ul>"
        
        # Add timing information if available
        if step_data.get('duration'):
            html += f"<p><em>Duration: {step_data['duration']:.2f}s</em></p>"
            
        html += "</div></details>"
    
    # Final summary section - always expanded
    # Prefer ranking steps, else fallback to step with most hypotheses
    final_hypotheses = []
    final_step = None
    step_order = ['ranking_final', 'ranking2', 'ranking', 'ranking1']
    for step_name in step_order:
        if step_name in steps and steps[step_name].get("hypotheses"):
            final_hypotheses = steps[step_name]["hypotheses"]
            final_step = step_name
            break

    # Fallback: use step with most hypotheses if no ranking step exists
    if not final_hypotheses:
        max_count = 0
        for sname, sdata in steps.items():
            hypos = sdata.get("hypotheses", [])
            if len(hypos) > max_count:
                final_hypotheses = hypos
                final_step = sname
                max_count = len(hypos)

    # Assertions: final list should not be empty and no duplicate IDs (only for ranking steps)
    ranking_steps = ['ranking_final', 'ranking2', 'ranking', 'ranking1']
    if final_hypotheses:
        ids = [h.get('id') for h in final_hypotheses]
        if final_step in ranking_steps:
            assert len(ids) == len(set(ids)), "Duplicate hypothesis IDs found in final rankings!"
        assert len(final_hypotheses) > 0, "Final hypothesis list is empty!"

        # Sort by Elo score if present, else by ID
        if any('elo_score' in h for h in final_hypotheses):
            final_hypotheses = sorted(final_hypotheses, key=lambda h: h.get('elo_score', 0), reverse=True)
        else:
            final_hypotheses = sorted(final_hypotheses, key=lambda h: h.get('id', ''))

        html += """
        <div style="margin: 20px 0; padding: 15px; border: 2px solid #28a745; border-radius: 8px; background-color: #f8fff8;">
            <h3>🏆 Final Rankings - Top Hypotheses</h3>
        """
        if final_step not in ranking_steps:
            html += '<p style="color: #e67e22;">Warning: No ranking step found. Showing hypotheses from the latest available step ("{}"). These may not be ranked.</p>'.format(final_step)

        # Log final rankings if log_file is provided
        if log_file:
            with open(log_file, "a") as f:
                f.write(f"--- Final Rankings Section (step: {final_step}) ---\n")
                for i, hypo in enumerate(final_hypotheses[:10]):
                    f.write(f"  #{i+1}: ID: {hypo.get('id')} | Title: {hypo.get('title')} | Elo: {hypo.get('elo_score', 'N/A')}\n")

        for i, hypo in enumerate(final_hypotheses[:10]):  # Show top 10
            rank_color = "#28a745" if i < 3 else "#17a2b8" if i < 6 else "#6c757d"
            html += f"""
            <div style="border-left: 4px solid {rank_color}; padding: 15px; margin: 10px 0; background-color: white; border-radius: 5px;">
                <h4>#{i+1}: {hypo.get('title', 'Untitled')}</h4>
                <p><strong>ID:</strong> {hypo.get('id', 'Unknown')} | 
                   <strong>Elo Score:</strong> {hypo.get('elo_score', 0):.2f}</p>
                <p><strong>Description:</strong> {hypo.get('text', 'No description')}</p>
                <p><strong>Novelty:</strong> {hypo.get('novelty_review', 'Not assessed')} | 
                   <strong>Feasibility:</strong> {hypo.get('feasibility_review', 'Not assessed')}</p>
            </div>
            """
        
        html += "</div>"
    else:
        html += """
        <div style="margin: 20px 0; padding: 15px; border: 2px solid #e74c3c; border-radius: 8px; background-color: #fff5f5;">
            <h3>🏆 Final Rankings - Top Hypotheses</h3>
            <p style="color: #e74c3c;">No hypotheses available for final ranking. This may indicate an error in the workflow.</p>
        </div>
        """
        # Log missing final rankings if log_file is provided
        if log_file:
            with open(log_file, "a") as f:
                f.write("--- Final Rankings Section: No hypotheses available for final ranking. ---\n")
    
    return html

def get_references_html(cycle_details: Dict) -> str:
    """Get references HTML for the cycle."""
    try:
        # Search for arXiv papers related to the research goal
        if current_research_goal and current_research_goal.description:
            arxiv_tool = ArxivSearchTool(max_results=5)
            papers = arxiv_tool.search_papers(
                query=current_research_goal.description,
                max_results=5,
                sort_by="relevance"
            )
            
            if papers:
                html = "<h3>📚 Related arXiv Papers</h3>"
                for paper in papers:
                    html += f"""
                    <div style="border: 1px solid #e0e0e0; padding: 15px; margin: 10px 0; border-radius: 8px; background-color: #fafafa;">
                        <h4>{paper.get('title', 'Untitled')}</h4>
                        <p><strong>Authors:</strong> {', '.join(paper.get('authors', [])[:5])}</p>
                        <p><strong>arXiv ID:</strong> {paper.get('arxiv_id', 'Unknown')} | 
                           <strong>Published:</strong> {paper.get('published', 'Unknown')}</p>
                        <p><strong>Abstract:</strong> {paper.get('abstract', 'No abstract')[:300]}...</p>
                        <p>
                            <a href="{paper.get('arxiv_url', '#')}" target="_blank">📄 View on arXiv</a> | 
                            <a href="{paper.get('pdf_url', '#')}" target="_blank">📁 Download PDF</a>
                        </p>
                    </div>
                    """
                return html
            else:
                return "<p>No related arXiv papers found.</p>"
        else:
            return "<p>No research goal set for reference search.</p>"
            
    except Exception as e:
        logger.error(f"Error fetching references: {e}")
        return f"<p>Error loading references: {str(e)}</p>"

def create_gradio_interface():
    """Create the Gradio interface."""
    
    # Fetch models on startup
    fetch_available_models()
    
    # Get deployment status
    status_text, status_color = get_deployment_status()
    
    with gr.Blocks(
        title="AI Co-Scientist - Hypothesis Evolution System",
        theme=gr.themes.Soft(),
        css="""
        .status-box {
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-weight: bold;
        }
        .orange { background-color: #fff3cd; border: 1px solid #ffeaa7; }
        .blue { background-color: #d1ecf1; border: 1px solid #bee5eb; }
        """
    ) as demo:
        
        # Header
        gr.Markdown("# 🔬 AI Co-Scientist - Hypothesis Evolution System")
        gr.Markdown("Generate, review, rank, and evolve research hypotheses using AI agents.")
        
        # Deployment status
        gr.HTML(f'<div class="status-box {status_color}">🔧 Deployment Status: {status_text}</div>')
        
        # Main interface
        with gr.Row():
            with gr.Column(scale=2):
                # Research goal input
                research_goal_input = gr.Textbox(
                    label="Research Goal",
                    placeholder="Enter your research goal (e.g., 'Develop new methods for increasing the efficiency of solar panels')",
                    lines=3
                )
                
                # Advanced settings
                with gr.Accordion("⚙️ Advanced Settings", open=False):
                    model_dropdown = gr.Dropdown(
                        choices=["-- Select Model --"] + available_models,
                        value="-- Select Model --",
                        label="LLM Model",
                        info="Leave as default to use system default model"
                    )
                    
                    with gr.Row():
                        num_hypotheses = gr.Slider(
                            minimum=1, maximum=10, value=3, step=1,
                            label="Hypotheses per Cycle"
                        )
                        top_k_hypotheses = gr.Slider(
                            minimum=2, maximum=5, value=2, step=1,
                            label="Top K for Evolution"
                        )
                    
                    with gr.Row():
                        generation_temp = gr.Slider(
                            minimum=0.1, maximum=1.0, value=0.7, step=0.1,
                            label="Generation Temperature (Creativity)"
                        )
                        reflection_temp = gr.Slider(
                            minimum=0.1, maximum=1.0, value=0.5, step=0.1,
                            label="Reflection Temperature (Analysis)"
                        )
                    
                    elo_k_factor = gr.Slider(
                        minimum=1, maximum=100, value=32, step=1,
                        label="Elo K-Factor (Ranking Sensitivity)"
                    )
                
                # Single action button
                with gr.Row():
                    run_cycle_btn = gr.Button("🔄 Run Cycle", variant="primary")
                
                # Status display
                status_output = gr.Textbox(
                    label="Status",
                    value="Enter a research goal and click 'Run Cycle' to begin.",
                    interactive=False,
                    lines=3
                )
            
            with gr.Column(scale=1):
                # Instructions
                gr.Markdown("""
                ### 📖 Instructions

                1. **Enter Research Goal**: Describe what you want to research.
                2. **Adjust Settings** (optional): Customize model and parameters.
                3. **Click "Run Cycle"**: The system will set your goal and immediately generate, review, rank, and evolve hypotheses in one step.

                ### 💡 Tips
                - Start with 3-5 hypotheses per cycle
                - Higher generation temperature = more creative ideas
                - Lower reflection temperature = more analytical reviews
                - Each cycle builds on previous results
                """)
        
        # Results section
        with gr.Row():
            with gr.Column():
                results_output = gr.HTML(
                    label="Results",
                    value="<p>Results will appear here after running cycles.</p>"
                )
        
        # References section
        with gr.Row():
            with gr.Column():
                references_output = gr.HTML(
                    label="References",
                    value="<p>Related research papers will appear here.</p>"
                )
        
        # Event handler: single button sets research goal and runs cycle
        def run_full_cycle(
            research_goal,
            llm_model,
            num_hypotheses,
            generation_temp,
            reflection_temp,
            elo_k_factor,
            top_k_hypotheses
        ):
            # Set research goal
            status_msg, _ = set_research_goal(
                research_goal,
                llm_model,
                num_hypotheses,
                generation_temp,
                reflection_temp,
                elo_k_factor,
                top_k_hypotheses
            )
            # Run cycle
            status, results, references = run_cycle()
            # Combine status messages
            return f"{status_msg}\n\n{status}", results, references

        run_cycle_btn.click(
            fn=run_full_cycle,
            inputs=[
                research_goal_input,
                model_dropdown,
                num_hypotheses,
                generation_temp,
                reflection_temp,
                elo_k_factor,
                top_k_hypotheses
            ],
            outputs=[status_output, results_output, references_output]
        )
        
        # Example inputs
        gr.Examples(
            examples=[
                ["Develop new methods for increasing the efficiency of solar panels"],
                ["Create novel approaches to treat Alzheimer's disease"],
                ["Design sustainable materials for construction"],
                ["Improve machine learning model interpretability"],
                ["Develop new quantum computing algorithms"]
            ],
            inputs=[research_goal_input],
            label="Example Research Goals"
        )
    
    return demo

if __name__ == "__main__":
    # Check for API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("⚠️  Warning: OPENROUTER_API_KEY environment variable not set.")
        print("The app will start but may not function properly without an API key.")
    
    # Create and launch the Gradio app
    demo = create_gradio_interface()
    
    # Launch with appropriate settings for HF Spaces
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )

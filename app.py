import gradio as gr
import os
import json
import time
from typing import List, Dict, Optional, Tuple
import logging

# Import the existing app components
from app.models import ResearchGoal, ContextMemory
from app.agents import SupervisorAgent
from app.utils import logger, is_huggingface_space, get_deployment_environment
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
        else:
            # Use all models in local/development environment
            available_models = all_models
            logger.info(f"Local/Development: Using all {len(available_models)} models")
            
    except Exception as e:
        logger.error(f"Failed to fetch models from OpenRouter: {e}")
        # Fallback to safe defaults
        available_models = ALLOWED_MODELS_PRODUCTION if is_hf_spaces else ["google/gemini-2.0-flash-001"]
    
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
    """Run a single research cycle."""
    global current_research_goal, global_context, supervisor
    
    if not current_research_goal:
        return "❌ Error: No research goal set. Please set a research goal first.", "", ""
    
    try:
        iteration = global_context.iteration_number + 1
        logger.info(f"Running cycle {iteration}")
        
        # Run the cycle
        cycle_details = supervisor.run_cycle(current_research_goal, global_context)
        
        # Format results for display
        results_html = format_cycle_results(cycle_details)
        
        # Get references
        references_html = get_references_html(cycle_details)
        
        # Status message
        status_msg = f"✅ Cycle {iteration} completed successfully!"
        
        return status_msg, results_html, references_html
        
    except Exception as e:
        error_msg = f"❌ Error during cycle execution: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg, "", ""

def format_cycle_results(cycle_details: Dict) -> str:
    """Format cycle results as HTML with expandable sections."""
    html = f"<h2>🔬 Iteration {cycle_details.get('iteration', 'Unknown')}</h2>"
    
    # Process steps in order
    steps = cycle_details.get('steps', {})
    step_order = ['generation', 'reflection', 'ranking', 'evolution', 'reflection_evolved', 'ranking_final', 'proximity', 'meta_review']
    
    # Step details with expandable sections
    for step_name in step_order:
        if step_name not in steps:
            continue
            
        step_data = steps[step_name]
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
                
        elif step_name in ['ranking', 'ranking_final']:
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
            nodes_str = step_data.get('nodes_str', '')
            edges_str = step_data.get('edges_str', '')
            
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
                
                # Interactive Graph Visualization
                if nodes_str and edges_str:
                    graph_id = f"graph_{int(time.time() * 1000)}"  # Unique ID for this graph
                    html += f"""
                    <h6>Interactive Similarity Graph:</h6>
                    <div style="margin: 15px 0;">
                        <p><em>Each node represents a hypothesis. Lines show similarity scores (only > 0.2 shown). Click and drag to explore!</em></p>
                        <div id="{graph_id}" style="width: 100%; height: 400px; border: 1px solid #ccc; background-color: #fafafa;"></div>
                    </div>
                    
                    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
                    <script type="text/javascript">
                        (function() {{
                            // Wait for vis.js to load
                            function initGraph() {{
                                if (typeof vis === 'undefined') {{
                                    setTimeout(initGraph, 100);
                                    return;
                                }}
                                
                                var nodes = new vis.DataSet([{nodes_str}]);
                                var edges = new vis.DataSet([{edges_str}]);
                                
                                var container = document.getElementById('{graph_id}');
                                if (!container) {{
                                    console.error('Graph container not found: {graph_id}');
                                    return;
                                }}
                                
                                var data = {{
                                    nodes: nodes,
                                    edges: edges
                                }};
                                
                                var options = {{
                                    nodes: {{
                                        shape: 'circle',
                                        font: {{ size: 14 }},
                                        color: {{
                                            background: '#97C2FC',
                                            border: '#2B7CE9',
                                            highlight: {{
                                                background: '#D2E5FF',
                                                border: '#2B7CE9'
                                            }}
                                        }}
                                    }},
                                    edges: {{
                                        font: {{ size: 12, align: 'middle' }},
                                        color: {{ color: '#848484' }},
                                        smooth: {{
                                            enabled: true,
                                            type: "dynamic"
                                        }}
                                    }},
                                    physics: {{
                                        stabilization: true,
                                        barnesHut: {{
                                            gravitationalConstant: -2000,
                                            centralGravity: 0.3,
                                            springLength: 150,
                                            springConstant: 0.04
                                        }}
                                    }},
                                    interaction: {{
                                        hover: true,
                                        tooltipDelay: 200
                                    }}
                                }};
                                
                                try {{
                                    var network = new vis.Network(container, data, options);
                                    
                                    // Add click event for node information
                                    network.on("click", function (params) {{
                                        if (params.nodes.length > 0) {{
                                            var nodeId = params.nodes[0];
                                            console.log('Clicked node:', nodeId);
                                        }}
                                    }});
                                    
                                }} catch (error) {{
                                    console.error('Error creating network graph:', error);
                                    container.innerHTML = '<p style="padding: 20px; text-align: center; color: #666;">Error loading graph visualization</p>';
                                }}
                            }}
                            
                            initGraph();
                        }})();
                    </script>
                    """
                
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
            meta_review = step_data.get('meta_review', {})
            if meta_review.get('meta_review_critique'):
                html += "<h5>Critique:</h5><ul>"
                for critique in meta_review['meta_review_critique']:
                    html += f"<li>{critique}</li>"
                html += "</ul>"
            
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
    all_hypotheses = []
    for step_name, step_data in steps.items():
        if step_data.get('hypotheses'):
            all_hypotheses.extend(step_data['hypotheses'])
    
    if all_hypotheses:
        # Sort by Elo score
        all_hypotheses.sort(key=lambda h: h.get('elo_score', 0), reverse=True)
        
        html += """
        <div style="margin: 20px 0; padding: 15px; border: 2px solid #28a745; border-radius: 8px; background-color: #f8fff8;">
            <h3>🏆 Final Rankings - Top Hypotheses</h3>
        """
        
        for i, hypo in enumerate(all_hypotheses[:10]):  # Show top 10
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
                
                # Action buttons
                with gr.Row():
                    set_goal_btn = gr.Button("🎯 Set Research Goal", variant="primary")
                    run_cycle_btn = gr.Button("🔄 Run Cycle", variant="secondary")
                
                # Status display
                status_output = gr.Textbox(
                    label="Status",
                    value="Enter a research goal and click 'Set Research Goal' to begin.",
                    interactive=False,
                    lines=3
                )
            
            with gr.Column(scale=1):
                # Instructions
                gr.Markdown("""
                ### 📖 Instructions
                
                1. **Enter Research Goal**: Describe what you want to research
                2. **Adjust Settings** (optional): Customize model and parameters
                3. **Set Goal**: Click to initialize the system
                4. **Run Cycles**: Generate and evolve hypotheses iteratively
                
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
        
        # Event handlers
        set_goal_btn.click(
            fn=set_research_goal,
            inputs=[
                research_goal_input,
                model_dropdown,
                num_hypotheses,
                generation_temp,
                reflection_temp,
                elo_k_factor,
                top_k_hypotheses
            ],
            outputs=[status_output, results_output]
        )
        
        run_cycle_btn.click(
            fn=run_cycle,
            inputs=[],
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

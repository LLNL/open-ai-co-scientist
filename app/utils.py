import logging
import time
import os
import random
import json
from typing import List, Dict
import openai
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Import config loading function and config object
from .config import config, load_config

# --- Logging Setup ---
# Configure a root logger or a specific logger for the app
# Using a basic configuration here, can be enhanced
logging.basicConfig(level=config.get("logging_level", logging.INFO),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("aicoscientist") # Use a specific name for the app logger

# Optional: Add file handler based on config (if needed globally)
# log_filename_base = config.get('log_file_name', 'app')
# timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
# file_handler = logging.FileHandler(f"{log_filename_base}_{timestamp}.txt")
# formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
# file_handler.setFormatter(formatter)
# logger.addHandler(file_handler)

# --- LLM Interaction ---
def call_llm(prompt: str, temperature: float = 0.7) -> str:
    """
    Calls an LLM via the OpenRouter API and returns the response. Handles retries.
    """
    client = OpenAI(
        base_url=config.get("openrouter_base_url"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )
    llm_model = config.get("llm_model")
    max_retries = config.get("max_retries", 3)
    initial_delay = config.get("initial_retry_delay", 1)

    if not llm_model:
        logger.error("LLM model not configured in config.yaml")
        return "Error: LLM model not configured."
    if not client.api_key:
        logger.error("OPENROUTER_API_KEY environment variable not set.")
        return "Error: OpenRouter API key not set."

    last_error_message = "API call failed after multiple retries." # Default error

    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model=llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            if completion.choices and len(completion.choices) > 0:
                return completion.choices[0].message.content or "" # Return empty string if content is None
            else:
                logger.error("No choices in the LLM response: %s", completion)
                last_error_message = f"No choices in the response: {completion}"
                # Continue to retry if possible

        except Exception as e:
            error_str = str(e)
            if "401" in error_str or "No auth credentials found" in error_str:
                logger.error(f"Authentication failed (401 Unauthorized): {e}")
                return (
                    "Authentication with OpenRouter failed (401 Unauthorized). "
                    "Please check that your OPENROUTER_API_KEY environment variable is set and valid "
                    "in the environment where the server is running. No hypotheses can be generated until this is resolved."
                )
            if "Rate limit exceeded" in error_str:
                logger.warning(f"Rate limit exceeded (attempt {attempt + 1}/{max_retries}): {e}")
                last_error_message = f"Rate limit exceeded: {e}"
            else:
                logger.error(f"API call failed (attempt {attempt + 1}/{max_retries}): {e}")
                last_error_message = f"API call failed: {e}"

            if attempt < max_retries - 1:
                wait_time = initial_delay * (2 ** attempt)
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error("Max retries reached. Giving up.")
                break # Exit loop after last attempt

    return f"Error: {last_error_message}" # Return the last recorded error


# --- Environment Detection ---
def is_huggingface_space() -> bool:
    """
    Detect if the application is running in Hugging Face Spaces.
    Returns True if running in HF Spaces, False otherwise.
    """
    # Primary indicators - HF Spaces sets these environment variables
    hf_env_vars = [
        "SPACE_ID",
        "SPACE_AUTHOR_NAME", 
        "SPACES_BUILDKIT_VERSION",
        "HF_HOME"
    ]
    
    for var in hf_env_vars:
        if os.getenv(var):
            logger.info(f"Detected Hugging Face Spaces environment via {var}")
            return True
    
    # Secondary indicator - hostname patterns
    hostname = os.getenv("HOSTNAME", "")
    if "huggingface.co" in hostname.lower():
        logger.info(f"Detected Hugging Face Spaces environment via hostname: {hostname}")
        return True
    
    return False

def get_deployment_environment() -> str:
    """
    Get a string description of the current deployment environment.
    Returns: 'Hugging Face Spaces', 'Local Development', or 'Unknown'
    """
    if is_huggingface_space():
        return "Hugging Face Spaces"
    elif os.getenv("LOCAL_DEV") or not os.getenv("PORT"):
        return "Local Development"
    else:
        return "Unknown"

def filter_free_models(all_models: List[str]) -> List[str]:
    """
    Filters a list of model IDs to include only those with ':free' in their name.
    """
    return [model for model in all_models if ":free" in model]

# --- ID Generation ---
def generate_unique_id(prefix="H") -> str:
    """Generates a unique identifier string."""
    return f"{prefix}{random.randint(1000, 9999)}"


# --- VIS.JS Graph Data Generation ---
def generate_visjs_data(adjacency_graph: Dict) -> Dict[str, list]:
    """Generates node and edge data lists for vis.js graph (for JSON serialization)."""
    nodes = []
    edges = []

    if not isinstance(adjacency_graph, dict):
        logger.error(f"Invalid adjacency_graph type: {type(adjacency_graph)}. Expected dict.")
        return {"nodes": [], "edges": []}

    for node_id, connections in adjacency_graph.items():
        nodes.append({"id": node_id, "label": node_id})
        if isinstance(connections, list):
            for connection in connections:
                if isinstance(connection, dict) and 'similarity' in connection and 'other_id' in connection:
                    similarity_val = connection.get('similarity')
                    if isinstance(similarity_val, (int, float)) and similarity_val > 0.2:
                        edges.append({
                            "from": node_id,
                            "to": connection['other_id'],
                            "label": f"{similarity_val:.2f}",
                            "arrows": "to"
                        })
                else:
                    logger.warning(f"Skipping invalid connection format for node {node_id}: {connection}")
        else:
            logger.warning(f"Skipping invalid connections format for node {node_id}: {connections}")

    return {
        "nodes": nodes,
        "edges": edges
    }

# --- Similarity Calculation ---
_sentence_transformer_model = None

def get_sentence_transformer_model():
    """Loads and returns a singleton instance of the sentence transformer model."""
    global _sentence_transformer_model
    if _sentence_transformer_model is None:
        model_name = config.get('sentence_transformer_model', 'all-MiniLM-L6-v2')
        try:
            logger.info(f"Loading sentence transformer model: {model_name}...")
            _sentence_transformer_model = SentenceTransformer(model_name)
            logger.info("Sentence transformer model loaded successfully.")
        except ImportError:
            logger.error("Failed to import sentence_transformers. Please install it: pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"Failed to load sentence transformer model '{model_name}': {e}")
            raise # Re-raise after logging
    return _sentence_transformer_model

def similarity_score(textA: str, textB: str) -> float:
    """Calculates cosine similarity between two texts using sentence embeddings."""
    try:
        if not textA or not textB:
            logger.warning("Empty string provided to similarity_score.")
            return 0.0

        model = get_sentence_transformer_model()
        if model is None: # Check if model loading failed previously
             return 0.0 # Or handle error appropriately

        embedding_a = model.encode(textA, convert_to_tensor=True)
        embedding_b = model.encode(textB, convert_to_tensor=True)

        # Ensure embeddings are 2D numpy arrays for cosine_similarity
        embedding_a_np = embedding_a.cpu().numpy().reshape(1, -1)
        embedding_b_np = embedding_b.cpu().numpy().reshape(1, -1)

        similarity = cosine_similarity(embedding_a_np, embedding_b_np)[0][0]

        # Clamp the value between 0.0 and 1.0
        similarity = float(np.clip(similarity, 0.0, 1.0))

        # logger.debug(f"Similarity score: {similarity:.4f}") # Use debug level
        return similarity
    except Exception as e:
        logger.error(f"Error calculating similarity score: {e}", exc_info=True) # Log traceback
        return 0.0 # Return 0 on error instead of 0.5

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
def call_llm(prompt: str, temperature: float = 0.7, call_type: str = "unknown", 
            session_id: str = None, hypothesis_id: str = None) -> str:
    """
    Calls an LLM via the OpenRouter API and returns the response. Handles retries and logs performance.
    """
    import time
    start_time = time.time()
    
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

    last_error_message = "API call failed after multiple retries."
    response_content = None
    success = False
    total_retry_count = 0
    rate_limited = False
    
    # Token tracking
    prompt_tokens = None
    completion_tokens = None
    openrouter_request_id = None

    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model=llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            
            # Extract response and usage information
            if completion.choices and len(completion.choices) > 0:
                response_content = completion.choices[0].message.content or ""
                success = True
                
                # Extract token usage if available
                if hasattr(completion, 'usage') and completion.usage:
                    prompt_tokens = completion.usage.prompt_tokens
                    completion_tokens = completion.usage.completion_tokens
                
                # Extract OpenRouter-specific metadata
                if hasattr(completion, 'id'):
                    openrouter_request_id = completion.id
                
                logger.debug(f"LLM call successful: {prompt_tokens} prompt tokens, "
                           f"{completion_tokens} completion tokens")
                break
            else:
                logger.error("No choices in the LLM response: %s", completion)
                last_error_message = f"No choices in the response: {completion}"

        except Exception as e:
            total_retry_count += 1
            error_str = str(e)
            
            if "Rate limit exceeded" in error_str or "rate_limit_exceeded" in error_str.lower():
                rate_limited = True
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
                break

    # Calculate response time
    response_time_ms = (time.time() - start_time) * 1000
    
    # Log to database if session_id is provided
    if session_id:
        try:
            from .database import get_db_manager
            db_manager = get_db_manager()
            
            final_response = response_content if success else f"Error: {last_error_message}"
            
            db_manager.save_llm_call(
                session_id=session_id,
                call_type=call_type,
                model_name=llm_model,
                prompt=prompt,
                response=final_response,
                temperature=temperature,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                response_time_ms=response_time_ms,
                success=success,
                error_message=last_error_message if not success else None,
                retry_count=total_retry_count,
                hypothesis_id=hypothesis_id,
                openrouter_model_id=llm_model,
                openrouter_request_id=openrouter_request_id,
                rate_limited=rate_limited
            )
            
            logger.debug(f"LLM call logged to database: {call_type} call took {response_time_ms:.2f}ms")
            
        except Exception as db_error:
            logger.warning(f"Failed to log LLM call to database: {db_error}")

    # Log performance metrics for monitoring
    logger.info(f"LLM call completed - Type: {call_type}, Model: {llm_model}, "
               f"Success: {success}, Time: {response_time_ms:.2f}ms, "
               f"Tokens: {prompt_tokens}/{completion_tokens}, Retries: {total_retry_count}")

    if success:
        return response_content
    else:
        return f"Error: {last_error_message}"


# --- ID Generation ---
def generate_unique_id(prefix="H") -> str:
    """Generates a unique identifier string."""
    return f"{prefix}{random.randint(1000, 9999)}"


# --- VIS.JS Graph Data Generation ---
def generate_visjs_data(adjacency_graph: Dict) -> Dict[str, str]:
    """Generates node and edge data strings for vis.js graph."""
    nodes = []
    edges = []

    if not isinstance(adjacency_graph, dict):
        logger.error(f"Invalid adjacency_graph type: {type(adjacency_graph)}. Expected dict.")
        return {"nodes_str": "", "edges_str": ""}

    for node_id, connections in adjacency_graph.items():
        nodes.append(f"{{id: '{node_id}', label: '{node_id}'}}")
        if isinstance(connections, list):
            for connection in connections:
                if isinstance(connection, dict) and 'similarity' in connection and 'other_id' in connection:
                    similarity_val = connection.get('similarity')
                    if isinstance(similarity_val, (int, float)) and similarity_val > 0.2:
                        edges.append(f"{{from: '{node_id}', to: '{connection['other_id']}', label: '{similarity_val:.2f}', arrows: 'to'}}")
                    # Optional: Log skipped edges due to low similarity
                    # else:
                    #     logger.debug(f"Skipping edge from {node_id} to {connection['other_id']} due to low/invalid similarity: {similarity_val}")
                else:
                    logger.warning(f"Skipping invalid connection format for node {node_id}: {connection}")
        else:
             logger.warning(f"Skipping invalid connections format for node {node_id}: {connections}")

    nodes_str = ",\n".join(nodes)
    edges_str = ",\n".join(edges)

    return {
        "nodes_str": nodes_str,
        "edges_str": edges_str
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

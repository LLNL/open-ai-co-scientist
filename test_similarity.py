import logging
import sys
import os

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Create a standalone version of the similarity_score function for testing
# This avoids issues with the logger in the main script
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Global variable to store the sentence transformer model
_sentence_transformer_model = None

def get_sentence_transformer_model():
    """
    Returns a singleton instance of the sentence transformer model.
    Loads the model only once to improve performance.
    
    Returns:
        SentenceTransformer: The sentence transformer model.
    """
    global _sentence_transformer_model
    if _sentence_transformer_model is None:
        try:
            logger.info("Loading sentence transformer model...")
            # Using a smaller model for efficiency, can be replaced with larger models for better accuracy
            _sentence_transformer_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Sentence transformer model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load sentence transformer model: {e}")
            raise
    return _sentence_transformer_model

def similarity_score(textA: str, textB: str) -> float:
    """
    Calculates a similarity score between two text strings using sentence embeddings
    and cosine similarity.

    Args:
        textA (str): The first text string.
        textB (str): The second text string.

    Returns:
        float: A similarity score between 0 and 1 (inclusive), where 1 indicates
              identical semantic meaning and 0 indicates completely different meanings.
    """
    try:
        # Handle empty strings
        if not textA.strip() or not textB.strip():
            logger.warning("Empty string provided to similarity_score")
            return 0.0
            
        # Get the model
        model = get_sentence_transformer_model()
        
        # Generate embeddings
        embedding_a = model.encode(textA, convert_to_tensor=True)
        embedding_b = model.encode(textB, convert_to_tensor=True)
        
        # Convert to numpy arrays if they're tensors
        if hasattr(embedding_a, 'cpu') and hasattr(embedding_b, 'cpu'):
            embedding_a = embedding_a.cpu().numpy().reshape(1, -1)
            embedding_b = embedding_b.cpu().numpy().reshape(1, -1)
        
        similarity = cosine_similarity(embedding_a, embedding_b)[0][0]
        
        # Ensure the result is between 0 and 1
        similarity = float(max(0.0, min(1.0, similarity)))
        
        logger.info(f"Similarity score between texts: {similarity:.4f}")
        return similarity
    except Exception as e:
        logger.error(f"Error calculating similarity score: {e}")
        # Fallback to a default value in case of error
        return 0.5

def test_similarity():
    """Test the similarity_score function with various text pairs."""
    
    # Test cases with expected similarity relationships
    test_cases = [
        # Similar texts
        ("The impact of climate change on global agriculture", 
         "How climate change affects farming worldwide",
         "high"),
        
        # Somewhat similar texts
        ("Machine learning applications in healthcare", 
         "Using artificial intelligence to improve medical diagnoses",
         "medium"),
        
        # Different texts
        ("Quantum computing fundamentals", 
         "Sustainable urban planning strategies",
         "low")
    ]
    
    logger.info("Testing similarity_score function...")
    
    results = []
    for i, (text1, text2, expected) in enumerate(test_cases):
        logger.info(f"Test case {i+1}:")
        logger.info(f"Text 1: {text1}")
        logger.info(f"Text 2: {text2}")
        logger.info(f"Expected similarity: {expected}")
        
        score = similarity_score(text1, text2)
        results.append((score, expected))
        
        logger.info(f"Actual similarity score: {score:.4f}")
        logger.info("-" * 50)
    
    # Verify that the relative ordering of similarities is correct
    scores = [r[0] for r in results]
    if scores[0] > scores[1] > scores[2]:
        logger.info("✅ Test PASSED: Similarity scores have the expected relative ordering")
    else:
        logger.info("❌ Test FAILED: Similarity scores do not have the expected relative ordering")
        logger.info(f"Expected: {results[0][0]} > {results[1][0]} > {results[2][0]}")

if __name__ == "__main__":
    test_similarity()

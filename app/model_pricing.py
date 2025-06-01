"""
Default model pricing data for common LLM providers
This data should be updated periodically as pricing changes
"""

from datetime import datetime
from .database import get_db_manager

# Default pricing data (prices per 1K tokens in USD)
DEFAULT_MODEL_PRICING = {
    # OpenAI Models
    "gpt-4": {
        "provider": "openai",
        "prompt_price_per_1k": 0.03,
        "completion_price_per_1k": 0.06,
        "context_window": 8192,
        "max_output_tokens": 4096
    },
    "gpt-4-turbo": {
        "provider": "openai", 
        "prompt_price_per_1k": 0.01,
        "completion_price_per_1k": 0.03,
        "context_window": 128000,
        "max_output_tokens": 4096
    },
    "gpt-3.5-turbo": {
        "provider": "openai",
        "prompt_price_per_1k": 0.001,
        "completion_price_per_1k": 0.002,
        "context_window": 16385,
        "max_output_tokens": 4096
    },
    
    # Google Models (via OpenRouter)
    "google/gemini-flash-1.5": {
        "provider": "openrouter",
        "prompt_price_per_1k": 0.000075,
        "completion_price_per_1k": 0.0003,
        "context_window": 1000000,
        "max_output_tokens": 8192
    },
    "google/gemini-2.0-flash-001": {
        "provider": "openrouter",
        "prompt_price_per_1k": 0.000075,
        "completion_price_per_1k": 0.0003,
        "context_window": 1000000,
        "max_output_tokens": 8192
    },
    "google/gemini-pro": {
        "provider": "openrouter",
        "prompt_price_per_1k": 0.0005,
        "completion_price_per_1k": 0.0015,
        "context_window": 32768,
        "max_output_tokens": 8192
    },
    
    # Anthropic Models
    "anthropic/claude-3-opus": {
        "provider": "openrouter",
        "prompt_price_per_1k": 0.015,
        "completion_price_per_1k": 0.075,
        "context_window": 200000,
        "max_output_tokens": 4096
    },
    "anthropic/claude-3-sonnet": {
        "provider": "openrouter",
        "prompt_price_per_1k": 0.003,
        "completion_price_per_1k": 0.015,
        "context_window": 200000,
        "max_output_tokens": 4096
    },
    "anthropic/claude-3-haiku": {
        "provider": "openrouter",
        "prompt_price_per_1k": 0.00025,
        "completion_price_per_1k": 0.00125,
        "context_window": 200000,
        "max_output_tokens": 4096
    },
    
    # Meta Models
    "meta-llama/llama-2-70b-chat": {
        "provider": "openrouter",
        "prompt_price_per_1k": 0.0007,
        "completion_price_per_1k": 0.0009,
        "context_window": 4096,
        "max_output_tokens": 4096
    },
    
    # Mistral Models
    "mistralai/mistral-7b-instruct": {
        "provider": "openrouter",
        "prompt_price_per_1k": 0.0001,
        "completion_price_per_1k": 0.0001,
        "context_window": 32768,
        "max_output_tokens": 32768
    },
    "mistralai/mixtral-8x7b-instruct": {
        "provider": "openrouter",
        "prompt_price_per_1k": 0.0005,
        "completion_price_per_1k": 0.0005,
        "context_window": 32768,
        "max_output_tokens": 32768
    }
}

def initialize_model_pricing():
    """Initialize the database with default model pricing"""
    try:
        db_manager = get_db_manager()
        
        for model_name, pricing in DEFAULT_MODEL_PRICING.items():
            db_manager.save_model_pricing(
                model_name=model_name,
                provider=pricing["provider"],
                prompt_price_per_1k=pricing["prompt_price_per_1k"],
                completion_price_per_1k=pricing["completion_price_per_1k"],
                context_window=pricing.get("context_window"),
                max_output_tokens=pricing.get("max_output_tokens")
            )
        
        print(f"✅ Initialized pricing for {len(DEFAULT_MODEL_PRICING)} models")
        
    except Exception as e:
        print(f"❌ Failed to initialize model pricing: {e}")

def update_model_pricing(model_name: str, prompt_price: float, completion_price: float,
                        provider: str = "openrouter", context_window: int = None,
                        max_output_tokens: int = None):
    """Update pricing for a specific model"""
    try:
        db_manager = get_db_manager()
        db_manager.save_model_pricing(
            model_name=model_name,
            provider=provider,
            prompt_price_per_1k=prompt_price,
            completion_price_per_1k=completion_price,
            context_window=context_window,
            max_output_tokens=max_output_tokens
        )
        print(f"✅ Updated pricing for {model_name}")
        
    except Exception as e:
        print(f"❌ Failed to update pricing for {model_name}: {e}")

if __name__ == "__main__":
    # Initialize pricing when run as a script
    initialize_model_pricing()
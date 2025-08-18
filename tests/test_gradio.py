#!/usr/bin/env python3
"""
Test script for the Gradio version of Open AI Co-Scientist app.
Run this to test the app locally before deploying to Hugging Face Spaces.
"""

import os
import sys

def test_imports():
    """Test that all required imports work."""
    print("Testing imports...")
    
    try:
        import gradio as gr
        print("✅ Gradio imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import Gradio: {e}")
        return False
    
    try:
        from app.models import ResearchGoal, ContextMemory
        from app.agents import SupervisorAgent
        from app.utils import logger, is_huggingface_space, get_deployment_environment
        from app.tools.arxiv_search import ArxivSearchTool
        print("✅ App components imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import app components: {e}")
        return False
    
    return True

def test_environment_detection():
    """Test environment detection functions."""
    print("\nTesting environment detection...")
    
    try:
        from app.utils import is_huggingface_space, get_deployment_environment
        
        is_hf = is_huggingface_space()
        env = get_deployment_environment()
        
        print(f"✅ Is Hugging Face Spaces: {is_hf}")
        print(f"✅ Deployment environment: {env}")
        
        return True
    except Exception as e:
        print(f"❌ Environment detection failed: {e}")
        return False

def test_gradio_app():
    """Test that the Gradio app can be created."""
    print("\nTesting Gradio app creation...")
    
    try:
        # Add parent directory to path for imports
        import os
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, parent_dir)
        
        # Import the app creation function from the root app.py file
        import importlib.util
        app_path = os.path.join(parent_dir, 'app.py')
        spec = importlib.util.spec_from_file_location("gradio_app", app_path)
        gradio_app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gradio_app)
        
        # Create the interface (but don't launch)
        demo = gradio_app.create_gradio_interface()
        print("✅ Gradio interface created successfully")
        
        return True
    except Exception as e:
        print(f"❌ Failed to create Gradio interface: {e}")
        return False

def main():
    """Run all tests."""
    print("🔬 Open AI Co-Scientist Gradio App Test Suite")
    print("=" * 50)
    
    # Check API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        print(f"✅ OPENROUTER_API_KEY is set (length: {len(api_key)})")
    else:
        print("⚠️  OPENROUTER_API_KEY is not set - app will show warnings")
    
    # Run tests
    tests = [
        test_imports,
        test_environment_detection,
        test_gradio_app
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"Test Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! The app should work correctly.")
        print("\nTo run the app locally:")
        print("  python app.py")
        print("\nTo deploy to Hugging Face Spaces:")
        print("  1. Copy README_HF.md to README.md in your HF Space")
        print("  2. Upload app.py and requirements.txt")
        print("  3. Set OPENROUTER_API_KEY in Space secrets")
    else:
        print("❌ Some tests failed. Please fix the issues before deploying.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

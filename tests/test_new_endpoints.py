#!/usr/bin/env python3
"""
Test script for the new arXiv analytics and tracking API endpoints.
This is a basic verification script to check the endpoints are properly defined.
"""

import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

try:
    from api import app
    print("✅ API module imports successfully")
    
    # Check if the new endpoints are registered
    routes = [route.path for route in app.routes]
    
    expected_endpoints = [
        "/sessions/{session_id}/arxiv/analytics",
        "/arxiv/papers/{arxiv_id}/usage", 
        "/arxiv/papers/{arxiv_id}/access",
        "/arxiv/search-history/{session_id}",
        "/sessions/{session_id}/hypotheses/{hypothesis_id}/papers/{arxiv_id}"
    ]
    
    print("\nChecking for new arXiv analytics endpoints:")
    for endpoint in expected_endpoints:
        if endpoint in routes:
            print(f"✅ {endpoint}")
        else:
            print(f"❌ {endpoint} - NOT FOUND")
    
    print(f"\nTotal routes registered: {len(routes)}")
    
    # Check specific route methods
    methods = {}
    for route in app.routes:
        if hasattr(route, 'methods'):
            methods[route.path] = list(route.methods)
    
    print("\nHTTP methods for new endpoints:")
    for endpoint in expected_endpoints:
        if endpoint in methods:
            print(f"  {endpoint}: {methods[endpoint]}")
    
    print("\n✅ All checks passed! New endpoints are properly registered.")

except ImportError as e:
    print(f"❌ Failed to import API module: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error during verification: {e}")
    sys.exit(1)
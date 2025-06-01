#!/usr/bin/env python3
"""
Simple verification script to check if the new arXiv analytics endpoints are in the API file.
"""

import os

def check_endpoints_in_file():
    """Check if the new endpoints are defined in the API file"""
    api_file = os.path.join('..', 'app', 'api.py')
    
    if not os.path.exists(api_file):
        print(f"❌ API file not found: {api_file}")
        return False
    
    with open(api_file, 'r') as f:
        content = f.read()
    
    # Check for endpoint signatures
    endpoints_to_check = [
        ('GET /sessions/{session_id}/arxiv/analytics', 'def get_session_arxiv_analytics'),
        ('GET /arxiv/papers/{arxiv_id}/usage', 'def get_paper_usage_statistics'),
        ('POST /arxiv/papers/{arxiv_id}/access', 'def log_paper_access'),
        ('GET /arxiv/search-history/{session_id}', 'def get_arxiv_search_history'),
        ('PUT /sessions/{session_id}/hypotheses/{hypothesis_id}/papers/{arxiv_id}', 'def link_paper_to_hypothesis')
    ]
    
    print("Checking for new arXiv analytics endpoints in api.py:")
    print("-" * 60)
    
    all_found = True
    for endpoint_desc, function_signature in endpoints_to_check:
        if function_signature in content:
            print(f"✅ {endpoint_desc}")
        else:
            print(f"❌ {endpoint_desc} - Function not found")
            all_found = False
    
    # Check for required imports
    print("\nChecking for required imports:")
    required_imports = [
        'import json',
        'import datetime',
        'from .database import get_db_manager'
    ]
    
    for import_stmt in required_imports:
        if import_stmt in content:
            print(f"✅ {import_stmt}")
        else:
            print(f"❌ {import_stmt} - Not found")
            all_found = False
    
    # Check for database function calls
    print("\nChecking for database function usage:")
    db_functions = [
        'get_session_arxiv_analytics',
        'save_arxiv_paper',
        'save_hypothesis_paper_reference',
        'log_message'
    ]
    
    for func in db_functions:
        if func in content:
            print(f"✅ {func}()")
        else:
            print(f"❌ {func}() - Not found")
    
    return all_found

if __name__ == "__main__":
    print("Verifying new arXiv analytics and tracking endpoints...")
    print("=" * 60)
    
    success = check_endpoints_in_file()
    
    if success:
        print("\n🎉 All endpoint verification checks passed!")
        print("\nNew endpoints added:")
        print("1. GET /sessions/{session_id}/arxiv/analytics")
        print("2. GET /arxiv/papers/{arxiv_id}/usage")
        print("3. POST /arxiv/papers/{arxiv_id}/access")
        print("4. GET /arxiv/search-history/{session_id}")
        print("5. PUT /sessions/{session_id}/hypotheses/{hypothesis_id}/papers/{arxiv_id}")
    else:
        print("\n❌ Some verification checks failed. Please review the implementation.")
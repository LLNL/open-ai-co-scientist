#!/usr/bin/env python3
"""
Test runner script for AI Co-Scientist
Runs all tests and provides a summary
"""

import sys
import os
import unittest
import subprocess

def run_individual_tests():
    """Run individual test files that are standalone scripts"""
    test_files = [
        'tests/test_arxiv.py',
        'tests/verify_endpoints.py'
    ]
    
    results = {}
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\n{'='*60}")
            print(f"Running {test_file}")
            print('='*60)
            
            try:
                result = subprocess.run([sys.executable, test_file], 
                                      capture_output=True, text=True, timeout=60)
                results[test_file] = {
                    'returncode': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
                
                if result.returncode == 0:
                    print(f"✅ {test_file} PASSED")
                    if result.stdout:
                        print("Output:", result.stdout[-500:])  # Last 500 chars
                else:
                    print(f"❌ {test_file} FAILED (exit code: {result.returncode})")
                    if result.stderr:
                        print("Errors:", result.stderr[-500:])
                    if result.stdout:
                        print("Output:", result.stdout[-500:])
                        
            except subprocess.TimeoutExpired:
                print(f"⏰ {test_file} TIMEOUT")
                results[test_file] = {'returncode': -1, 'error': 'timeout'}
            except Exception as e:
                print(f"💥 {test_file} ERROR: {e}")
                results[test_file] = {'returncode': -1, 'error': str(e)}
        else:
            print(f"⚠️  {test_file} not found")
    
    return results

def run_unittest_tests():
    """Run unittest-based tests"""
    print(f"\n{'='*60}")
    print("Running unittest-based tests")
    print('='*60)
    
    # Discover and run tests
    test_dir = os.path.join(os.path.dirname(__file__), 'tests')
    
    try:
        # Try to run unittest discovery
        loader = unittest.TestLoader()
        start_dir = test_dir
        suite = loader.discover(start_dir, pattern='test_*.py')
        
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        return {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'success': result.wasSuccessful()
        }
    except Exception as e:
        print(f"Error running unittest discovery: {e}")
        return {'error': str(e)}

def main():
    """Main test runner"""
    print("🧪 AI Co-Scientist Test Suite")
    print("="*60)
    
    # Check if we're in the right directory
    if not os.path.exists('app') or not os.path.exists('tests'):
        print("❌ Please run this script from the project root directory")
        print("   (Should contain 'app' and 'tests' directories)")
        sys.exit(1)
    
    # Run individual test scripts
    individual_results = run_individual_tests()
    
    # Run unittest-based tests
    unittest_results = run_unittest_tests()
    
    # Print summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print('='*60)
    
    # Individual test results
    print("\nIndividual Test Scripts:")
    for test_file, result in individual_results.items():
        if result.get('returncode') == 0:
            print(f"  ✅ {os.path.basename(test_file)}")
        else:
            print(f"  ❌ {os.path.basename(test_file)} - {result.get('error', 'failed')}")
    
    # Unittest results
    print("\nUnittest Results:")
    if 'error' in unittest_results:
        print(f"  ❌ Error: {unittest_results['error']}")
    else:
        tests_run = unittest_results.get('tests_run', 0)
        failures = unittest_results.get('failures', 0)
        errors = unittest_results.get('errors', 0)
        
        print(f"  📊 Tests run: {tests_run}")
        print(f"  ❌ Failures: {failures}")
        print(f"  💥 Errors: {errors}")
        
        if unittest_results.get('success', False):
            print("  ✅ All unittest tests passed!")
        else:
            print("  ❌ Some unittest tests failed")
    
    # Overall result
    individual_passed = sum(1 for r in individual_results.values() if r.get('returncode') == 0)
    individual_total = len(individual_results)
    unittest_success = unittest_results.get('success', False)
    
    print(f"\n🎯 Overall Results:")
    print(f"   Individual scripts: {individual_passed}/{individual_total} passed")
    print(f"   Unittest tests: {'✅ PASSED' if unittest_success else '❌ FAILED'}")
    
    if individual_passed == individual_total and unittest_success:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        return 0
    else:
        print("\n💥 SOME TESTS FAILED")
        return 1

if __name__ == '__main__':
    sys.exit(main())
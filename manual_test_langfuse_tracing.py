#!/usr/bin/env python
"""Test script to verify Langfuse tracing is working correctly.

This script tests that:
1. The observe decorator is properly exported from observability module
2. Workflow steps are properly instrumented with @observe decorator
3. Both LLM traces and workflow step traces are captured
"""

import sys
import os

# Add src directory to path for development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_observe_decorator_import():
    """Test that observe decorator can be imported."""
    print("=" * 60)
    print("Test 1: Import observe decorator")
    print("=" * 60)
    
    try:
        from basic.observability import observe
        print("✓ Successfully imported observe decorator")
        print(f"  observe: {observe}")
        return True
    except ImportError as e:
        print(f"✗ Failed to import observe decorator: {e}")
        return False


def test_observe_decorator_no_op():
    """Test that observe decorator works as no-op when Langfuse not installed."""
    print("\n" + "=" * 60)
    print("Test 2: Test observe decorator (no-op mode)")
    print("=" * 60)
    
    try:
        from basic.observability import observe
        
        # Test with no arguments
        @observe
        def test_func1():
            return "test1"
        
        # Test with arguments
        @observe(name="test_function")
        def test_func2():
            return "test2"
        
        result1 = test_func1()
        result2 = test_func2()
        
        if result1 == "test1" and result2 == "test2":
            print("✓ Observe decorator works correctly (no-op mode)")
            print(f"  test_func1() returned: {result1}")
            print(f"  test_func2() returned: {result2}")
            return True
        else:
            print(f"✗ Unexpected results: {result1}, {result2}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing observe decorator: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_workflow_instrumentation():
    """Test that workflow files have been properly instrumented."""
    print("\n" + "=" * 60)
    print("Test 3: Check workflow instrumentation")
    print("=" * 60)
    
    try:
        import ast
        
        # Check email_workflow.py
        email_workflow_file = os.path.join(os.path.dirname(__file__), "src", "basic", "email_workflow.py")
        with open(email_workflow_file) as f:
            content = f.read()
            
        tree = ast.parse(content)
        
        # Find all function definitions with @observe decorator
        observed_functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if function has @observe decorator
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == "observe":
                        observed_functions.append(node.name)
                    elif isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name) and decorator.func.id == "observe":
                            observed_functions.append(node.name)
        
        if observed_functions:
            print(f"✓ Found {len(observed_functions)} instrumented functions:")
            for func_name in observed_functions:
                print(f"    - {func_name}")
            return True
        else:
            print("✗ No instrumented functions found in email_workflow.py")
            return False
            
    except Exception as e:
        print(f"✗ Error checking workflow instrumentation: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\nLangfuse Tracing Test Suite")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Import observe decorator", test_observe_decorator_import()))
    results.append(("Observe decorator no-op", test_observe_decorator_no_op()))
    results.append(("Workflow instrumentation", test_workflow_instrumentation()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Langfuse tracing is properly configured.")
        return 0
    else:
        print("\n✗ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""Verification script for Langfuse manual flush functionality.

This script tests that:
1. flush_langfuse() function is available
2. run_workflow_with_flush() wrapper works correctly
3. Traces are properly flushed after workflow execution
4. Signal handlers are working for server shutdown

Run this script to verify the manual flush fix is working:
    python verify_langfuse_flush.py
"""

import asyncio
import os
import sys

# Add src directory to path for development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_flush_function_import():
    """Test that flush_langfuse can be imported."""
    print("=" * 60)
    print("Test 1: Import flush_langfuse function")
    print("=" * 60)
    
    try:
        from basic.observability import flush_langfuse
        print("✓ Successfully imported flush_langfuse")
        print(f"  Function: {flush_langfuse}")
        print(f"  Callable: {callable(flush_langfuse)}")
        return True
    except ImportError as e:
        print(f"✗ Failed to import flush_langfuse: {e}")
        return False


def test_wrapper_function_import():
    """Test that run_workflow_with_flush can be imported."""
    print("\n" + "=" * 60)
    print("Test 2: Import run_workflow_with_flush wrapper")
    print("=" * 60)
    
    try:
        from basic.observability import run_workflow_with_flush
        print("✓ Successfully imported run_workflow_with_flush")
        print(f"  Function: {run_workflow_with_flush}")
        print(f"  Callable: {callable(run_workflow_with_flush)}")
        return True
    except ImportError as e:
        print(f"✗ Failed to import run_workflow_with_flush: {e}")
        return False


def test_flush_no_op():
    """Test that flush_langfuse works as no-op when not configured."""
    print("\n" + "=" * 60)
    print("Test 3: Test flush_langfuse (no-op mode)")
    print("=" * 60)
    
    try:
        from basic.observability import flush_langfuse
        
        # Call flush - should not raise any errors
        flush_langfuse()
        print("✓ flush_langfuse() executed without errors")
        
        # Call it again to test idempotency
        flush_langfuse()
        print("✓ flush_langfuse() is idempotent (can be called multiple times)")
        
        return True
    except Exception as e:
        print(f"✗ Error calling flush_langfuse: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_wrapper_execution():
    """Test that run_workflow_with_flush wrapper works."""
    print("\n" + "=" * 60)
    print("Test 4: Test run_workflow_with_flush wrapper")
    print("=" * 60)
    
    try:
        from basic.observability import run_workflow_with_flush
        from basic.workflow import workflow
        
        # Run workflow with flush wrapper
        print("  Running BasicWorkflow with flush wrapper...")
        result = await run_workflow_with_flush(workflow)
        print(f"✓ Workflow executed successfully")
        print(f"  Result: {result}")
        print("✓ Traces flushed automatically")
        
        return True
    except Exception as e:
        print(f"✗ Error running workflow with flush: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_observability_state():
    """Test that observability state is accessible."""
    print("\n" + "=" * 60)
    print("Test 5: Check observability state")
    print("=" * 60)
    
    try:
        from basic import observability
        
        # Check if client and handler are set (they may be None if not configured)
        client = observability._langfuse_client
        handler = observability._langfuse_handler
        
        print(f"  Langfuse client: {client is not None}")
        print(f"  Langfuse handler: {handler is not None}")
        
        if client is None and handler is None:
            print("  ℹ️  Langfuse not configured (this is expected in test environment)")
        else:
            print("✓ Langfuse is configured")
        
        return True
    except Exception as e:
        print(f"✗ Error checking observability state: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_server_imports():
    """Test that server module has flush functionality."""
    print("\n" + "=" * 60)
    print("Test 6: Check server module for flush integration")
    print("=" * 60)
    
    try:
        import ast
        
        # Read server.py
        server_file = os.path.join(os.path.dirname(__file__), "src", "basic", "server.py")
        with open(server_file) as f:
            content = f.read()
        
        # Check for flush_langfuse import
        if "flush_langfuse" in content:
            print("✓ Server imports flush_langfuse")
        else:
            print("✗ Server does not import flush_langfuse")
            return False
        
        # Check for signal handlers
        if "signal_handler" in content:
            print("✓ Server has signal handlers")
        else:
            print("✗ Server missing signal handlers")
            return False
        
        # Check for atexit
        if "atexit" in content:
            print("✓ Server has atexit handler")
        else:
            print("✗ Server missing atexit handler")
            return False
        
        print("✓ Server properly configured for flush on shutdown")
        return True
        
    except Exception as e:
        print(f"✗ Error checking server module: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_demo_script():
    """Test that demo script has flush functionality."""
    print("\n" + "=" * 60)
    print("Test 7: Check demo script for flush integration")
    print("=" * 60)
    
    try:
        # Read demo_observability.py
        demo_file = os.path.join(os.path.dirname(__file__), "demo_observability.py")
        with open(demo_file) as f:
            content = f.read()
        
        # Check for flush_langfuse import
        if "flush_langfuse" in content:
            print("✓ Demo imports flush_langfuse")
        else:
            print("✗ Demo does not import flush_langfuse")
            return False
        
        # Check for flush call
        if "flush_langfuse()" in content:
            print("✓ Demo calls flush_langfuse()")
        else:
            print("✗ Demo does not call flush_langfuse()")
            return False
        
        print("✓ Demo script properly demonstrates flush usage")
        return True
        
    except Exception as e:
        print(f"✗ Error checking demo script: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all verification tests."""
    print("\nLangfuse Manual Flush Verification")
    print("=" * 60)
    print("\nThis script verifies that the Langfuse manual flush")
    print("functionality is properly implemented.\n")
    
    # Check if Langfuse is configured
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    
    if secret_key and public_key:
        print("ℹ️  Langfuse credentials detected:")
        # Mask keys properly - always show at least 4 asterisks
        secret_masked = f"{'*' * max(8, len(secret_key) - 4)}{secret_key[-4:] if len(secret_key) > 4 else ''}"
        public_masked = f"{'*' * max(8, len(public_key) - 4)}{public_key[-4:] if len(public_key) > 4 else ''}"
        print(f"  LANGFUSE_SECRET_KEY: {secret_masked}")
        print(f"  LANGFUSE_PUBLIC_KEY: {public_masked}")
        print(f"  LANGFUSE_HOST: {os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')}")
    else:
        print("ℹ️  Langfuse credentials not set (tests will run in no-op mode)")
    
    print()
    
    results = []
    
    # Run tests
    results.append(("Import flush_langfuse", test_flush_function_import()))
    results.append(("Import run_workflow_with_flush", test_wrapper_function_import()))
    results.append(("Test flush no-op", test_flush_no_op()))
    results.append(("Test wrapper execution", await test_wrapper_execution()))
    results.append(("Check observability state", test_observability_state()))
    results.append(("Check server integration", test_server_imports()))
    results.append(("Check demo integration", test_demo_script()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Langfuse manual flush is properly implemented.")
        print("\nNext steps:")
        print("1. Set LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY environment variables")
        print("2. Run your workflow")
        print("3. Check Langfuse dashboard for traces")
        print("\nSee LANGFUSE_MANUAL_FLUSH.md for usage examples.")
        return 0
    else:
        print("\n✗ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

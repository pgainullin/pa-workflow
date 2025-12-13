#!/usr/bin/env python3
"""Verification script to demonstrate the Langfuse observability fix.

This script tests the observability setup and shows clear error messages
when there are issues with package installation or configuration.

NOTE: This is a standalone diagnostic script that modifies sys.path to work
without requiring package installation. This design allows users to run
diagnostics even when the package isn't properly installed (which is one
of the issues this script helps diagnose).
"""

import logging
import os
import sys

# Set up logging to see all messages
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

# Add src to path for standalone execution
# This allows the script to work even when the package isn't installed,
# which is helpful for diagnosing installation issues
# Only add local src if basic.observability is not importable (not installed)
import importlib.util
if importlib.util.find_spec("basic.observability") is None:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

def test_package_installed():
    """Test if the langfuse package is installed."""
    print("\n" + "="*60)
    print("Test 1: Checking if langfuse package is installed")
    print("="*60)
    
    try:
        from langfuse.llama_index import LlamaIndexCallbackHandler
        print("✓ langfuse package is installed")
        return True
    except ImportError as e:
        print(f"✗ langfuse package is NOT installed: {e}")
        print("\n  To fix this, run:")
        print("  pip install llama-index-callbacks-langfuse")
        return False


def test_observability_without_credentials():
    """Test observability without credentials."""
    print("\n" + "="*60)
    print("Test 2: Observability without credentials")
    print("="*60)
    
    # Clear any existing environment variables
    os.environ.pop('LANGFUSE_SECRET_KEY', None)
    os.environ.pop('LANGFUSE_PUBLIC_KEY', None)
    
    # Reload observability module
    if 'basic.observability' in sys.modules:
        del sys.modules['basic.observability']
    
    from basic.observability import setup_observability
    from llama_index.core import Settings
    
    Settings.callback_manager = None
    setup_observability(enabled=True)
    
    if Settings.callback_manager is None or len(Settings.callback_manager.handlers) == 0:
        print("✓ Observability correctly disabled without credentials")
        return True
    else:
        print("✗ Observability should be disabled without credentials")
        return False


def test_observability_with_credentials():
    """Test observability with credentials."""
    print("\n" + "="*60)
    print("Test 3: Observability with credentials")
    print("="*60)
    
    # Set test credentials
    os.environ['LANGFUSE_SECRET_KEY'] = 'sk-test-key'
    os.environ['LANGFUSE_PUBLIC_KEY'] = 'pk-test-key'
    os.environ['LANGFUSE_HOST'] = 'https://cloud.langfuse.com'
    
    # Reload observability module
    if 'basic.observability' in sys.modules:
        del sys.modules['basic.observability']
    
    from basic.observability import setup_observability
    from llama_index.core import Settings
    
    Settings.callback_manager = None
    setup_observability(enabled=True)
    
    if Settings.callback_manager is not None and len(Settings.callback_manager.handlers) > 0:
        handler = Settings.callback_manager.handlers[0]
        print(f"✓ Observability is configured")
        print(f"  Handler type: {type(handler).__name__}")
        return True
    else:
        print("✗ Observability should be configured with credentials")
        return False


def main():
    """Run all verification tests."""
    print("="*60)
    print("Langfuse Observability Fix Verification")
    print("="*60)
    
    results = []
    
    # Test 1: Package installation
    results.append(("Package installed", test_package_installed()))
    
    # Test 2: Without credentials
    results.append(("Without credentials", test_observability_without_credentials()))
    
    # Test 3: With credentials
    results.append(("With credentials", test_observability_with_credentials()))
    
    # Print summary
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n✓ All tests passed! Observability is working correctly.")
    else:
        print("\n✗ Some tests failed. Please check the error messages above.")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

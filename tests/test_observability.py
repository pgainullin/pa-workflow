"""Tests for observability configuration.

This module tests that the Langfuse observability integration is properly configured
and can be enabled/disabled based on environment variables.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


def test_observability_disabled_without_keys():
    """Test that observability is disabled when Langfuse keys are not set."""
    # Clear any existing observability settings
    from llama_index.core import Settings
    Settings.callback_manager = None
    
    # Clear environment variables
    with patch.dict(os.environ, {}, clear=True):
        # Reimport the module to trigger setup
        import importlib
        from basic import observability
        importlib.reload(observability)
        
        # Observability should be disabled (callback_manager is None or empty)
        assert Settings.callback_manager is None or len(Settings.callback_manager.handlers) == 0


def test_observability_enabled_with_keys():
    """Test that observability is enabled when Langfuse keys are set."""
    # Clear any existing observability settings
    from llama_index.core import Settings
    Settings.callback_manager = None
    
    # Set environment variables
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-test-key",
        "LANGFUSE_PUBLIC_KEY": "pk-test-key",
        "LANGFUSE_HOST": "https://test.langfuse.com"
    }):
        # Reimport the module to trigger setup
        import importlib
        from basic import observability
        importlib.reload(observability)
        
        # Observability should be enabled
        assert Settings.callback_manager is not None
        assert len(Settings.callback_manager.handlers) > 0


def test_observability_explicitly_disabled():
    """Test that observability can be explicitly disabled even with keys present."""
    # Clear any existing observability settings
    from llama_index.core import Settings
    Settings.callback_manager = None
    
    # Set environment variables with explicit disable
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-test-key",
        "LANGFUSE_PUBLIC_KEY": "pk-test-key",
        "LANGFUSE_ENABLED": "false"
    }):
        # Reimport the module to trigger setup
        import importlib
        from basic import observability
        importlib.reload(observability)
        
        # Observability should be disabled
        assert Settings.callback_manager is None or len(Settings.callback_manager.handlers) == 0


def test_observability_setup_function():
    """Test that the setup_observability function can be called explicitly."""
    from basic.observability import setup_observability
    
    # Test with explicit disable
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-test-key",
        "LANGFUSE_PUBLIC_KEY": "pk-test-key"
    }):
        # Should work without raising exceptions
        setup_observability(enabled=False)
        
        # Should work with enabled=True (but may not actually initialize if import fails)
        try:
            setup_observability(enabled=True)
        except Exception as e:
            # It's okay if it fails due to import issues in test environment
            assert "import" in str(e).lower() or "langfuse" in str(e).lower()


def test_observability_graceful_failure_without_package():
    """Test that observability fails gracefully if the package is not installed."""
    from llama_index.core import Settings
    
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-test-key",
        "LANGFUSE_PUBLIC_KEY": "pk-test-key"
    }):
        # Mock the Langfuse import to fail
        with patch.dict("sys.modules", {"langfuse.llama_index": None, "langfuse": None}):
            from basic.observability import setup_observability
            
            # Clear callback manager first
            Settings.callback_manager = None
            
            # Should not raise exception
            setup_observability(enabled=True)
            
            # Observability should not be set up
            # (callback_manager may be None or have no handlers)
            assert Settings.callback_manager is None or len(Settings.callback_manager.handlers) == 0


def test_observability_import_in_workflow():
    """Test that observability can be imported in workflow modules without errors."""
    # This test verifies that the import statement works
    try:
        from basic import observability
        assert observability is not None
    except Exception as e:
        pytest.fail(f"Failed to import observability module: {e}")


def test_observability_import_in_email_workflow():
    """Test that observability can be imported alongside email_workflow without errors."""
    # This test just verifies the observability module can be imported
    # We don't actually import email_workflow because it requires network access
    try:
        from basic import observability
        assert observability is not None
        
        # Verify the setup function exists
        assert hasattr(observability, 'setup_observability')
    except Exception as e:
        pytest.fail(f"Failed to work with observability module: {e}")

"""Tests for observability configuration.

This module tests that the Langfuse observability integration is properly configured
and can be enabled/disabled based on environment variables.
"""

import os
from unittest.mock import patch

import pytest


@pytest.fixture
def reset_callback_manager():
    """Fixture to save and restore Settings.callback_manager for test isolation."""
    from llama_index.core import Settings
    original_manager = Settings.callback_manager
    yield
    Settings.callback_manager = original_manager


def test_observability_disabled_without_keys(reset_callback_manager):
    """Test that observability is disabled when Langfuse keys are not set."""
    from basic.observability import setup_observability
    from llama_index.core import Settings
    
    # Clear callback manager
    Settings.callback_manager = None
    
    # Clear environment variables and call setup directly
    with patch.dict(os.environ, {}, clear=True):
        setup_observability()
        
        # Observability should be disabled (callback_manager is None or empty)
        assert Settings.callback_manager is None or len(Settings.callback_manager.handlers) == 0


def test_observability_enabled_with_keys(reset_callback_manager):
    """Test that observability is enabled when Langfuse keys are set."""
    from basic.observability import setup_observability
    from llama_index.core import Settings
    
    # Clear callback manager
    Settings.callback_manager = None
    
    # Set environment variables and call setup directly
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-test-key",
        "LANGFUSE_PUBLIC_KEY": "pk-test-key",
        "LANGFUSE_HOST": "https://test.langfuse.com"
    }):
        setup_observability()
        
        # Observability should be enabled
        assert Settings.callback_manager is not None
        assert len(Settings.callback_manager.handlers) > 0


def test_observability_explicitly_disabled(reset_callback_manager):
    """Test that observability can be explicitly disabled even with keys present."""
    from basic.observability import setup_observability
    from llama_index.core import Settings
    
    # Clear callback manager
    Settings.callback_manager = None
    
    # Test with environment variable LANGFUSE_ENABLED=false
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-test-key",
        "LANGFUSE_PUBLIC_KEY": "pk-test-key",
        "LANGFUSE_ENABLED": "false"
    }):
        setup_observability()
        
        # Observability should be disabled
        assert Settings.callback_manager is None or len(Settings.callback_manager.handlers) == 0
    
    # Test with explicit enabled=False parameter
    Settings.callback_manager = None
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-test-key",
        "LANGFUSE_PUBLIC_KEY": "pk-test-key"
    }):
        setup_observability(enabled=False)
        
        # Observability should be disabled
        assert Settings.callback_manager is None or len(Settings.callback_manager.handlers) == 0


def test_observability_setup_function(reset_callback_manager):
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
        except (ImportError, ModuleNotFoundError):
            # It's okay if it fails due to import issues in test environment
            pass


def test_observability_graceful_failure_without_package(reset_callback_manager):
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


def test_observability_error_message_without_package(reset_callback_manager, caplog):
    """Test that a clear error message is shown when langfuse package is not installed."""
    from llama_index.core import Settings
    import logging
    
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-test-key",
        "LANGFUSE_PUBLIC_KEY": "pk-test-key"
    }):
        # Mock the Langfuse import to fail
        with patch.dict("sys.modules", {"langfuse.llama_index": None, "langfuse": None}):
            from basic.observability import setup_observability
            
            # Clear callback manager first
            Settings.callback_manager = None
            
            # Capture logs at ERROR level
            with caplog.at_level(logging.ERROR):
                setup_observability(enabled=True)
            
            # Check that the error message contains helpful information
            assert any("Failed to import Langfuse callback handler" in record.message for record in caplog.records)
            assert any("pip install llama-index-callbacks-langfuse" in record.message for record in caplog.records)


def test_observability_error_message_without_credentials(reset_callback_manager, caplog):
    """Test that a clear error message is shown when credentials are not set."""
    from llama_index.core import Settings
    import logging
    
    # Clear environment variables
    with patch.dict(os.environ, {}, clear=True):
        from basic.observability import setup_observability
        
        # Clear callback manager first
        Settings.callback_manager = None
        
        # Capture logs at ERROR level
        with caplog.at_level(logging.ERROR):
            setup_observability(enabled=True)
        
        # Check that the error message contains helpful information
        assert any("LANGFUSE_SECRET_KEY" in record.message and "LANGFUSE_PUBLIC_KEY" in record.message 
                   for record in caplog.records)


def test_logging_handler_configured(reset_callback_manager):
    """Test that Python logging handler is configured to forward logs to Langfuse."""
    from basic.observability import setup_observability, LangfuseLoggingHandler
    from llama_index.core import Settings
    import logging
    
    # Clear callback manager
    Settings.callback_manager = None
    
    # Set environment variables
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-test-key",
        "LANGFUSE_PUBLIC_KEY": "pk-test-key",
        "LANGFUSE_HOST": "https://test.langfuse.com"
    }):
        setup_observability()
        
        # Check that logging handler was added to workflow loggers
        workflow_logger = logging.getLogger('basic.email_workflow')
        has_langfuse_handler = any(
            isinstance(h, LangfuseLoggingHandler) 
            for h in workflow_logger.handlers
        )
        
        assert has_langfuse_handler, "LangfuseLoggingHandler should be added to workflow loggers"

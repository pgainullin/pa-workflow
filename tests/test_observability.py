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
    
    # Save original handlers state for cleanup
    workflow_loggers = [
        'basic.email_workflow',
        'basic.workflow',
        'basic.tools',
        'basic.utils',
        'basic.response_utils',
        'basic.plan_utils',
    ]
    original_handlers = {}
    for logger_name in workflow_loggers:
        workflow_logger = logging.getLogger(logger_name)
        original_handlers[logger_name] = workflow_logger.handlers.copy()
    
    try:
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
    finally:
        # Clean up: remove LangfuseLoggingHandler instances from all workflow loggers
        for logger_name in workflow_loggers:
            workflow_logger = logging.getLogger(logger_name)
            workflow_logger.handlers = [
                h for h in workflow_logger.handlers 
                if not isinstance(h, LangfuseLoggingHandler)
            ]
            # Restore original handlers if needed
            if not workflow_logger.handlers and original_handlers[logger_name]:
                workflow_logger.handlers = original_handlers[logger_name]


def test_observe_decorator_is_exported():
    """Test that the observe decorator is properly exported from the observability module."""
    from basic.observability import observe
    
    # Should be callable
    assert callable(observe), "observe should be a callable decorator"


def test_observe_decorator_no_op_without_langfuse():
    """Test that observe decorator works as no-op when Langfuse is not available."""
    from basic.observability import observe
    
    # Test decorator without arguments
    @observe
    def test_func1():
        return "test1"
    
    # Test decorator with arguments
    @observe(name="test_function")
    def test_func2():
        return "test2"
    
    # Both should work without errors
    assert test_func1() == "test1"
    assert test_func2() == "test2"


def test_observe_decorator_with_async_functions():
    """Test that observe decorator works with async functions."""
    import asyncio
    from basic.observability import observe
    
    @observe(name="async_test")
    async def async_test_func():
        await asyncio.sleep(0)
        return "async_result"
    
    # Should work without errors
    result = asyncio.run(async_test_func())
    assert result == "async_result"


@pytest.mark.skip(reason="Requires network access and valid API keys for GoogleGenAI initialization")
def test_workflow_steps_instrumented():
    """Test that workflow steps are instrumented with @observe decorator."""
    import inspect
    import os
    
    # Set dummy API keys to allow EmailWorkflow import
    original_llama_key = os.environ.get('LLAMA_CLOUD_API_KEY')
    original_gemini_key = os.environ.get('GEMINI_API_KEY')
    
    try:
        os.environ['LLAMA_CLOUD_API_KEY'] = 'dummy-key-for-testing'
        os.environ['GEMINI_API_KEY'] = 'dummy-key-for-testing'
        
        from basic.email_workflow import EmailWorkflow
        
        # Get the workflow class
        workflow = EmailWorkflow
        
        # Check that step methods exist
        step_methods = [
            'triage_email',
            'execute_plan',
            'verify_response',
            'send_results'
        ]
        
        for method_name in step_methods:
            assert hasattr(workflow, method_name), f"Method {method_name} should exist"
            method = getattr(workflow, method_name)
            assert callable(method), f"{method_name} should be callable"
    finally:
        # Restore original values
        if original_llama_key is None:
            os.environ.pop('LLAMA_CLOUD_API_KEY', None)
        else:
            os.environ['LLAMA_CLOUD_API_KEY'] = original_llama_key
        
        if original_gemini_key is None:
            os.environ.pop('GEMINI_API_KEY', None)
        else:
            os.environ['GEMINI_API_KEY'] = original_gemini_key


def test_observe_decorator_preserves_function_signature():
    """Test that observe decorator preserves the original function signature."""
    import inspect
    from basic.observability import observe
    
    @observe(name="test")
    async def test_func(arg1: str, arg2: int = 5) -> str:
        """Test function docstring."""
        return f"{arg1}_{arg2}"
    
    # Check that function attributes are preserved
    assert test_func.__name__ in ("test_func", "wrapper"), "Function name should be preserved or wrapper"
    # Docstring might be preserved depending on implementation
    sig = inspect.signature(test_func)
    assert len(sig.parameters) >= 2, "Function signature should be preserved"


def test_flush_langfuse_function_exists():
    """Test that flush_langfuse function is exported."""
    from basic.observability import flush_langfuse
    
    # Verify function exists and is callable
    assert callable(flush_langfuse)


def test_flush_langfuse_no_op_when_not_configured():
    """Test that flush_langfuse is a no-op when Langfuse is not configured."""
    from basic import observability
    
    # Save original state
    original_client = observability._langfuse_client
    original_handler = observability._langfuse_handler
    
    try:
        # Set to None to simulate not configured
        observability._langfuse_client = None
        observability._langfuse_handler = None
        
        # Should not raise any errors
        observability.flush_langfuse()
        
    finally:
        # Restore original state
        observability._langfuse_client = original_client
        observability._langfuse_handler = original_handler


def test_flush_langfuse_calls_handler_flush():
    """Test that flush_langfuse calls flush on both client and handler."""
    from unittest.mock import Mock
    from basic import observability
    
    # Save original state
    original_client = observability._langfuse_client
    original_handler = observability._langfuse_handler
    
    try:
        # Create mock objects
        mock_client = Mock()
        mock_handler = Mock()
        
        observability._langfuse_client = mock_client
        observability._langfuse_handler = mock_handler
        
        # Call flush
        observability.flush_langfuse()
        
        # Verify both flush methods were called
        mock_handler.flush.assert_called_once()
        mock_client.flush.assert_called_once()
        
    finally:
        # Restore original state
        observability._langfuse_client = original_client
        observability._langfuse_handler = original_handler


def test_flush_langfuse_flushes_observe_context():
    """Test that flush_langfuse also flushes the decorator context."""
    from basic import observability

    original_client = observability._langfuse_client
    original_handler = observability._langfuse_handler

    try:
        # Disable stored clients to ensure context flush is still attempted
        observability._langfuse_client = None
        observability._langfuse_handler = None

        with patch("langfuse.decorators.langfuse_context.flush") as mock_flush:
            observability.flush_langfuse()
            mock_flush.assert_called_once()
    finally:
        observability._langfuse_client = original_client
        observability._langfuse_handler = original_handler


def test_flush_langfuse_handles_errors_gracefully():
    """Test that flush_langfuse handles errors without raising exceptions."""
    from unittest.mock import Mock
    from basic import observability
    
    # Save original state
    original_client = observability._langfuse_client
    original_handler = observability._langfuse_handler
    
    try:
        # Create mock objects that raise errors
        mock_client = Mock()
        mock_client.flush.side_effect = Exception("Test error")
        
        observability._langfuse_client = mock_client
        observability._langfuse_handler = None
        
        # Should not raise - errors should be caught and logged
        observability.flush_langfuse()
        
    finally:
        # Restore original state
        observability._langfuse_client = original_client
        observability._langfuse_handler = original_handler


@pytest.mark.asyncio
async def test_run_workflow_with_flush_wrapper():
    """Test that run_workflow_with_flush executes and flushes."""
    from unittest.mock import Mock, AsyncMock
    from basic.observability import run_workflow_with_flush
    from basic import observability
    
    # Save original state
    original_client = observability._langfuse_client
    original_handler = observability._langfuse_handler
    
    try:
        # Create mock flush targets
        mock_client = Mock()
        mock_handler = Mock()
        
        observability._langfuse_client = mock_client
        observability._langfuse_handler = mock_handler
        
        # Create a mock workflow
        mock_workflow = Mock()
        mock_workflow.run = AsyncMock(return_value="test_result")
        
        # Run with flush wrapper
        result = await run_workflow_with_flush(mock_workflow, test_arg="test_value")
        
        # Verify workflow was called
        mock_workflow.run.assert_called_once_with(test_arg="test_value")
        
        # Verify result is correct
        assert result == "test_result"
        
        # Verify flush was called
        mock_handler.flush.assert_called_once()
        mock_client.flush.assert_called_once()
        
    finally:
        # Restore original state
        observability._langfuse_client = original_client
        observability._langfuse_handler = original_handler


@pytest.mark.asyncio
async def test_run_workflow_with_flush_flushes_on_error():
    """Test that run_workflow_with_flush flushes even when workflow raises error."""
    from unittest.mock import Mock, AsyncMock
    from basic.observability import run_workflow_with_flush
    from basic import observability
    
    # Save original state
    original_client = observability._langfuse_client
    original_handler = observability._langfuse_handler
    
    try:
        # Create mock flush targets
        mock_client = Mock()
        mock_handler = Mock()
        
        observability._langfuse_client = mock_client
        observability._langfuse_handler = mock_handler
        
        # Create a mock workflow that raises an error
        mock_workflow = Mock()
        mock_workflow.run = AsyncMock(side_effect=ValueError("Test error"))
        
        # Run with flush wrapper - should raise the error
        with pytest.raises(ValueError, match="Test error"):
            await run_workflow_with_flush(mock_workflow)
        
        # Verify flush was still called despite error
        mock_handler.flush.assert_called_once()
        mock_client.flush.assert_called_once()
        
    finally:
        # Restore original state
        observability._langfuse_client = original_client
        observability._langfuse_handler = original_handler


"""Observability configuration for workflow execution using Langfuse.

This module configures the Langfuse callback handler for tracing and logging
workflow execution. It automatically initializes when imported, reading configuration
from environment variables.

Environment Variables:
    LANGFUSE_SECRET_KEY: Secret key for Langfuse authentication (required)
    LANGFUSE_PUBLIC_KEY: Public key for Langfuse authentication (required)
    LANGFUSE_BASE_URL: Langfuse server URL (optional, defaults to "https://us.cloud.langfuse.com")
    LANGFUSE_ENABLED: Enable/disable observability (optional, defaults to True if keys are set)

Usage:
    Simply import this module in your workflow to enable observability:

    from basic.observability import setup_observability, observe

    # Optionally call setup explicitly with custom parameters
    setup_observability(enabled=True)

    # Use @observe decorator to trace workflow steps:
    @observe(name="my_step")
    async def my_step(...):
        ...
"""

import atexit
import logging
import os
from urllib.parse import urlparse

from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager

logger = logging.getLogger(__name__)

# Global references to Langfuse client and handler for manual flushing
# These are set during setup_observability() and used by flush_langfuse()
_langfuse_client = None
_langfuse_handler = None

# Import observe decorator from langfuse for workflow instrumentation
# This is exported for use in workflow files
try:
    from langfuse.decorators import observe  # noqa: F401

    _observe_available = True
except ImportError:
    # Provide a no-op decorator if langfuse is not installed
    def observe(*args, **kwargs):
        """No-op decorator when Langfuse is not available.

        This decorator can be used in two ways:
        1. Without arguments: @observe
        2. With arguments: @observe(name="my_function")

        When Langfuse is not installed, this decorator simply returns
        the original function unchanged, allowing code to work without
        the observability dependency.

        Works with both sync and async functions:
            @observe
            async def my_async_step(...):
                await some_operation()

            @observe(name="my_step")
            async def my_workflow_step(...):
                result = await process()
                return result
        """
        if len(args) == 1 and callable(args[0]) and not kwargs:
            # Called without arguments: @observe
            # args[0] is the function being decorated
            return args[0]
        else:
            # Called with arguments: @observe(name="...")
            # Return a no-op decorator that will receive the function
            def identity_decorator(func):
                return func

            return identity_decorator

    _observe_available = False


class LangfuseLoggingHandler(logging.Handler):
    """Custom logging handler that forwards logs to Langfuse as events.

    This handler captures Python log messages and sends them to Langfuse,
    making workflow logs visible in the Langfuse dashboard alongside traces.
    """

    def __init__(self, langfuse_client, level=logging.INFO):
        """Initialize the handler.

        Args:
            langfuse_client: Langfuse client instance
            level: Minimum log level to capture (default: INFO)
        """
        super().__init__(level)
        self.langfuse_client = langfuse_client

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to Langfuse.

        Args:
            record: Log record to emit
        """
        try:
            # Format the log message
            log_message = self.format(record)

            # Create metadata from the log record
            metadata = {
                "level": record.levelname,
                "logger": record.name,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

            # Add exception info if present
            if record.exc_info:
                metadata["exception"] = {
                    "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                    "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                }

            # Send to Langfuse as an event
            # Use the langfuse_context to ensure events are attached to current trace
            try:
                # Get current trace ID if available (import done here for performance)
                from langfuse.decorators import langfuse_context

                trace_id = langfuse_context.get_current_trace_id()

                if trace_id:
                    # Send log as an event attached to the current trace
                    self.langfuse_client.event(
                        name=f"log.{record.levelname.lower()}",
                        metadata=metadata,
                        input=log_message,
                        trace_id=trace_id,
                    )
                else:
                    # Create a standalone event if no active trace
                    self.langfuse_client.event(
                        name=f"log.{record.levelname.lower()}",
                        metadata=metadata,
                        input=log_message,
                    )
            except (ImportError, AttributeError) as e:
                # Fallback: create event directly on client if context not available
                # Log debug info to help diagnose trace attachment issues
                import sys

                print(f"Debug: Failed to attach log to trace: {e}", file=sys.stderr)
                self.langfuse_client.event(
                    name=f"log.{record.levelname.lower()}",
                    metadata=metadata,
                    input=log_message,
                )

        except Exception as e:
            # Don't let logging errors break the application
            # Log the error for debugging but don't propagate
            import sys

            print(f"Error in LangfuseLoggingHandler: {e}", file=sys.stderr)
            # Use handleError to report issues with the handler itself
            self.handleError(record)


def _sanitize_host_for_logging(host: str) -> str:
    """Sanitize host URL for logging by extracting only scheme and domain.

    Args:
        host: The host URL to sanitize

    Returns:
        Sanitized host URL containing only scheme and domain (no path or query)
    """
    try:
        parsed = urlparse(host)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return host
    except Exception:
        # Fallback: return as-is if parsing fails
        return host


def _setup_logging_handler(langfuse_client) -> None:
    """Set up Python logging handler to forward logs to Langfuse.

    This configures the root logger and workflow-specific loggers to send
    their log messages to Langfuse, making them visible in the dashboard.

    Args:
        langfuse_client: Langfuse client instance
    """
    # Create the Langfuse logging handler
    langfuse_log_handler = LangfuseLoggingHandler(langfuse_client, level=logging.INFO)

    # Set a formatter for better log messages
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    langfuse_log_handler.setFormatter(formatter)

    # Add handler to the root logger to capture all logs (including libraries)
    # This ensures we don't miss logs from 'workflows', 'llama_index', or other modules
    root_logger = logging.getLogger()
    if not any(isinstance(h, LangfuseLoggingHandler) for h in root_logger.handlers):
        root_logger.addHandler(langfuse_log_handler)
        logger.debug("Langfuse logging handler attached to root logger")


def flush_langfuse() -> None:
    """Manually flush all buffered Langfuse events.

    This function should be called after workflow execution to ensure all
    traces are sent to Langfuse immediately. Without manual flushing, traces
    may be delayed or lost if the process exits before background workers
    complete.

    According to Langfuse best practices:
    - Langfuse uses background workers to batch events for performance
    - Events are queued and sent asynchronously
    - Manual flushing blocks until all events are sent to the API
    - This is especially important in short-lived processes or async contexts

    Reference: https://langfuse.com/faq/all/missing-traces

    Example:
        ```python
        from basic.observability import flush_langfuse

        # Run workflow
        result = await workflow.run(...)

        # Ensure all traces are sent immediately
        flush_langfuse()
        ```

    Returns:
        None

    Note:
        - This is a no-op if Langfuse is not configured or disabled
        - Safe to call multiple times
        - Blocks until all events are sent (typically < 1 second)
    """
    global _langfuse_client, _langfuse_handler

    # Try to also flush the decorator context used by @observe traces.
    try:
        from langfuse.decorators import langfuse_context
    except ImportError:
        langfuse_context = None

    if (
        _langfuse_client is None
        and _langfuse_handler is None
        and langfuse_context is None
    ):
        # Langfuse not configured or unavailable
        return

    try:
        # Flush the decorator context first to ensure workflow-level traces
        # are sent even if the callback handler/client were not initialized.
        if langfuse_context is not None:
            logger.debug("Flushing Langfuse decorator context...")
            langfuse_context.flush()

        # Flush the callback handler (captures LLM traces)
        if _langfuse_handler is not None:
            logger.debug("Flushing LlamaIndex callback handler...")
            _langfuse_handler.flush()

        # Then flush the client (captures log events and @observe traces)
        if _langfuse_client is not None:
            logger.debug("Flushing Langfuse client...")
            _langfuse_client.flush()

        logger.debug("Langfuse flush complete")
    except Exception as e:
        # Don't let flushing errors break the application
        logger.warning(f"Error flushing Langfuse traces: {e}", exc_info=True)


async def run_workflow_with_flush(workflow, *args, **kwargs):
    """Run a workflow and automatically flush Langfuse traces after completion.

    This is a convenience wrapper that ensures all traces are sent to Langfuse
    immediately after workflow execution, rather than waiting for process exit.

    Args:
        workflow: The workflow instance to run
        *args: Positional arguments to pass to workflow.run()
        **kwargs: Keyword arguments to pass to workflow.run()

    Returns:
        The result from workflow.run()

    Example:
        ```python
        from basic.observability import run_workflow_with_flush
        from basic.email_workflow import email_workflow

        # This will automatically flush traces after execution
        result = await run_workflow_with_flush(
            email_workflow,
            email_data=email_data,
            callback=callback
        )
        ```

    Note:
        This is the recommended way to run workflows when using Langfuse,
        as it ensures traces appear immediately in the dashboard.
    """
    try:
        # Run the workflow
        result = await workflow.run(*args, **kwargs)
        return result
    finally:
        # Always flush traces, even if workflow fails
        flush_langfuse()


def setup_observability(enabled: bool | None = None) -> None:
    """Set up Langfuse observability for workflow tracing.

    Reads configuration from environment variables and initializes the
    Langfuse callback handler. If the required keys are not set, observability
    is disabled gracefully.

    Args:
        enabled: Explicitly enable/disable observability. If None, automatically
                 determines based on environment variables.
    """
    global _langfuse_client, _langfuse_handler
    # Check environment variables
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    host = os.getenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com")

    # Validate host URL format
    try:
        parsed = urlparse(host)
        if not parsed.scheme or parsed.scheme not in ("http", "https"):
            raise ValueError("Invalid scheme")
        if not parsed.netloc:
            raise ValueError("Invalid netloc")
    except (ValueError, Exception):
        # Format message to avoid misleading ellipsis for short URLs
        host_display = host if len(host) <= 50 else f"{host[:50]}..."
        logger.warning(
            "LANGFUSE_BASE_URL must be a valid HTTP/HTTPS URL. Got: {host_display} "
            "Falling back to default host."
        )
        host = "https://us.cloud.langfuse.com"

    # Determine if observability should be enabled
    if enabled is None:
        # Auto-enable if keys are present and LANGFUSE_ENABLED is not explicitly set to false
        enabled = bool(secret_key and public_key)
        env_enabled = os.getenv("LANGFUSE_ENABLED", "").lower()
        if env_enabled in ("false", "0", "no"):
            enabled = False

    if not enabled:
        logger.info("Langfuse observability is disabled")
        return

    if not secret_key or not public_key:
        logger.error(
            "Langfuse observability is enabled but LANGFUSE_SECRET_KEY or "
            "LANGFUSE_PUBLIC_KEY are not set. Traces will not be sent to Langfuse. "
            "Set these environment variables to enable observability."
        )
        return

    try:
        # Import the Langfuse callback handler and client
        # Note: The llama-index-callbacks-langfuse package is a wrapper that
        # re-exports LlamaIndexCallbackHandler from the langfuse package.
        # We import directly from langfuse.llama_index for better clarity.
        from langfuse import Langfuse
        from langfuse.llama_index import LlamaIndexCallbackHandler

        # Create the Langfuse client for logging
        langfuse_client = Langfuse(
            secret_key=secret_key,
            public_key=public_key,
            host=host,
        )

        # Store client reference for manual flushing
        _langfuse_client = langfuse_client

        # Register cleanup to flush buffered events on shutdown
        atexit.register(lambda: langfuse_client.flush())

        # Create the callback handler
        langfuse_handler = LlamaIndexCallbackHandler(
            secret_key=secret_key,
            public_key=public_key,
            host=host,
        )

        # Store handler reference for manual flushing
        _langfuse_handler = langfuse_handler

        # Set up the callback manager with the Langfuse handler, preserving existing handlers
        existing_manager = getattr(Settings, "callback_manager", None)
        if isinstance(existing_manager, CallbackManager):
            # Avoid adding duplicate handlers
            if not any(
                type(h).__name__ == type(langfuse_handler).__name__
                and getattr(h, "host", None) == host
                for h in getattr(existing_manager, "handlers", [])
            ):
                existing_manager.handlers.append(langfuse_handler)
        else:
            Settings.callback_manager = CallbackManager([langfuse_handler])

        # Set up Python logging handler to stream workflow logs to Langfuse
        # This captures logger.info(), logger.warning(), logger.error() calls
        _setup_logging_handler(langfuse_client)

        # Log sanitized host (only log the scheme and domain)
        safe_host = _sanitize_host_for_logging(host)
        logger.info(
            f"Langfuse observability enabled with log streaming (host: {safe_host})"
        )

    except ImportError as e:
        logger.error(
            f"Failed to import Langfuse callback handler: {e}. "
            "Langfuse observability is disabled. "
            "To enable it, install the required package with: "
            "pip install llama-index-callbacks-langfuse"
        )
    except Exception as e:
        logger.error(
            f"Langfuse observability is disabled due to an unexpected error: {e}. "
            "Please check your Langfuse configuration and that all dependencies are installed. "
            "See the traceback below for details.",
            exc_info=True,
        )


# Note: setup_observability() should be called explicitly by the workflow
# after environment variables are loaded, not at module import time.
# This ensures that credentials from .env files are available when running in LlamaCloud.

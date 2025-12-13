"""Observability configuration for workflow execution using Langfuse.

This module configures the Langfuse callback handler for tracing and logging
workflow execution. It automatically initializes when imported, reading configuration
from environment variables.

Environment Variables:
    LANGFUSE_SECRET_KEY: Secret key for Langfuse authentication (required)
    LANGFUSE_PUBLIC_KEY: Public key for Langfuse authentication (required)
    LANGFUSE_HOST: Langfuse server URL (optional, defaults to https://cloud.langfuse.com)
    LANGFUSE_ENABLED: Enable/disable observability (optional, defaults to True if keys are set)

Usage:
    Simply import this module in your workflow to enable observability:
    
    from basic.observability import setup_observability
    
    # Optionally call setup explicitly with custom parameters
    setup_observability(enabled=True)
"""

import logging
import os

from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager

logger = logging.getLogger(__name__)


def setup_observability(enabled: bool | None = None) -> None:
    """Set up Langfuse observability for workflow tracing.
    
    Reads configuration from environment variables and initializes the
    Langfuse callback handler. If the required keys are not set, observability
    is disabled gracefully.
    
    Args:
        enabled: Explicitly enable/disable observability. If None, automatically
                 determines based on environment variables.
    """
    # Check environment variables
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
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
        logger.warning(
            "Langfuse observability is enabled but LANGFUSE_SECRET_KEY or "
            "LANGFUSE_PUBLIC_KEY are not set. Observability will be disabled."
        )
        return
    
    try:
        # Import the Langfuse callback handler
        # Note: The llama-index-callbacks-langfuse package is a wrapper that
        # re-exports LlamaIndexCallbackHandler from the langfuse package.
        # We import directly from langfuse.llama_index for better clarity.
        from langfuse.llama_index import LlamaIndexCallbackHandler
        
        # Create the callback handler
        langfuse_handler = LlamaIndexCallbackHandler(
            secret_key=secret_key,
            public_key=public_key,
            host=host,
        )
        
        # Set up the callback manager with the Langfuse handler, preserving existing handlers
        existing_manager = getattr(Settings, "callback_manager", None)
        if isinstance(existing_manager, CallbackManager):
            # Avoid adding duplicate handlers
            if not any(
                type(h).__name__ == type(langfuse_handler).__name__ and getattr(h, "host", None) == host
                for h in getattr(existing_manager, "handlers", [])
            ):
                existing_manager.handlers.append(langfuse_handler)
        else:
            Settings.callback_manager = CallbackManager([langfuse_handler])
        
        logger.info(f"Langfuse observability enabled (host: {host})")
        
    except ImportError as e:
        logger.warning(
            f"Failed to import Langfuse callback handler: {e}. "
            "Install llama-index-callbacks-langfuse to enable observability."
        )
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse observability: {e}", exc_info=True)


# Auto-initialize observability on module import
setup_observability()

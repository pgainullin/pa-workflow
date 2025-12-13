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
from urllib.parse import urlparse

from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager

logger = logging.getLogger(__name__)


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
    
    # Validate host URL if provided
    if host:
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
                f"LANGFUSE_HOST must be a valid HTTP/HTTPS URL. Got: {host_display} "
                "Falling back to default host."
            )
            host = "https://cloud.langfuse.com"
    
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
            "LANGFUSE_PUBLIC_KEY are not set. Skipping observability setup."
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
        
        # Log sanitized host (only log the scheme and domain)
        safe_host = _sanitize_host_for_logging(host)
        logger.info(f"Langfuse observability enabled (host: {safe_host})")
        
    except ImportError as e:
        logger.warning(
            f"Failed to import Langfuse callback handler: {e}. "
            "Install llama-index-callbacks-langfuse to enable observability."
        )
    except Exception as e:
        logger.error(
            f"Langfuse observability is disabled due to an unexpected error: {e}. "
            "Please check your Langfuse configuration and that all dependencies are installed. "
            "See the traceback below for details.",
            exc_info=True
        )


# Auto-initialize observability on module import
setup_observability()

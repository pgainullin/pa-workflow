"""Utility functions for the basic workflow package."""

from __future__ import annotations

import html
import logging
import os
from typing import TYPE_CHECKING, Optional

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

if TYPE_CHECKING:
    from llama_cloud.client import AsyncLlamaCloud

    from .models import Attachment

logger = logging.getLogger(__name__)


def is_retryable_error(exception: Exception) -> bool:
    """Check if an exception is retryable (transient API errors).
    
    This includes:
    - HTTP 429 (Too Many Requests / Rate Limit)
    - HTTP 500 (Internal Server Error)
    - HTTP 503 (Service Unavailable / Overloaded)
    - Connection errors and timeouts
    
    Args:
        exception: The exception to check
        
    Returns:
        True if the error should be retried
    """
    import re
    
    # Convert exception to string for error message matching
    error_str = str(exception)
    
    # Check for HTTP status codes with context to avoid false positives
    # Matches patterns like "503 UNAVAILABLE", "HTTP 503", "status: 503", etc.
    # But not "503 items"
    if re.search(r'(http\s+)?[45]0[03](\s+(unavailable|error|server|internal|service|too\s+many)|\s*[:\-])', error_str, re.IGNORECASE):
        return True
    
    # Also match common HTTP error formats
    if re.search(r'\b(429|500|503)\s+(error|unavailable|too\s+many|internal|server)', error_str, re.IGNORECASE):
        return True
    
    # Convert to lowercase for remaining checks
    error_str_lower = error_str.lower()
    
    # Check for common transient error messages with word boundaries
    retryable_patterns = [
        r'\brate.?limit',  # rate limit, rate-limit
        r'\bquota\s+(exceeded|limit)',  # quota exceeded/limit
        r'\boverload(ed)?',
        r'\bunavailable\b',  # unavailable (not unavailability)
        r'\btimeout\b',  # timeout (not timeouts as part of other words)
        r'\bconnection\s+(error|refused|failed|timeout)',  # connection error/refused/failed
        r'\btemporarily\s+unavailable',
    ]
    
    for pattern in retryable_patterns:
        if re.search(pattern, error_str_lower):
            return True
    
    # Check for httpx-specific errors
    try:
        import httpx
        if isinstance(exception, (httpx.TimeoutException, httpx.ConnectError)):
            return True
    except ImportError:
        pass
    
    return False


# Create a reusable retry decorator for API calls
api_retry = retry(
    retry=retry_if_exception(is_retryable_error),
    stop=stop_after_attempt(5),  # Maximum 5 attempts
    wait=wait_exponential(multiplier=1, min=1, max=45),  # Exponential backoff: 1s, 2s, 4s, 8s, 16s (max 45s)
    before_sleep=before_sleep_log(logger, logging.WARNING),  # Log retry attempts
    reraise=True,  # Re-raise the exception after all retries exhausted
)


def text_to_html(text: str) -> str:
    """Convert plain text to simple HTML format.

    Args:
        text: Plain text string with newlines

    Returns:
        HTML-formatted string with paragraphs
    """
    # Escape HTML special characters to prevent XSS
    escaped_text = html.escape(text)
    # Split text into paragraphs (separated by double newlines)
    paragraphs = escaped_text.split("\n\n")
    # Wrap each paragraph in <p> tags, converting single newlines to <br>
    html_paragraphs = [
        f"<p>{para.replace(chr(10), '<br>')}</p>" for para in paragraphs if para.strip()
    ]
    return "".join(html_paragraphs)


async def get_llama_cloud_client() -> tuple["AsyncLlamaCloud", str]:
    """Get an AsyncLlamaCloud client instance for LlamaCloud operations.
    
    Returns:
        tuple: (AsyncLlamaCloud client, project_id)
        
    Raises:
        ValueError: If required environment variables are not set
    """
    from llama_cloud.client import AsyncLlamaCloud

    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key:
        raise ValueError("LLAMA_CLOUD_API_KEY environment variable is required")
    
    project_id = os.getenv("LLAMA_CLOUD_PROJECT_ID")
    if not project_id:
        raise ValueError("LLAMA_CLOUD_PROJECT_ID environment variable is required")
    
    client = AsyncLlamaCloud(token=api_key)
    return client, project_id


@api_retry
async def download_file_from_llamacloud(file_id: str) -> bytes:
    """Download a file from LlamaCloud using its file_id.
    
    This function automatically retries on transient errors (503, 429, 500)
    with exponential backoff.
    
    Args:
        file_id: The LlamaCloud file ID
        
    Returns:
        The file content as bytes
        
    Raises:
        ValueError: If file_id is invalid, file cannot be downloaded, or any
            LlamaCloud API error occurs. The original exception is preserved
            in the chain for debugging.
    """
    import httpx
    
    try:
        client, project_id = await get_llama_cloud_client()
        
        # Get presigned URL for the file
        presigned_url_obj = await client.files.read_file_content(
            id=file_id,
            project_id=project_id
        )
        
        # Fetch the actual file content from the presigned URL
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(presigned_url_obj.url)
            response.raise_for_status()
            content = response.content
            
        logger.info(f"Successfully downloaded file {file_id} from LlamaCloud")
        return content
    except ValueError:
        # Re-raise ValueError from get_llama_cloud_client (missing env vars)
        raise
    except Exception as e:
        # Wrap all LlamaCloud API errors (network, auth, not found, etc.)
        # in ValueError with preserved exception chain for debugging
        logger.error(f"Failed to download file {file_id} from LlamaCloud: {e}")
        raise ValueError(f"Failed to download file {file_id} from LlamaCloud: {e}") from e


@api_retry
async def upload_file_to_llamacloud(
    file_content: bytes, filename: str, external_file_id: Optional[str] = None
) -> str:
    """Upload a file to LlamaCloud.
    
    This function automatically retries on transient errors (503, 429, 500)
    with exponential backoff.
    
    Args:
        file_content: The file content as bytes
        filename: The filename for the uploaded file
        external_file_id: Optional external ID to use for the file
        
    Returns:
        The LlamaCloud file_id of the uploaded file
        
    Raises:
        ValueError: If upload fails due to any reason (network, auth, quota, etc.).
            The original exception is preserved in the chain for debugging.
    """
    import io
    
    try:
        client, project_id = await get_llama_cloud_client()
        
        # Create a file-like object from bytes
        file_obj = io.BytesIO(file_content)
        file_obj.name = filename
        
        # Upload the file
        file = await client.files.upload_file(
            upload_file=file_obj,
            external_file_id=external_file_id or filename,
            project_id=project_id
        )
        
        logger.info(f"Successfully uploaded file {filename} to LlamaCloud: {file.id}")
        return file.id
    except ValueError:
        # Re-raise ValueError from get_llama_cloud_client (missing env vars)
        raise
    except Exception as e:
        # Wrap all LlamaCloud API errors (network, auth, quota, etc.)
        # in ValueError with preserved exception chain for debugging
        logger.error(f"Failed to upload file {filename} to LlamaCloud: {e}")
        raise ValueError(f"Failed to upload file {filename} to LlamaCloud: {e}") from e


async def create_llamacloud_attachment(
    file_content: bytes,
    filename: str,
    content_type: str,
    attachment_id: Optional[str] = None,
    external_file_id: Optional[str] = None,
) -> "Attachment":
    """Create an Attachment with file uploaded to LlamaCloud.
    
    This is a convenience function for creating attachments that reference
    files in LlamaCloud. The file is uploaded first, then an Attachment
    object is created with the file_id.
    
    Use this when preparing attachments to send back in email callbacks.
    
    Args:
        file_content: The file content as bytes
        filename: The filename for the attachment
        content_type: The MIME type (e.g., 'application/pdf')
        attachment_id: Optional ID for the attachment (defaults to filename)
        external_file_id: Optional external ID for the file in LlamaCloud
        
    Returns:
        Attachment object with file_id pointing to the uploaded file
        
    Raises:
        ValueError: If upload fails
        
    Example:
        # Upload a generated report and create attachment for callback
        report_data = generate_report()
        attachment = await create_llamacloud_attachment(
            file_content=report_data,
            filename="report.pdf",
            content_type="application/pdf"
        )
        
        # Include in email response
        response_email = SendEmailRequest(
            to_email=user_email,
            subject="Your Report",
            text="Please find your report attached",
            attachments=[attachment]
        )
    """
    from .models import Attachment

    # Upload file to LlamaCloud
    file_id = await upload_file_to_llamacloud(
        file_content, filename, external_file_id
    )
    
    # Create Attachment with file_id
    return Attachment(
        id=attachment_id or filename,
        name=filename,
        type=content_type,
        file_id=file_id,
    )



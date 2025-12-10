"""Utility functions for the basic workflow package."""

import html
import logging
import os
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .models import Attachment

logger = logging.getLogger(__name__)


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


async def get_file_client():
    """Get a FileClient instance for LlamaCloud operations.
    
    Returns:
        FileClient configured with API key and project ID from environment
        
    Raises:
        ValueError: If required environment variables are not set
    """
    from llama_cloud_services import AsyncLlamaCloud, FileClient

    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key:
        raise ValueError("LLAMA_CLOUD_API_KEY environment variable is required")
    
    project_id = os.getenv("LLAMA_CLOUD_PROJECT_ID")
    if not project_id:
        raise ValueError("LLAMA_CLOUD_PROJECT_ID environment variable is required")
    
    client = AsyncLlamaCloud(api_key=api_key)
    return FileClient(client, project_id=project_id)


async def download_file_from_llamacloud(file_id: str) -> bytes:
    """Download a file from LlamaCloud using its file_id.
    
    Args:
        file_id: The LlamaCloud file ID
        
    Returns:
        The file content as bytes
        
    Raises:
        ValueError: If file_id is invalid or file cannot be downloaded
    """
    try:
        file_client = await get_file_client()
        content = await file_client.read_file_content(file_id=file_id)
        logger.info(f"Successfully downloaded file {file_id} from LlamaCloud")
        return content
    except Exception as e:
        logger.error(f"Failed to download file {file_id} from LlamaCloud: {e}")
        raise ValueError(f"Failed to download file from LlamaCloud: {e}") from e


async def upload_file_to_llamacloud(
    file_content: bytes, filename: str, external_file_id: Optional[str] = None
) -> str:
    """Upload a file to LlamaCloud.
    
    Args:
        file_content: The file content as bytes
        filename: The filename for the uploaded file
        external_file_id: Optional external ID to use for the file
        
    Returns:
        The LlamaCloud file_id of the uploaded file
        
    Raises:
        ValueError: If upload fails
    """
    try:
        file_client = await get_file_client()
        file = await file_client.upload_bytes(
            file_content, filename=filename, external_file_id=external_file_id
        )
        logger.info(f"Successfully uploaded file {filename} to LlamaCloud: {file.id}")
        return file.id
    except Exception as e:
        logger.error(f"Failed to upload file {filename} to LlamaCloud: {e}")
        raise ValueError(f"Failed to upload file to LlamaCloud: {e}") from e


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



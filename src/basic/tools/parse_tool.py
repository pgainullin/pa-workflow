"""Tool for parsing documents using LlamaCloud Parse."""

from __future__ import annotations

import base64
import logging
import pathlib
import tempfile
from typing import Any

from .base import Tool
from ..utils import download_file_from_llamacloud, api_retry

logger = logging.getLogger(__name__)


class ParseTool(Tool):
    """Tool for parsing documents using LlamaCloud Parse."""

    def __init__(self, llama_parser):
        self.llama_parser = llama_parser

    @property
    def name(self) -> str:
        return "parse"

    @property
    def description(self) -> str:
        return (
            "Parse documents (PDF, Word, PowerPoint, etc.) into structured text using LlamaParse. "
            "Input: file_id (LlamaCloud file ID) or file_content (base64-encoded). "
            "Output: parsed_text (markdown format)"
        )

    def _is_valid_uuid(self, value: str) -> bool:
        """Check if a string is a valid UUID.

        Args:
            value: String to check

        Returns:
            True if the string is a valid UUID format
        """
        try:
            import uuid

            uuid.UUID(value)
            return True
        except (ValueError, AttributeError):
            return False

    @api_retry
    async def _parse_with_retry(self, tmp_path: str, file_extension: str = ".pdf") -> tuple[list, str]:
        """Parse document with automatic retry on transient errors.

        Args:
            tmp_path: Path to the temporary file to parse
            file_extension: File extension for diagnostic logging

        Returns:
            Tuple of (list of parsed documents, parsed text content)

        Raises:
            Exception: If parsing fails after all retry attempts or if content is empty
        """
        import asyncio

        documents = await asyncio.to_thread(self.llama_parser.load_data, tmp_path)
        parsed_text = "\n".join([doc.get_content() for doc in documents])
        
        # Validate that we got some content - if not, raise an exception to trigger retry
        if not parsed_text or not parsed_text.strip():
            logger.warning(
                f"ParseTool returned empty text for file (will retry). "
                f"Documents returned: {len(documents)}, "
                f"File extension: {file_extension}"
            )
            raise Exception(
                f"Document parsing returned no text content (documents: {len(documents)}). "
                "Content temporarily unavailable and will be retried."
            )
        
        return documents, parsed_text

    async def execute(self, **kwargs) -> dict[str, Any]:
        """Parse a document using LlamaParse.

        Args:
            **kwargs: Keyword arguments including:
                - file_id: LlamaCloud file ID (optional)
                - file_content: Base64-encoded file content (optional)
                - filename: Original filename for extension detection (optional)

        Returns:
            Dictionary with 'success' and 'parsed_text' or 'error'
        """
        import tempfile
        import pathlib

        file_id = kwargs.get("file_id")
        file_content = kwargs.get("file_content")
        file_content_from_param = kwargs.get(
            "file_id_content"
        )  # Added by _resolve_params when file_id is None
        filename = kwargs.get("filename") or kwargs.get(
            "file_id_filename"
        )  # Also check for filename from _resolve_params

        try:
            # Get file content
            if file_id:
                # Validate file_id looks like a UUID
                if not self._is_valid_uuid(file_id):
                    # file_id doesn't look like a UUID - might be a filename
                    # Try to use file_content as fallback if available
                    if file_content or file_content_from_param:
                        logger.warning(
                            f"file_id '{file_id}' doesn't appear to be a valid UUID. "
                            f"Using base64 content instead."
                        )
                        content = base64.b64decode(
                            file_content or file_content_from_param
                        )
                    else:
                        return {
                            "success": False,
                            "error": f"file_id '{file_id}' is not a valid UUID and no file_content available. "
                            f"The file reference might not have been resolved correctly.",
                        }
                else:
                    content = await download_file_from_llamacloud(file_id)
            elif file_content or file_content_from_param:
                content = base64.b64decode(file_content or file_content_from_param)
            else:
                return {
                    "success": False,
                    "error": "Either file_id or file_content must be provided",
                }

            # Create temporary file for LlamaParse
            # Determine file extension from filename if provided
            file_extension = ".pdf"  # Default to .pdf
            if filename:
                import os

                _, ext = os.path.splitext(filename)
                if ext:
                    file_extension = ext

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=file_extension
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                # Parse the document with automatic retry
                # The retry logic now includes content validation
                documents, parsed_text = await self._parse_with_retry(tmp_path, file_extension)
                
                return {"success": True, "parsed_text": parsed_text}
            finally:
                # Clean up temp file
                pathlib.Path(tmp_path).unlink()

        except Exception as e:
            logger.exception("Error parsing document")
            error_msg = str(e)
            # Make error message more user-friendly for empty content issues
            if "no text content" in error_msg.lower():
                error_msg = "Document parsing returned no text content. The document may be empty, corrupted, or in an unsupported format."
            return {"success": False, "error": error_msg}

"""Tool for parsing documents using LlamaCloud Parse."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import pathlib
import tempfile
import uuid
from typing import Any

from llama_parse import LlamaParse

from .base import Tool
from ..utils import download_file_from_llamacloud, api_retry, MAX_RETRY_ATTEMPTS

logger = logging.getLogger(__name__)


class ParseTool(Tool):
    """Tool for parsing documents using LlamaCloud Parse."""

    def __init__(self, llama_parser=None):
        """Initialize the ParseTool.

        Args:
            llama_parser: Optional LlamaParse instance. If not provided,
                         one will be created using environment variables.
        """
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
            uuid.UUID(value)
            return True
        except (ValueError, AttributeError):
            return False

    def _is_text_file(self, file_extension: str) -> bool:
        """Check if a file is a text-based file that doesn't need LlamaParse.

        Args:
            file_extension: File extension to check

        Returns:
            True if the file is a text-based file
        """
        # Common text file extensions that don't need LlamaParse.
        # Note: .csv is included as a fallback - while SheetsTool provides better
        # structured parsing, ParseTool can handle CSV as plain text when triage
        # incorrectly assigns a Parse step instead of a Sheets step.
        text_extensions = {
            ".txt", ".md", ".markdown", ".text", ".log",
            ".csv", ".tsv", ".json", ".xml", ".html", ".htm",
            ".yaml", ".yml", ".ini", ".cfg", ".conf",
        }
        return file_extension.lower() in text_extensions

    @api_retry
    async def _parse_with_retry(self, tmp_path: str, file_extension: str = ".pdf") -> tuple[list, str, int]:
        """Parse document with automatic retry on transient errors.

        Args:
            tmp_path: Path to the temporary file to parse
            file_extension: File extension for diagnostic logging

        Returns:
            Tuple of (list of parsed documents, parsed text content, attempt number)

        Raises:
            Exception: If parsing fails after all retry attempts or if content is empty
        """
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
        
        return documents, parsed_text, 1

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
        file_id = kwargs.get("file_id")
        file_content = kwargs.get("file_content")
        file_content_from_param = kwargs.get(
            "file_id_content"
        )  # Added by _resolve_params when file_id is None
        filename = kwargs.get("filename") or kwargs.get(
            "file_id_filename"
        )  # Also check for filename from _resolve_params

        # Initialize variables that may be referenced in exception handler
        content = None
        file_extension = ".pdf"  # Default extension

        try:
            # Get or create LlamaParse instance
            if self.llama_parser is None:
                # Using LlamaParse v2 API with tier-based configuration
                # Note: high_res_ocr, adaptive_long_table, and outlined_table_extraction
                # are always enabled in v2 and no longer need to be specified
                self.llama_parser = LlamaParse(
                    result_type="markdown",
                    language="en,ch_sim,ch_tra,ja,ko,ar,hi,th,vi",  # Multi-language OCR support
                    tier="agentic",  # v2 tier: fast, cost_effective, agentic, or agentic_plus
                    # Agentic tier provides best quality for complex documents with tables/images
                    # Previously used parse_mode="parse_page_with_agent" which is now replaced by tier system
                )

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
                # No file provided - this can happen when LLM incorrectly schedules a parse step
                # for non-existent attachments. Fail gracefully to avoid breaking downstream steps.
                logger.warning(
                    "ParseTool called without file_id or file_content. "
                    "This likely means the LLM scheduled a parse step for a non-existent attachment. "
                    "Skipping parse and returning empty result."
                )
                return {
                    "success": True,
                    "parsed_text": "",
                    "skipped": True,
                    "message": "No file provided to parse - step skipped",
                }

            if not content:
                logger.warning(
                    f"Empty file content provided to ParseTool (filename: {filename or 'unknown'}). "
                    "Skipping parse and returning empty result."
                )
                return {
                    "success": True,
                    "parsed_text": "",
                    "skipped": True,
                    "message": "File content is empty - step skipped",
                }

            # Determine file extension from filename if provided
            file_extension = ".pdf"  # Default to .pdf
            if filename:
                _, ext = os.path.splitext(filename)
                if ext:
                    file_extension = ext

            # Check if this is a text file that doesn't need LlamaParse
            if self._is_text_file(file_extension):
                logger.info(
                    f"ParseTool: Detected text file ({file_extension}), "
                    f"returning content directly without LlamaParse"
                )
                try:
                    # Decode the content as text
                    parsed_text = content.decode("utf-8")
                    return {"success": True, "parsed_text": parsed_text}
                except UnicodeDecodeError:
                    # If UTF-8 fails, try other common encodings
                    for encoding in ["latin-1", "cp1252", "iso-8859-1"]:
                        try:
                            parsed_text = content.decode(encoding)
                            logger.info(f"Decoded text file using {encoding} encoding")
                            return {"success": True, "parsed_text": parsed_text}
                        except UnicodeDecodeError:
                            continue
                    # If all encodings fail, return error instead of falling through
                    error_msg = (
                        f"Failed to decode text file ({file_extension}) with UTF-8, "
                        "latin-1, cp1252, or iso-8859-1 encodings. "
                        "The file may be corrupted or in an unsupported encoding."
                    )
                    logger.error(error_msg)
                    return {"success": False, "error": error_msg}

            # For binary documents, use LlamaParse
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=file_extension
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                # Parse the document with automatic retry
                # The retry logic now includes content validation
                documents, parsed_text, _ = await self._parse_with_retry(tmp_path, file_extension)
                
                return {"success": True, "parsed_text": parsed_text}
            finally:
                # Clean up temp file
                pathlib.Path(tmp_path).unlink()

        except Exception as e:
            error_msg = str(e)
            # Make error message more user-friendly for empty content issues
            if "no text content" in error_msg.lower():
                # Log as warning instead of exception to avoid scary tracebacks for expected failures
                logger.warning(
                    f"ParseTool failed after all retries: {error_msg}. "
                    f"File: {filename or 'unknown'}, Extension: {file_extension}"
                )
                
                # Return success with empty content and diagnostic info to avoid blocking downstream steps
                # This allows the workflow to continue even when parse fails persistently
                return {
                    "success": True,
                    "parsed_text": "",
                    "parse_failed": True,  # Flag to indicate parse failure
                    "parse_warning": "Document parsing returned no text content after multiple retries. "
                                   "The document may be empty, corrupted, in an unsupported format, "
                                   "or the parsing service may be experiencing issues.",
                    "filename": filename or "unknown",
                    "file_extension": file_extension,
                    "retry_exhausted": True,
                    "diagnostic_info": {
                        "error_type": "empty_content_after_retries",
                        "max_retries": MAX_RETRY_ATTEMPTS,
                        "file_size_bytes": len(content) if content else 0,
                    }
                }
            else:
                logger.exception("Error parsing document")
            
            return {"success": False, "error": error_msg}

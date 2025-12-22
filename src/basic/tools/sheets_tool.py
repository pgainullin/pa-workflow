"""Tool for processing spreadsheets using LlamaParse."""

from __future__ import annotations

import base64
import logging
import os
import pathlib
import tempfile
from typing import Any

from llama_parse import LlamaParse

from .base import Tool
from ..utils import download_file_from_llamacloud

logger = logging.getLogger(__name__)


class SheetsTool(Tool):
    """Tool for processing spreadsheets using LlamaParse."""

    def __init__(self, llama_parser=None):
        """Initialize the SheetsTool.

        Args:
            llama_parser: Optional LlamaParse instance. If not provided,
                         one will be created using environment variables.
        """
        self.llama_parser = llama_parser

    @property
    def name(self) -> str:
        return "sheets"

    @property
    def description(self) -> str:
        return (
            "Process spreadsheet files (Excel, CSV) using LlamaParse. "
            "Input: file_id or file_content (base64), filename (optional). "
            "Output: sheet_data (parsed spreadsheet content as JSON)"
        )

    async def execute(self, **kwargs) -> dict[str, Any]:
        """Process a spreadsheet file using LlamaParse.

        Args:
            **kwargs: Keyword arguments including:
                - file_id: LlamaCloud file ID (optional)
                - file_content: Base64-encoded file content (optional)
                - filename: Filename for format detection (optional)

        Returns:
            Dictionary with 'success' and 'sheet_data' or 'error'
        """
        file_id = kwargs.get("file_id")
        file_content = kwargs.get("file_content")
        file_content_from_param = kwargs.get("file_id_content")
        filename = kwargs.get("filename") or kwargs.get("file_id_filename")

        try:
            # Get or create LlamaParse instance
            if self.llama_parser is None:
                self.llama_parser = LlamaParse(
                    result_type="markdown",
                    language="en,ch_sim,ch_tra,ja,ko,ar,hi,th,vi",  # Multi-language OCR support
                    high_res_ocr=True,  # Enable high-resolution OCR for scanned documents
                    parse_mode="parse_page_with_agent",  # Use agent-based parsing for better accuracy
                    adaptive_long_table=True,  # Better handling of long tables
                    outlined_table_extraction=True,  # Extract outlined tables
                    output_tables_as_HTML=True,  # Output tables in HTML format
                )

            # Get file content
            if file_id:
                content = await download_file_from_llamacloud(file_id)
            elif file_content or file_content_from_param:
                content = base64.b64decode(file_content or file_content_from_param)
            else:
                # No file provided - this can happen when LLM incorrectly schedules a sheets step
                # for non-existent attachments. Fail gracefully to avoid breaking downstream steps.
                logger.warning(
                    "SheetsTool called without file_id or file_content. "
                    "This likely means the LLM scheduled a sheets step for a non-existent attachment. "
                    "Skipping sheets processing and returning empty result."
                )
                return {
                    "success": True,
                    "sheet_data": {"tables": [], "table_count": 0},
                    "skipped": True,
                    "message": "No file provided to process - step skipped",
                }

            # Determine file extension from filename
            file_extension = ".xlsx"  # Default to Excel
            if filename:
                _, ext = os.path.splitext(filename.lower())
                if ext:
                    file_extension = ext

            # Create temporary file for LlamaParse and ensure cleanup
            tmp_path = None
            try:
                # Create temporary file for LlamaParse
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=file_extension
                ) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name

                # Parse the spreadsheet using LlamaParse
                # LlamaParse returns JSON representation of tables
                json_result = await self.llama_parser.aget_json(tmp_path)

                # Extract table data from the JSON result
                # The json_result contains parsed table data in a structured format
                sheet_data = {
                    "tables": json_result,
                    "table_count": len(json_result)
                    if isinstance(json_result, list)
                    else 1,
                }

                return {"success": True, "sheet_data": sheet_data}

            finally:
                # Clean up temp file if it was created
                if tmp_path and pathlib.Path(tmp_path).exists():
                    pathlib.Path(tmp_path).unlink()

        except Exception as e:
            logger.exception("Error processing spreadsheet")
            return {"success": False, "error": str(e)}

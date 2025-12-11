"""Tool implementations for the agent triage workflow.

This module provides tool implementations that can be used by the triage agent
to process email attachments and content.
"""

from __future__ import annotations

import base64
import io
import logging
from abc import ABC, abstractmethod
from typing import Any

from deep_translator import GoogleTranslator
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .utils import (
    download_file_from_llamacloud,
    upload_file_to_llamacloud,
)

logger = logging.getLogger(__name__)


class Tool(ABC):
    """Abstract base class for workflow tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return the tool description for the LLM."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> dict[str, Any]:
        """Execute the tool with the given parameters.

        Returns:
            Dictionary containing the tool execution results
        """
        pass


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

    async def execute(
        self, file_id: str | None = None, file_content: str | None = None
    ) -> dict[str, Any]:
        """Parse a document using LlamaParse.

        Args:
            file_id: LlamaCloud file ID
            file_content: Base64-encoded file content

        Returns:
            Dictionary with 'success' and 'parsed_text' or 'error'
        """
        import asyncio
        import tempfile
        import pathlib

        try:
            # Get file content
            if file_id:
                content = await download_file_from_llamacloud(file_id)
            elif file_content:
                content = base64.b64decode(file_content)
            else:
                return {
                    "success": False,
                    "error": "Either file_id or file_content must be provided",
                }

            # Create temporary file for LlamaParse
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                # Parse the document
                documents = await asyncio.to_thread(
                    self.llama_parser.load_data, tmp_path
                )
                parsed_text = "\n".join([doc.get_content() for doc in documents])
                return {"success": True, "parsed_text": parsed_text}
            finally:
                # Clean up temp file
                pathlib.Path(tmp_path).unlink()

        except Exception as e:
            logger.exception("Error parsing document")
            return {"success": False, "error": str(e)}


class ExtractTool(Tool):
    """Tool for extracting structured data using LlamaCloud Extract."""

    @property
    def name(self) -> str:
        return "extract"

    @property
    def description(self) -> str:
        return (
            "Extract structured data from documents using LlamaCloud Extract. "
            "Input: file_id, schema (JSON schema definition). "
            "Output: extracted_data (structured JSON)"
        )

    async def execute(self, file_id: str, schema: dict) -> dict[str, Any]:
        """Extract structured data from a document.

        Args:
            file_id: LlamaCloud file ID
            schema: JSON schema for extraction

        Returns:
            Dictionary with 'success' and 'extracted_data' or 'error'
        """
        # Note: This is a placeholder implementation
        # Real implementation would use LlamaCloud Extract API
        return {
            "success": True,
            "extracted_data": {
                "note": "Extract tool requires LlamaCloud Extract API integration"
            },
        }


class SheetsTool(Tool):
    """Tool for processing spreadsheets using LlamaCloud."""

    @property
    def name(self) -> str:
        return "sheets"

    @property
    def description(self) -> str:
        return (
            "Process spreadsheet files (Excel, CSV, Google Sheets). "
            "Input: file_id. "
            "Output: sheet_data (parsed spreadsheet content)"
        )

    async def execute(self, file_id: str) -> dict[str, Any]:
        """Process a spreadsheet file.

        Args:
            file_id: LlamaCloud file ID

        Returns:
            Dictionary with 'success' and 'sheet_data' or 'error'
        """
        # Note: This is a placeholder implementation
        return {
            "success": True,
            "sheet_data": {
                "note": "Sheets tool requires specific spreadsheet processing implementation"
            },
        }


class SplitTool(Tool):
    """Tool for splitting documents into sections using LlamaCloud."""

    @property
    def name(self) -> str:
        return "split"

    @property
    def description(self) -> str:
        return (
            "Split documents into logical sections or chunks. "
            "Input: text or file_id, split_strategy (e.g., 'by_section', 'by_page'). "
            "Output: splits (list of document sections)"
        )

    async def execute(
        self,
        text: str | None = None,
        file_id: str | None = None,
        split_strategy: str = "by_section",
    ) -> dict[str, Any]:
        """Split a document into sections.

        Args:
            text: Text content to split
            file_id: LlamaCloud file ID
            split_strategy: Strategy for splitting

        Returns:
            Dictionary with 'success' and 'splits' or 'error'
        """
        try:
            if text:
                # Simple split by double newlines as placeholder
                splits = text.split("\n\n")
                return {"success": True, "splits": splits}
            elif file_id:
                # Download and split
                content = await download_file_from_llamacloud(file_id)
                text = content.decode("utf-8", errors="ignore")
                splits = text.split("\n\n")
                return {"success": True, "splits": splits}
            else:
                return {
                    "success": False,
                    "error": "Either text or file_id must be provided",
                }
        except Exception as e:
            logger.exception("Error splitting document")
            return {"success": False, "error": str(e)}


class ClassifyTool(Tool):
    """Tool for classifying content using LlamaCloud."""

    def __init__(self, llm):
        self.llm = llm

    @property
    def name(self) -> str:
        return "classify"

    @property
    def description(self) -> str:
        return (
            "Classify text or documents into categories. "
            "Input: text, categories (list of possible categories). "
            "Output: category (selected category)"
        )

    async def execute(self, data: dict[str, Any]) -> dict[str, Any]:
        """Classify text into one of the given categories.

        Args:
            data: Dictionary with keys 'text' and 'categories'

        Returns:
            Dictionary with 'success', 'category' or 'error'
        """
        try:
            text = data.get("text")
            categories = data.get("categories")
            if not text or not categories:
                return {"success": False, "error": "Both 'text' and 'categories' must be provided"}
            prompt = (
                f"Classify the following text into one of these categories: {', '.join(categories)}\n\n"
                f"Text: {text}\n\n"
                "Respond with only the category name."
            )
            response = await self.llm.acomplete(prompt)
            category = str(response).strip()

            return {"success": True, "category": category}
        except Exception as e:
            logger.exception("Error classifying text")
            return {"success": False, "error": str(e)}


class TranslateTool(Tool):
    """Tool for translating text using Google Translate."""

    @property
    def name(self) -> str:
        return "translate"

    @property
    def description(self) -> str:
        return (
            "Translate text from one language to another using Google Translate. "
            "Input: text, source_lang (default: 'auto'), target_lang (default: 'en'). "
            "Output: translated_text"
        )

    async def execute(
        self, text: str, source_lang: str = "auto", target_lang: str = "en"
    ) -> dict[str, Any]:
        """Translate text to target language.

        Args:
            text: Text to translate
            source_lang: Source language code (auto-detect if 'auto')
            target_lang: Target language code

        Returns:
            Dictionary with 'success', 'translated_text' or 'error'
        """
        try:
            import asyncio

            # Create translator instance for this translation
            translator = GoogleTranslator(source=source_lang, target=target_lang)

            # Run translation in thread pool since deep-translator is synchronous
            translated = await asyncio.to_thread(translator.translate, text)

            return {"success": True, "translated_text": translated}
        except Exception as e:
            logger.exception("Error translating text")
            return {"success": False, "error": str(e)}


class SummariseTool(Tool):
    """Tool for summarising text using an LLM."""

    def __init__(self, llm):
        self.llm = llm

    @property
    def name(self) -> str:
        return "summarise"

    @property
    def description(self) -> str:
        return (
            "Summarise long text into a concise summary using an LLM. "
            "Input: text, max_length (optional, target summary length in words). "
            "Output: summary"
        )

    async def execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """Summarise text using an LLM.

        Args:
            input: Dictionary with keys:
                - 'text': Text to summarise (required)
                - 'max_length': Target summary length in words (optional)

        Returns:
            Dictionary with 'success' and 'summary' or 'error'
        """
        try:
            text = input.get("text")
            max_length = input.get("max_length")
            length_instruction = f" in about {max_length} words" if max_length else ""
            prompt = (
                f"Provide a concise summary{length_instruction} of the following text:\n\n"
                f"{text}"
            )
            response = await self.llm.acomplete(prompt)
            summary = str(response).strip()

            return {"success": True, "summary": summary}
        except Exception as e:
            logger.exception("Error summarising text")
            return {"success": False, "error": str(e)}


class PrintToPDFTool(Tool):
    """Tool for converting text to PDF."""

    # PDF layout constants
    PDF_MARGIN_INCHES = 1  # 1 inch margins
    PDF_MARGIN_POINTS = 72  # 72 points = 1 inch
    PDF_LINE_SPACING = 15  # Points between lines
    PDF_MAX_LINE_WIDTH = 468  # Max width in points (letter width - 2*margin)
    PDF_FONT_SIZE = 12  # Default font size
    PDF_FONT_NAME = "Helvetica"  # Default font

    @property
    def name(self) -> str:
        return "print_to_pdf"

    @property
    def description(self) -> str:
        return (
            "Convert text content to a PDF file. "
            "Input: text, filename (optional). "
            "Output: file_id (LlamaCloud file ID of generated PDF)"
        )

    def _wrap_text(self, text: str, canvas_obj, max_width: float) -> list[str]:
        """Wrap text to fit within the specified width.

        Args:
            text: Text to wrap
            canvas_obj: ReportLab canvas object for measuring text width
            max_width: Maximum width in points

        Returns:
            List of wrapped lines
        """
        words = text.split(" ")
        lines = []
        current_line = ""

        for word in words:
            # Test if adding this word would exceed the width
            test_line = current_line + (" " if current_line else "") + word
            text_width = canvas_obj.stringWidth(
                test_line, self.PDF_FONT_NAME, self.PDF_FONT_SIZE
            )

            if text_width <= max_width:
                current_line = test_line
            else:
                # Current line is full, save it and start a new line
                if current_line:
                    lines.append(current_line)
                    current_line = word
                else:
                    # Single word is too long, we need to break it
                    lines.append(word[:100])  # Fallback: truncate extremely long words
                    current_line = ""

        # Add the last line
        if current_line:
            lines.append(current_line)

        return lines if lines else [""]

    async def execute(self, input: str) -> dict[str, Any]:
        """Convert text to PDF and upload to LlamaCloud.

        Args:
            input: Input string containing text and optionally filename.
                If input is a JSON string: {"text": "...", "filename": "..."}
                If input is plain text, filename defaults to "output.pdf".

        Returns:
            Dictionary with 'success' and 'file_id' or 'error'
        """
        import json

        try:
            # Try to parse input as JSON for text and filename
            text = None
            filename = "output.pdf"
            try:
                data = json.loads(input)
                if isinstance(data, dict) and "text" in data:
                    text = data["text"]
                    filename = data.get("filename", "output.pdf")
                else:
                    text = input
            except Exception:
                # Not JSON, treat input as plain text
                text = input

            # Create PDF in memory
            pdf_buffer = io.BytesIO()
            pdf_canvas = canvas.Canvas(pdf_buffer, pagesize=letter)
            pdf_canvas.setFont(self.PDF_FONT_NAME, self.PDF_FONT_SIZE)

            # Set up text
            width, height = letter
            y_position = height - self.PDF_MARGIN_POINTS

            # Split text into lines and write to PDF
            input_lines = text.split("\n")
            for input_line in input_lines:
                # Wrap long lines
                wrapped_lines = self._wrap_text(
                    input_line, pdf_canvas, self.PDF_MAX_LINE_WIDTH
                )

                for wrapped_line in wrapped_lines:
                    # Check if we need a new page
                    if y_position < self.PDF_MARGIN_POINTS:
                        pdf_canvas.showPage()
                        pdf_canvas.setFont(self.PDF_FONT_NAME, self.PDF_FONT_SIZE)
                        y_position = height - self.PDF_MARGIN_POINTS

                    # Replace characters that can't be encoded in latin-1 (default font encoding)
                    safe_line = wrapped_line.encode("latin-1", errors="replace").decode(
                        "latin-1"
                    )
                    pdf_canvas.drawString(self.PDF_MARGIN_POINTS, y_position, safe_line)
                    y_position -= self.PDF_LINE_SPACING  # Move down for next line

            pdf_canvas.save()

            # Get PDF bytes
            pdf_bytes = pdf_buffer.getvalue()

            # Upload to LlamaCloud
            file_id = await upload_file_to_llamacloud(pdf_bytes, filename)

            return {"success": True, "file_id": file_id}
        except Exception as e:
            logger.exception("Error creating PDF")
            return {"success": False, "error": str(e)}


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self):
        self.tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register
        """
        self.tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool | None:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self.tools.get(name)

    def get_tool_descriptions(self) -> str:
        """Get descriptions of all registered tools.

        Returns:
            Formatted string with all tool descriptions
        """
        descriptions = []
        for tool in self.tools.values():
            descriptions.append(f"- **{tool.name}**: {tool.description}")
        return "\n".join(descriptions)

    def list_tool_names(self) -> list[str]:
        """Get list of all registered tool names.

        Returns:
            List of tool names
        """
        return list(self.tools.keys())

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
        import asyncio
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

    def __init__(self, llama_extract=None):
        """Initialize the ExtractTool.

        Args:
            llama_extract: Optional LlamaExtract instance. If not provided,
                          one will be created using environment variables.
        """
        self.llama_extract = llama_extract
        self._extract_agent = None

    @property
    def name(self) -> str:
        return "extract"

    @property
    def description(self) -> str:
        return (
            "Extract structured data from documents using LlamaCloud Extract. "
            "Input: file_id or text, schema (JSON schema definition). "
            "Output: extracted_data (structured JSON)"
        )

    async def execute(self, **kwargs) -> dict[str, Any]:
        """Extract structured data from a document.

        Args:
            **kwargs: Keyword arguments including:
                - file_id: LlamaCloud file ID (optional)
                - text: Text content to extract from (optional)
                - file_content: Base64-encoded file content (optional)
                - schema: JSON schema for extraction (required)

        Returns:
            Dictionary with 'success' and 'extracted_data' or 'error'
        """
        try:
            from llama_cloud_services import LlamaExtract
            from llama_cloud_services.extract.extract import SourceText
            from pydantic import BaseModel

            file_id = kwargs.get("file_id")
            text = kwargs.get("text")
            file_content = kwargs.get("file_content")
            file_content_from_param = kwargs.get("file_id_content")
            schema = kwargs.get("schema")

            if not schema:
                return {
                    "success": False,
                    "error": "Missing required parameter: schema",
                }

            # Get or create LlamaExtract instance
            if self.llama_extract is None:
                self.llama_extract = LlamaExtract()

            # Create a dynamic Pydantic model from the schema
            # Schema can be a dict or already a Pydantic model
            if isinstance(schema, dict):
                # Create a Pydantic model from dict schema
                # The schema should have field definitions
                data_schema = schema
            elif isinstance(schema, type) and issubclass(schema, BaseModel):
                # Already a Pydantic model
                data_schema = schema
            else:
                return {
                    "success": False,
                    "error": "Schema must be a dict or Pydantic BaseModel class",
                }

            # Create or get extraction agent
            # Use a generic agent name based on schema hash
            import hashlib

            schema_str = str(schema)
            schema_hash = hashlib.md5(schema_str.encode()).hexdigest()[:8]
            agent_name = f"extract_agent_{schema_hash}"

            try:
                extract_agent = self.llama_extract.get_agent(name=agent_name)
            except Exception:
                # Agent doesn't exist, create it
                from llama_cloud import ExtractConfig, ExtractMode

                extract_config = ExtractConfig(
                    extraction_mode=ExtractMode.BALANCED,
                )
                extract_agent = self.llama_extract.create_agent(
                    agent_name, data_schema=data_schema, config=extract_config
                )

            # Prepare the content for extraction
            if text:
                # Extract from text
                source = SourceText(text_content=text)
            elif file_id:
                # Download file from LlamaCloud
                content = await download_file_from_llamacloud(file_id)
                source = SourceText(file=content)
            elif file_content or file_content_from_param:
                # Use base64 content
                content = base64.b64decode(file_content or file_content_from_param)
                source = SourceText(file=content)
            else:
                return {
                    "success": False,
                    "error": "Either file_id, text, or file_content must be provided",
                }

            # Run extraction
            result = await extract_agent.aextract(source)

            # Extract the data from the result
            extracted_data = result.data if hasattr(result, "data") else result

            return {"success": True, "extracted_data": extracted_data}

        except Exception as e:
            logger.exception("Error extracting data")
            return {"success": False, "error": str(e)}


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
        import tempfile
        import pathlib

        file_id = kwargs.get("file_id")
        file_content = kwargs.get("file_content")
        file_content_from_param = kwargs.get("file_id_content")
        filename = kwargs.get("filename") or kwargs.get("file_id_filename")

        try:
            from llama_parse import LlamaParse

            # Get or create LlamaParse instance
            if self.llama_parser is None:
                self.llama_parser = LlamaParse(result_type="markdown")

            # Get file content
            if file_id:
                content = await download_file_from_llamacloud(file_id)
            elif file_content or file_content_from_param:
                content = base64.b64decode(file_content or file_content_from_param)
            else:
                return {
                    "success": False,
                    "error": "Either file_id or file_content must be provided",
                }

            # Determine file extension from filename
            file_extension = ".xlsx"  # Default to Excel
            if filename:
                import os

                _, ext = os.path.splitext(filename.lower())
                if ext:
                    file_extension = ext

            # Create temporary file for LlamaParse
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=file_extension
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
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
                # Clean up temp file
                pathlib.Path(tmp_path).unlink()

        except Exception as e:
            logger.exception("Error processing spreadsheet")
            return {"success": False, "error": str(e)}


class SplitTool(Tool):
    """Tool for splitting documents into sections using LlamaIndex."""

    def __init__(self, chunk_size: int = 1024, chunk_overlap: int = 200):
        """Initialize the SplitTool.

        Args:
            chunk_size: Maximum size of each chunk in tokens (default: 1024)
            chunk_overlap: Number of tokens to overlap between chunks (default: 200)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @property
    def name(self) -> str:
        return "split"

    @property
    def description(self) -> str:
        return (
            "Split documents into logical sections or chunks using LlamaIndex. "
            "Input: text or file_id, chunk_size (optional, default: 1024), chunk_overlap (optional, default: 200). "
            "Output: splits (list of document sections)"
        )

    async def execute(self, **kwargs) -> dict[str, Any]:
        """Split a document into sections using LlamaIndex SentenceSplitter.

        Args:
            **kwargs: Keyword arguments including:
                - text: Text content to split (optional)
                - file_id: LlamaCloud file ID (optional)
                - chunk_size: Maximum chunk size in tokens (optional, default: 1024)
                - chunk_overlap: Overlap between chunks in tokens (optional, default: 200)

        Returns:
            Dictionary with 'success' and 'splits' or 'error'
        """
        from llama_index.core.node_parser import SentenceSplitter

        text = kwargs.get("text")
        file_id = kwargs.get("file_id")
        chunk_size = kwargs.get("chunk_size", self.chunk_size)
        chunk_overlap = kwargs.get("chunk_overlap", self.chunk_overlap)

        try:
            # Get text content
            if file_id:
                content = await download_file_from_llamacloud(file_id)
                text = content.decode("utf-8", errors="ignore")
            elif not text:
                return {
                    "success": False,
                    "error": "Either text or file_id must be provided",
                }

            # Limit text length to prevent excessive processing
            max_length = 100000
            if len(text) > max_length:
                logger.warning(
                    f"Text truncated from {len(text)} to {max_length} characters for splitting"
                )
                text = text[:max_length]

            # Use LlamaIndex SentenceSplitter for intelligent text splitting
            splitter = SentenceSplitter(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap
            )
            splits = splitter.split_text(text)

            return {"success": True, "splits": splits}

        except Exception as e:
            logger.exception("Error splitting document")
            return {"success": False, "error": str(e)}


class ClassifyTool(Tool):
    """Tool for classifying content using LlamaIndex."""

    def __init__(self, llm):
        self.llm = llm

    @property
    def name(self) -> str:
        return "classify"

    @property
    def description(self) -> str:
        return (
            "Classify text or documents into categories using LlamaIndex. "
            "Input: text, categories (list of possible categories). "
            "Output: category (selected category)"
        )

    async def execute(self, **kwargs) -> dict[str, Any]:
        """Classify text into one of the given categories using LlamaIndex.

        Args:
            **kwargs: Keyword arguments including:
                - text: Text to classify
                - categories: List of possible categories

        Returns:
            Dictionary with 'success', 'category' or 'error'
        """
        from llama_index.core.program import LLMTextCompletionProgram
        from pydantic import BaseModel, Field

        text = kwargs.get("text")
        categories = kwargs.get("categories")

        if not text or not categories:
            return {
                "success": False,
                "error": "Both 'text' and 'categories' must be provided",
            }

        try:
            # Limit text length to prevent prompt injection and excessive costs
            max_length = 10000
            if len(text) > max_length:
                logger.warning(
                    f"Text truncated from {len(text)} to {max_length} characters for classification"
                )
                text = text[:max_length]

            # Create a dynamic Pydantic model for classification
            # Using Literal type for the category field would be ideal but requires dynamic creation
            class Classification(BaseModel):
                """Classification result."""

                category: str = Field(
                    description=f"The category that best matches the text. Must be one of: {', '.join(categories)}"
                )
                confidence: str = Field(
                    description="Confidence level: high, medium, or low",
                    default="medium",
                )

            # Create a LlamaIndex program for structured output
            prompt_template = """
            Classify the following text into one of these categories: {categories}
            
            Text to classify:
            {text}
            
            Return the category that best matches the text along with your confidence level.
            """

            program = LLMTextCompletionProgram.from_defaults(
                output_cls=Classification,
                prompt_template_str=prompt_template,
                llm=self.llm,
                verbose=False,
            )

            # Run the classification
            result = await program.acall(text=text, categories=", ".join(categories))

            return {
                "success": True,
                "category": result.category,
                "confidence": result.confidence,
            }
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

    async def execute(self, **kwargs) -> dict[str, Any]:
        """Translate text to target language.

        Args:
            **kwargs: Keyword arguments including:
                - text: Text to translate (required)
                - source_lang: Source language code (optional, default: 'auto')
                - target_lang: Target language code (optional, default: 'en')

        Returns:
            Dictionary with 'success', 'translated_text' or 'error'
        """
        text = kwargs.get("text")
        source_lang = kwargs.get("source_lang", "auto")
        target_lang = kwargs.get("target_lang", "en")

        if not text:
            return {"success": False, "error": "Missing required parameter: text"}

        try:
            import asyncio

            # Limit text length to prevent excessive API usage
            max_length = 50000
            if len(text) > max_length:
                logger.warning(
                    f"Text truncated from {len(text)} to {max_length} characters for translation"
                )
                text = text[:max_length]

            # Validate language codes
            # Create a temporary instance to get supported languages
            temp_translator = GoogleTranslator(source="auto", target="en")
            supported_langs = temp_translator.get_supported_languages(as_dict=True)
            supported_codes = set(supported_langs.keys())
            # "auto" is allowed for source_lang
            if source_lang != "auto" and source_lang not in supported_codes:
                return {
                    "success": False,
                    "error": f"Invalid source_lang '{source_lang}'. Supported codes: {sorted(supported_codes)}",
                }
            if target_lang not in supported_codes:
                return {
                    "success": False,
                    "error": f"Invalid target_lang '{target_lang}'. Supported codes: {sorted(supported_codes)}",
                }
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

    async def execute(self, **kwargs) -> dict[str, Any]:
        """Summarise text using an LLM.

        Args:
            text: Text to summarise (required)
            max_length: Target summary length in words (optional)

        Returns:
            Dictionary with 'success' and 'summary' or 'error'
        """
        text = kwargs.get("text")
        max_length = kwargs.get("max_length")

        if not text:
            return {"success": False, "error": "Missing required parameter: text"}

        try:
            # Limit text length to prevent excessive LLM costs and prompt injection
            max_input_length = 50000
            if len(text) > max_input_length:
                logger.warning(
                    f"Text truncated from {len(text)} to {max_input_length} characters for summarization"
                )
                text = text[:max_input_length]

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
                    logger.warning(
                        f"Truncating extremely long word in PDF output: '{word}' to '{word[:100]}'"
                    )
                    lines.append(word[:100])  # Fallback: truncate extremely long words
                    current_line = ""

        # Add the last line
        if current_line:
            lines.append(current_line)

        return lines if lines else [""]

    async def execute(self, **kwargs) -> dict[str, Any]:
        """Convert text to PDF and upload to LlamaCloud.

        Args:
            **kwargs: Keyword arguments including:
                - text: Text to convert to PDF (required)
                - filename: Output filename (optional, default: "output.pdf")

        Returns:
            Dictionary with 'success' and 'file_id' or 'error'
        """
        text = kwargs.get("text")
        filename = kwargs.get("filename", "output.pdf")

        if not text:
            return {"success": False, "error": "Missing required parameter: text"}

        try:
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

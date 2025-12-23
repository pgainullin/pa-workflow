"""Tool for extracting structured data using LlamaCloud Extract."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from llama_cloud import ExtractConfig, ExtractMode
from llama_cloud_services import LlamaExtract
from llama_cloud_services.extract.extract import SourceText
from pydantic import BaseModel

from .base import Tool
from ..utils import process_text_in_batches

logger = logging.getLogger(__name__)


class ExtractTool(Tool):
    """Tool for extracting structured data using LlamaCloud Extract."""

    def __init__(self, llama_extract=None):
        """Initialize the ExtractTool.

        Args:
            llama_extract: Optional LlamaExtract instance. If not provided,
                          one will be created using environment variables.
        """
        self.llama_extract = llama_extract

    @property
    def name(self) -> str:
        return "extract"

    @property
    def description(self) -> str:
        return (
            "Extract structured data from text using LlamaCloud Extract. "
            "Input: text (parsed document text), schema (JSON schema definition). "
            "Output: extracted_data (structured JSON). "
            "Note: For files, use ParseTool first to extract text, then pass the text to this tool."
        )

    async def execute(self, **kwargs) -> dict[str, Any]:
        """Extract structured data from text.

        Args:
            **kwargs: Keyword arguments including:
                - text: Text content to extract from (required)
                - schema: JSON schema for extraction (required)

        Returns:
            Dictionary with 'success' and 'extracted_data' or 'error'
        """
        try:
            text = kwargs.get("text")
            schema = kwargs.get("schema")
            file_id = kwargs.get("file_id")
            file_content = kwargs.get("file_content")

            # Explicitly detect and reject file-based parameters
            if file_id is not None:
                return {
                    "success": False,
                    "error": "file_id parameter is no longer supported. Use ParseTool first to extract text from files, then pass the text to ExtractTool.",
                }

            if file_content is not None:
                return {
                    "success": False,
                    "error": "file_content parameter is no longer supported. Use ParseTool first to extract text from files, then pass the text to ExtractTool.",
                }

            if not text:
                return {
                    "success": False,
                    "error": "Missing required parameter: text. Use ParseTool first to extract text from files.",
                }

            if not schema:
                return {
                    "success": False,
                    "error": "Missing required parameter: schema",
                }

            # Get or create LlamaExtract instance
            if self.llama_extract is None:
                self.llama_extract = LlamaExtract()

            # Handle schema if it's a string (JSON)
            if isinstance(schema, str):
                try:
                    import json
                    schema = json.loads(schema)
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to parse schema as JSON: {e}",
                    }

            # Create a dynamic Pydantic model from the schema
            # Schema can be a dict, a Pydantic model class, or a Pydantic model instance
            if isinstance(schema, dict):
                # Create a Pydantic model from dict schema
                # The schema should have field definitions
                data_schema = schema
            elif isinstance(schema, type) and issubclass(schema, BaseModel):
                # Already a Pydantic model class
                data_schema = schema
            elif isinstance(schema, BaseModel):
                # It's an instance of a Pydantic model, LlamaExtract might want the class
                data_schema = schema.__class__
            else:
                return {
                    "success": False,
                    "error": f"Schema must be a dict or Pydantic BaseModel class, got {type(schema).__name__}. Value: {str(schema)[:100]}",
                }

            # Create or get extraction agent
            # Use a generic agent name based on schema hash
            schema_str = str(schema)
            schema_hash = hashlib.sha256(schema_str.encode()).hexdigest()[:8]
            agent_name = f"extract_agent_{schema_hash}"

            try:
                extract_agent = self.llama_extract.get_agent(name=agent_name)
            except Exception as e:
                logger.warning(
                    f"Failed to get agent '{agent_name}': {e}. Creating a new agent."
                )
                # Agent doesn't exist, create it
                extract_config = ExtractConfig(
                    extraction_mode=ExtractMode.BALANCED,
                )
                extract_agent = self.llama_extract.create_agent(
                    agent_name, data_schema=data_schema, config=extract_config
                )

            # For text-based extraction, use batch processing for long text
            # LlamaCloud Extract API's SourceText has a 5000 character limit
            max_text_length = 4900  # Slightly under 5000 to be safe

            async def extract_from_chunk(chunk: str) -> dict:
                source = SourceText(text_content=chunk)
                result = await extract_agent.aextract(source)
                return result.data if hasattr(result, "data") else result

            # Process text in batches if needed
            if len(text) > max_text_length:
                logger.info(
                    f"Processing text extraction in batches (length: {len(text)})"
                )

                # Combine extracted data from all batches
                def combine_extractions(extractions: list[dict]) -> dict:
                    if len(extractions) == 1:
                        return extractions[0]
                    # Return list of extractions for batch processing
                    return {
                        "batch_results": extractions,
                        "batch_count": len(extractions),
                    }

                extracted_data = await process_text_in_batches(
                    text=text,
                    max_length=max_text_length,
                    processor=extract_from_chunk,
                    combiner=combine_extractions,
                )
            else:
                extracted_data = await extract_from_chunk(text)

            return {"success": True, "extracted_data": extracted_data}

        except Exception as e:
            logger.exception("Error extracting data")
            return {"success": False, "error": str(e)}

"""Tool for splitting documents into sections using LlamaIndex."""

from __future__ import annotations

import logging
from typing import Any

from llama_index.core.node_parser import SentenceSplitter

from .base import Tool
from ..utils import download_file_from_llamacloud

logger = logging.getLogger(__name__)


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

            # Use LlamaIndex SentenceSplitter for intelligent text splitting
            # No truncation needed - the purpose of this tool is to split long text
            splitter = SentenceSplitter(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap
            )
            splits = splitter.split_text(text)

            return {"success": True, "splits": splits}

        except Exception as e:
            logger.exception("Error splitting document")
            return {"success": False, "error": str(e)}

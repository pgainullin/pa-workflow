"""Tool for summarising text using an LLM."""

from __future__ import annotations

import logging
from typing import Any

from .base import Tool
from ..utils import process_text_in_batches

logger = logging.getLogger(__name__)


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
            length_instruction = f" in about {max_length} words" if max_length else ""

            # Define processor for a single batch
            async def summarise_chunk(chunk: str) -> str:
                prompt = (
                    f"Provide a concise summary{length_instruction} of the following text:\n\n"
                    f"{chunk}"
                )
                response = await self.llm.acomplete(prompt)
                return str(response).strip()

            # Process text in batches if it's too long
            max_input_length = 50000

            # For summarization, we want to combine batch summaries into a final summary
            def combine_summaries(summaries: list[str]) -> str:
                if len(summaries) == 1:
                    return summaries[0]
                # Join all summaries and return
                return "\n\n".join(
                    f"Part {i + 1}: {s}" for i, s in enumerate(summaries)
                )

            summary = await process_text_in_batches(
                text=text,
                max_length=max_input_length,
                processor=summarise_chunk,
                combiner=combine_summaries,
            )

            return {"success": True, "summary": summary}
        except Exception as e:
            logger.exception("Error summarising text")
            return {"success": False, "error": str(e)}

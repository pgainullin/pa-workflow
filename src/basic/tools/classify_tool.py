"""Tool for classifying content using LlamaIndex."""

from __future__ import annotations

import logging
from typing import Any

from llama_index.core.program import LLMTextCompletionProgram
from pydantic import BaseModel, Field

from .base import Tool

logger = logging.getLogger(__name__)


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
            "Output: category (selected category), confidence (high, medium, or low)"
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
        text = kwargs.get("text")
        categories = kwargs.get("categories")

        if not text or not categories:
            return {
                "success": False,
                "error": "Both 'text' and 'categories' must be provided",
            }

        try:
            max_length = 10000

            # For classification, if text is too long, we extract representative samples
            # from beginning, middle, and end
            if len(text) > max_length:
                sample_size = max_length // 3
                beginning = text[:sample_size]
                middle_start = len(text) // 2 - sample_size // 2
                middle = text[middle_start : middle_start + sample_size]
                end = text[-sample_size:]

                text = f"{beginning}\n\n[...middle section...]\n\n{middle}\n\n[...end section...]\n\n{end}"
                logger.info(
                    f"Text sampled from {len(kwargs.get('text'))} to {len(text)} characters for classification"
                )

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
            prompt_template = """Classify the following text into one of these categories: {categories}

Text to classify:
{text}

Return the category that best matches the text along with your confidence level."""

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

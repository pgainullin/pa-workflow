"""Tool for translating text using Google Translate."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from deep_translator import GoogleTranslator

from .base import Tool
from ..utils import process_text_in_batches

logger = logging.getLogger(__name__)


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
            "Languages can be specified as codes (e.g., 'en', 'fr') or full names (e.g., 'english', 'french'). "
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
            # Validate language codes
            # Create a temporary instance to get supported languages
            temp_translator = GoogleTranslator(source="auto", target="en")
            supported_langs = temp_translator.get_supported_languages(as_dict=True)
            # get_supported_languages returns dict with language names as keys and codes as values
            # e.g., {'english': 'en', 'french': 'fr', ...}
            # GoogleTranslator accepts both formats, but we should validate both
            supported_names = set(
                supported_langs.keys()
            )  # Full names: 'english', 'french', etc.
            supported_codes = set(
                supported_langs.values()
            )  # Short codes: 'en', 'fr', etc.

            # "auto" is allowed for source_lang
            if (
                source_lang != "auto"
                and source_lang not in supported_codes
                and source_lang not in supported_names
            ):
                return {
                    "success": False,
                    "error": f"Invalid source_lang '{source_lang}'. Supported codes: {sorted(supported_codes)}",
                }
            if (
                target_lang not in supported_codes
                and target_lang not in supported_names
            ):
                return {
                    "success": False,
                    "error": f"Invalid target_lang '{target_lang}'. Supported codes: {sorted(supported_codes)}",
                }

            # Create translator instance for this translation
            translator = GoogleTranslator(source=source_lang, target=target_lang)

            # Define processor for a single batch
            async def translate_chunk(chunk: str) -> str:
                # Run translation in thread pool since deep-translator is synchronous
                return await asyncio.to_thread(translator.translate, chunk)

            # Process text in batches if it's too long
            # Google Translate API has a 5000 character limit per request
            max_length = 5000
            translated = await process_text_in_batches(
                text=text,
                max_length=max_length,
                processor=translate_chunk,
                combiner=lambda chunks: "".join(chunks),
            )

            return {"success": True, "translated_text": translated}
        except Exception as e:
            logger.exception("Error translating text")
            return {"success": False, "error": str(e)}

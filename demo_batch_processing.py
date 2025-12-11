"""
Demonstration script showing batch processing in action.

This script shows how tools handle long text with the new batch processing feature.
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Set dummy API keys for demo
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["LLAMA_CLOUD_API_KEY"] = "test-key"
os.environ["LLAMA_CLOUD_PROJECT_ID"] = "test-project"


async def demo_translate_tool():
    """Demonstrate TranslateTool handling long text with batching."""
    print("\n" + "=" * 70)
    print("DEMO 1: TranslateTool with Long Text")
    print("=" * 70)

    from basic.tools import TranslateTool

    tool = TranslateTool()

    # Create long text (60KB) that will be split into batches
    long_text = " ".join(f"This is sentence number {i}." for i in range(1, 3001))  # ~60KB

    print(f"\nInput text length: {len(long_text)} characters")
    print("Expected behavior: Split into 2 batches (50KB each)")

    with patch("basic.tools.GoogleTranslator") as mock_translator_class:
        mock_translator = MagicMock()
        call_count = 0
        batch_sizes = []

        def mock_translate(text):
            nonlocal call_count
            call_count += 1
            batch_sizes.append(len(text))
            print(f"  - Batch {call_count}: {len(text)} characters")
            return f"[Translated batch {call_count}]"

        mock_translator.translate = MagicMock(side_effect=mock_translate)
        mock_translator.get_supported_languages = MagicMock(
            return_value={"english": "en", "french": "fr"}
        )
        mock_translator_class.return_value = mock_translator

        result = await tool.execute(text=long_text, target_lang="fr")

        print(f"\nResult: {result['success']}")
        print(f"Total batches processed: {call_count}")
        print(f"Output preview: {result['translated_text'][:100]}...")


async def demo_summarise_tool():
    """Demonstrate SummariseTool handling long text with batching."""
    print("\n" + "=" * 70)
    print("DEMO 2: SummariseTool with Long Text")
    print("=" * 70)

    from basic.tools import SummariseTool

    # Mock LLM
    mock_llm = MagicMock()
    call_count = 0

    async def mock_acomplete(prompt):
        nonlocal call_count
        call_count += 1
        chunk_size = len(prompt.split("following text:")[1][:100])
        print(f"  - Batch {call_count}: Generating summary")
        mock_response = MagicMock()
        mock_response.__str__ = lambda x: f"Summary of batch {call_count}"
        return mock_response

    mock_llm.acomplete = mock_acomplete

    tool = SummariseTool(mock_llm)

    # Create long text (80KB)
    long_text = "This is a long document paragraph. " * 4000

    print(f"\nInput text length: {len(long_text)} characters")
    print("Expected behavior: Split into 2 batches, label each part")

    result = await tool.execute(text=long_text)

    print(f"\nResult: {result['success']}")
    print(f"Total batches processed: {call_count}")
    print(f"Output:\n{result['summary']}")


async def demo_classify_tool():
    """Demonstrate ClassifyTool handling long text with sampling."""
    print("\n" + "=" * 70)
    print("DEMO 3: ClassifyTool with Long Text (Sampling Strategy)")
    print("=" * 70)

    from basic.tools import ClassifyTool

    mock_llm = MagicMock()

    from pydantic import BaseModel

    class MockClassification(BaseModel):
        category: str = "Technical"
        confidence: str = "high"

    tool = ClassifyTool(mock_llm)

    with patch(
        "llama_index.core.program.LLMTextCompletionProgram"
    ) as mock_program_class:
        sampled_text = None

        async def capture_acall(**kwargs):
            nonlocal sampled_text
            sampled_text = kwargs.get("text", "")
            return MockClassification()

        mock_program = MagicMock()
        mock_program.acall = AsyncMock(side_effect=capture_acall)
        mock_program_class.from_defaults = MagicMock(return_value=mock_program)

        # Create very long text (50KB)
        long_text = "This is about software development and technology. " * 1000

        print(f"\nInput text length: {len(long_text)} characters")
        print("Expected behavior: Sample beginning, middle, and end sections")

        categories = ["Technical", "Business", "Personal"]
        result = await tool.execute(text=long_text, categories=categories)

        print(f"\nResult: {result['success']}")
        print(f"Category: {result['category']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Sampled text length: {len(sampled_text)} characters")
        print(f"Sampling ratio: {len(sampled_text) / len(long_text) * 100:.1f}%")
        print(f"Contains sampling markers: {'middle section' in sampled_text}")


async def demo_batch_utility():
    """Demonstrate the core batch processing utility."""
    print("\n" + "=" * 70)
    print("DEMO 4: Core Batch Processing Utility")
    print("=" * 70)

    from basic.utils import process_text_in_batches

    # Track processing
    processed_batches = []

    async def mock_processor(text: str) -> str:
        batch_num = len(processed_batches) + 1
        processed_batches.append(len(text))
        print(f"  - Processing batch {batch_num}: {len(text)} characters")
        # Find first and last words to show boundaries
        first_words = " ".join(text.split()[:3])
        last_words = " ".join(text.split()[-3:])
        print(f"    Start: '{first_words}...'")
        print(f"    End: '...{last_words}'")
        return f"[Batch {batch_num}]"

    # Create text with clear sentence boundaries
    sentences = [
        f"This is sentence number {i}. It contains some information."
        for i in range(100)
    ]
    long_text = " ".join(sentences)

    print(f"\nInput text length: {len(long_text)} characters")
    print(f"Number of sentences: {len(sentences)}")
    print("Max batch size: 1000 characters\n")

    result = await process_text_in_batches(
        text=long_text, max_length=1000, processor=mock_processor
    )

    print(f"\nTotal batches: {len(processed_batches)}")
    print(f"Batch sizes: {processed_batches}")
    print(f"Result: {result}")


async def main():
    """Run all demonstrations."""
    print("\n" + "=" * 70)
    print("BATCH PROCESSING DEMONSTRATION")
    print("=" * 70)
    print("\nThis demonstration shows how tools handle long text inputs")
    print("using the new batch processing feature.\n")

    try:
        await demo_translate_tool()
        await demo_summarise_tool()
        await demo_classify_tool()
        await demo_batch_utility()

        print("\n" + "=" * 70)
        print("DEMONSTRATION COMPLETE")
        print("=" * 70)
        print("\nKey Takeaways:")
        print("1. TranslateTool: Processes text in 50KB batches, concatenates results")
        print("2. SummariseTool: Processes text in 50KB batches, labels each part")
        print("3. ClassifyTool: Samples representative sections (beginning/middle/end)")
        print("4. Batch utility: Intelligently splits at sentence/word boundaries")
        print("\nNo text is lost due to truncation!")

    except Exception as e:
        print(f"\nError during demonstration: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

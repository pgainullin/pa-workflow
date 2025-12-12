"""
Demonstration script showing that ExtractTool now handles long text correctly.

This demonstrates the fix for the issue where execution was blocked when
ParseTool output exceeded 5000 characters.
"""

import asyncio
import os
from unittest.mock import MagicMock, patch

# Set dummy API keys for demo
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["LLAMA_CLOUD_API_KEY"] = "test-key"
os.environ["LLAMA_CLOUD_PROJECT_ID"] = "test-project"


async def demo_extract_tool_with_long_text():
    """Demonstrate ExtractTool handling text longer than 5000 characters."""
    print("\n" + "=" * 70)
    print("DEMO: ExtractTool with Long Text (Fix Verification)")
    print("=" * 70)

    from basic.tools import ExtractTool

    tool = ExtractTool()

    # Mock LlamaExtract
    with patch("llama_cloud_services.LlamaExtract") as mock_extract_class:
        mock_extract = MagicMock()
        mock_agent = MagicMock()

        chunks_received = []
        call_count = 0

        async def mock_aextract(source):
            nonlocal call_count
            call_count += 1
            # Capture chunk information
            if hasattr(source, 'text_content'):
                chunk_size = len(source.text_content)
                chunks_received.append(chunk_size)
                print(f"  - API call {call_count}: Received chunk of {chunk_size} characters")
                # Verify chunk is under 5000 characters
                if chunk_size > 5000:
                    print(f"    ⚠️  WARNING: Chunk exceeds 5000 character API limit!")
                else:
                    print(f"    ✓ Chunk is within API limit")
            
            mock_result = MagicMock()
            mock_result.data = {"extracted": f"data_from_chunk_{call_count}"}
            return mock_result

        mock_agent.aextract = mock_aextract
        mock_extract.get_agent = MagicMock(return_value=mock_agent)
        mock_extract_class.return_value = mock_extract

        # Test scenarios
        scenarios = [
            ("Short text (< 5000 chars)", "This is a short document. " * 100, 1),
            ("Medium text (~ 6000 chars)", "This is a medium document. " * 250, 2),
            ("Long text (~ 15000 chars)", "This is a long document. " * 600, 4),
            ("Very long text (~ 50000 chars)", "This is a very long document. " * 2000, 11),
        ]

        for name, text, expected_calls in scenarios:
            print(f"\n{name}")
            print(f"  Text length: {len(text)} characters")
            print(f"  Expected batches: ~{expected_calls}")
            
            chunks_received.clear()
            call_count = 0
            
            result = await tool.execute(text=text, schema={"field": "string"})
            
            print(f"  Actual batches: {call_count}")
            print(f"  Batch sizes: {chunks_received}")
            print(f"  All chunks valid: {all(size <= 5000 for size in chunks_received)}")
            print(f"  Status: {'✓ SUCCESS' if result['success'] else '✗ FAILED'}")

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)
    print("\nKey Takeaway:")
    print("ExtractTool now correctly splits long text into batches that respect")
    print("the LlamaCloud Extract API's 5000 character limit, preventing the")
    print("'Text length need to be between 0 and 5000 characters' error.")


if __name__ == "__main__":
    asyncio.run(demo_extract_tool_with_long_text())

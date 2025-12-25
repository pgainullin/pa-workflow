"""Tests for batch processing of long text in tools."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set dummy API keys
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_PROJECT_ID", "test-project-id")


@pytest.mark.asyncio
async def test_process_text_in_batches_short_text():
    """Test that short text is processed without batching."""
    from basic.utils import process_text_in_batches

    call_count = 0

    async def mock_processor(text: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"processed: {text}"

    short_text = "This is a short text."
    result = await process_text_in_batches(
        text=short_text, max_length=1000, processor=mock_processor
    )

    assert call_count == 1
    assert result == "processed: This is a short text."


@pytest.mark.asyncio
async def test_process_text_in_batches_long_text():
    """Test that long text is split into batches."""
    from basic.utils import process_text_in_batches

    call_count = 0
    processed_chunks = []

    async def mock_processor(text: str) -> str:
        nonlocal call_count
        call_count += 1
        processed_chunks.append(text)
        return f"batch_{call_count}"

    # Create text longer than max_length
    long_text = "This is sentence one. " * 100  # ~2200 characters
    result = await process_text_in_batches(
        text=long_text, max_length=500, processor=mock_processor
    )

    assert call_count > 1  # Should be split into multiple batches
    assert isinstance(result, str)
    assert "batch_" in result


@pytest.mark.asyncio
async def test_process_text_in_batches_with_combiner():
    """Test batch processing with custom combiner."""
    from basic.utils import process_text_in_batches

    async def mock_processor(text: str) -> int:
        return len(text)

    def combiner(results: list[int]) -> int:
        return sum(results)

    long_text = "word " * 200  # 1000 characters
    result = await process_text_in_batches(
        text=long_text, max_length=300, processor=mock_processor, combiner=combiner
    )

    assert isinstance(result, int)
    assert result == len(long_text)


@pytest.mark.asyncio
async def test_translate_tool_batching():
    """Test TranslateTool handles long text with batching."""
    from basic.tools import TranslateTool

    tool = TranslateTool()

    # Mock the translator
    with patch("basic.tools.translate_tool.GoogleTranslator") as mock_translator_class:
        mock_translator = MagicMock()
        # Track how many times translate is called
        call_count = 0

        def mock_translate(text):
            nonlocal call_count
            call_count += 1
            return f"translated_batch_{call_count}"

        mock_translator.translate = MagicMock(side_effect=mock_translate)
        mock_translator.get_supported_languages = MagicMock(
            return_value={"english": "en", "french": "fr", "spanish": "es"}
        )
        mock_translator_class.return_value = mock_translator

        # Create long text that should be split into batches
        long_text = "This is a sentence. " * 3000  # ~60000 characters
        result = await tool.execute(
            text=long_text, source_lang="en", target_lang="fr"
        )

        assert result["success"] is True
        assert "translated_text" in result
        # Should have been called multiple times due to batching
        assert call_count > 1


@pytest.mark.asyncio
async def test_translate_tool_respects_5000_char_limit():
    """Test TranslateTool respects the 5000 character Google Translate API limit."""
    from basic.tools import TranslateTool

    tool = TranslateTool()

    # Track chunk sizes to ensure they don't exceed 5000 characters
    chunk_sizes = []

    # Mock the translator
    with patch("basic.tools.translate_tool.GoogleTranslator") as mock_translator_class:
        mock_translator = MagicMock()

        def mock_translate(text):
            chunk_sizes.append(len(text))
            # Verify each chunk is under the 5000 character limit
            assert len(text) <= 5000, f"Chunk size {len(text)} exceeds Google Translate API limit of 5000"
            return f"translated({len(text)} chars)"

        mock_translator.translate = MagicMock(side_effect=mock_translate)
        mock_translator.get_supported_languages = MagicMock(
            return_value={"english": "en", "french": "fr", "spanish": "es"}
        )
        mock_translator_class.return_value = mock_translator

        # Create text just over 5000 characters
        long_text = "This is a sentence. " * 300  # ~6000 characters
        result = await tool.execute(
            text=long_text, source_lang="en", target_lang="fr"
        )

        assert result["success"] is True
        assert "translated_text" in result
        # Should have been split into multiple batches
        assert len(chunk_sizes) >= 2
        # Each chunk should be under 5000 characters
        for size in chunk_sizes:
            assert size <= 5000


@pytest.mark.asyncio
async def test_summarise_tool_batching():
    """Test SummariseTool handles long text with batching."""
    from basic.tools import SummariseTool

    # Mock LLM
    mock_llm = MagicMock()
    call_count = 0

    async def mock_acomplete(prompt):
        nonlocal call_count
        call_count += 1
        mock_response = MagicMock()
        mock_response.__str__ = lambda x: f"Summary part {call_count}"
        return mock_response

    mock_llm.acomplete = mock_acomplete

    tool = SummariseTool(mock_llm)

    # Create long text that should be split into batches
    long_text = "This is a long document. " * 3000  # ~75000 characters
    result = await tool.execute(text=long_text)

    assert result["success"] is True
    assert "summary" in result
    # Should have been called multiple times due to batching
    assert call_count > 1
    # Summary should contain parts from different batches
    assert "Part" in result["summary"]


@pytest.mark.asyncio
async def test_classify_tool_long_text_sampling():
    """Test ClassifyTool handles long text with sampling."""
    from basic.tools import ClassifyTool

    # Mock LLM
    mock_llm = MagicMock()

    from pydantic import BaseModel

    class MockClassification(BaseModel):
        category: str = "Technical"
        confidence: str = "high"

    tool = ClassifyTool(mock_llm)

    # Patch the LLMTextCompletionProgram
    with patch(
        "basic.tools.classify_tool.LLMTextCompletionProgram"
    ) as mock_program_class:
        mock_program = MagicMock()
        mock_program.acall = AsyncMock(return_value=MockClassification())
        mock_program_class.from_defaults = MagicMock(return_value=mock_program)

        # Create very long text
        long_text = "This is about software development. " * 1000  # ~37000 characters
        categories = ["Technical", "Business", "Personal"]
        result = await tool.execute(text=long_text, categories=categories)

        assert result["success"] is True
        assert "category" in result
        assert result["category"] == "Technical"

        # Verify that acall was called with sampled text (not full text)
        call_args = mock_program.acall.call_args
        called_text = call_args[1]["text"]
        # Sampled text should be much shorter than original
        assert len(called_text) < len(long_text)
        # Should contain sampling indicators
        assert "middle section" in called_text and "end section" in called_text


@pytest.mark.asyncio
async def test_extract_tool_text_batching():
    """Test ExtractTool handles long text with batching."""
    from basic.tools import ExtractTool

    tool = ExtractTool()

    # Mock LlamaExtract at the correct import location
    with patch("basic.tools.extract_tool.LlamaExtract") as mock_extract_class:
        mock_extract = MagicMock()
        mock_agent = MagicMock()

        call_count = 0
        chunk_sizes = []

        async def mock_aextract(source):
            nonlocal call_count
            call_count += 1
            # Capture the chunk size
            if hasattr(source, 'text_content'):
                chunk_sizes.append(len(source.text_content))
            mock_result = MagicMock()
            mock_result.data = {"field": f"value_{call_count}"}
            return mock_result

        mock_agent.aextract = mock_aextract
        mock_extract.get_agent = MagicMock(return_value=mock_agent)
        mock_extract_class.return_value = mock_extract

        # Create long text that should be split
        long_text = "Some data to extract. " * 6000  # ~138000 characters
        schema = {"field": "string"}

        result = await tool.execute(text=long_text, schema=schema)

        assert result["success"] is True
        assert "extracted_data" in result
        # Should have been called multiple times due to batching
        assert call_count > 1
        # Each chunk should be under 5000 characters (the API limit)
        for size in chunk_sizes:
            assert size <= 5000, f"Chunk size {size} exceeds API limit of 5000"


@pytest.mark.asyncio
async def test_extract_tool_respects_5000_char_limit():
    """Test ExtractTool respects the 5000 character API limit."""
    from basic.tools import ExtractTool

    tool = ExtractTool()

    # Mock LlamaExtract
    with patch("basic.tools.extract_tool.LlamaExtract") as mock_extract_class:
        mock_extract = MagicMock()
        mock_agent = MagicMock()

        chunks_received = []

        async def mock_aextract(source):
            # Capture each chunk
            if hasattr(source, 'text_content'):
                chunks_received.append(source.text_content)
            mock_result = MagicMock()
            mock_result.data = {"extracted": "data"}
            return mock_result

        mock_agent.aextract = mock_aextract
        mock_extract.get_agent = MagicMock(return_value=mock_agent)
        mock_extract_class.return_value = mock_extract

        # Test with text just over 5000 characters
        text_5500 = "x" * 5500
        result = await tool.execute(text=text_5500, schema={"field": "string"})

        assert result["success"] is True
        # Should be split into at least 2 chunks
        assert len(chunks_received) >= 2
        # Each chunk should be under 5000 characters
        for chunk in chunks_received:
            assert len(chunk) <= 5000


@pytest.mark.asyncio
async def test_extract_tool_rejects_file_parameters():
    """Test ExtractTool rejects file_id and file_content parameters with specific error messages."""
    from basic.tools import ExtractTool

    tool = ExtractTool()

    # Mock LlamaExtract
    with patch("basic.tools.extract_tool.LlamaExtract") as mock_extract_class:
        mock_extract = MagicMock()
        mock_agent = MagicMock()
        mock_extract.get_agent = MagicMock(return_value=mock_agent)
        mock_extract_class.return_value = mock_extract

        # Test with file_id (should fail with specific message)
        result = await tool.execute(file_id="test-file-id", schema={"field": "string"})
        assert result["success"] is False
        assert "file_id parameter is no longer supported" in result["error"]
        assert "ParseTool first" in result["error"]
        assert "ExtractTool" in result["error"]

        # Test with file_content (should fail with specific message)
        result = await tool.execute(file_content="base64content", schema={"field": "string"})
        assert result["success"] is False
        assert "file_content parameter is no longer supported" in result["error"]
        assert "ParseTool first" in result["error"]
        assert "ExtractTool" in result["error"]

        # Test with neither text nor file (should fail with generic message)
        result = await tool.execute(schema={"field": "string"})
        assert result["success"] is False
        assert "Missing required parameter: text" in result["error"]
        assert "ParseTool" in result["error"]



@pytest.mark.asyncio
async def test_split_tool_no_truncation():
    """Test SplitTool doesn't truncate long text."""
    from basic.tools import SplitTool

    tool = SplitTool()

    # Create very long text
    long_text = "Sentence. " * 20000  # ~200000 characters

    result = await tool.execute(text=long_text)

    assert result["success"] is True
    assert "splits" in result
    assert len(result["splits"]) > 0
    # Verify that the total length of splits is close to original
    # (may differ slightly due to splitting logic)
    total_split_length = sum(len(split) for split in result["splits"])
    # Should process all text, not just first 100k characters
    assert total_split_length > 100000


@pytest.mark.asyncio
async def test_batch_processing_sentence_boundaries():
    """Test that batch processing respects sentence boundaries."""
    from basic.utils import process_text_in_batches

    processed_chunks = []

    async def mock_processor(text: str) -> str:
        processed_chunks.append(text)
        return text

    # Text with clear sentence boundaries
    text = "First sentence. " + "Second sentence. " * 50 + "Last sentence."
    await process_text_in_batches(text=text, max_length=200, processor=mock_processor)

    # Each chunk should ideally end at a sentence boundary
    for chunk in processed_chunks[:-1]:  # All but last chunk
        # Should end with period and space or just period
        assert chunk.rstrip().endswith(".")

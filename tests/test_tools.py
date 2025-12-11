"""Tests for workflow tools."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set dummy API keys
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_PROJECT_ID", "test-project-id")


@pytest.mark.asyncio
async def test_summarise_tool():
    """Test the summarise tool."""
    # Mock LLM
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.__str__ = lambda x: "This is a summary of the text."
    mock_llm.acomplete = AsyncMock(return_value=mock_response)

    from basic.tools import SummariseTool

    tool = SummariseTool(mock_llm)

    # Test execution
    result = await tool.execute({"text": "This is a long text that needs summarization."})

    assert result["success"] is True
    assert "summary" in result
    assert result["summary"] == "This is a summary of the text."
    assert mock_llm.acomplete.called


@pytest.mark.asyncio
async def test_translate_tool():
    """Test the translate tool."""
    from basic.tools import TranslateTool

    tool = TranslateTool()

    # Mock the translator
    with patch("basic.tools.GoogleTranslator") as mock_translator_class:
        mock_translator = MagicMock()
        mock_translator.translate = MagicMock(return_value="Bonjour le monde")
        mock_translator_class.return_value = mock_translator

        # Test execution
        result = await tool.execute(text="Hello world", source_lang="en", target_lang="fr")

        assert result["success"] is True
        assert "translated_text" in result
        assert result["translated_text"] == "Bonjour le monde"


@pytest.mark.asyncio
async def test_classify_tool():
    """Test the classify tool."""
    # Mock LLM
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.__str__ = lambda x: "Technical"
    mock_llm.acomplete = AsyncMock(return_value=mock_response)

    from basic.tools import ClassifyTool

    tool = ClassifyTool(mock_llm)

    # Test execution
    categories = ["Technical", "Business", "Personal"]
    result = await tool.execute(text="This is about software development.", categories=categories)

    assert result["success"] is True
    assert "category" in result
    assert result["category"] == "Technical"


@pytest.mark.asyncio
async def test_split_tool():
    """Test the split tool."""
    from basic.tools import SplitTool

    tool = SplitTool()

    # Test with text
    text = "Section 1 content here.\n\nSection 2 content here.\n\nSection 3 content here."
    result = await tool.execute(text=text)

    assert result["success"] is True
    assert "splits" in result
    assert len(result["splits"]) == 3
    assert "Section 1" in result["splits"][0]


@pytest.mark.asyncio
async def test_print_to_pdf_tool():
    """Test the print to PDF tool."""
    from basic.tools import PrintToPDFTool
    import json

    tool = PrintToPDFTool()

    # Mock upload function
    with patch("basic.tools.upload_file_to_llamacloud") as mock_upload:
        mock_upload.return_value = "file-123"

        # Test execution with JSON input
        input_data = json.dumps({"text": "Hello, this is a test PDF content.", "filename": "test.pdf"})
        result = await tool.execute(input_data)

        assert result["success"] is True
        assert "file_id" in result
        assert result["file_id"] == "file-123"
        assert mock_upload.called


@pytest.mark.asyncio
async def test_parse_tool():
    """Test the parse tool."""
    # Mock LlamaParse
    mock_parser = MagicMock()
    mock_doc = MagicMock()
    mock_doc.get_content = MagicMock(return_value="Parsed document content")
    mock_parser.load_data = MagicMock(return_value=[mock_doc])

    from basic.tools import ParseTool

    tool = ParseTool(mock_parser)

    # Mock download function
    with patch("basic.tools.download_file_from_llamacloud") as mock_download:
        mock_download.return_value = b"PDF content"

        # Test execution with file_id
        result = await tool.execute(file_id="file-123")

        assert result["success"] is True
        assert "parsed_text" in result
        assert result["parsed_text"] == "Parsed document content"


@pytest.mark.asyncio
async def test_tool_registry():
    """Test the tool registry."""
    from basic.tools import ToolRegistry, SummariseTool

    # Mock LLM
    mock_llm = MagicMock()
    mock_llm.acomplete = AsyncMock(return_value=MagicMock(__str__=lambda x: "Summary"))

    registry = ToolRegistry()

    # Register a tool
    tool = SummariseTool(mock_llm)
    registry.register(tool)

    # Test getting a tool
    retrieved_tool = registry.get_tool("summarise")
    assert retrieved_tool is not None
    assert retrieved_tool.name == "summarise"

    # Test listing tools
    tool_names = registry.list_tool_names()
    assert "summarise" in tool_names

    # Test tool descriptions
    descriptions = registry.get_tool_descriptions()
    assert "summarise" in descriptions.lower()

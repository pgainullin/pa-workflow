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
    result = await tool.execute(text="This is a long text that needs summarization.")

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
        # Mock get_supported_languages as instance method
        mock_translator.get_supported_languages = MagicMock(
            return_value={"en": "English", "fr": "French", "es": "Spanish"}
        )
        mock_translator_class.return_value = mock_translator

        # Test execution
        result = await tool.execute(
            text="Hello world", source_lang="en", target_lang="fr"
        )

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
    result = await tool.execute(
        text="This is about software development.", categories=categories
    )

    assert result["success"] is True
    assert "category" in result
    assert result["category"] == "Technical"


@pytest.mark.asyncio
async def test_split_tool():
    """Test the split tool."""
    from basic.tools import SplitTool

    tool = SplitTool()

    # Test with text
    text = (
        "Section 1 content here.\n\nSection 2 content here.\n\nSection 3 content here."
    )
    result = await tool.execute(text=text)

    assert result["success"] is True
    assert "splits" in result
    assert len(result["splits"]) == 3
    assert "Section 1" in result["splits"][0]


@pytest.mark.asyncio
async def test_print_to_pdf_tool():
    """Test the print to PDF tool."""
    from basic.tools import PrintToPDFTool

    tool = PrintToPDFTool()

    # Mock upload function
    with patch("basic.tools.upload_file_to_llamacloud") as mock_upload:
        mock_upload.return_value = "file-123"

        # Test execution with keyword arguments
        result = await tool.execute(
            text="Hello, this is a test PDF content.", filename="test.pdf"
        )

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

        # Test execution with valid UUID file_id
        result = await tool.execute(file_id="550e8400-e29b-41d4-a716-446655440000")

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


@pytest.mark.asyncio
async def test_extract_tool():
    """Test the extract tool."""
    from basic.tools import ExtractTool
    from pydantic import BaseModel

    # Define a test schema
    class TestSchema(BaseModel):
        name: str
        age: int

    # Mock LlamaExtract and agent
    mock_llama_extract = MagicMock()
    mock_agent = MagicMock()
    mock_result = MagicMock()
    mock_result.data = {"name": "John Doe", "age": 30}
    mock_agent.aextract = AsyncMock(return_value=mock_result)
    mock_llama_extract.get_agent = MagicMock(return_value=mock_agent)

    tool = ExtractTool(llama_extract=mock_llama_extract)

    # Test with text input
    result = await tool.execute(
        text="John Doe is 30 years old.", schema={"name": "str", "age": "int"}
    )

    assert result["success"] is True
    assert "extracted_data" in result
    assert result["extracted_data"]["name"] == "John Doe"
    assert result["extracted_data"]["age"] == 30


@pytest.mark.asyncio
async def test_extract_tool_missing_schema():
    """Test extract tool with missing schema."""
    from basic.tools import ExtractTool

    tool = ExtractTool()

    # Test without schema
    result = await tool.execute(text="Some text")

    assert result["success"] is False
    assert "error" in result
    assert "schema" in result["error"].lower()


@pytest.mark.asyncio
async def test_sheets_tool_csv():
    """Test the sheets tool with CSV content."""
    from basic.tools import SheetsTool
    import io

    tool = SheetsTool()

    # Create a simple CSV in memory
    csv_content = "Name,Age,City\nAlice,30,New York\nBob,25,London\nCharlie,35,Paris"
    csv_bytes = csv_content.encode("utf-8")
    base64_content = __import__("base64").b64encode(csv_bytes).decode("utf-8")

    # Mock download function (won't be called since we're using file_content)
    with patch("basic.tools.download_file_from_llamacloud") as mock_download:
        # Test with base64 content
        result = await tool.execute(file_content=base64_content, filename="test.csv")

        assert result["success"] is True
        assert "sheet_data" in result
        assert "rows" in result["sheet_data"]
        assert "columns" in result["sheet_data"]
        assert result["sheet_data"]["row_count"] == 3
        assert result["sheet_data"]["column_count"] == 3
        assert result["sheet_data"]["columns"] == ["Name", "Age", "City"]
        assert result["sheet_data"]["rows"][0]["Name"] == "Alice"
        assert result["sheet_data"]["rows"][1]["Age"] == 25


@pytest.mark.asyncio
async def test_sheets_tool_excel():
    """Test the sheets tool with Excel content."""
    from basic.tools import SheetsTool
    import pandas as pd
    import io

    tool = SheetsTool()

    # Create a simple Excel file in memory
    df = pd.DataFrame(
        {
            "Product": ["Widget", "Gadget", "Doohickey"],
            "Price": [10.99, 25.50, 5.00],
            "Quantity": [100, 50, 200],
        }
    )

    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False)
    excel_bytes = excel_buffer.getvalue()
    base64_content = __import__("base64").b64encode(excel_bytes).decode("utf-8")

    # Test with base64 content
    result = await tool.execute(file_content=base64_content, filename="test.xlsx")

    assert result["success"] is True
    assert "sheet_data" in result
    assert result["sheet_data"]["row_count"] == 3
    assert result["sheet_data"]["column_count"] == 3
    assert "Product" in result["sheet_data"]["columns"]
    assert result["sheet_data"]["rows"][0]["Product"] == "Widget"
    assert result["sheet_data"]["rows"][1]["Price"] == 25.50


@pytest.mark.asyncio
async def test_sheets_tool_max_rows():
    """Test the sheets tool with max_rows limit."""
    from basic.tools import SheetsTool
    import pandas as pd
    import io

    tool = SheetsTool()

    # Create a larger CSV with many rows
    rows = [f"Row{i},Value{i}" for i in range(100)]
    csv_content = "Column1,Column2\n" + "\n".join(rows)
    csv_bytes = csv_content.encode("utf-8")
    base64_content = __import__("base64").b64encode(csv_bytes).decode("utf-8")

    # Test with max_rows limit
    result = await tool.execute(
        file_content=base64_content, filename="test.csv", max_rows=10
    )

    assert result["success"] is True
    assert result["sheet_data"]["row_count"] == 10  # Should be limited to 10


@pytest.mark.asyncio
async def test_sheets_tool_missing_file():
    """Test sheets tool with missing file input."""
    from basic.tools import SheetsTool

    tool = SheetsTool()

    # Test without file_id or file_content
    result = await tool.execute()

    assert result["success"] is False
    assert "error" in result
    assert (
        "file_id" in result["error"].lower()
        or "file_content" in result["error"].lower()
    )

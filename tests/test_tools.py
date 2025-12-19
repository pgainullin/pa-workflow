"""Tests for workflow tools."""

import base64
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set dummy API keys
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_PROJECT_ID", "test-project-id")
os.environ.setdefault("OPENAI_API_KEY", "test-dummy-openai-key-for-testing")


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
    with patch("basic.tools.translate_tool.GoogleTranslator") as mock_translator_class:
        mock_translator = MagicMock()
        mock_translator.translate = MagicMock(return_value="Bonjour le monde")
        # Mock get_supported_languages as instance method
        # get_supported_languages returns dict with names as keys and codes as values
        mock_translator.get_supported_languages = MagicMock(
            return_value={"english": "en", "french": "fr", "spanish": "es"}
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

    # Mock the LLMTextCompletionProgram
    from pydantic import BaseModel

    class MockClassification(BaseModel):
        category: str = "Technical"
        confidence: str = "high"

    from basic.tools import ClassifyTool

    tool = ClassifyTool(mock_llm)

    # Patch the LLMTextCompletionProgram at the correct import location
    with patch(
        "llama_index.core.program.LLMTextCompletionProgram"
    ) as mock_program_class:
        mock_program = MagicMock()
        mock_program.acall = AsyncMock(return_value=MockClassification())
        mock_program_class.from_defaults = MagicMock(return_value=mock_program)

        # Test execution
        categories = ["Technical", "Business", "Personal"]
        result = await tool.execute(
            text="This is about software development.", categories=categories
        )

        assert result["success"] is True
        assert "category" in result
        assert result["category"] == "Technical"
        assert "confidence" in result
        assert result["confidence"] == "high"


@pytest.mark.asyncio
async def test_split_tool():
    """Test the split tool."""
    from basic.tools import SplitTool

    tool = SplitTool()

    # Test with text - LlamaIndex SentenceSplitter will split intelligently
    text = (
        "This is the first sentence. This is the second sentence. This is the third sentence. "
        * 100
    )
    result = await tool.execute(text=text, chunk_size=100, chunk_overlap=20)

    assert result["success"] is True
    assert "splits" in result
    assert len(result["splits"]) > 0
    # With intelligent splitting, we should get multiple chunks
    assert isinstance(result["splits"], list)


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
async def test_print_to_pdf_with_markdown_tables():
    """Test that markdown tables are properly rendered in PDF."""
    from basic.tools import PrintToPDFTool

    tool = PrintToPDFTool()

    # Test markdown with tables
    markdown_text = """# Mineral Resources

| Variety | Volume | Density |
|---------|--------|---------|
| Oxidized | 9,830 | 2.58 |
| Sulfide | 67,880 | 2.72 |
| Oks. + Sulf. | 77,710 | 2.70 |

Additional text after the table.
"""

    # Mock upload function
    with patch(
        "basic.tools.print_to_pdf_tool.upload_file_to_llamacloud"
    ) as mock_upload:
        mock_upload.return_value = "file-456"

        # Test execution with markdown content
        result = await tool.execute(text=markdown_text, filename="test_table.pdf")

        assert result["success"] is True
        assert "file_id" in result
        assert result["file_id"] == "file-456"
        assert mock_upload.called

        # Verify PDF was generated (has content)
        pdf_bytes = mock_upload.call_args[0][0]
        assert len(pdf_bytes) > 0
        # PDFs start with %PDF header
        assert pdf_bytes[:4] == b"%PDF"

        # Verify the PDF is significantly larger than plain text would be
        # Tables with formatting should produce larger PDFs (with table structures)
        # A plain text version would be much smaller
        # This table has 3 rows + header, expect at least 1500 bytes for formatted table
        assert len(pdf_bytes) > 1500, (
            f"PDF size {len(pdf_bytes)} suggests no table formatting was applied"
        )


@pytest.mark.asyncio
async def test_print_to_pdf_edge_cases():
    """Test edge cases for markdown table rendering."""
    from basic.tools import PrintToPDFTool

    tool = PrintToPDFTool()

    # Test various edge cases
    edge_case_markdown = """# Edge Cases Test

## Table with unequal row lengths
| Name | Age | City |
|------|-----|------|
| John | 25 |
| Jane | 30 | NYC |
| Bob |

## Table with empty cells
| Col1 | Col2 | Col3 |
|------|------|------|
|      | Data | More |
| Data |      |      |

## Multiple consecutive tables
| Table1 | Data |
|--------|------|
| A | 1 |

| Table2 | Info |
|--------|------|
| B | 2 |

### Different header levels
#### H4 Header
##### H5 Header
###### H6 Header

Regular text with special characters: café, naïve, résumé
"""

    with patch(
        "basic.tools.print_to_pdf_tool.upload_file_to_llamacloud"
    ) as mock_upload:
        mock_upload.return_value = "file-edge"

        result = await tool.execute(text=edge_case_markdown, filename="edge_cases.pdf")

        assert result["success"] is True
        assert "file_id" in result

        # Verify PDF was generated
        pdf_bytes = mock_upload.call_args[0][0]
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b"%PDF"


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
    with patch("basic.tools.parse_tool.download_file_from_llamacloud") as mock_download:
        mock_download.return_value = b"PDF content"

        # Test execution with valid UUID file_id
        result = await tool.execute(file_id="550e8400-e29b-41d4-a716-446655440000")

        assert result["success"] is True
        assert "parsed_text" in result
        assert result["parsed_text"] == "Parsed document content"


@pytest.mark.asyncio
async def test_parse_tool_retries_on_transient_errors():
    """Test that ParseTool retries on transient API errors."""
    from basic.tools import ParseTool

    # Mock LlamaParse
    mock_parser = MagicMock()
    mock_doc = MagicMock()
    mock_doc.get_content = MagicMock(return_value="Parsed document content")

    # Simulate transient error on first attempt, success on second
    mock_parser.load_data = MagicMock(
        side_effect=[
            Exception("503 Service Unavailable"),  # First attempt fails
            [mock_doc],  # Second attempt succeeds
        ]
    )

    tool = ParseTool(mock_parser)

    # Mock download function
    with patch("basic.tools.parse_tool.download_file_from_llamacloud") as mock_download:
        mock_download.return_value = b"PDF content"

        # Test execution - should succeed after retry
        result = await tool.execute(file_id="550e8400-e29b-41d4-a716-446655440000")

        assert result["success"] is True
        assert "parsed_text" in result
        assert result["parsed_text"] == "Parsed document content"
        # Verify it was called twice (initial + 1 retry)
        assert mock_parser.load_data.call_count == 2


@pytest.mark.asyncio
async def test_parse_tool_retries_on_empty_content():
    """Test that ParseTool retries when API returns empty content intermittently."""
    from basic.tools import ParseTool

    # Mock LlamaParse
    mock_parser = MagicMock()

    # Create mock documents - some with empty content, some with real content
    empty_doc = MagicMock()
    empty_doc.get_content = MagicMock(return_value="")  # Empty content

    valid_doc = MagicMock()
    valid_doc.get_content = MagicMock(return_value="Parsed document content")

    # Simulate empty content on first attempt, valid content on second attempt
    # This simulates the intermittent empty content issue
    mock_parser.load_data = MagicMock(
        side_effect=[
            [empty_doc],  # First attempt returns empty content
            [valid_doc],  # Second attempt succeeds with content
        ]
    )

    tool = ParseTool(mock_parser)

    # Mock download function
    with patch("basic.tools.parse_tool.download_file_from_llamacloud") as mock_download:
        mock_download.return_value = b"PDF content"

        # Test execution - should succeed after retry
        result = await tool.execute(file_id="550e8400-e29b-41d4-a716-446655440000")

        assert result["success"] is True
        assert "parsed_text" in result
        assert result["parsed_text"] == "Parsed document content"
        # Verify it was called twice (initial + 1 retry due to empty content)
        assert mock_parser.load_data.call_count == 2


@pytest.mark.asyncio
async def test_parse_tool_fails_after_max_retries_on_empty_content():
    """Test that ParseTool fails gracefully after max retries with empty content."""
    from basic.tools import ParseTool

    # Mock LlamaParse
    mock_parser = MagicMock()

    # Create mock document with empty content
    empty_doc = MagicMock()
    empty_doc.get_content = MagicMock(return_value="")  # Always empty content

    # Always return empty content to exhaust retries
    mock_parser.load_data = MagicMock(return_value=[empty_doc])

    tool = ParseTool(mock_parser)

    # Mock download function
    with patch("basic.tools.parse_tool.download_file_from_llamacloud") as mock_download:
        mock_download.return_value = b"PDF content"

        # Test execution - should fail after max retries
        result = await tool.execute(file_id="550e8400-e29b-41d4-a716-446655440000")

        assert result["success"] is False
        assert "error" in result
        # Should have user-friendly error message
        assert (
            "empty" in result["error"].lower()
            or "no text content" in result["error"].lower()
        )
        # Verify it was called 5 times (initial + 4 retries as per api_retry config)
        assert mock_parser.load_data.call_count == 5


@pytest.mark.asyncio
async def test_parse_tool_graceful_handling_of_missing_file():
    """Test that ParseTool handles missing file_id/file_content gracefully."""
    from basic.tools import ParseTool

    # Mock LlamaParse (won't be called in this case)
    mock_parser = MagicMock()
    tool = ParseTool(mock_parser)

    # Test execution with no file_id or file_content
    # This simulates when LLM incorrectly schedules a parse step for non-existent attachments
    result = await tool.execute()

    # Should succeed gracefully instead of failing
    assert result["success"] is True
    assert result["parsed_text"] == ""
    assert result["skipped"] is True
    assert "message" in result
    assert "No file provided" in result["message"]
    # Parser should not be called at all
    assert mock_parser.load_data.call_count == 0


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
    """Test the sheets tool with CSV content using LlamaParse."""
    from basic.tools import SheetsTool

    # Mock LlamaParse
    mock_parser = MagicMock()
    mock_parser.aget_json = AsyncMock(
        return_value=[
            {
                "table": [
                    {"Name": "Alice", "Age": 30, "City": "New York"},
                    {"Name": "Bob", "Age": 25, "City": "London"},
                    {"Name": "Charlie", "Age": 35, "City": "Paris"},
                ]
            }
        ]
    )

    tool = SheetsTool(llama_parser=mock_parser)

    # Create a simple CSV in memory
    csv_content = "Name,Age,City\nAlice,30,New York\nBob,25,London\nCharlie,35,Paris"
    csv_bytes = csv_content.encode("utf-8")
    base64_content = base64.b64encode(csv_bytes).decode("utf-8")

    # Mock download function (won't be called since we're using file_content)
    with patch("basic.tools.sheets_tool.download_file_from_llamacloud"):
        # Test with base64 content
        result = await tool.execute(file_content=base64_content, filename="test.csv")

        assert result["success"] is True
        assert "sheet_data" in result
        assert "tables" in result["sheet_data"]
        assert "table_count" in result["sheet_data"]
        assert result["sheet_data"]["table_count"] == 1
        assert len(result["sheet_data"]["tables"]) == 1


@pytest.mark.asyncio
async def test_sheets_tool_excel():
    """Test the sheets tool with Excel content using LlamaParse."""
    from basic.tools import SheetsTool

    # Mock LlamaParse
    mock_parser = MagicMock()
    mock_parser.aget_json = AsyncMock(
        return_value=[
            {
                "table": [
                    {"Product": "Widget", "Price": 10.99, "Quantity": 100},
                    {"Product": "Gadget", "Price": 25.50, "Quantity": 50},
                    {"Product": "Doohickey", "Price": 5.00, "Quantity": 200},
                ]
            }
        ]
    )

    tool = SheetsTool(llama_parser=mock_parser)

    # Create mock Excel content
    excel_bytes = b"mock excel content"
    base64_content = base64.b64encode(excel_bytes).decode("utf-8")

    # Test with base64 content
    result = await tool.execute(file_content=base64_content, filename="test.xlsx")

    assert result["success"] is True
    assert "sheet_data" in result
    assert "tables" in result["sheet_data"]
    assert result["sheet_data"]["table_count"] == 1


@pytest.mark.asyncio
async def test_sheets_tool_missing_file():
    """Test that SheetsTool handles missing file input gracefully by returning success with skipped flag."""
    from basic.tools import SheetsTool

    tool = SheetsTool()

    # Test without file_id or file_content
    # Should now succeed gracefully instead of failing
    result = await tool.execute()

    assert result["success"] is True
    assert result["skipped"] is True
    assert "sheet_data" in result
    assert result["sheet_data"]["table_count"] == 0
    assert "message" in result
    assert "No file provided" in result["message"]
    )


@pytest.mark.asyncio
async def test_search_tool():
    """Test the web search tool."""
    from basic.tools import SearchTool

    tool = SearchTool(max_results=3)

    # Mock httpx client
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
            <div class="result">
                <a class="result__a" href="https://example.com/1">Example Result 1</a>
                <a class="result__snippet">This is a snippet for result 1</a>
            </div>
            <div class="result">
                <a class="result__a" href="https://example.com/2">Example Result 2</a>
                <a class="result__snippet">This is a snippet for result 2</a>
            </div>
        </html>
        """

        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        # Test execution
        result = await tool.execute(query="test query", max_results=3)

        assert result["success"] is True
        assert "results" in result
        assert result["query"] == "test query"
        assert len(result["results"]) == 2
        assert result["results"][0]["title"] == "Example Result 1"
        assert result["results"][0]["url"] == "https://example.com/1"
        assert result["results"][0]["snippet"] == "This is a snippet for result 1"


@pytest.mark.asyncio
async def test_search_tool_missing_query():
    """Test search tool with missing query parameter."""
    from basic.tools import SearchTool

    tool = SearchTool()

    # Test without query
    result = await tool.execute()

    assert result["success"] is False
    assert "error" in result
    assert "query" in result["error"].lower()


@pytest.mark.asyncio
async def test_search_tool_no_results():
    """Test search tool when no results are found."""
    from basic.tools import SearchTool

    tool = SearchTool()

    # Mock httpx client with empty results
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>No results</body></html>"

        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await tool.execute(query="test query")

        assert result["success"] is True
        assert "results" in result
        assert len(result["results"]) == 0
        assert "message" in result


@pytest.mark.asyncio
async def test_image_gen_tool():
    """Test the image generation tool."""
    from basic.tools import ImageGenTool

    # Mock the genai client
    with patch("basic.tools.image_gen_tool.genai.Client") as mock_client_class:
        mock_client = MagicMock()
        
        # Mock the part with inline_data
        mock_part = MagicMock()
        mock_inline_data = MagicMock()
        mock_inline_data.data = b"fake_image_data"
        mock_part.inline_data = mock_inline_data

        mock_response = MagicMock()
        mock_response.parts = [mock_part]

        mock_client.models.generate_content = MagicMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        # Mock upload function
        with patch(
            "basic.tools.image_gen_tool.upload_file_to_llamacloud"
        ) as mock_upload:
            mock_upload.return_value = "file-image-123"

            tool = ImageGenTool()

            # Test execution
            result = await tool.execute(prompt="A beautiful sunset over mountains")

            assert result["success"] is True
            assert "file_id" in result
            assert result["file_id"] == "file-image-123"
            assert result["prompt"] == "A beautiful sunset over mountains"
            # Verify single image doesn't have file_ids field
            assert "file_ids" not in result
            assert "count" not in result
            assert mock_upload.called
            assert mock_client.models.generate_content.called


@pytest.mark.asyncio
async def test_image_gen_tool_multiple_images():
    """Test generating multiple images."""
    from basic.tools import ImageGenTool

    with patch("basic.tools.image_gen_tool.genai.Client") as mock_client_class:
        mock_client = MagicMock()

        # Create multiple mock parts with inline_data
        def create_mock_response():
            mock_part = MagicMock()
            mock_inline_data = MagicMock()
            mock_inline_data.data = b"fake_image_data"
            mock_part.inline_data = mock_inline_data
            mock_response = MagicMock()
            mock_response.parts = [mock_part]
            return mock_response

        # Return a new response for each call
        mock_client.models.generate_content = MagicMock(
            side_effect=[create_mock_response() for _ in range(3)]
        )
        mock_client_class.return_value = mock_client

        with patch(
            "basic.tools.image_gen_tool.upload_file_to_llamacloud"
        ) as mock_upload:
            # Return different file IDs for each upload
            mock_upload.side_effect = ["file-1", "file-2", "file-3"]

            tool = ImageGenTool()
            result = await tool.execute(
                prompt="A cat playing with a ball", number_of_images=3
            )

            assert result["success"] is True
            assert "file_ids" in result
            assert len(result["file_ids"]) == 3
            assert result["count"] == 3
            # Verify multiple images doesn't have file_id field
            assert "file_id" not in result
            assert mock_upload.call_count == 3


@pytest.mark.asyncio
async def test_image_gen_tool_missing_prompt():
    """Test image gen tool with missing prompt."""
    from basic.tools import ImageGenTool

    with patch("basic.tools.image_gen_tool.genai.Client"):
        tool = ImageGenTool()
        result = await tool.execute()

        assert result["success"] is False
        assert "error" in result
        assert "prompt" in result["error"].lower()


@pytest.mark.asyncio
async def test_image_gen_tool_invalid_number_of_images():
    """Test image gen tool with invalid number_of_images parameter."""
    from basic.tools import ImageGenTool

    with patch("basic.tools.image_gen_tool.genai.Client"):
        tool = ImageGenTool()

        # Test with number > 4
        result = await tool.execute(prompt="test prompt", number_of_images=5)
        assert result["success"] is False
        assert "error" in result

        # Test with number < 1
        result = await tool.execute(prompt="test prompt", number_of_images=0)
        assert result["success"] is False
        assert "error" in result


@pytest.mark.asyncio
async def test_image_gen_tool_no_images_generated():
    """Test when API returns no images (filtered)."""
    from basic.tools import ImageGenTool

    with patch("basic.tools.image_gen_tool.genai.Client") as mock_client_class:
        mock_client = MagicMock()
        
        # Mock response with no parts containing inline_data
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.inline_data = None
        mock_response.parts = [mock_part]

        mock_client.models.generate_content = MagicMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        tool = ImageGenTool()
        result = await tool.execute(prompt="inappropriate content")

        assert result["success"] is False
        assert "error" in result
        assert "filtered" in result["error"].lower()


@pytest.mark.asyncio
async def test_image_gen_tool_fewer_images_than_requested():
    """Test when API returns fewer images than requested."""
    from basic.tools import ImageGenTool

    with patch("basic.tools.image_gen_tool.genai.Client") as mock_client_class:
        mock_client = MagicMock()

        # Create mock responses - 2 with images, 2 without (simulating filtering)
        def create_mock_response_with_image():
            mock_part = MagicMock()
            mock_inline_data = MagicMock()
            mock_inline_data.data = b"fake_image_data"
            mock_part.inline_data = mock_inline_data
            mock_response = MagicMock()
            mock_response.parts = [mock_part]
            return mock_response

        def create_mock_response_without_image():
            mock_part = MagicMock()
            mock_part.inline_data = None
            mock_response = MagicMock()
            mock_response.parts = [mock_part]
            return mock_response

        # Return 2 successful and 2 filtered responses
        mock_client.models.generate_content = MagicMock(
            side_effect=[
                create_mock_response_with_image(),
                create_mock_response_with_image(),
                create_mock_response_without_image(),
                create_mock_response_without_image(),
            ]
        )
        mock_client_class.return_value = mock_client

        with patch(
            "basic.tools.image_gen_tool.upload_file_to_llamacloud"
        ) as mock_upload:
            mock_upload.side_effect = ["file-1", "file-2"]

            tool = ImageGenTool()
            result = await tool.execute(prompt="Test prompt", number_of_images=4)

            # Should still succeed but with a warning
            assert result["success"] is True
            assert "file_ids" in result
            assert len(result["file_ids"]) == 2
            assert result["count"] == 2
            assert "warning" in result
            assert "4" in result["warning"]
            assert "2" in result["warning"]
            assert mock_upload.call_count == 2

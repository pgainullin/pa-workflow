
import pytest
import base64
from unittest.mock import MagicMock, AsyncMock, patch
from basic.tools import ParseTool, ExtractTool

@pytest.mark.asyncio
async def test_parse_to_extract_pipeline():
    """
    Test the integration pipeline:
    1. Parse a PDF to get text
    2. Feed that text into ExtractTool
    3. Verify numerical data is extracted
    """
    # 1. Setup mocks for LlamaParse (used by ParseTool)
    mock_doc = MagicMock()
    # Content contains numerical data
    mock_content = """
    Invoice Number: INV-2023-001
    Date: 2023-12-01
    Items:
    - Laptop: $1200.50
    - Mouse: $25.00
    - Keyboard: $75.25
    
    Total Amount: $1300.75
    Tax Rate: 8.5%
    """
    mock_doc.get_content.return_value = mock_content
    
    # Mock LlamaParse.load_data
    with patch("llama_parse.LlamaParse") as mock_llama_parse_class:
        mock_llama_parse = MagicMock()
        mock_llama_parse.load_data = MagicMock(return_value=[mock_doc])
        mock_llama_parse_class.return_value = mock_llama_parse
        
        parse_tool = ParseTool(llama_parser=mock_llama_parse)
        
        # 2. Setup mocks for LlamaExtract (used by ExtractTool)
        with patch("llama_cloud_services.LlamaExtract") as mock_llama_extract_class:
            mock_llama_extract = MagicMock()
            mock_agent = MagicMock()
            
            # Mock the extracted data result
            mock_extract_result = MagicMock()
            mock_extract_result.data = {
                "invoice_number": "INV-2023-001",
                "total_amount": 1300.75,
                "tax_rate": 8.5,
                "item_count": 3
            }
            mock_agent.aextract = AsyncMock(return_value=mock_extract_result)
            mock_llama_extract.get_agent = MagicMock(return_value=mock_agent)
            mock_llama_extract_class.return_value = mock_llama_extract
            
            extract_tool = ExtractTool(llama_extract=mock_llama_extract)
            
            # --- START PIPELINE EXECUTION ---
            
            # Step 1: Parse
            dummy_pdf_content = base64.b64encode(b"fake pdf content").decode("utf-8")
            parse_result = await parse_tool.execute(
                file_content=dummy_pdf_content,
                filename="invoice.pdf"
            )
            
            assert parse_result["success"] is True
            parsed_text = parse_result["parsed_text"]
            assert "Total Amount: $1300.75" in parsed_text
            
            # Step 2: Extract numerical data
            schema = {
                "invoice_number": "string",
                "total_amount": "number",
                "tax_rate": "number",
                "item_count": "integer"
            }
            
            extract_result = await extract_tool.execute(
                text=parsed_text,
                schema=schema
            )
            
            # --- VERIFY RESULTS ---
            
            assert extract_result["success"] is True
            extracted_data = extract_result["extracted_data"]
            
            # Verify numerical data types and values
            assert extracted_data["invoice_number"] == "INV-2023-001"
            assert isinstance(extracted_data["total_amount"], float)
            assert extracted_data["total_amount"] == 1300.75
            assert isinstance(extracted_data["tax_rate"], float)
            assert extracted_data["tax_rate"] == 8.5
            assert isinstance(extracted_data["item_count"], int)
            assert extracted_data["item_count"] == 3
            
            # Verify ExtractTool was called with the correct text
            mock_agent.aextract.assert_called_once()
            call_args = mock_agent.aextract.call_args
            source_text_obj = call_args[0][0]
            assert source_text_obj.text_content == parsed_text

@pytest.mark.asyncio
async def test_parse_to_extract_pipeline_json_string_schema():
    """
    Test the integration pipeline with schema passed as a JSON string.
    """
    import json
    
    # 1. Setup mocks for LlamaParse
    mock_doc = MagicMock()
    mock_content = "Total: 500.00 USD"
    mock_doc.get_content.return_value = mock_content
    
    with patch("llama_parse.LlamaParse") as mock_llama_parse_class:
        mock_llama_parse = MagicMock()
        mock_llama_parse.load_data = MagicMock(return_value=[mock_doc])
        mock_llama_parse_class.return_value = mock_llama_parse
        
        parse_tool = ParseTool(llama_parser=mock_llama_parse)
        
        # 2. Setup mocks for LlamaExtract
        with patch("llama_cloud_services.LlamaExtract") as mock_llama_extract_class:
            mock_llama_extract = MagicMock()
            mock_agent = MagicMock()
            
            mock_extract_result = MagicMock()
            mock_extract_result.data = {"total": 500.0}
            mock_agent.aextract = AsyncMock(return_value=mock_extract_result)
            mock_llama_extract.get_agent = MagicMock(return_value=mock_agent)
            mock_llama_extract_class.return_value = mock_llama_extract
            
            extract_tool = ExtractTool(llama_extract=mock_llama_extract)
            
            # --- EXECUTION ---
            valid_base64 = base64.b64encode(b"fake content").decode("utf-8")
            parse_result = await parse_tool.execute(file_content=valid_base64, filename="test.pdf")
            
            # Use JSON string for schema
            schema_str = json.dumps({"total": "number"})
            
            extract_result = await extract_tool.execute(
                text=parse_result["parsed_text"],
                schema=schema_str
            )
            
            # --- VERIFY ---
            assert extract_result["success"] is True
            assert extract_result["extracted_data"]["total"] == 500.0

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_parse_to_extract_pipeline())

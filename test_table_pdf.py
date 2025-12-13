#!/usr/bin/env python3
"""Test script to verify markdown table rendering in PDFs."""

import asyncio
import sys
from unittest.mock import AsyncMock, patch

# Add src to path
sys.path.insert(0, '/home/runner/work/pa-workflow/pa-workflow/src')

from basic.tools import PrintToPDFTool


async def test_markdown_table():
    """Test that markdown tables are properly rendered in PDF."""
    
    # Test markdown with tables from the issue
    markdown_text = """# Mineral Resources

| Variety | Volume |         |           |      | Stocks |      |   |   | Density |   |   |   | Average copper content |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |
| ------------- | ------ | ------- | --------- | ---- | ------- | ---- | - | - | --------- | - | - | - | ----------------------- | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| block | ore | thousand m3 | thousandtons | t/m3 | % | tons |   |   |           |   |   |   |                         |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |
| Oxidized | 9 830 | 25 350 | 2.58 | 0.25 | 62,940 |      |   |   |           |   |   |   |                         |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |
| Sulfide | 67,880 | 184 630 | 2.72 | 0.23 | 423 660 |      |   |   |           |   |   |   |                         |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |
| Oks. + Sulf. | 77 710 | 209 980 | 2.70 | 0.23 | 486 600 |      |   |   |           |   |   |   |                         |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |

# Mineral Data

| Variety | Volume |         |           |      | Stocks |        |         |      | Density |         |   |   | Average copper content |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |
| ------------- | ----- | ------- | --------- | ---- | ----------- | ------ | ------- | ---- | --------- | ------- | - | - | ----------------------- | - | - | - | - | - | - | - | - | - | - | - | - | - | - | - |
| block | ore | thousand m3 | thousand tons | t/m3 | % | tons |         |      |           |         |   |   |                         |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |
|               |       |         |           |      | Oxidized | 10,575 | 27,390 | 2.59 | 0.25 | 68 100 |   |   |                         |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |
| Sulfide |       |         |           |      |             | 79 656 | 213 477 | 2.68 | 0.24 | 522,000 |   |   |                         |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |
| Oks. + Sulf. |       |         |           |      |             | 90 231 | 240 867 | 2.67 | 0.24 | 590 100 |   |   |                         |   |   |   |   |   |   |   |   |   |   |   |   |   |   |   |

Some additional text after the tables.
"""
    
    # Create tool instance
    tool = PrintToPDFTool()
    
    # Mock the upload function
    with patch("basic.tools.upload_file_to_llamacloud") as mock_upload:
        mock_upload.return_value = "test-file-123"
        
        # Execute the tool
        result = await tool.execute(text=markdown_text, filename="test_table.pdf")
        
        # Check result
        assert result["success"] is True, f"Tool failed: {result.get('error')}"
        assert "file_id" in result
        print("✓ PDF generation succeeded")
        
        # Check that upload was called
        assert mock_upload.called
        print("✓ Upload was called")
        
        # Get the PDF bytes that were uploaded
        pdf_bytes = mock_upload.call_args[0][0]
        assert len(pdf_bytes) > 0
        print(f"✓ PDF generated with {len(pdf_bytes)} bytes")
        
        # Optionally save to file for manual inspection
        with open("/tmp/test_table.pdf", "wb") as f:
            f.write(pdf_bytes)
        print("✓ PDF saved to /tmp/test_table.pdf for inspection")


async def test_simple_table():
    """Test a simple markdown table."""
    
    simple_table = """# Simple Test

| Name | Age | City |
|------|-----|------|
| John | 25 | NYC |
| Jane | 30 | LA |
| Bob | 35 | SF |

Some text after the table.
"""
    
    tool = PrintToPDFTool()
    
    with patch("basic.tools.upload_file_to_llamacloud") as mock_upload:
        mock_upload.return_value = "test-file-456"
        
        result = await tool.execute(text=simple_table, filename="simple_test.pdf")
        
        assert result["success"] is True, f"Tool failed: {result.get('error')}"
        print("✓ Simple table PDF generation succeeded")
        
        # Save for inspection
        pdf_bytes = mock_upload.call_args[0][0]
        with open("/tmp/simple_test.pdf", "wb") as f:
            f.write(pdf_bytes)
        print("✓ Simple table PDF saved to /tmp/simple_test.pdf")


async def main():
    """Run all tests."""
    print("Testing markdown table rendering in PDFs...\n")
    
    try:
        print("Test 1: Complex tables from issue")
        await test_markdown_table()
        print()
        
        print("Test 2: Simple table")
        await test_simple_table()
        print()
        
        print("✅ All tests passed!")
        return 0
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

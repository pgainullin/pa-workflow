import os
import base64
import pytest
from pathlib import Path
from llama_parse import LlamaParse
from basic.tools.parse_tool import ParseTool

# Define path to test PDFs
TEST_PDFS_DIR = Path(__file__).parent.parent / ".test_pdfs"
ENV_FILE = Path(__file__).parent.parent / ".env"

def load_env():
    """Load environment variables from .env file manually."""
    if not ENV_FILE.exists():
        return
    
    print(f"Loading environment from {ENV_FILE}")
    with open(ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                key, value = line.split("=", 1)
                # Remove quotes if present
                value = value.strip("'").strip('"')
                if key not in os.environ:
                    os.environ[key] = value
            except ValueError:
                continue

# Load env vars at module level
load_env()

def get_test_pdfs():
    """Get list of PDF files in the test directory."""
    if not TEST_PDFS_DIR.exists():
        return []
    return [f.name for f in TEST_PDFS_DIR.glob("*.pdf")]

def is_api_key_valid():
    """Check if a likely valid API key is present."""
    key = os.getenv("LLAMA_CLOUD_API_KEY")
    return key and key != "test-dummy-key-for-testing" and not key.startswith("test-")

@pytest.mark.skipif(not TEST_PDFS_DIR.exists(), reason=".test_pdfs directory not found")
@pytest.mark.skipif(not is_api_key_valid(), reason="Valid LLAMA_CLOUD_API_KEY not found in environment")
@pytest.mark.asyncio
@pytest.mark.parametrize("filename", get_test_pdfs())
async def test_pdf_parsing_real(filename):
    """
    Test that specific local PDF files can be parsed successfully by the ParseTool.
    This runs against the real LlamaParse service to verify file integrity and parser compatibility.
    """
    file_path = TEST_PDFS_DIR / filename
    print(f"\nTesting parsing for: {file_path}")

    # Read and encode file
    with open(file_path, "rb") as f:
        file_content = f.read()
    
    encoded_content = base64.b64encode(file_content).decode("utf-8")

    # Initialize tool with real parser
    parser = LlamaParse(result_type="markdown")
    parse_tool = ParseTool(parser)

    # Execute tool
    # We pass the filename so the tool knows the extension
    result = await parse_tool.execute(
        file_content=encoded_content,
        filename=filename
    )

    # Verify results
    assert result["success"] is True, f"Parsing failed for {filename}: {result.get('error')}"
    
    parsed_text = result.get("parsed_text", "")
    assert parsed_text, f"Parsed text is empty for {filename}"
    assert len(parsed_text) > 100, f"Parsed text seems too short ({len(parsed_text)} chars) for {filename}"
    
    print(f"Successfully parsed {filename} ({len(parsed_text)} characters)")
    print(f"Snippet: {parsed_text[:200]}...")


import os
import pytest
import base64
from pathlib import Path
from basic.tools.parse_tool import ParseTool
from basic.tools.translate_tool import TranslateTool
from basic.tools.print_to_pdf_tool import PrintToPDFTool
from basic.utils import download_file_from_llamacloud

# Define path to test PDFs
TEST_PDFS_DIR = Path(__file__).parent.parent / ".test_pdfs"
INPUT_PDF = "6-3 Z11.pdf"
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

def is_api_key_valid():
    """Check if a likely valid API key is present."""
    key = os.getenv("LLAMA_CLOUD_API_KEY")
    return key and key != "test-dummy-key-for-testing" and not key.startswith("test-")

@pytest.mark.skip(reason="Depends on real LlamaParse service and valid API keys")
@pytest.mark.skipif(not TEST_PDFS_DIR.exists(), reason=".test_pdfs directory not found")
@pytest.mark.skipif(not is_api_key_valid(), reason="Valid LLAMA_CLOUD_API_KEY not found in environment")
@pytest.mark.asyncio
async def test_pdf_translation_flow():
    """
    End-to-end test:
    1. Parse 6-3 Z11.pdf (Chinese)
    2. Translate Chinese -> English
    3. Translate English -> Chinese
    4. Print to PDF
    5. Save locally
    """
    file_path = TEST_PDFS_DIR / INPUT_PDF
    print(f"\n--- Step 1: Parsing {file_path} ---")

    # Read and encode file
    with open(file_path, "rb") as f:
        file_content = f.read()
    
    encoded_content = base64.b64encode(file_content).decode("utf-8")

    # Initialize tools
    parse_tool = ParseTool()
    translate_tool = TranslateTool()
    pdf_tool = PrintToPDFTool()

    # Monkeypatch upload_file_to_llamacloud in the tool module to save locally
    # This avoids needing a project ID and allows us to verify the file content directly
    original_upload = None
    
    async def mock_upload(content, filename):
        print(f"Mock upload: Saving {len(content)} bytes to local file: {filename}")
        # Save to the test directory immediately
        output_path = TEST_PDFS_DIR / filename
        with open(output_path, "wb") as f:
            f.write(content)
        return "mock-file-id-local-save"

    # Apply patch
    import basic.tools.print_to_pdf_tool
    basic.tools.print_to_pdf_tool.upload_file_to_llamacloud = mock_upload

    # 1. Parse
    parse_result = await parse_tool.execute(
        file_content=encoded_content,
        filename=INPUT_PDF
    )
    
    assert parse_result["success"] is True, f"Parsing failed: {parse_result.get('error')}"
    parsed_text = parse_result.get("parsed_text", "")
    assert parsed_text, "Parsed text is empty"
    
    print(f"\n--- Parsed Text (Truncated) ---\n{parsed_text[:200]}...\n-------------------------------")

    # 2. Translate to English
    print("\n--- Step 2: Translating to English ---")
    tr_en_result = await translate_tool.execute(
        text=parsed_text,
        source_lang="zh-CN", # Simplified Chinese
        target_lang="en"
    )
    assert tr_en_result["success"] is True, f"Translation to EN failed: {tr_en_result.get('error')}"
    english_text = tr_en_result["translated_text"]
    print(f"\n--- English Text (Truncated) ---\n{english_text[:200]}...\n--------------------------------")

    # 3. Translate back to Chinese
    print("\n--- Step 3: Translating back to Chinese ---")
    tr_cn_result = await translate_tool.execute(
        text=english_text,
        source_lang="en",
        target_lang="zh-CN"
    )
    assert tr_cn_result["success"] is True, f"Translation back to CN failed: {tr_cn_result.get('error')}"
    chinese_text = tr_cn_result["translated_text"]
    print(f"\n--- Back-Translated Chinese Text (Truncated) ---\n{chinese_text[:200]}...\n------------------------------------------------")

    # 4. Print to PDF
    print("\n--- Step 4: Printing to PDF ---")
    pdf_filename = "translated_6-3_Z11.pdf"
    pdf_result = await pdf_tool.execute(
        text=chinese_text,
        filename=pdf_filename
    )
    assert pdf_result["success"] is True, f"PDF generation failed: {pdf_result.get('error')}"
    file_id = pdf_result["file_id"]
    print(f"PDF generated with file_id: {file_id}")

    # 5. Verify saved PDF
    print("\n--- Step 5: Verifying Saved PDF ---")
    # Since we mocked the upload to save directly, we just check the file
    output_path = TEST_PDFS_DIR / pdf_filename
    
    print(f"Checking if PDF exists at: {output_path}")
    
    # Verify file exists and has size
    assert output_path.exists()
    assert output_path.stat().st_size > 0
    print("Test Complete!")

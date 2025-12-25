"""Tests for workflow bug fixes.

This module tests the fixes for the PDF workflow processing errors:
- Bug 1: ParseTool UUID validation and fallback
- Bug 2: TranslateTool get_supported_languages fix
- Bug 3: Template resolution with single and double braces
- Bug 4: Result formatting with file_id
"""

import os
from unittest.mock import MagicMock, patch

import pytest

# Set dummy API keys
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_PROJECT_ID", "test-project-id")


@pytest.mark.asyncio
async def test_translate_tool_get_supported_languages_fix():
    """Test Bug 2: TranslateTool correctly calls get_supported_languages as instance method."""
    from basic.tools import TranslateTool

    tool = TranslateTool()

    # Mock the translator
    with patch("basic.tools.translate_tool.GoogleTranslator") as mock_translator_class:
        # Create a mock instance
        mock_translator_instance = MagicMock()
        mock_translator_instance.translate = MagicMock(return_value="Bonjour le monde")
        mock_translator_instance.get_supported_languages = MagicMock(
            return_value={"en": "English", "fr": "French", "es": "Spanish"}
        )

        # Make the class constructor return the mock instance
        mock_translator_class.return_value = mock_translator_instance

        # Test execution
        result = await tool.execute(
            text="Hello world", source_lang="en", target_lang="fr"
        )

        assert result["success"] is True
        assert "translated_text" in result
        assert result["translated_text"] == "Bonjour le monde"


@pytest.mark.asyncio
async def test_parse_tool_uuid_validation():
    """Test Bug 1: ParseTool validates UUID and provides helpful error messages."""
    from basic.tools import ParseTool

    # Mock LlamaParse
    mock_parser = MagicMock()
    tool = ParseTool(mock_parser)

    # Test with invalid UUID (filename instead) and no content
    result = await tool.execute(file_id="SHAGALA_Copper.pdf")

    assert result["success"] is False
    assert "not a valid UUID" in result["error"]
    assert "file reference might not have been resolved correctly" in result["error"]


@pytest.mark.asyncio
async def test_parse_tool_fallback_to_content():
    """Test Bug 1: ParseTool falls back to content when UUID is invalid."""
    import base64

    from basic.tools import ParseTool

    # Mock LlamaParse
    mock_parser = MagicMock()
    mock_doc = MagicMock()
    mock_doc.get_content = MagicMock(return_value="Parsed document content")
    mock_parser.load_data = MagicMock(return_value=[mock_doc])

    tool = ParseTool(mock_parser)

    # Test with invalid UUID but with content as fallback
    test_content = base64.b64encode(b"PDF content here").decode()

    result = await tool.execute(file_id="SHAGALA_Copper.pdf", file_content=test_content)

    assert result["success"] is True
    assert "parsed_text" in result
    assert result["parsed_text"] == "Parsed document content"


@pytest.mark.asyncio
async def test_attachment_resolution_by_filename():
    """Test Bug 1: Workflow resolves attachments by filename in addition to att-X format."""
    with patch("llama_index.llms.google_genai.GoogleGenAI") as mock_llm, patch(
        "google.genai.Client"
    ) as mock_genai:

        from basic.email_workflow import EmailWorkflow
        from basic.models import Attachment, EmailData

        workflow = EmailWorkflow()

        # Create test email data with attachments
        email_data = EmailData(
            from_email="test@example.com",
            to_email="workflow@example.com",
            subject="Test",
            text="Test email",
            attachments=[
                Attachment(
                    id="att-1",
                    name="SHAGALA_Copper.pdf",
                    type="application/pdf",
                    file_id="550e8400-e29b-41d4-a716-446655440000",
                    content=None,
                )
            ],
        )

        # Test resolving by filename
        from basic.plan_utils import resolve_params
        params = {"file_id": "SHAGALA_Copper.pdf"}
        resolved = resolve_params(params, {}, email_data)

        assert resolved["file_id"] == "550e8400-e29b-41d4-a716-446655440000"

        # Test resolving by att-X format
        params = {"file_id": "att-1"}
        resolved = resolve_params(params, {}, email_data)

        assert resolved["file_id"] == "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_template_resolution_single_and_double_braces():
    """Test Bug 3: Template resolution works with both single and double braces."""
    with patch("llama_index.llms.google_genai.GoogleGenAI") as mock_llm, patch(
        "google.genai.Client"
    ) as mock_genai:

        from basic.email_workflow import EmailWorkflow
        from basic.models import EmailData

        workflow = EmailWorkflow()

        email_data = EmailData(
            from_email="test@example.com",
            to_email="workflow@example.com",
            subject="Test",
            text="Test email",
        )

        context = {
            "step_1": {"success": True, "parsed_text": "This is parsed text"},
        }

        # Test double-brace template resolution
        from basic.plan_utils import resolve_params
        params = {"text": "{{step_1.parsed_text}}"}
        resolved = resolve_params(params, context, email_data)
        assert resolved["text"] == "This is parsed text"

        # Test single-brace template resolution
        params = {"text": "{step_1.parsed_text}"}
        resolved = resolve_params(params, context, email_data)
        assert resolved["text"] == "This is parsed text"


@pytest.mark.asyncio
async def test_dependency_checking_single_and_double_braces():
    """Test Bug 3: Dependency checking works with both single and double braces."""
    with patch("llama_index.llms.google_genai.GoogleGenAI") as mock_llm, patch(
        "google.genai.Client"
    ) as mock_genai:

        from basic.email_workflow import EmailWorkflow
        from basic.models import EmailData

        workflow = EmailWorkflow()


        context = {
            "step_1": {"success": True, "parsed_text": "This is parsed text"},
            "step_2": {"success": False, "error": "Translation failed"},
        }

        # Test dependency checking with double braces
        from basic.plan_utils import check_step_dependencies
        params = {"text": "{{step_2.translated_text}}"}
        has_failed_dep = check_step_dependencies(params, context, 3)
        assert has_failed_dep is True

        # Test dependency checking with single braces
        params = {"text": "{step_2.translated_text}"}
        has_failed_dep = check_step_dependencies(params, context, 3)
        assert has_failed_dep is True


@pytest.mark.asyncio
async def test_result_formatting_with_file_id():
    """Test Bug 4: Result formatting shows file_id for generated files."""
    with patch("llama_index.llms.google_genai.GoogleGenAI") as mock_llm, patch(
        "google.genai.Client"
    ) as mock_genai:

        from basic.email_workflow import EmailWorkflow
        from basic.models import EmailData

        workflow = EmailWorkflow()

        email_data = EmailData(
            from_email="test@example.com",
            to_email="workflow@example.com",
            subject="Test",
            text="Test email",
        )

        results = [
            {
                "step": 1,
                "tool": "print_to_pdf",
                "description": "Convert text to PDF",
                "success": True,
                "file_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        ]

        from basic.response_utils import create_execution_log
        formatted = create_execution_log(results, email_data)

        # Check that file_id is included in the output
        assert "Generated File ID" in formatted
        assert "550e8400-e29b-41d4-a716-446655440000" in formatted

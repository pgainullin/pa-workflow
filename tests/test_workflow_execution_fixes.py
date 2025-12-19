"""Tests for workflow execution issue fixes.

This module tests the fixes for workflow execution inconsistency issues:
- Issue 1: TranslateTool language code validation
- Issue 2: ParseTool empty result validation
- Issue 3: Triage prompt improvements for attachment processing
- Issue 4: Attachment collection and inclusion in response emails
- Issue 5: Callback retry logic
"""

import base64
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set dummy API keys
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_PROJECT_ID", "test-project-id")


@pytest.mark.asyncio
async def test_translate_tool_accepts_language_codes():
    """Test that TranslateTool accepts both language codes ('en') and full names ('english')."""
    from basic.tools import TranslateTool

    tool = TranslateTool()

    # Mock the translator
    with patch("basic.tools.GoogleTranslator") as mock_translator_class:
        # Create a mock instance
        mock_translator_instance = MagicMock()
        mock_translator_instance.translate = MagicMock(return_value="Bonjour le monde")
        # get_supported_languages returns dict with names as keys, codes as values
        mock_translator_instance.get_supported_languages = MagicMock(
            return_value={"english": "en", "french": "fr", "spanish": "es"}
        )

        # Make the class constructor return the mock instance
        mock_translator_class.return_value = mock_translator_instance

        # Test with language code (short form like 'en')
        result = await tool.execute(
            text="Hello world", source_lang="en", target_lang="fr"
        )

        assert result["success"] is True
        assert "translated_text" in result
        assert result["translated_text"] == "Bonjour le monde"


@pytest.mark.asyncio
async def test_translate_tool_accepts_language_names():
    """Test that TranslateTool accepts full language names ('english')."""
    from basic.tools import TranslateTool

    tool = TranslateTool()

    # Mock the translator
    with patch("basic.tools.GoogleTranslator") as mock_translator_class:
        # Create a mock instance
        mock_translator_instance = MagicMock()
        mock_translator_instance.translate = MagicMock(return_value="Hola mundo")
        # get_supported_languages returns dict with names as keys, codes as values
        mock_translator_instance.get_supported_languages = MagicMock(
            return_value={"english": "en", "french": "fr", "spanish": "es"}
        )

        # Make the class constructor return the mock instance
        mock_translator_class.return_value = mock_translator_instance

        # Test with full language name
        result = await tool.execute(
            text="Hello world", source_lang="english", target_lang="spanish"
        )

        assert result["success"] is True
        assert "translated_text" in result
        assert result["translated_text"] == "Hola mundo"


@pytest.mark.asyncio
async def test_translate_tool_rejects_invalid_language():
    """Test that TranslateTool rejects invalid language codes."""
    from basic.tools import TranslateTool

    tool = TranslateTool()

    # Mock the translator
    with patch("basic.tools.GoogleTranslator") as mock_translator_class:
        # Create a mock instance
        mock_translator_instance = MagicMock()
        mock_translator_instance.get_supported_languages = MagicMock(
            return_value={"english": "en", "french": "fr", "spanish": "es"}
        )

        # Make the class constructor return the mock instance
        mock_translator_class.return_value = mock_translator_instance

        # Test with invalid language code
        result = await tool.execute(
            text="Hello world", source_lang="auto", target_lang="invalid_lang"
        )

        assert result["success"] is False
        assert "Invalid target_lang" in result["error"]
        assert "invalid_lang" in result["error"]


@pytest.mark.asyncio
async def test_parse_tool_detects_empty_results():
    """Test that ParseTool detects and reports empty parsing results."""
    from basic.tools import ParseTool

    # Mock LlamaParse
    mock_parser = MagicMock()
    mock_doc = MagicMock()
    mock_doc.get_content = MagicMock(return_value="")  # Empty content
    mock_parser.load_data = MagicMock(return_value=[mock_doc])

    tool = ParseTool(mock_parser)

    # Test with valid UUID but empty parsing result
    test_content = base64.b64encode(b"Empty PDF").decode()

    result = await tool.execute(file_id="test-file.pdf", file_content=test_content)

    assert result["success"] is False
    assert "parsing returned no text content" in result["error"].lower()
    assert (
        "empty, corrupted, or in an unsupported format" in result["error"].lower()
    )


@pytest.mark.asyncio
async def test_parse_tool_accepts_non_empty_results():
    """Test that ParseTool accepts non-empty parsing results."""
    from basic.tools import ParseTool

    # Mock LlamaParse
    mock_parser = MagicMock()
    mock_doc = MagicMock()
    mock_doc.get_content = MagicMock(return_value="Some parsed content")
    mock_parser.load_data = MagicMock(return_value=[mock_doc])

    tool = ParseTool(mock_parser)

    # Test with valid content
    test_content = base64.b64encode(b"PDF content").decode()

    result = await tool.execute(file_id="test-file.pdf", file_content=test_content)

    assert result["success"] is True
    assert result["parsed_text"] == "Some parsed content"


def test_sanitize_filename_from_prompt_basic():
    """Test basic sanitization of prompts to filenames."""
    from basic.response_utils import sanitize_filename_from_prompt
    
    assert sanitize_filename_from_prompt("A beautiful sunset") == "a_beautiful_sunset"
    assert sanitize_filename_from_prompt("Simple text") == "simple_text"
    assert sanitize_filename_from_prompt("Multiple   spaces") == "multiple_spaces"


def test_sanitize_filename_from_prompt_special_chars():
    """Test that special characters are removed from filenames."""
    from basic.response_utils import sanitize_filename_from_prompt
    
    assert sanitize_filename_from_prompt("Hello@World!") == "helloworld"
    assert sanitize_filename_from_prompt("Test#123$456") == "test123456"
    assert sanitize_filename_from_prompt("A cat's toy") == "a_cats_toy"
    assert sanitize_filename_from_prompt("100% perfect!") == "100_perfect"


def test_sanitize_filename_from_prompt_truncation():
    """Test that long prompts are truncated."""
    from basic.response_utils import sanitize_filename_from_prompt
    
    long_prompt = "This is a very long prompt that should be truncated to the maximum length"
    result = sanitize_filename_from_prompt(long_prompt, max_length=20)
    assert len(result) <= 20
    assert result == "this_is_a_very_long"


def test_sanitize_filename_from_prompt_empty():
    """Test handling of empty or whitespace-only prompts."""
    from basic.response_utils import sanitize_filename_from_prompt
    
    assert sanitize_filename_from_prompt("") == "generated_image"
    assert sanitize_filename_from_prompt("   ") == "generated_image"
    assert sanitize_filename_from_prompt("!!!") == "generated_image"


def test_sanitize_filename_from_prompt_trailing_underscores():
    """Test that trailing underscores are removed."""
    from basic.response_utils import sanitize_filename_from_prompt
    
    assert sanitize_filename_from_prompt("Test   ") == "test"
    assert sanitize_filename_from_prompt("End with spaces   ", max_length=10) == "end_with_s"


@pytest.mark.asyncio
async def test_collect_attachments_from_results():
    """Test that workflow collects file attachments from tool results."""
    from basic.response_utils import collect_attachments

    # Mock results with a print_to_pdf step that generated a file
    results = [
        {
            "step": 1,
            "tool": "parse",
            "success": True,
            "parsed_text": "Some text",
        },
        {
            "step": 2,
            "tool": "print_to_pdf",
            "success": True,
            "file_id": "test-file-uuid-123",
        },
        {
            "step": 3,
            "tool": "summarise",
            "success": True,
            "summary": "Summary text",
        },
    ]

    attachments = collect_attachments(results)

    assert len(attachments) == 1
    assert attachments[0].file_id == "test-file-uuid-123"
    assert attachments[0].name == "output_step_2.pdf"
    assert attachments[0].type == "application/pdf"
    assert attachments[0].id == "generated-2"


@pytest.mark.asyncio
async def test_collect_attachments_skips_failed_steps():
    """Test that workflow only collects attachments from successful steps."""
    from basic.response_utils import collect_attachments

    # Mock results with failed and successful steps
    results = [
        {
            "step": 1,
            "tool": "print_to_pdf",
            "success": False,
            "error": "Some error",
        },
        {
            "step": 2,
            "tool": "print_to_pdf",
            "success": True,
            "file_id": "test-file-uuid-456",
        },
    ]

    attachments = collect_attachments(results)

    assert len(attachments) == 1
    assert attachments[0].file_id == "test-file-uuid-456"


@pytest.mark.asyncio
async def test_collect_attachments_image_gen_with_prompt():
    """Test that image_gen attachments use .png extension and intuitive filename from prompt."""
    from basic.response_utils import collect_attachments

    # Mock results with image_gen step including prompt
    results = [
        {
            "step": 1,
            "tool": "image_gen",
            "success": True,
            "file_id": "test-image-uuid-123",
            "prompt": "A beautiful sunset over snow-capped mountains",
        },
    ]

    attachments = collect_attachments(results)

    assert len(attachments) == 1
    assert attachments[0].file_id == "test-image-uuid-123"
    assert attachments[0].name == "a_beautiful_sunset_over_snow_capped_mountains_step_1.png"
    assert attachments[0].type == "image/png"
    assert attachments[0].id == "generated-1"


@pytest.mark.asyncio
async def test_collect_attachments_image_gen_without_prompt():
    """Test that image_gen attachments use default filename when prompt is missing."""
    from basic.response_utils import collect_attachments

    # Mock results with image_gen step without prompt
    results = [
        {
            "step": 2,
            "tool": "image_gen",
            "success": True,
            "file_id": "test-image-uuid-456",
        },
    ]

    attachments = collect_attachments(results)

    assert len(attachments) == 1
    assert attachments[0].file_id == "test-image-uuid-456"
    assert attachments[0].name == "generated_image_step_2.png"
    assert attachments[0].type == "image/png"
    assert attachments[0].id == "generated-2"


@pytest.mark.asyncio
async def test_collect_attachments_image_gen_long_prompt():
    """Test that image_gen attachments truncate very long prompts."""
    from basic.response_utils import collect_attachments

    # Mock results with image_gen step with very long prompt
    long_prompt = "A very detailed and extremely long description that goes on and on about various aspects of the image including colors, composition, lighting, and many other elements"
    results = [
        {
            "step": 3,
            "tool": "image_gen",
            "success": True,
            "file_id": "test-image-uuid-789",
            "prompt": long_prompt,
        },
    ]

    attachments = collect_attachments(results)

    assert len(attachments) == 1
    assert attachments[0].file_id == "test-image-uuid-789"
    # Should be truncated to 50 characters max (plus step suffix and ".png")
    # Format: "{base_filename}_step_{step_num}.png" where base is max 50 chars
    assert attachments[0].name.endswith("_step_3.png")
    assert attachments[0].type == "image/png"


@pytest.mark.asyncio
async def test_collect_attachments_image_gen_special_characters():
    """Test that image_gen attachments sanitize special characters in prompt."""
    from basic.response_utils import collect_attachments

    # Mock results with image_gen step with special characters in prompt
    results = [
        {
            "step": 4,
            "tool": "image_gen",
            "success": True,
            "file_id": "test-image-uuid-abc",
            "prompt": "A cat's portrait @ home! (With toys & fun)",
        },
    ]

    attachments = collect_attachments(results)

    assert len(attachments) == 1
    assert attachments[0].file_id == "test-image-uuid-abc"
    # Special characters should be removed, spaces converted to underscores
    assert attachments[0].name == "a_cats_portrait_home_with_toys_fun_step_4.png"
    assert attachments[0].type == "image/png"


@pytest.mark.asyncio
async def test_collect_attachments_image_gen_multiple_images_with_prompt():
    """Test that image_gen attachments handle multiple images with file_ids array."""
    from basic.response_utils import collect_attachments

    # Mock results with image_gen step with multiple images
    results = [
        {
            "step": 5,
            "tool": "image_gen",
            "success": True,
            "file_ids": ["test-image-uuid-001", "test-image-uuid-002", "test-image-uuid-003"],
            "count": 3,
            "prompt": "A playful kitten with yarn",
        },
    ]

    attachments = collect_attachments(results)

    assert len(attachments) == 3
    
    # Check first attachment
    assert attachments[0].file_id == "test-image-uuid-001"
    assert attachments[0].name == "a_playful_kitten_with_yarn_step_5_1.png"
    assert attachments[0].type == "image/png"
    assert attachments[0].id == "generated-5-1"
    
    # Check second attachment
    assert attachments[1].file_id == "test-image-uuid-002"
    assert attachments[1].name == "a_playful_kitten_with_yarn_step_5_2.png"
    assert attachments[1].type == "image/png"
    assert attachments[1].id == "generated-5-2"
    
    # Check third attachment
    assert attachments[2].file_id == "test-image-uuid-003"
    assert attachments[2].name == "a_playful_kitten_with_yarn_step_5_3.png"
    assert attachments[2].type == "image/png"
    assert attachments[2].id == "generated-5-3"


@pytest.mark.asyncio
async def test_collect_attachments_image_gen_multiple_images_without_prompt():
    """Test that image_gen attachments handle multiple images without prompt."""
    from basic.response_utils import collect_attachments

    # Mock results with image_gen step with multiple images but no prompt
    results = [
        {
            "step": 6,
            "tool": "image_gen",
            "success": True,
            "file_ids": ["test-image-uuid-100", "test-image-uuid-101"],
            "count": 2,
        },
    ]

    attachments = collect_attachments(results)

    assert len(attachments) == 2
    
    # Check first attachment
    assert attachments[0].file_id == "test-image-uuid-100"
    assert attachments[0].name == "generated_image_step_6_1.png"
    assert attachments[0].type == "image/png"
    assert attachments[0].id == "generated-6-1"
    
    # Check second attachment
    assert attachments[1].file_id == "test-image-uuid-101"
    assert attachments[1].name == "generated_image_step_6_2.png"
    assert attachments[1].type == "image/png"
    assert attachments[1].id == "generated-6-2"


@pytest.mark.asyncio
async def test_callback_retry_on_transient_error():
    """Test that callback retries on transient errors."""
    with patch("llama_index.llms.google_genai.GoogleGenAI") as mock_llm, patch(
        "google.genai.Client"
    ) as mock_genai:
        from basic.email_workflow import EmailWorkflow
        from basic.models import SendEmailRequest

        workflow = EmailWorkflow()

        # Mock httpx client to fail once then succeed
        with patch("httpx.AsyncClient") as mock_client_class:
            import httpx
            
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            # First call fails with 503, second call succeeds
            # Create a realistic HTTPStatusError with proper request/response
            mock_request = httpx.Request("POST", "http://test.com/callback")
            mock_response_fail = httpx.Response(503, request=mock_request)
            
            mock_response_success = MagicMock()
            mock_response_success.raise_for_status = MagicMock(return_value=None)

            # First post returns 503 response, raise_for_status will raise HTTPStatusError
            # Second post returns success response
            async def mock_post_side_effect(*args, **kwargs):
                if mock_client.post.call_count == 1:
                    return mock_response_fail
                return mock_response_success
            
            mock_client.post = AsyncMock(side_effect=mock_post_side_effect)
            mock_client_class.return_value = mock_client

            email_request = SendEmailRequest(
                to_email="test@example.com",
                subject="Test",
                text="Test body",
                html="<p>Test body</p>",
            )

            # Should succeed after retry
            await workflow._send_callback_email(
                "http://test.com/callback", "test-token", email_request
            )

            # Verify it was called twice (initial + 1 retry)
            assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_triage_prompt_emphasizes_attachments():
    """Test that triage prompt emphasizes processing attachments."""
    with patch("llama_index.llms.google_genai.GoogleGenAI") as mock_llm, patch(
        "google.genai.Client"
    ) as mock_genai:
        from basic.email_workflow import EmailWorkflow, RESPONSE_BEST_PRACTICES
        from basic.models import Attachment, EmailData
        from basic.prompt_utils import build_triage_prompt

        workflow = EmailWorkflow()

        email_data = EmailData(
            from_email="test@example.com",
            to_email="workflow@example.com",
            subject="Test email with attachment",
            text="Please process the attached PDF",
            attachments=[
                Attachment(
                    id="att-1",
                    name="test.pdf",
                    type="application/pdf",
                    content="base64content",
                )
            ],
        )

        prompt = build_triage_prompt(
            email_data,
            workflow.tool_registry.get_tool_descriptions(),
            RESPONSE_BEST_PRACTICES,
        )

        # Check that prompt emphasizes attachment processing
        assert "MUST process them using appropriate tools" in prompt
        assert "Do not create overly simplistic plans" in prompt
        assert "Analyze what type of processing each attachment needs" in prompt
        assert "attachments:" in prompt.lower()
        assert "test.pdf" in prompt


@pytest.mark.asyncio
async def test_triage_prompt_without_attachments():
    """Test that triage prompt works without attachments."""
    with patch("llama_index.llms.google_genai.GoogleGenAI") as mock_llm, patch(
        "google.genai.Client"
    ) as mock_genai:
        from basic.email_workflow import EmailWorkflow, RESPONSE_BEST_PRACTICES
        from basic.models import EmailData
        from basic.prompt_utils import build_triage_prompt

        workflow = EmailWorkflow()

        email_data = EmailData(
            from_email="test@example.com",
            to_email="workflow@example.com",
            subject="Test email without attachment",
            text="Just a simple email",
            attachments=[],
        )

        prompt = build_triage_prompt(
            email_data,
            workflow.tool_registry.get_tool_descriptions(),
            RESPONSE_BEST_PRACTICES,
        )

        # Should still generate valid prompt
        assert "triage agent" in prompt.lower()
        assert "Available Tools:" in prompt
        # No attachment info section
        assert "Attachments:" not in prompt

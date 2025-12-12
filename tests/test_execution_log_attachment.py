"""Tests for execution log attachment feature."""

import os
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set dummy API keys
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_PROJECT_ID", "test-project-id")

# Mock the LLM/genai clients before importing the workflow
with patch("llama_index.llms.google_genai.GoogleGenAI"):
    with patch("google.genai.Client"):
        with patch("llama_parse.LlamaParse"):
            from basic.email_workflow import EmailWorkflow, PlanExecutionEvent

from basic.models import CallbackConfig, EmailData


@pytest.mark.asyncio
async def test_execution_log_created_as_attachment():
    """Test that execution log is created as an attachment."""
    workflow = EmailWorkflow(timeout=60)

    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test Subject",
        text="Test content",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    results = [
        {
            "step": 1,
            "tool": "summarise",
            "description": "Summarize content",
            "success": True,
            "summary": "This is the summary",
        },
    ]

    # Mock the LLM response for user response generation
    mock_llm_response = MagicMock()
    mock_llm_response.__str__ = lambda x: "Your email has been processed and summarized."
    workflow._llm_complete_with_retry = AsyncMock(return_value=mock_llm_response)

    # Mock the callback method
    workflow._send_callback_email = AsyncMock()

    # Execute send_results step
    event = PlanExecutionEvent(
        results=results, email_data=email_data, callback=callback
    )
    
    from workflows import Context
    ctx = Context(workflow)
    
    await workflow.send_results(event, ctx)

    # Verify callback was called
    assert workflow._send_callback_email.called
    
    # Get the email request that was sent
    call_args = workflow._send_callback_email.call_args
    email_request = call_args[0][2]  # third positional argument
    
    # Verify the email has attachments
    assert len(email_request.attachments) > 0
    
    # Find the execution log attachment
    exec_log_attachment = None
    for att in email_request.attachments:
        if att.name == "execution_log.md":
            exec_log_attachment = att
            break
    
    assert exec_log_attachment is not None, "execution_log.md attachment not found"
    assert exec_log_attachment.type == "text/markdown"
    assert exec_log_attachment.content is not None
    
    # Decode and verify content
    decoded_content = base64.b64decode(exec_log_attachment.content).decode("utf-8")
    assert "Workflow Execution Log" in decoded_content
    assert "Test Subject" in decoded_content
    assert "summarise" in decoded_content
    assert "This is the summary" in decoded_content


@pytest.mark.asyncio
async def test_user_response_is_natural_language():
    """Test that the email body contains natural language response, not verbose log."""
    workflow = EmailWorkflow(timeout=60)

    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Summarize my document",
        text="Test content",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    results = [
        {
            "step": 1,
            "tool": "parse",
            "description": "Parse document",
            "success": True,
            "parsed_text": "This is the parsed document content.",
        },
        {
            "step": 2,
            "tool": "summarise",
            "description": "Summarize content",
            "success": True,
            "summary": "This is the summary of the document.",
        },
    ]

    # Mock the LLM response for user response generation
    mock_llm_response = MagicMock()
    mock_llm_response.__str__ = lambda x: "I've parsed and summarized your document. The summary is: This is the summary of the document."
    workflow._llm_complete_with_retry = AsyncMock(return_value=mock_llm_response)

    # Mock the callback method
    workflow._send_callback_email = AsyncMock()

    # Execute send_results step
    event = PlanExecutionEvent(
        results=results, email_data=email_data, callback=callback
    )
    
    from workflows import Context
    ctx = Context(workflow)
    
    await workflow.send_results(event, ctx)

    # Get the email request that was sent
    call_args = workflow._send_callback_email.call_args
    email_request = call_args[0][2]
    
    # Verify the body is natural language, not verbose log
    assert email_request.text is not None
    assert "I've parsed and summarized your document" in email_request.text
    
    # Should NOT contain verbose step-by-step format
    assert "Step 1:" not in email_request.text
    assert "Step 2:" not in email_request.text


@pytest.mark.asyncio
async def test_execution_log_format():
    """Test the format of the execution log."""
    workflow = EmailWorkflow(timeout=60)

    email_data = EmailData(
        from_email="user@example.com",
        subject="Test",
        text="Test",
    )

    results = [
        {
            "step": 1,
            "tool": "summarise",
            "description": "Summarize content",
            "success": True,
            "summary": "This is the summary",
        },
        {
            "step": 2,
            "tool": "translate",
            "description": "Translate to French",
            "success": False,
            "error": "Translation API error",
        },
    ]

    log = workflow._create_execution_log(results, email_data)

    # Check markdown structure
    assert "# Workflow Execution Log" in log
    assert "## Step 1: summarise" in log
    assert "## Step 2: translate" in log
    assert "**Status:** ✓ Success" in log
    assert "**Status:** ✗ Failed" in log
    assert "**Summary:**" in log
    assert "This is the summary" in log
    assert "**Error:**" in log
    assert "Translation API error" in log
    assert "**Processing complete.**" in log


@pytest.mark.asyncio
async def test_user_response_generation_with_fallback():
    """Test user response generation with LLM fallback."""
    workflow = EmailWorkflow(timeout=60)

    email_data = EmailData(
        from_email="user@example.com",
        subject="Test",
        text="Test",
    )

    results = [
        {
            "step": 1,
            "tool": "summarise",
            "description": "Summarize content",
            "success": True,
            "summary": "This is the summary",
        },
    ]

    # Mock LLM to fail
    workflow._llm_complete_with_retry = AsyncMock(side_effect=Exception("LLM error"))

    response = await workflow._generate_user_response(results, email_data)

    # Should use fallback response
    assert "Your email has been processed successfully" in response
    assert "Summary: This is the summary" in response
    assert "execution_log.md" in response


@pytest.mark.asyncio
async def test_user_response_with_no_successful_results():
    """Test user response when all steps failed."""
    workflow = EmailWorkflow(timeout=60)

    email_data = EmailData(
        from_email="user@example.com",
        subject="Test",
        text="Test",
    )

    results = [
        {
            "step": 1,
            "tool": "parse",
            "description": "Parse document",
            "success": False,
            "error": "File not found",
        },
    ]

    response = await workflow._generate_user_response(results, email_data)

    # Should indicate failure
    assert response == "I've processed your email, but encountered issues with all steps. Please see the attached execution log for details."
    assert "execution log" in response.lower()

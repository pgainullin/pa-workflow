"""Tests for agent triage email workflow."""

import os
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
            from basic.email_workflow import EmailWorkflow

from basic.models import CallbackConfig, EmailData


@pytest.mark.asyncio
async def test_triage_simple_email():
    """Test triage of a simple email."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Please summarize this",
        text="This is a long document that needs to be summarized.",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    # Mock the LLM to return a simple plan
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.__str__ = (
        lambda x: """[
        {
            "tool": "summarise",
            "params": {"text": "This is a long document that needs to be summarized."},
            "description": "Summarize the email content"
        }
    ]"""
    )
    mock_llm.acomplete = AsyncMock(return_value=mock_response)

    workflow = EmailWorkflow(timeout=60)
    workflow.llm = mock_llm

    # Run triage step
    from basic.email_workflow import EmailStartEvent

    result = await workflow.triage_email(
        EmailStartEvent(email_data=email_data, callback=callback), MagicMock()
    )

    assert result.plan is not None
    assert len(result.plan) > 0
    assert result.plan[0]["tool"] == "summarise"


@pytest.mark.asyncio
async def test_plan_parsing():
    """Test parsing of execution plan from LLM response."""
    from basic.models import EmailData

    workflow = EmailWorkflow(timeout=60)

    email_data = EmailData(
        from_email="test@example.com", subject="Test", text="Test content"
    )

    # Test valid JSON plan
    response = """[
        {
            "tool": "parse",
            "params": {"file_id": "file-123"},
            "description": "Parse the document"
        },
        {
            "tool": "summarise",
            "params": {"text": "{{step_1.parsed_text}}"},
            "description": "Summarize parsed content"
        }
    ]"""

    plan = workflow._parse_plan(response, email_data)

    assert len(plan) == 2
    assert plan[0]["tool"] == "parse"
    assert plan[1]["tool"] == "summarise"


@pytest.mark.asyncio
async def test_plan_parsing_with_noise():
    """Test parsing plan when LLM includes extra text."""
    from basic.models import EmailData

    workflow = EmailWorkflow(timeout=60)

    email_data = EmailData(
        from_email="test@example.com", subject="Test", text="Test content"
    )

    # Test response with extra text
    response = """Here is the plan:
    [
        {
            "tool": "summarise",
            "params": {"text": "content"},
            "description": "Summarize"
        }
    ]
    This should work well."""

    plan = workflow._parse_plan(response, email_data)

    assert len(plan) == 1
    assert plan[0]["tool"] == "summarise"


@pytest.mark.asyncio
async def test_plan_execution():
    """Test execution of a simple plan."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test",
        text="Test content",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    # Create a workflow with mocked tools
    workflow = EmailWorkflow(timeout=60)

    # Mock the summarise tool
    mock_summarise_tool = MagicMock()
    mock_summarise_tool.execute = AsyncMock(
        return_value={"success": True, "summary": "This is a summary"}
    )
    workflow.tool_registry.tools["summarise"] = mock_summarise_tool

    # Create a simple plan
    from basic.email_workflow import TriageEvent

    plan = [
        {
            "tool": "summarise",
            "params": {"text": "Test content"},
            "description": "Summarize the content",
        }
    ]

    triage_event = TriageEvent(plan=plan, email_data=email_data, callback=callback)

    # Execute the plan
    result = await workflow.execute_plan(triage_event, MagicMock())

    assert result.results is not None
    assert len(result.results) == 1
    assert result.results[0]["success"] is True
    assert "summary" in result.results[0]


@pytest.mark.asyncio
async def test_parameter_resolution():
    """Test resolution of parameters from execution context."""
    workflow = EmailWorkflow(timeout=60)

    email_data = EmailData(from_email="user@example.com", subject="Test", text="Test")

    # Test simple parameter
    params = {"text": "hello"}
    resolved = workflow._resolve_params(params, {}, email_data)
    assert resolved["text"] == "hello"

    # Test template parameter
    context = {"step_1": {"parsed_text": "This is parsed content"}}
    params = {"text": "{{step_1.parsed_text}}"}
    resolved = workflow._resolve_params(params, context, email_data)
    assert resolved["text"] == "This is parsed content"


@pytest.mark.asyncio
async def test_result_formatting():
    """Test formatting of execution results."""
    workflow = EmailWorkflow(timeout=60)

    email_data = EmailData(
        from_email="user@example.com", subject="Test Subject", text="Test"
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
            "success": True,
            "translated_text": "C'est le résumé",
        },
    ]

    formatted = workflow._create_execution_log(results, email_data)

    assert "Test Subject" in formatted
    assert "summarise" in formatted
    assert "translate" in formatted
    assert "This is the summary" in formatted
    assert "C'est le résumé" in formatted
    assert "Success" in formatted or "✓" in formatted


@pytest.mark.asyncio
async def test_end_to_end_workflow():
    """Test the complete workflow from start to finish."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Summarize this email",
        text="This is a long email that needs summarization.",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    # Mock LLM for triage
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.__str__ = (
        lambda x: """[
        {
            "tool": "summarise",
            "params": {"text": "This is a long email that needs summarization."},
            "description": "Summarize email"
        }
    ]"""
    )
    mock_llm.acomplete = AsyncMock(return_value=mock_response)

    # Mock httpx for callback
    mock_http_response = MagicMock()
    mock_http_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_http_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=None)

    workflow = EmailWorkflow(timeout=60)
    workflow.llm = mock_llm

    # Mock the summarise tool
    mock_summarise_tool = MagicMock()
    mock_summarise_tool.execute = AsyncMock(
        return_value={"success": True, "summary": "Brief summary of the email"}
    )
    workflow.tool_registry.tools["summarise"] = mock_summarise_tool

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        # Run the workflow
        result = await workflow.run(email_data=email_data, callback=callback)

        # Verify callback was called
        assert mock_http_client.post.called

        # Verify result
        assert result.success is True
        assert "1 steps" in result.message or "steps" in result.message.lower()


@pytest.mark.asyncio
async def test_workflow_with_unknown_tool():
    """Test that workflow handles unknown tools gracefully."""
    email_data = EmailData(
        from_email="user@example.com", subject="Test", text="Test content"
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    workflow = EmailWorkflow(timeout=60)

    # Create a plan with an unknown tool
    from basic.email_workflow import TriageEvent

    plan = [
        {
            "tool": "unknown_tool",
            "params": {},
            "description": "This tool doesn't exist",
        }
    ]

    triage_event = TriageEvent(plan=plan, email_data=email_data, callback=callback)

    # Execute the plan
    result = await workflow.execute_plan(triage_event, MagicMock())

    # Should have a result indicating failure
    assert len(result.results) == 1
    assert result.results[0]["success"] is False
    assert "not found" in result.results[0]["error"]


@pytest.mark.asyncio
async def test_critical_step_stops_execution():
    """Test that critical step failure stops subsequent steps."""
    email_data = EmailData(
        from_email="user@example.com", subject="Test", text="Test content"
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    workflow = EmailWorkflow(timeout=60)

    from basic.email_workflow import TriageEvent

    # Create a plan where step 1 is critical and will fail
    plan = [
        {
            "tool": "unknown_tool",
            "params": {},
            "description": "Critical step that will fail",
            "critical": True,  # Mark as critical
        },
        {
            "tool": "summarise",
            "params": {"text": "This should not execute"},
            "description": "This step should be skipped",
        },
    ]

    triage_event = TriageEvent(plan=plan, email_data=email_data, callback=callback)

    # Execute the plan
    result = await workflow.execute_plan(triage_event, MagicMock())

    # Should only have result for first step (critical step stopped execution)
    assert len(result.results) == 1
    assert result.results[0]["success"] is False
    assert "not found" in result.results[0]["error"]


@pytest.mark.asyncio
async def test_dependency_checking_skips_dependent_steps():
    """Test that steps depending on failed steps are skipped."""
    email_data = EmailData(
        from_email="user@example.com", subject="Test", text="Test content"
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    workflow = EmailWorkflow(timeout=60)

    from basic.email_workflow import TriageEvent

    # Create a plan where step 2 depends on step 1, but step 1 will fail
    plan = [
        {
            "tool": "unknown_tool",
            "params": {},
            "description": "This step will fail",
        },
        {
            "tool": "summarise",
            "params": {"text": "{{step_1.parsed_text}}"},  # Depends on step 1
            "description": "This step depends on step 1",
        },
    ]

    triage_event = TriageEvent(plan=plan, email_data=email_data, callback=callback)

    # Execute the plan
    result = await workflow.execute_plan(triage_event, MagicMock())

    # Should have two results
    assert len(result.results) == 2
    # First step failed
    assert result.results[0]["success"] is False
    # Second step should be skipped due to dependency failure
    assert result.results[1]["success"] is False
    assert "Dependent step(s) failed" in result.results[1]["error"]
    assert result.results[1].get("skipped") is True

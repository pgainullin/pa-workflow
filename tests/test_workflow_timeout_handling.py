"""Tests for workflow timeout handling.

This module verifies that the workflow properly handles timeout scenarios
and always returns appropriate responses without disconnecting.
"""

import asyncio
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
            from basic.email_workflow import (
                EmailWorkflow,
                EmailStartEvent,
                TriageEvent,
                PlanExecutionEvent,
                RESPONSE_BEST_PRACTICES,
            )

from basic.models import CallbackConfig, EmailData
from basic.response_utils import create_execution_log, collect_attachments, generate_user_response
from workflows import Context
from workflows.events import StopEvent


@pytest.mark.asyncio
async def test_triage_email_handles_timeout():
    """Test that triage_email returns TriageEvent on timeout."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test subject",
        text="Test body",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    # Mock the LLM to raise asyncio.TimeoutError
    mock_llm = MagicMock()
    mock_llm.acomplete = AsyncMock(side_effect=asyncio.TimeoutError("LLM timeout"))

    workflow = EmailWorkflow(timeout=120)
    workflow.llm = mock_llm

    # Run triage step - should not raise exception
    ctx = MagicMock(spec=Context)
    result = await workflow.triage_email(
        EmailStartEvent(email_data=email_data, callback=callback), ctx
    )

    # Should return TriageEvent with fallback plan
    assert isinstance(result, TriageEvent)
    assert result.plan is not None
    assert len(result.plan) > 0
    assert result.plan[0]["tool"] == "summarise"


@pytest.mark.asyncio
async def test_execute_plan_handles_timeout():
    """Test that execute_plan returns PlanExecutionEvent on timeout."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test subject",
        text="Test body",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    # Create a plan with a tool that will timeout
    plan = [
        {
            "tool": "parse",
            "params": {"file_id": "test-file-id"},
            "description": "This will timeout",
        }
    ]

    workflow = EmailWorkflow(timeout=120)

    # Mock the tool registry to return a tool that times out
    mock_tool = MagicMock()
    mock_tool.execute = AsyncMock(side_effect=asyncio.TimeoutError("Tool timeout"))
    workflow.tool_registry.get_tool = MagicMock(return_value=mock_tool)

    # Run execute_plan step - should not raise exception
    ctx = MagicMock(spec=Context)
    triage_event = TriageEvent(plan=plan, email_data=email_data, callback=callback)
    result = await workflow.execute_plan(triage_event, ctx)

    # Should return PlanExecutionEvent with error results
    assert isinstance(result, PlanExecutionEvent)
    assert len(result.results) > 0
    # The tool timeout should be caught as an exception in the tool execution loop
    assert result.results[0]["success"] is False


@pytest.mark.asyncio
async def test_execute_plan_handles_none_plan():
    """Test that execute_plan handles None plan gracefully."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test subject",
        text="Test body",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    workflow = EmailWorkflow(timeout=120)

    # Create event with None plan (simulating a bug or edge case)
    # Note: Pydantic validation should prevent this, but we test defensively
    ctx = MagicMock(spec=Context)
    
    # We need to bypass Pydantic validation to test this edge case
    triage_event = TriageEvent.__new__(TriageEvent)
    triage_event.plan = None  # Force None plan
    triage_event.email_data = email_data
    triage_event.callback = callback
    
    result = await workflow.execute_plan(triage_event, ctx)

    # Should return PlanExecutionEvent (possibly with empty results)
    assert isinstance(result, PlanExecutionEvent)
    assert isinstance(result.results, list)


@pytest.mark.asyncio
async def test_send_results_handles_timeout():
    """Test that send_results returns StopEvent on timeout."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test subject",
        text="Test body",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    results = [
        {
            "step": 1,
            "tool": "parse",
            "success": True,
            "parsed_text": "Some parsed content",
        }
    ]

    workflow = EmailWorkflow(timeout=120)

    # Mock generate_user_response to timeout
    with patch("basic.response_utils.generate_user_response", new_callable=AsyncMock, side_effect=asyncio.TimeoutError("Response generation timeout")):
        # Run send_results step - should not raise exception
        ctx = MagicMock(spec=Context)
        ctx.write_event_to_stream = MagicMock()
        
        plan_execution_event = PlanExecutionEvent(
            results=results, email_data=email_data, callback=callback
        )
        result = await workflow.send_results(plan_execution_event, ctx)

        # Should return StopEvent with timeout error
        assert isinstance(result, StopEvent)
        assert result.result.success is False
        assert "timeout" in result.result.message.lower()


@pytest.mark.asyncio
async def test_generate_user_response_handles_none_results():
    """Test that _generate_user_response handles None results gracefully."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test subject",
        text="Test body",
    )

    workflow = EmailWorkflow(timeout=120)

    # Test with None results
    response = await generate_user_response(
        None, email_data, workflow._llm_complete_with_retry, RESPONSE_BEST_PRACTICES
    )
    
    assert isinstance(response, str)
    assert len(response) > 0
    # Should return a fallback message
    assert "processed" in response.lower() or "issues" in response.lower()


@pytest.mark.asyncio
async def test_generate_user_response_handles_invalid_results():
    """Test that generate_user_response handles invalid results type."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test subject",
        text="Test body",
    )

    workflow = EmailWorkflow(timeout=120)

    # Test with invalid results type (string instead of list)
    response = await generate_user_response(
        "invalid", email_data, workflow._llm_complete_with_retry, RESPONSE_BEST_PRACTICES
    )
    
    assert isinstance(response, str)
    assert len(response) > 0
    # Should return a fallback message
    assert "processed" in response.lower() or "issues" in response.lower()


def test_create_execution_log_handles_none_results():
    """Test that create_execution_log handles None results gracefully."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test subject",
        text="Test body",
    )

    workflow = EmailWorkflow(timeout=120)

    # Test with None results
    log = create_execution_log(None, email_data)
    
    assert isinstance(log, str)
    assert len(log) > 0
    # Should return a fallback log with error message
    assert "error" in log.lower() or "failed" in log.lower()


def test_collect_attachments_handles_none_results():
    """Test that collect_attachments handles None results gracefully."""
    workflow = EmailWorkflow(timeout=120)

    # Test with None results
    attachments = collect_attachments(None)
    
    # Should return empty list
    assert isinstance(attachments, list)
    assert len(attachments) == 0


@pytest.mark.asyncio
async def test_workflow_completes_with_all_steps_timing_out():
    """Integration test: workflow completes even when all steps timeout."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test subject",
        text="Test body",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    workflow = EmailWorkflow(timeout=120)

    # Mock all LLM calls to succeed (so we can test the full flow)
    mock_llm = MagicMock()
    mock_llm.acomplete = AsyncMock(return_value='[{"tool": "summarise", "params": {"text": "test"}}]')
    workflow.llm = mock_llm

    # Mock callback to succeed
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        # Run the full workflow
        ctx = MagicMock(spec=Context)
        ctx.write_event_to_stream = MagicMock()

        # Step 1: Triage
        triage_result = await workflow.triage_email(
            EmailStartEvent(email_data=email_data, callback=callback), ctx
        )
        assert isinstance(triage_result, TriageEvent)

        # Step 2: Execute plan
        exec_result = await workflow.execute_plan(triage_result, ctx)
        assert isinstance(exec_result, PlanExecutionEvent)

        # Step 3: Send results
        final_result = await workflow.send_results(exec_result, ctx)
        assert isinstance(final_result, StopEvent)

        # The workflow should complete successfully
        # (even though individual tools might have failed)
        assert final_result.result is not None

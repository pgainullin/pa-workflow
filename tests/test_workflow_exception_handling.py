"""Tests for workflow exception handling to prevent server disconnects.

This module verifies that the workflow always returns proper event types
even when fatal errors occur, preventing the server from disconnecting
without sending a response.
"""

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
            )

from basic.models import CallbackConfig, EmailData
from workflows import Context
from workflows.events import StopEvent


@pytest.mark.asyncio
async def test_triage_email_handles_fatal_errors():
    """Test that triage_email returns TriageEvent even on fatal errors."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test subject",
        text="Test body",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    # Mock the LLM to raise an exception
    mock_llm = MagicMock()
    mock_llm.acomplete = AsyncMock(side_effect=Exception("Fatal LLM error"))

    workflow = EmailWorkflow(timeout=60)
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
async def test_execute_plan_handles_fatal_errors():
    """Test that execute_plan returns PlanExecutionEvent even on fatal errors."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test subject",
        text="Test body",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    # Create a plan that will cause an error
    plan = [
        {
            "tool": "nonexistent_tool",
            "params": {},
            "description": "This should fail gracefully",
        }
    ]

    workflow = EmailWorkflow(timeout=60)

    # Run execute_plan step - should not raise exception
    ctx = MagicMock(spec=Context)
    triage_event = TriageEvent(plan=plan, email_data=email_data, callback=callback)
    result = await workflow.execute_plan(triage_event, ctx)

    # Should return PlanExecutionEvent with error results
    assert isinstance(result, PlanExecutionEvent)
    assert len(result.results) > 0
    assert result.results[0]["success"] is False


@pytest.mark.asyncio
async def test_execute_plan_handles_malformed_plan():
    """Test that execute_plan handles malformed plans gracefully."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test subject",
        text="Test body",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    # Create a completely malformed plan (not a list)
    plan = None  # This should cause an error

    workflow = EmailWorkflow(timeout=60)

    # Run execute_plan step - should not raise exception
    ctx = MagicMock(spec=Context)
    triage_event = TriageEvent(plan=plan, email_data=email_data, callback=callback)
    
    # This should handle the error and return PlanExecutionEvent
    result = await workflow.execute_plan(triage_event, ctx)
    
    # Should return PlanExecutionEvent with error information
    assert isinstance(result, PlanExecutionEvent)
    assert len(result.results) > 0
    assert result.results[0]["success"] is False
    assert "Fatal error" in result.results[0]["error"]


@pytest.mark.asyncio
async def test_send_results_handles_fatal_errors():
    """Test that send_results returns StopEvent even on fatal errors."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test subject",
        text="Test body",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    # Create results that might cause errors during processing
    results = [
        {
            "step": 1,
            "tool": "test_tool",
            "success": True,
            "output": "Test output",
        }
    ]

    workflow = EmailWorkflow(timeout=60)
    
    # Mock _generate_user_response to raise an exception
    workflow._generate_user_response = AsyncMock(side_effect=Exception("Fatal response generation error"))

    # Run send_results step - should not raise exception
    ctx = MagicMock(spec=Context)
    ctx.write_event_to_stream = MagicMock()
    
    plan_event = PlanExecutionEvent(
        results=results, email_data=email_data, callback=callback
    )
    
    result = await workflow.send_results(plan_event, ctx)

    # Should return StopEvent with error information
    assert isinstance(result, StopEvent)
    assert hasattr(result, "result")
    assert result.result.success is False
    assert "Fatal error" in result.result.message


@pytest.mark.asyncio
async def test_send_results_handles_callback_errors():
    """Test that send_results handles callback errors gracefully."""
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
            "tool": "test_tool",
            "success": True,
            "output": "Test output",
        }
    ]

    workflow = EmailWorkflow(timeout=60)
    
    # Mock methods to work normally until callback
    workflow._generate_user_response = AsyncMock(return_value="Test response")
    workflow._create_execution_log = MagicMock(return_value="Test log")
    workflow._collect_attachments = MagicMock(return_value=[])
    
    # Mock _send_callback_email to raise an httpx error
    import httpx
    workflow._send_callback_email = AsyncMock(
        side_effect=httpx.HTTPError("Connection failed")
    )

    # Run send_results step - should not raise exception
    ctx = MagicMock(spec=Context)
    ctx.write_event_to_stream = MagicMock()
    
    plan_event = PlanExecutionEvent(
        results=results, email_data=email_data, callback=callback
    )
    
    result = await workflow.send_results(plan_event, ctx)

    # Should return StopEvent with error information about callback failure
    assert isinstance(result, StopEvent)
    assert hasattr(result, "result")
    assert result.result.success is False
    assert "callback failed" in result.result.message.lower()


@pytest.mark.asyncio
async def test_workflow_never_raises_unhandled_exceptions():
    """Integration test: verify workflow always completes with a result."""
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test subject",
        text="Test body",
    )

    callback = CallbackConfig(
        callback_url="http://test.local/callback", auth_token="test-token"
    )

    # Mock everything to potentially fail
    mock_llm = MagicMock()
    mock_llm.acomplete = AsyncMock(side_effect=Exception("LLM failed"))

    workflow = EmailWorkflow(timeout=60)
    workflow.llm = mock_llm

    # Run the workflow steps in sequence
    ctx = MagicMock(spec=Context)
    ctx.write_event_to_stream = MagicMock()
    
    # Step 1: Triage (will fail but return fallback)
    triage_result = await workflow.triage_email(
        EmailStartEvent(email_data=email_data, callback=callback), ctx
    )
    assert isinstance(triage_result, TriageEvent)
    
    # Step 2: Execute plan
    execute_result = await workflow.execute_plan(triage_result, ctx)
    assert isinstance(execute_result, PlanExecutionEvent)
    
    # Step 3: Send results (mock callback to avoid network issues)
    workflow._send_callback_email = AsyncMock()
    send_result = await workflow.send_results(execute_result, ctx)
    assert isinstance(send_result, StopEvent)
    
    # Workflow completed without raising exceptions
    assert send_result.result is not None

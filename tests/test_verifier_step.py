"""Tests for response verification step.

This module tests the new verify_response step that checks and improves
the final response based on best practices.
"""

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from basic.email_workflow import (
    EmailWorkflow,
    PlanExecutionEvent,
    VerificationEvent,
    RESPONSE_BEST_PRACTICES,
)
from basic.models import CallbackConfig, EmailData


def get_workflow_file_path():
    """Get the path to the email workflow file relative to this test file."""
    test_dir = Path(__file__).parent
    project_root = test_dir.parent
    return project_root / "src" / "basic" / "email_workflow.py"


def test_verification_event_exists():
    """Test that VerificationEvent class is defined in the workflow."""
    # Read the source file
    workflow_file = get_workflow_file_path()
    with open(workflow_file, "r") as f:
        source = f.read()

    # Parse the AST
    tree = ast.parse(source)

    # Find all class definitions
    class_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_names.add(node.name)

    assert "VerificationEvent" in class_names, (
        "VerificationEvent class not found in workflow file"
    )


def test_verify_response_step_exists():
    """Test that verify_response step method exists in EmailWorkflow."""
    # Read the source file
    workflow_file = get_workflow_file_path()
    with open(workflow_file, "r") as f:
        source = f.read()

    # Parse the AST
    tree = ast.parse(source)

    # Find the EmailWorkflow class
    email_workflow_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "EmailWorkflow":
            email_workflow_class = node
            break

    assert email_workflow_class is not None, "EmailWorkflow class not found"

    # Find the verify_response method
    verify_response_method = None
    for item in email_workflow_class.body:
        if isinstance(item, ast.AsyncFunctionDef) and item.name == "verify_response":
            verify_response_method = item
            break

    assert verify_response_method is not None, "verify_response method not found"


def test_verify_response_returns_verification_event():
    """Test that verify_response step declares VerificationEvent in its return type."""
    # Read the source file
    workflow_file = get_workflow_file_path()
    with open(workflow_file, "r") as f:
        source = f.read()

    # Parse the AST
    tree = ast.parse(source)

    # Find the EmailWorkflow class
    email_workflow_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "EmailWorkflow":
            email_workflow_class = node
            break

    assert email_workflow_class is not None, "EmailWorkflow class not found"

    # Find the verify_response method
    verify_response_method = None
    for item in email_workflow_class.body:
        if isinstance(item, ast.AsyncFunctionDef) and item.name == "verify_response":
            verify_response_method = item
            break

    assert verify_response_method is not None, "verify_response method not found"

    # Get the return annotation as a string
    if verify_response_method.returns:
        return_annotation = ast.unparse(verify_response_method.returns)

        # Check that VerificationEvent is in the return type
        assert "VerificationEvent" in return_annotation, (
            f"VerificationEvent must be in verify_response return type. "
            f"Found: {return_annotation}"
        )
    else:
        pytest.fail("verify_response method has no return type annotation")


def test_send_results_accepts_verification_event():
    """Test that send_results step now accepts VerificationEvent instead of PlanExecutionEvent."""
    # Read the source file
    workflow_file = get_workflow_file_path()
    with open(workflow_file, "r") as f:
        source = f.read()

    # Parse the AST
    tree = ast.parse(source)

    # Find the EmailWorkflow class
    email_workflow_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "EmailWorkflow":
            email_workflow_class = node
            break

    assert email_workflow_class is not None, "EmailWorkflow class not found"

    # Find the send_results method
    send_results_method = None
    for item in email_workflow_class.body:
        if isinstance(item, ast.AsyncFunctionDef) and item.name == "send_results":
            send_results_method = item
            break

    assert send_results_method is not None, "send_results method not found"

    # Check the first parameter (after self) is VerificationEvent
    # Parameters: self, ev: VerificationEvent, ctx: Context
    if len(send_results_method.args.args) >= 2:
        ev_param = send_results_method.args.args[1]  # Second parameter (after self)
        if ev_param.annotation:
            param_annotation = ast.unparse(ev_param.annotation)
            assert "VerificationEvent" in param_annotation, (
                f"send_results should accept VerificationEvent as input event. "
                f"Found: {param_annotation}"
            )
        else:
            pytest.fail("send_results 'ev' parameter has no type annotation")
    else:
        pytest.fail("send_results method doesn't have enough parameters")


def test_best_practices_constant_exists():
    """Test that RESPONSE_BEST_PRACTICES constant is defined."""
    # Read the source file
    workflow_file = get_workflow_file_path()
    with open(workflow_file, "r") as f:
        source = f.read()

    assert "RESPONSE_BEST_PRACTICES" in source, (
        "RESPONSE_BEST_PRACTICES constant not found in workflow file"
    )


@pytest.mark.asyncio
async def test_verify_response_step_execution():
    """Test that verify_response step can execute successfully with mocked LLM."""
    # Create mock email data
    email_data = EmailData(
        from_email="user@example.com",
        to_email="assistant@example.com",
        subject="Test Email",
        text="Please process this document",
    )

    callback = CallbackConfig(
        callback_url="https://example.com/callback",
        auth_token="test-token",
    )

    results = [
        {
            "step": 1,
            "tool": "summarise",
            "success": True,
            "summary": "Document has been summarized successfully.",
        }
    ]

    # Create the event
    plan_execution_event = PlanExecutionEvent(
        results=results,
        email_data=email_data,
        callback=callback,
    )

    # Create workflow instance with mocked LLM
    workflow = EmailWorkflow(timeout=60)

    # Mock the LLM completion
    mock_response = "I've successfully summarized your document. The key points are included above."
    
    with patch.object(
        workflow, "_llm_complete_with_retry", new_callable=AsyncMock
    ) as mock_llm:
        mock_llm.return_value = mock_response

        # Create a mock context
        mock_context = MagicMock()

        # Execute the verify_response step
        result = await workflow.verify_response(plan_execution_event, mock_context)

        # Verify the result
        assert isinstance(result, VerificationEvent)
        assert result.verified_response == mock_response
        assert result.results == results
        assert result.email_data == email_data
        assert result.callback == callback

        # Verify LLM was called with appropriate prompt
        assert mock_llm.called
        call_args = mock_llm.call_args[0][0]
        assert "best practices" in call_args.lower()
        assert RESPONSE_BEST_PRACTICES in call_args  # Check constant is used in the prompt


@pytest.mark.asyncio
async def test_verify_response_handles_empty_llm_response():
    """Test that verify_response falls back to original response if LLM returns empty."""
    # Create mock email data
    email_data = EmailData(
        from_email="user@example.com",
        to_email="assistant@example.com",
        subject="Test Email",
        text="Please process this document",
    )

    callback = CallbackConfig(
        callback_url="https://example.com/callback",
        auth_token="test-token",
    )

    results = [
        {
            "step": 1,
            "tool": "summarise",
            "success": True,
            "summary": "Document has been summarized successfully.",
        }
    ]

    # Create the event
    plan_execution_event = PlanExecutionEvent(
        results=results,
        email_data=email_data,
        callback=callback,
    )

    # Create workflow instance
    workflow = EmailWorkflow(timeout=60)

    # Mock the LLM completion to return empty string
    with patch.object(
        workflow, "_llm_complete_with_retry", new_callable=AsyncMock
    ) as mock_llm:
        mock_llm.return_value = ""  # Empty response

        # Mock _generate_user_response to return a fallback
        with patch.object(
            workflow, "_generate_user_response", new_callable=AsyncMock
        ) as mock_generate:
            mock_generate.return_value = "Original response text"

            # Create a mock context
            mock_context = MagicMock()

            # Execute the verify_response step
            result = await workflow.verify_response(plan_execution_event, mock_context)

            # Verify that it fell back to original response
            assert isinstance(result, VerificationEvent)
            assert result.verified_response == "Original response text"


@pytest.mark.asyncio
async def test_verify_response_handles_llm_exception():
    """Test that verify_response handles LLM exceptions gracefully."""
    # Create mock email data
    email_data = EmailData(
        from_email="user@example.com",
        to_email="assistant@example.com",
        subject="Test Email",
        text="Please process this document",
    )

    callback = CallbackConfig(
        callback_url="https://example.com/callback",
        auth_token="test-token",
    )

    results = [
        {
            "step": 1,
            "tool": "summarise",
            "success": True,
            "summary": "Document has been summarized successfully.",
        }
    ]

    # Create the event
    plan_execution_event = PlanExecutionEvent(
        results=results,
        email_data=email_data,
        callback=callback,
    )

    # Create workflow instance
    workflow = EmailWorkflow(timeout=60)

    # Mock the LLM completion to raise an exception
    with patch.object(
        workflow, "_llm_complete_with_retry", new_callable=AsyncMock
    ) as mock_llm:
        mock_llm.side_effect = Exception("LLM API error")

        # Mock _generate_user_response to return a fallback
        with patch.object(
            workflow, "_generate_user_response", new_callable=AsyncMock
        ) as mock_generate:
            mock_generate.return_value = "Original response text"

            # Create a mock context
            mock_context = MagicMock()

            # Execute the verify_response step
            result = await workflow.verify_response(plan_execution_event, mock_context)

            # Verify that it fell back to original response
            assert isinstance(result, VerificationEvent)
            assert result.verified_response == "Original response text"


@pytest.mark.asyncio
async def test_verify_response_handles_timeout_error():
    """Test that verify_response handles asyncio.TimeoutError gracefully."""
    import asyncio
    
    # Create mock email data
    email_data = EmailData(
        from_email="user@example.com",
        to_email="assistant@example.com",
        subject="Test Email",
        text="Please process this document",
    )

    callback = CallbackConfig(
        callback_url="https://example.com/callback",
        auth_token="test-token",
    )

    results = [
        {
            "step": 1,
            "tool": "summarise",
            "success": True,
            "summary": "Document has been summarized successfully.",
        }
    ]

    # Create the event
    plan_execution_event = PlanExecutionEvent(
        results=results,
        email_data=email_data,
        callback=callback,
    )

    # Create workflow instance
    workflow = EmailWorkflow(timeout=60)

    # Mock _generate_user_response to succeed initially, then be called again in timeout handler
    with patch.object(
        workflow, "_generate_user_response", new_callable=AsyncMock
    ) as mock_generate:
        # First call succeeds for initial response
        # Second call in timeout handler should also succeed
        mock_generate.return_value = "Fallback response after timeout"

        # Mock the LLM completion to raise TimeoutError
        with patch.object(
            workflow, "_llm_complete_with_retry", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.side_effect = asyncio.TimeoutError("LLM timeout")

            # Create a mock context
            mock_context = MagicMock()

            # Execute the verify_response step
            result = await workflow.verify_response(plan_execution_event, mock_context)

            # Verify that it handled timeout and returned fallback
            assert isinstance(result, VerificationEvent)
            assert result.verified_response == "Fallback response after timeout"
            # _generate_user_response should be called twice: once for initial, once in timeout handler
            assert mock_generate.call_count == 2

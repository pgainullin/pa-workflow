"""Tests for email workflow validation.

This module tests that the email workflow type signatures are correctly defined,
ensuring all events are properly declared in step return types.
"""

import ast
from pathlib import Path

import pytest


def get_workflow_file_path():
    """Get the path to the email workflow file relative to this test file."""
    test_dir = Path(__file__).parent
    project_root = test_dir.parent
    return project_root / "src" / "basic" / "email_workflow.py"


def test_triage_email_step_returns_triage_event():
    """Test that triage_email step declares TriageEvent in its return type.

    The triage_email step is the first step in the refactored workflow and must
    return a TriageEvent containing the execution plan.
    """
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

    # Find the triage_email method
    triage_email_method = None
    for item in email_workflow_class.body:
        if isinstance(item, ast.AsyncFunctionDef) and item.name == "triage_email":
            triage_email_method = item
            break

    assert triage_email_method is not None, "triage_email method not found"

    # Get the return annotation as a string
    if triage_email_method.returns:
        return_annotation = ast.unparse(triage_email_method.returns)

        # Check that TriageEvent is in the return type
        assert "TriageEvent" in return_annotation, (
            f"TriageEvent must be in triage_email return type. "
            f"Found: {return_annotation}"
        )
    else:
        pytest.fail("triage_email method has no return type annotation")


def test_workflow_events_structure():
    """Test that workflow events are properly structured using AST parsing."""
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

    # Check that all required event classes are defined for the refactored workflow
    required_events = [
        "EmailStartEvent",
        "TriageEvent",
        "PlanExecutionEvent",
        "VerificationEvent",
        "EmailProcessedEvent",
    ]

    for event_name in required_events:
        assert event_name in class_names, (
            f"{event_name} class not found in workflow file"
        )

"""Tests for email workflow validation.

This module tests that the email workflow type signatures are correctly defined,
ensuring all events are properly declared in step return types.
"""

import ast
import inspect


def test_process_email_step_includes_attachment_found_event_in_return_type():
    """Test that process_email step declares AttachmentFoundEvent in its return type.
    
    This is critical because the step uses ctx.send_event(AttachmentFoundEvent(...))
    to fan out events. According to workflow validation rules, when a step sends
    an event using ctx.send_event(), it must still declare that event type in its
    return type annotation for proper workflow validation.
    
    The error "The following events are consumed but never produced: AttachmentFoundEvent"
    occurs when this return type is missing.
    """
    # Read the source file
    with open('src/basic/email_workflow.py', 'r') as f:
        source = f.read()
    
    # Parse the AST
    tree = ast.parse(source)
    
    # Find the EmailWorkflow class
    email_workflow_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'EmailWorkflow':
            email_workflow_class = node
            break
    
    assert email_workflow_class is not None, "EmailWorkflow class not found"
    
    # Find the process_email method
    process_email_method = None
    for item in email_workflow_class.body:
        if isinstance(item, ast.AsyncFunctionDef) and item.name == 'process_email':
            process_email_method = item
            break
    
    assert process_email_method is not None, "process_email method not found"
    
    # Get the return annotation as a string
    if process_email_method.returns:
        return_annotation = ast.unparse(process_email_method.returns)
        
        # Check that AttachmentFoundEvent is in the return type
        assert 'AttachmentFoundEvent' in return_annotation, (
            f"AttachmentFoundEvent must be in process_email return type. "
            f"Found: {return_annotation}"
        )
        
        # Also verify StopEvent and None are present (the other possible returns)
        assert 'StopEvent' in return_annotation, (
            f"StopEvent must be in process_email return type. "
            f"Found: {return_annotation}"
        )
        assert 'None' in return_annotation, (
            f"None must be in process_email return type. "
            f"Found: {return_annotation}"
        )
    else:
        pytest.fail("process_email method has no return type annotation")


def test_workflow_events_structure():
    """Test that workflow events are properly structured."""
    # Read the source file
    with open('src/basic/email_workflow.py', 'r') as f:
        source = f.read()
    
    # Check that all required event classes are defined
    assert 'class AttachmentFoundEvent(Event):' in source
    assert 'class AttachmentSummaryEvent(Event):' in source
    assert 'class EmailReceivedEvent(Event):' in source
    assert 'class EmailProcessedEvent(Event):' in source

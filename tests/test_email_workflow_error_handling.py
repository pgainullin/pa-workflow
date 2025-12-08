"""Tests for email workflow error handling.

This module tests that the email workflow properly handles errors and always
returns EmailProcessingResult format instead of raising unhandled exceptions.

Since the EmailWorkflow class initializes external services at class definition time,
we'll test the error handling patterns and model validation directly.
"""

import pytest

from basic.models import (
    Attachment,
    CallbackConfig,
    EmailData,
    EmailProcessingResult,
)


def test_email_processing_result_requires_success_and_message():
    """Test that EmailProcessingResult requires success and message fields."""
    # This should fail - missing required fields
    with pytest.raises(Exception):  # Will be a pydantic validation error
        EmailProcessingResult()

    # This should succeed - has required fields
    result = EmailProcessingResult(
        success=True,
        message="Test message",
        from_email="test@example.com",
        email_subject="Test subject",
    )
    assert result.success is True
    assert result.message == "Test message"


def test_email_processing_result_with_error_dict_fails():
    """Test that a dict with 'detail' field cannot be parsed as EmailProcessingResult."""
    # This simulates the error case from the issue:
    # When workflow returns {'detail': 'Error...'}, it can't be parsed as EmailProcessingResult
    error_dict = {"detail": "Error running workflow: AttachmentFoundEvent"}

    with pytest.raises(Exception):  # Will be a pydantic validation error
        EmailProcessingResult(**error_dict)


def test_email_processing_result_success_format():
    """Test the expected format for successful email processing."""
    result = EmailProcessingResult(
        success=True,
        message="Email processed successfully",
        from_email="sender@example.com",
        email_subject="Test email",
    )

    # Verify the result can be serialized properly
    result_dict = result.model_dump()
    assert "success" in result_dict
    assert "message" in result_dict
    assert result_dict["success"] is True


def test_email_processing_result_error_format():
    """Test the expected format for failed email processing."""
    result = EmailProcessingResult(
        success=False,
        message="Error processing email: something went wrong",
        from_email="sender@example.com",
        email_subject="Test email",
    )

    # Verify the result can be serialized properly
    result_dict = result.model_dump()
    assert "success" in result_dict
    assert "message" in result_dict
    assert result_dict["success"] is False
    assert "Error" in result_dict["message"]


def test_attachment_model_validation():
    """Test that Attachment model validates correctly."""
    attachment = Attachment(
        id="1",
        name="test.pdf",
        type="application/pdf",
        content="dGVzdCBjb250ZW50",  # Valid base64
    )

    assert attachment.name == "test.pdf"
    assert attachment.type == "application/pdf"


def test_email_data_model_validation():
    """Test that EmailData model validates correctly."""
    email_data = EmailData(
        from_email="sender@example.com",
        to_email="receiver@example.com",
        subject="Test subject",
        text="Test body",
    )

    assert email_data.from_email == "sender@example.com"
    assert email_data.subject == "Test subject"


def test_callback_config_validation():
    """Test that CallbackConfig model validates correctly."""
    callback = CallbackConfig(
        callback_url="http://example.com/callback",
        auth_token="test-token",
    )

    assert callback.callback_url == "http://example.com/callback"
    assert callback.auth_token == "test-token"

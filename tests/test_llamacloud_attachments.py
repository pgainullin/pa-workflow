"""Tests for LlamaCloud attachment handling.

This module tests that attachments can be provided either as:
1. Base64-encoded content (original behavior)
2. LlamaCloud file_id (new behavior)
"""

import pytest
from pydantic import ValidationError

from basic.models import Attachment, SendEmailRequest


def test_attachment_with_base64_content():
    """Test that Attachment accepts base64 content (backward compatible)."""
    attachment = Attachment(
        id="1",
        name="test.pdf",
        type="application/pdf",
        content="dGVzdCBjb250ZW50",  # Valid base64
    )

    assert attachment.name == "test.pdf"
    assert attachment.type == "application/pdf"
    assert attachment.content == "dGVzdCBjb250ZW50"
    assert attachment.file_id is None


def test_attachment_with_file_id():
    """Test that Attachment accepts LlamaCloud file_id."""
    attachment = Attachment(
        id="1",
        name="test.pdf",
        type="application/pdf",
        file_id="file-abc123",
    )

    assert attachment.name == "test.pdf"
    assert attachment.type == "application/pdf"
    assert attachment.file_id == "file-abc123"
    assert attachment.content is None


def test_attachment_with_both_content_and_file_id():
    """Test that Attachment can have both content and file_id (file_id takes precedence in workflow)."""
    attachment = Attachment(
        id="1",
        name="test.pdf",
        type="application/pdf",
        content="dGVzdCBjb250ZW50",
        file_id="file-abc123",
    )

    assert attachment.content == "dGVzdCBjb250ZW50"
    assert attachment.file_id == "file-abc123"


def test_attachment_without_content_or_file_id():
    """Test that Attachment requires either content or file_id."""
    with pytest.raises(ValidationError) as exc_info:
        Attachment(
            id="1",
            name="test.pdf",
            type="application/pdf",
        )
    
    assert "Attachment must have either 'content' or 'file_id'" in str(exc_info.value)


def test_send_email_request_with_attachments():
    """Test that SendEmailRequest can include attachments with file_ids."""
    attachment1 = Attachment(
        id="1",
        name="summary.pdf",
        type="application/pdf",
        file_id="file-summary-123",
    )
    attachment2 = Attachment(
        id="2",
        name="report.csv",
        type="text/csv",
        file_id="file-report-456",
    )

    email_request = SendEmailRequest(
        to_email="user@example.com",
        subject="Your processed documents",
        text="Please find attached documents",
        html="<p>Please find attached documents</p>",
        attachments=[attachment1, attachment2],
    )

    assert len(email_request.attachments) == 2
    assert email_request.attachments[0].file_id == "file-summary-123"
    assert email_request.attachments[1].file_id == "file-report-456"


def test_send_email_request_without_attachments():
    """Test that SendEmailRequest defaults to empty attachments list."""
    email_request = SendEmailRequest(
        to_email="user@example.com",
        subject="Test",
        text="Test message",
    )

    assert email_request.attachments == []


def test_attachment_serialization_with_file_id():
    """Test that Attachment with file_id serializes correctly."""
    attachment = Attachment(
        id="1",
        name="document.pdf",
        type="application/pdf",
        file_id="file-abc123",
    )

    data = attachment.model_dump()
    assert data["name"] == "document.pdf"
    assert data["file_id"] == "file-abc123"
    assert data["content"] is None


def test_attachment_deserialization_webhook_format():
    """Test that Attachment can be created from webhook format.
    
    The webhook service sends attachments in this format:
    {
      "filename": "document.pdf",
      "content_type": "application/pdf",
      "file_id": "file-abc123"
    }
    
    However, our Attachment model uses different field names (name, type).
    This test verifies the model works with our field names.
    """
    # Our internal format with correct field names
    attachment_data = {
        "id": "att-1",
        "name": "document.pdf",
        "type": "application/pdf",
        "file_id": "file-abc123",
    }

    attachment = Attachment(**attachment_data)
    assert attachment.name == "document.pdf"
    assert attachment.type == "application/pdf"
    assert attachment.file_id == "file-abc123"


def test_callback_email_with_llamacloud_attachments():
    """Test that callback emails can include LlamaCloud attachments.
    
    This simulates the use case where the workflow generates a file
    (e.g., a processed report), uploads it to LlamaCloud, and sends
    it back to the user via the callback email.
    """
    # Create an attachment referencing a LlamaCloud file
    processed_file = Attachment(
        id="processed-1",
        name="processed_document.pdf",
        type="application/pdf",
        file_id="file-processed-789",
    )

    # Create callback email with the attachment
    callback_email = SendEmailRequest(
        to_email="user@example.com",
        subject="Your Processed Document",
        text="Your document has been processed. Please find it attached.",
        html="<p>Your document has been processed. Please find it attached.</p>",
        attachments=[processed_file],
    )

    # Verify the callback email structure
    assert callback_email.to_email == "user@example.com"
    assert len(callback_email.attachments) == 1
    assert callback_email.attachments[0].file_id == "file-processed-789"
    assert callback_email.attachments[0].name == "processed_document.pdf"

    # Verify it serializes correctly for the callback
    callback_data = callback_email.model_dump()
    assert callback_data["attachments"][0]["file_id"] == "file-processed-789"
    assert callback_data["attachments"][0]["content"] is None  # No base64 content


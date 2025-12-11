"""Tests for LlamaCloud attachment handling.

This module tests that attachments can be provided either as:
1. Base64-encoded content (original behavior)
2. LlamaCloud file_id (new behavior)
"""

from unittest.mock import AsyncMock, MagicMock, patch

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


# ============================================================================
# Integration Tests for LlamaCloud Utility Functions
# ============================================================================


@pytest.mark.asyncio
async def test_download_file_from_llamacloud_success():
    """Test successful file download from LlamaCloud."""
    from basic.utils import download_file_from_llamacloud

    mock_file_content = b"test file content"
    presigned_url = "https://s3.amazonaws.com/bucket/file?signature=xyz"

    # Mock the presigned URL object
    mock_presigned_url = MagicMock()
    mock_presigned_url.url = presigned_url

    # Mock the AsyncLlamaCloud client
    mock_client = AsyncMock()
    mock_client.files.read_file_content = AsyncMock(return_value=mock_presigned_url)

    # Mock get_llama_cloud_client to return our mock
    with patch(
        "basic.utils.get_llama_cloud_client",
        return_value=(mock_client, "test-project-id"),
    ):
        # Mock httpx to return file content
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_response = MagicMock()
            mock_response.content = mock_file_content
            mock_response.raise_for_status = MagicMock()

            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)

            mock_httpx.return_value = mock_http_client

            result = await download_file_from_llamacloud("file-test-123")

            assert result == mock_file_content
            mock_client.files.read_file_content.assert_called_once_with(
                id="file-test-123", project_id="test-project-id"
            )
            mock_http_client.get.assert_called_once_with(presigned_url)


@pytest.mark.asyncio
async def test_download_file_from_llamacloud_missing_env_vars():
    """Test download fails when environment variables are missing."""
    from basic.utils import download_file_from_llamacloud

    # Mock get_llama_cloud_client to raise ValueError for missing env vars
    with patch(
        "basic.utils.get_llama_cloud_client",
        side_effect=ValueError("LLAMA_CLOUD_API_KEY environment variable is required"),
    ):
        with pytest.raises(ValueError) as exc_info:
            await download_file_from_llamacloud("file-test-123")

        assert "LLAMA_CLOUD_API_KEY environment variable is required" in str(
            exc_info.value
        )


@pytest.mark.asyncio
async def test_download_file_from_llamacloud_api_error():
    """Test error handling when LlamaCloud API fails."""
    from basic.utils import download_file_from_llamacloud

    # Mock the AsyncLlamaCloud client to raise an exception
    mock_client = AsyncMock()
    mock_client.files.read_file_content = AsyncMock(
        side_effect=Exception("API Error: File not found")
    )

    with patch(
        "basic.utils.get_llama_cloud_client",
        return_value=(mock_client, "test-project-id"),
    ):
        with pytest.raises(ValueError) as exc_info:
            await download_file_from_llamacloud("file-nonexistent")

        assert "Failed to download file file-nonexistent from LlamaCloud" in str(
            exc_info.value
        )
        assert "API Error: File not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_upload_file_to_llamacloud_success():
    """Test successful file upload to LlamaCloud."""
    from basic.utils import upload_file_to_llamacloud

    file_content = b"test file content"
    filename = "test.pdf"
    expected_file_id = "file-uploaded-456"

    # Mock the file object returned by upload_file
    mock_file = MagicMock()
    mock_file.id = expected_file_id

    # Mock the AsyncLlamaCloud client
    mock_client = AsyncMock()
    mock_client.files.upload_file = AsyncMock(return_value=mock_file)

    with patch(
        "basic.utils.get_llama_cloud_client",
        return_value=(mock_client, "test-project-id"),
    ):
        result = await upload_file_to_llamacloud(file_content, filename)

        assert result == expected_file_id
        # Verify upload_file was called
        assert mock_client.files.upload_file.call_count == 1
        call_kwargs = mock_client.files.upload_file.call_args.kwargs
        assert call_kwargs["external_file_id"] == filename
        assert call_kwargs["project_id"] == "test-project-id"
        # Check that upload_file is a file-like object
        assert hasattr(call_kwargs["upload_file"], "read")


@pytest.mark.asyncio
async def test_upload_file_to_llamacloud_with_external_id():
    """Test file upload with external file ID."""
    from basic.utils import upload_file_to_llamacloud

    file_content = b"test content"
    filename = "document.pdf"
    external_id = "custom-ext-id-789"
    expected_file_id = "file-uploaded-789"

    mock_file = MagicMock()
    mock_file.id = expected_file_id

    mock_client = AsyncMock()
    mock_client.files.upload_file = AsyncMock(return_value=mock_file)

    with patch(
        "basic.utils.get_llama_cloud_client",
        return_value=(mock_client, "test-project-id"),
    ):
        result = await upload_file_to_llamacloud(file_content, filename, external_id)

        assert result == expected_file_id
        # Verify upload_file was called with external_id
        call_kwargs = mock_client.files.upload_file.call_args.kwargs
        assert call_kwargs["external_file_id"] == external_id
        assert call_kwargs["project_id"] == "test-project-id"


@pytest.mark.asyncio
async def test_upload_file_to_llamacloud_api_error():
    """Test error handling when upload fails."""
    from basic.utils import upload_file_to_llamacloud

    mock_client = AsyncMock()
    mock_client.files.upload_file = AsyncMock(
        side_effect=Exception("API Error: Upload quota exceeded")
    )

    with patch(
        "basic.utils.get_llama_cloud_client",
        return_value=(mock_client, "test-project-id"),
    ):
        with pytest.raises(ValueError) as exc_info:
            await upload_file_to_llamacloud(b"content", "test.pdf")

        assert "Failed to upload file test.pdf to LlamaCloud" in str(exc_info.value)
        assert "Upload quota exceeded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_llamacloud_attachment_success():
    """Test creating an attachment with file uploaded to LlamaCloud."""
    from basic.utils import create_llamacloud_attachment

    file_content = b"report content"
    filename = "report.pdf"
    content_type = "application/pdf"
    expected_file_id = "file-created-999"

    # Mock upload_file_to_llamacloud
    with patch("basic.utils.upload_file_to_llamacloud", return_value=expected_file_id):
        attachment = await create_llamacloud_attachment(
            file_content, filename, content_type
        )

        assert isinstance(attachment, Attachment)
        assert attachment.name == filename
        assert attachment.type == content_type
        assert attachment.file_id == expected_file_id
        assert attachment.id == filename  # Default to filename


@pytest.mark.asyncio
async def test_create_llamacloud_attachment_with_custom_id():
    """Test creating an attachment with custom attachment ID."""
    from basic.utils import create_llamacloud_attachment

    file_content = b"data"
    filename = "data.csv"
    content_type = "text/csv"
    attachment_id = "custom-att-123"
    expected_file_id = "file-created-555"

    with patch("basic.utils.upload_file_to_llamacloud", return_value=expected_file_id):
        attachment = await create_llamacloud_attachment(
            file_content, filename, content_type, attachment_id=attachment_id
        )

        assert attachment.id == attachment_id
        assert attachment.name == filename
        assert attachment.file_id == expected_file_id


@pytest.mark.asyncio
async def test_create_llamacloud_attachment_upload_fails():
    """Test error propagation when upload fails."""
    from basic.utils import create_llamacloud_attachment

    # Mock upload to fail
    with patch(
        "basic.utils.upload_file_to_llamacloud",
        side_effect=ValueError("Upload failed: Network error"),
    ):
        with pytest.raises(ValueError) as exc_info:
            await create_llamacloud_attachment(b"data", "file.txt", "text/plain")

        assert "Upload failed: Network error" in str(exc_info.value)

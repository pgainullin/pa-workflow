"""Tests for API retry mechanism.

This module tests that API calls are automatically retried on transient errors
(503 Service Unavailable, 429 Rate Limit, 500 Internal Server Error, etc.)
with exponential backoff.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from basic.utils import (
    is_retryable_error,
    download_file_from_llamacloud,
    upload_file_to_llamacloud,
)


def test_is_retryable_error_with_503():
    """Test that 503 errors are identified as retryable."""
    error = Exception(
        "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'The model is overloaded. Please try again later.', 'status': 'UNAVAILABLE'}}"
    )
    assert is_retryable_error(error) is True


def test_is_retryable_error_with_429():
    """Test that 429 rate limit errors are identified as retryable."""
    error = Exception("429 Too Many Requests: Rate limit exceeded")
    assert is_retryable_error(error) is True


def test_is_retryable_error_with_500():
    """Test that 500 server errors are identified as retryable."""
    error = Exception("500 Internal Server Error")
    assert is_retryable_error(error) is True


def test_is_retryable_error_with_overload_message():
    """Test that overload messages are identified as retryable."""
    error = Exception("The model is overloaded. Please try again later.")
    assert is_retryable_error(error) is True


def test_is_retryable_error_with_quota_message():
    """Test that quota messages are identified as retryable."""
    error = Exception("Quota exceeded. Please try again.")
    assert is_retryable_error(error) is True


def test_is_retryable_error_with_rate_limit_message():
    """Test that rate limit messages are identified as retryable."""
    error = Exception("Rate limit exceeded")
    assert is_retryable_error(error) is True


def test_is_retryable_error_with_timeout_message():
    """Test that timeout messages are identified as retryable."""
    error = Exception("Connection timeout")
    assert is_retryable_error(error) is True


def test_is_retryable_error_with_connection_error():
    """Test that connection errors are identified as retryable."""
    error = Exception("Connection refused")
    assert is_retryable_error(error) is True


def test_is_retryable_error_with_unavailable_message():
    """Test that unavailable messages are identified as retryable."""
    error = Exception("Service temporarily unavailable")
    assert is_retryable_error(error) is True


def test_is_retryable_error_with_non_retryable():
    """Test that non-retryable errors are not identified as retryable."""
    # 400 Bad Request - not retryable
    error = Exception("400 Bad Request: Invalid parameters")
    assert is_retryable_error(error) is False

    # 401 Unauthorized - not retryable
    error = Exception("401 Unauthorized: Invalid API key")
    assert is_retryable_error(error) is False

    # 404 Not Found - not retryable
    error = Exception("404 Not Found: Resource does not exist")
    assert is_retryable_error(error) is False

    # Generic error - not retryable
    error = Exception("Something went wrong")
    assert is_retryable_error(error) is False


def test_is_retryable_error_avoids_false_positives():
    """Test that error detection doesn't match unrelated strings."""
    # Should not match numbers in non-HTTP contexts
    error = Exception("Processing 503 items failed")
    assert is_retryable_error(error) is False

    # Should not match partial words
    error = Exception("The quotable phrase was disconnection warning")
    assert is_retryable_error(error) is False

    # Should not match "timeout" in other contexts
    error = Exception("No timeouts configured")
    assert is_retryable_error(error) is False

    # Should match actual quota exceeded error
    error = Exception("Quota exceeded for this API")
    assert is_retryable_error(error) is True

    # Should match actual connection error
    error = Exception("Connection refused by server")
    assert is_retryable_error(error) is True


def test_is_retryable_error_with_httpx_timeout():
    """Test that httpx timeout exceptions are identified as retryable."""
    try:
        import httpx

        error = httpx.TimeoutException("Request timeout")
        assert is_retryable_error(error) is True
    except ImportError:
        pytest.skip("httpx not available")


def test_is_retryable_error_with_httpx_connect_error():
    """Test that httpx connection errors are identified as retryable."""
    try:
        import httpx

        error = httpx.ConnectError("Connection refused")
        assert is_retryable_error(error) is True
    except ImportError:
        pytest.skip("httpx not available")


@pytest.mark.asyncio
async def test_download_file_retries_on_503():
    """Test that download_file_from_llamacloud retries on 503 errors."""
    from tenacity import RetryError

    # Mock that always raises 503 error
    mock_client = AsyncMock()
    mock_client.files.read_file_content = AsyncMock(
        side_effect=Exception("503 Service Unavailable: Model is overloaded")
    )

    with patch(
        "basic.utils.get_llama_cloud_client",
        return_value=(mock_client, "test-project-id"),
    ):
        # Should retry and eventually raise after max attempts
        with pytest.raises((ValueError, RetryError)) as exc_info:
            await download_file_from_llamacloud("file-test-123")

        # Verify that it tried multiple times (at least 2)
        assert mock_client.files.read_file_content.call_count >= 2


@pytest.mark.asyncio
async def test_download_file_succeeds_after_retries():
    """Test that download_file_from_llamacloud succeeds after transient failures."""
    mock_file_content = b"test file content"
    presigned_url = "https://s3.amazonaws.com/bucket/file?signature=xyz"

    # Mock the presigned URL object
    mock_presigned_url = MagicMock()
    mock_presigned_url.url = presigned_url

    # Mock that fails once then succeeds
    mock_client = AsyncMock()
    call_count = 0

    async def read_file_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("503 Service Unavailable")
        return mock_presigned_url

    mock_client.files.read_file_content = AsyncMock(side_effect=read_file_side_effect)

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

            # Should succeed after retry
            result = await download_file_from_llamacloud("file-test-123")

            assert result == mock_file_content
            # Verify it was called twice (failed once, succeeded once)
            assert call_count == 2


@pytest.mark.asyncio
async def test_upload_file_retries_on_429():
    """Test that upload_file_to_llamacloud retries on 429 rate limit errors."""
    from tenacity import RetryError

    # Mock that always raises 429 error
    mock_client = AsyncMock()
    mock_client.files.upload_file = AsyncMock(
        side_effect=Exception("429 Too Many Requests: Rate limit exceeded")
    )

    with patch(
        "basic.utils.get_llama_cloud_client",
        return_value=(mock_client, "test-project-id"),
    ):
        # Should retry and eventually raise after max attempts
        with pytest.raises((ValueError, RetryError)) as exc_info:
            await upload_file_to_llamacloud(b"test content", "test.pdf")

        # Verify that it tried multiple times (at least 2)
        assert mock_client.files.upload_file.call_count >= 2


@pytest.mark.asyncio
async def test_upload_file_succeeds_after_retries():
    """Test that upload_file_to_llamacloud succeeds after transient failures."""
    expected_file_id = "file-uploaded-456"

    # Mock the file object returned by upload_file
    mock_file = MagicMock()
    mock_file.id = expected_file_id

    # Mock that fails twice then succeeds
    mock_client = AsyncMock()
    call_count = 0

    async def upload_file_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise Exception("500 Internal Server Error")
        return mock_file

    mock_client.files.upload_file = AsyncMock(side_effect=upload_file_side_effect)

    with patch(
        "basic.utils.get_llama_cloud_client",
        return_value=(mock_client, "test-project-id"),
    ):
        # Should succeed after retries
        result = await upload_file_to_llamacloud(b"test content", "test.pdf")

        assert result == expected_file_id
        # Verify it was called three times (failed twice, succeeded once)
        assert call_count == 3


@pytest.mark.asyncio
async def test_upload_file_does_not_retry_on_auth_error():
    """Test that upload_file_to_llamacloud does not retry on non-retryable errors."""
    # Mock that raises 401 Unauthorized (not retryable)
    mock_client = AsyncMock()
    mock_client.files.upload_file = AsyncMock(
        side_effect=Exception("401 Unauthorized: Invalid API key")
    )

    with patch(
        "basic.utils.get_llama_cloud_client",
        return_value=(mock_client, "test-project-id"),
    ):
        # Should fail immediately without retries
        with pytest.raises(ValueError) as exc_info:
            await upload_file_to_llamacloud(b"test content", "test.pdf")

        # Verify that it was only called once (no retries)
        assert mock_client.files.upload_file.call_count == 1
        assert "Invalid API key" in str(exc_info.value)


@pytest.mark.asyncio
async def test_download_file_does_not_retry_on_not_found():
    """Test that download_file_from_llamacloud does not retry on 404 errors."""
    # Mock that raises 404 Not Found (not retryable)
    mock_client = AsyncMock()
    mock_client.files.read_file_content = AsyncMock(
        side_effect=Exception("404 Not Found: File does not exist")
    )

    with patch(
        "basic.utils.get_llama_cloud_client",
        return_value=(mock_client, "test-project-id"),
    ):
        # Should fail immediately without retries
        with pytest.raises(ValueError) as exc_info:
            await download_file_from_llamacloud("file-nonexistent")

        # Verify that it was only called once (no retries)
        assert mock_client.files.read_file_content.call_count == 1
        assert "File does not exist" in str(exc_info.value)

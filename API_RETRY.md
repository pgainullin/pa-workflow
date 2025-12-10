# API Retry Mechanism

This document describes the automatic retry mechanism implemented for handling transient API errors.

## Overview

The workflow automatically retries API calls when encountering transient errors such as:
- **503 Service Unavailable** - API service is temporarily overloaded
- **429 Too Many Requests** - Rate limit exceeded
- **500 Internal Server Error** - Temporary server error
- **Connection/Timeout Errors** - Network connectivity issues

This ensures the workflow continues processing even when external services experience temporary issues.

## Retry Configuration

### Parameters
- **Max Attempts**: 5 (1 initial attempt + 4 retries)
- **Backoff Strategy**: Exponential with multiplier of 1
  - Initial attempt: immediate
  - 1st retry: wait 1 second
  - 2nd retry: wait 2 seconds
  - 3rd retry: wait 4 seconds
  - 4th retry: wait 8 seconds
- **Total Max Wait Time**: ~15 seconds of backoff (1+2+4+8) plus API call time

### Retryable Errors

The following errors will trigger automatic retries:

#### HTTP Status Codes
- `429` - Too Many Requests / Rate Limit Exceeded
- `500` - Internal Server Error
- `503` - Service Unavailable / Overloaded

#### Error Messages (case-insensitive)
- "rate limit"
- "quota"
- "overload"
- "unavailable"
- "timeout"
- "connection"
- "temporarily"

#### Connection Errors
- `httpx.TimeoutException`
- `httpx.ConnectError`

### Non-Retryable Errors

The following errors will fail immediately without retries:

- `400` - Bad Request (client error)
- `401` - Unauthorized (authentication error)
- `403` - Forbidden (authorization error)
- `404` - Not Found (resource doesn't exist)
- Other client errors and permanent failures

## Components with Retry Logic

### LlamaCloud Operations
Both file upload and download operations automatically retry on transient errors:

```python
from basic.utils import upload_file_to_llamacloud, download_file_from_llamacloud

# Upload with automatic retry
file_id = await upload_file_to_llamacloud(file_bytes, "report.pdf")

# Download with automatic retry
content = await download_file_from_llamacloud(file_id)
```

### LLM API Calls
All LLM operations use retry-wrapped methods:

```python
class EmailWorkflow(Workflow):
    async def _llm_complete_with_retry(self, prompt: str) -> str:
        """LLM text completion with automatic retry"""
        
    async def _genai_generate_content_with_retry(self, model: str, contents: list) -> str:
        """Gemini multimodal generation with automatic retry"""
        
    async def _parse_document_with_retry(self, file_path: str) -> list:
        """LlamaParse document parsing with automatic retry"""
```

**Important**: Never call `llm.acomplete()` or `genai_client.generate_content()` directly. Always use the retry-wrapped methods.

## Logging

Retry attempts are logged at WARNING level before each retry:

```
WARNING:basic.utils:Retrying basic.utils.download_file_from_llamacloud in 2 seconds as it raised Exception: 503 Service Unavailable.
```

This allows monitoring of API reliability and identifying patterns in failures.

## Example: Handling API Overload

### Before (No Retry)
```
Error: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'The model is overloaded. Please try again later.', 'status': 'UNAVAILABLE'}}
```
The workflow would fail immediately, and the user would receive an error email.

### After (With Retry)
```
1st attempt: 503 Service Unavailable
   ↓ wait 1 second
2nd attempt: 503 Service Unavailable
   ↓ wait 2 seconds
3rd attempt: Success!
```
The workflow succeeds after the transient overload condition clears, and the user receives their processed result.

## Testing

The retry mechanism is thoroughly tested with 18 test cases covering:

- Error detection for all retryable error types
- Proper identification of non-retryable errors
- Retry behavior (max attempts, backoff timing)
- Success after transient failures
- No retries for permanent errors

Run the retry tests:
```bash
pytest tests/test_api_retry.py -v
```

## Implementation Details

### Custom Retry Logic

If you need to add retry logic to a new API call, use the `@api_retry` decorator:

```python
from basic.utils import api_retry

@api_retry
async def my_api_call():
    # Your API call here
    pass
```

### Custom Retry Detection

To customize retry behavior, you can modify `is_retryable_error()` in `src/basic/utils.py`:

```python
def is_retryable_error(exception: Exception) -> bool:
    """Check if an exception is retryable."""
    error_str = str(exception).lower()
    
    # Add your custom logic here
    if "custom_error_pattern" in error_str:
        return True
        
    # ... existing logic ...
```

## Best Practices

1. **Always use retry-wrapped methods** for external API calls
2. **Monitor retry logs** to identify API reliability issues
3. **Don't retry on auth errors** (401, 403) - fix the credentials instead
4. **Don't retry on client errors** (400, 404) - fix the request instead
5. **Use appropriate timeouts** - ensure your workflow timeout is longer than the max retry wait time

## Configuration

Retry parameters are configured in `src/basic/utils.py`:

```python
api_retry = retry(
    retry=retry_if_exception(is_retryable_error),
    stop=stop_after_attempt(5),  # Max 5 attempts
    wait=wait_exponential(multiplier=1, min=1, max=45),  # Exponential backoff
    before_sleep=before_sleep_log(logger, logging.WARNING),  # Log retries
    reraise=True,  # Re-raise exception after all retries exhausted
)
```

To adjust these parameters, modify the values in the `retry()` decorator.

## Related Documentation

- [README.md](README.md) - Project overview
- [LLAMACLOUD_FILES.md](LLAMACLOUD_FILES.md) - LlamaCloud file integration
- [ATTACHMENT_SUPPORT.md](ATTACHMENT_SUPPORT.md) - Attachment handling

## References

- [Tenacity Documentation](https://tenacity.readthedocs.io/) - Retry library used
- [Issue: API quota or overload handling is not consistent](https://github.com/pgainullin/pa-workflow/issues/XXX)

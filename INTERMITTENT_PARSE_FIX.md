# Fix for Intermittent PDF Parse Failures (Issue #39)

## Problem Statement

Users were experiencing intermittent failures when parsing PDF documents with the error:
```
Document parsing returned no text content. The document may be empty, corrupted, or in an unsupported format.
```

**Key characteristics of the issue:**
- The same document that parsed successfully before would fail intermittently
- The document itself was not corrupted or empty
- The failure was non-deterministic and appeared to be an API-level issue

## Root Cause Analysis

The issue was caused by the LlamaParse API occasionally returning document objects that appeared successful (no exceptions thrown) but contained empty content when `get_content()` was called.

### Original Code Flow

```python
@api_retry
async def _parse_with_retry(self, tmp_path: str) -> list:
    """Only retries the API call, not content validation"""
    return await asyncio.to_thread(self.llama_parser.load_data, tmp_path)

async def execute(self, **kwargs):
    # ...
    documents = await self._parse_with_retry(tmp_path)  # Retry happens here
    parsed_text = "\n".join([doc.get_content() for doc in documents])  # But not here
    
    # Content validation AFTER retry mechanism
    if not parsed_text or not parsed_text.strip():
        return {"success": False, "error": "..."}  # No retry, just fail
```

**The problem:** The retry mechanism only covered the `load_data` API call. If the API succeeded but returned documents with empty content, no retry would occur.

## Solution

Move the content validation **inside** the retry mechanism so that empty content triggers a retry:

```python
@api_retry
async def _parse_with_retry(self, tmp_path: str, file_extension: str = ".pdf") -> tuple[list, str]:
    """Retries both API failures AND empty content responses"""
    import asyncio

    documents = await asyncio.to_thread(self.llama_parser.load_data, tmp_path)
    parsed_text = "\n".join([doc.get_content() for doc in documents])
    
    # Validate content and raise exception to trigger retry if empty
    if not parsed_text or not parsed_text.strip():
        logger.warning(
            f"ParseTool returned empty text for file (will retry). "
            f"Documents returned: {len(documents)}, "
            f"File extension: {file_extension}"
        )
        raise Exception(
            f"Document parsing returned no text content (documents: {len(documents)}). "
            "This may be a transient API issue and will be retried."
        )
    
    return documents, parsed_text
```

### Key Changes

1. **Content validation moved into retry method**: The `_parse_with_retry` method now validates content and raises an exception if it's empty, triggering the retry mechanism.

2. **Returns tuple instead of list**: Changed return type from `list` (just documents) to `tuple[list, str]` (documents and parsed text) to avoid re-extracting content.

3. **Better error messaging**: Distinguishes between retrying (logs warning) and final failure (user-friendly error).

4. **Passes file extension for diagnostics**: Helps with debugging by logging the file type.

## Retry Behavior

The fix leverages the existing `@api_retry` decorator configuration:

- **Max Attempts**: 5 (1 initial + 4 retries)
- **Backoff Strategy**: Exponential (1s, 2s, 4s, 8s)
- **Triggers on**: 
  - API errors (503, 429, 500, timeouts)
  - **NEW:** Empty content responses

### Example Scenario

**Before Fix:**
```
1. User uploads PDF
2. API call succeeds but returns empty content
3. Immediate failure: "Document parsing returned no text content"
4. User gets error email
```

**After Fix:**
```
1. User uploads PDF
2. API call succeeds but returns empty content
3. Exception raised → retry triggered
   ↓ wait 1 second
4. Second attempt succeeds with content
5. User gets successful result
```

## Testing

### Test: Retry on Empty Content
```python
@pytest.mark.asyncio
async def test_parse_tool_retries_on_empty_content():
    """Test that ParseTool retries when API returns empty content intermittently."""
    # Simulate empty content on first attempt, valid content on second
    mock_parser.load_data = MagicMock(
        side_effect=[
            [empty_doc],  # First attempt returns empty content
            [valid_doc],  # Second attempt succeeds
        ]
    )
    
    result = await tool.execute(file_id="...")
    
    assert result["success"] is True
    assert mock_parser.load_data.call_count == 2  # Verified retry occurred
```

### Test: Graceful Failure After Max Retries
```python
@pytest.mark.asyncio
async def test_parse_tool_fails_after_max_retries_on_empty_content():
    """Test that ParseTool fails gracefully after max retries with empty content."""
    # Always return empty content
    mock_parser.load_data = MagicMock(return_value=[empty_doc])
    
    result = await tool.execute(file_id="...")
    
    assert result["success"] is False
    assert "no text content" in result["error"].lower()
    assert mock_parser.load_data.call_count == 5  # Max retries exhausted
```

## Impact

### Improved Reliability
- **Automatic recovery** from transient empty content responses
- **Higher success rate** for document parsing operations
- **Better user experience** with fewer unexplained failures

### Backward Compatibility
- ✅ All existing functionality preserved
- ✅ Return type change is internal to ParseTool
- ✅ No breaking changes to public API
- ✅ Existing tests continue to pass

### Error Handling
- **During retries**: Logs warning with diagnostic information
- **After max retries**: Returns user-friendly error message
- **Exception handling**: Converts technical errors to readable messages

## Code Changes

### Files Modified

1. **src/basic/tools.py**
   - Modified `_parse_with_retry` to include content validation
   - Changed return type to `tuple[list, str]`
   - Updated exception handling for user-friendly error messages
   - Added file extension parameter for better diagnostics

2. **tests/test_tools.py**
   - Added `test_parse_tool_retries_on_empty_content` 
   - Added `test_parse_tool_fails_after_max_retries_on_empty_content`

## Related Issues

- Original Issue: #39 - "PDF parse continues to fail intermittently"
- Related: API_RETRY.md - Automatic retry mechanism documentation

## Monitoring

To monitor the effectiveness of this fix, look for these log patterns:

**Successful retry:**
```
WARNING:basic.tools:ParseTool returned empty text for file (will retry). Documents returned: 1, File extension: .pdf
WARNING:basic.utils:Retrying basic.tools.ParseTool._parse_with_retry in 1 seconds...
```

**Final failure after retries:**
```
ERROR:basic.tools:Error parsing document
```

If you see many retry warnings, it may indicate ongoing API issues with LlamaParse that should be reported upstream.

## Conclusion

This fix addresses the intermittent parse failures by treating empty content responses as transient errors. The retry mechanism now covers both API-level failures and content-level issues, significantly improving the reliability of document parsing operations.

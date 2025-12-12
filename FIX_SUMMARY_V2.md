# Fix Summary V2: Long Text Processing Continues to Fail Despite Batching

## Issue Description
After the initial fix that set max_text_length to 4900, the error still occurred in some cases:
```
Text length need to be between 0 and 5000 characters
```

This was because file-based extraction in ExtractTool bypassed all batching logic.

## Root Cause Analysis

### The Complete Problem Flow
1. **Initial Fix** (documented in FIX_SUMMARY.md): Reduced max_text_length from 100KB to 4.9KB
2. **Remaining Issue**: ExtractTool had TWO code paths:
   - **Text-based extraction** (`text` parameter): ✓ Properly batched with 4900 char limit
   - **File-based extraction** (`file_id` or `file_content` parameters): ✗ NO batching applied

### Why File-Based Extraction Failed
When `file_id` or `file_content` was provided, ExtractTool would:
1. Download or decode the file content
2. Create `SourceText(file=content)` directly
3. Pass it to the Extract API

The LlamaCloud Extract API's `SourceText` class internally:
1. Extracts text from the file
2. Validates text length < 5000 characters
3. Rejects files with > 5000 chars of text content

This meant that **any file with more than 5000 characters of text would fail**, regardless of the batching logic implemented for text-based extraction.

## Solution

### Code Changes

#### 1. src/basic/tools.py - ExtractTool
**Removed file-based extraction entirely** (lines 340-356 in original)

**Before:**
```python
if text:
    # Batching logic for text
    ...
elif file_id:
    # Download file and pass to SourceText directly - NO BATCHING!
    content = await download_file_from_llamacloud(file_id)
    source = SourceText(file=content)
    result = await extract_agent.aextract(source)
elif file_content:
    # Decode and pass to SourceText directly - NO BATCHING!
    content = base64.b64decode(file_content)
    source = SourceText(file=content)
    result = await extract_agent.aextract(source)
```

**After:**
```python
text = kwargs.get("text")
schema = kwargs.get("schema")

if not text:
    return {
        "success": False,
        "error": "Missing required parameter: text. Use ParseTool first to extract text from files.",
    }

# Always apply batching for text
if len(text) > max_text_length:
    # Batch processing logic
    ...
```

#### 2. Updated Tool Description
```python
return (
    "Extract structured data from text using LlamaCloud Extract. "
    "Input: text (parsed document text), schema (JSON schema definition). "
    "Output: extracted_data (structured JSON). "
    "Note: For files, use ParseTool first to extract text, then pass the text to this tool."
)
```

#### 3. tests/test_batch_processing.py
Added test to ensure file parameters are rejected:
```python
@pytest.mark.asyncio
async def test_extract_tool_rejects_file_parameters():
    """Test ExtractTool rejects file_id and file_content parameters."""
    tool = ExtractTool()
    
    # Test with file_id (should fail with helpful message)
    result = await tool.execute(file_id="test-file-id", schema={"field": "string"})
    assert result["success"] is False
    assert "text" in result["error"].lower()
    assert "parsetool" in result["error"].lower()
```

## Verification

### Test Results
All tests pass successfully:
- ✅ `test_process_text_in_batches_short_text`: PASSED
- ✅ `test_process_text_in_batches_long_text`: PASSED
- ✅ `test_process_text_in_batches_with_combiner`: PASSED
- ✅ `test_translate_tool_batching`: PASSED
- ✅ `test_summarise_tool_batching`: PASSED
- ✅ `test_classify_tool_long_text_sampling`: PASSED
- ✅ `test_extract_tool_text_batching`: PASSED
- ✅ `test_extract_tool_respects_5000_char_limit`: PASSED
- ✅ `test_extract_tool_rejects_file_parameters`: PASSED (NEW)
- ✅ `test_split_tool_no_truncation`: PASSED
- ✅ `test_batch_processing_sentence_boundaries`: PASSED

All 13 tool tests also pass (test_tools.py).

## Impact

### Before the Fix
```
Workflow Flow with Text:
ParseTool → (returns 100KB text) → ExtractTool (text param) → ✓ BATCHED → SUCCESS

Workflow Flow with File:
ExtractTool (file_id param) → ❌ ERROR (> 5000 chars)
"Text length need to be between 0 and 5000 characters"
```

### After the Fix
```
Correct Workflow Pattern:
ParseTool (file_id) → (returns text) → ExtractTool (text param) → ✓ BATCHED → SUCCESS

Invalid Workflow Pattern:
ExtractTool (file_id) → ✗ REJECTED with helpful error message
"Missing required parameter: text. Use ParseTool first to extract text from files."
```

## Benefits

1. **Eliminates Bypass**: All extraction now goes through batching logic
2. **Clear Error Messages**: Users are guided to use ParseTool for files
3. **Simplified Code**: Removed complex file-handling code paths
4. **Enforces Best Practice**: The Parse → Extract workflow is now mandatory
5. **Prevents Confusion**: No ambiguity about when to use file_id vs text
6. **Better Testing**: Single code path is easier to test and maintain

## Workflow Pattern

The correct workflow for extracting from files:

```json
[
  {
    "tool": "parse",
    "params": {"file_id": "att-1"},
    "description": "Parse the PDF attachment to extract text"
  },
  {
    "tool": "extract",
    "params": {
      "text": "{{step_1.parsed_text}}",
      "schema": {"field": "string"}
    },
    "description": "Extract structured data from parsed text"
  }
]
```

This ensures:
1. **Files are properly parsed**: ParseTool handles various file formats
2. **Long text is batched**: ExtractTool applies 4900 char batches automatically
3. **API limits respected**: No text chunk ever exceeds 5000 chars
4. **Clear workflow**: Two-step process is explicit and predictable

## Related Changes

This fix complements the existing batch processing infrastructure:
- **TranslateTool**: Uses 50KB batches (GoogleTranslator has higher limits)
- **SummariseTool**: Uses 50KB batches (LLM has higher context limits)
- **ClassifyTool**: Samples 10KB (uses intelligent sampling strategy)
- **ExtractTool**: Now uses 4.9KB batches for ALL text (no file bypass)
- **SplitTool**: No limit (splitting is its purpose)

## Conclusion

This fix resolves the remaining edge case where long text processing could still fail. By removing the file-based extraction code paths that bypassed batching, we ensure that all text extraction is properly batched and respects the 5000 character API limit.

The solution is cleaner, easier to maintain, and enforces a best-practice workflow pattern that separates file parsing from data extraction.

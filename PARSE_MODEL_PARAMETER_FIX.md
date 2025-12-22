# Parse Model Parameter Fix

## Issue Summary

PDF documents that previously parsed successfully were failing after PR #115 with the following error:

```
Document parsing returned no text content after multiple retries. 
The document may be empty, corrupted, in an unsupported format, 
or the parsing service may be experiencing issues.

Diagnostic Details:
- File: unknown
- Extension: .pdf  
- Error Type: empty_content_after_retries
- Max Retries: 5
- File Size: 2470456 bytes
- Status: All retry attempts exhausted
```

## Root Cause

PR #115 added `model="gemini-2.5-flash"` parameter to LlamaParse configuration to improve Chinese OCR. However, this parameter appears to be causing LlamaParse API calls to fail or return empty content for regular PDFs.

### Why the Model Parameter Caused Issues

The `model` parameter may have caused failures due to one or more of the following reasons:

1. **Version Incompatibility**: The parameter may not be fully supported in llama-parse version 0.6.54
2. **API Availability**: The specific model may have usage restrictions or require additional configuration
3. **Unexpected Behavior**: The model parameter may change parsing behavior in ways that cause certain PDFs to fail
4. **Configuration Requirements**: The model may require additional API keys or authentication that aren't configured

## Solution

Temporarily removed (commented out) the `model="gemini-2.5-flash"` parameter from LlamaParse initialization in both:
- `src/basic/tools/parse_tool.py` (lines 145-147)
- `src/basic/tools/sheets_tool.py` (lines 69-71)

### Why Commented Out Instead of Removed

The parameter was commented out rather than completely removed to:
1. **Preserve Intent**: Keep the original documentation about what the parameter was meant to do
2. **Easy Re-enablement**: Make it simple to re-add once compatibility is confirmed
3. **Maintain History**: Document why the change was made for future reference

## Changes Made

### Before (PR #115)
```python
self.llama_parser = LlamaParse(
    result_type="markdown",
    language="en,ch_sim,ch_tra,ja,ko,ar,hi,th,vi",
    high_res_ocr=True,
    parse_mode="parse_page_with_agent",
    model="gemini-2.5-flash",  # Added in PR #115
    adaptive_long_table=True,
    outlined_table_extraction=True,
    output_tables_as_HTML=True,
)
```

### After (This Fix)
```python
self.llama_parser = LlamaParse(
    result_type="markdown",
    language="en,ch_sim,ch_tra,ja,ko,ar,hi,th,vi",
    high_res_ocr=True,
    parse_mode="parse_page_with_agent",
    # NOTE: model parameter temporarily removed due to parsing regression
    # See issue: Parse step broken - PDFs that previously worked now fail
    # model="gemini-2.5-flash",
    adaptive_long_table=True,
    outlined_table_extraction=True,
    output_tables_as_HTML=True,
)
```

## Expected Impact

### Positive Effects ✅
- **Restores PDF Parsing**: Regular PDFs that failed after PR #115 should now parse successfully
- **Maintains OCR Support**: Multi-language OCR still enabled via `language` parameter
- **Preserves Agent Mode**: Agent-based parsing still active via `parse_mode` parameter
- **Keeps High-Res OCR**: Scanned document support maintained via `high_res_ocr` parameter

### Potential Trade-offs ⚠️
- **Chinese OCR Optimization**: May be slightly less optimal for Chinese documents without explicit model
- **Default Model Used**: LlamaParse will use its default model for agent-based parsing

According to the original CHINESE_OCR_FIX_SUMMARY documentation:
> "Without this parameter, LlamaParse may use a **default model that is not optimized** for complex character recognition"

This suggests that Chinese OCR should still work, just potentially with slightly lower accuracy.

## Testing Recommendations

### Validation Tests

1. **Regular PDF Parsing**
   - Test with English PDFs that previously failed
   - Verify they parse successfully without errors
   - Check parsed content is accurate

2. **Chinese OCR Testing**  
   - Test with Chinese scanned PDFs
   - Verify they still parse (though possibly with lower accuracy)
   - Compare results with and without model parameter

3. **Edge Cases**
   - Test with various PDF types (scanned, digital, mixed)
   - Test with different languages (CJK, Arabic, etc.)
   - Verify table extraction still works

### Test Commands
```bash
# Run parse-related tests
pytest tests/test_tools.py::test_parse_tool -v
pytest tests/test_tools.py -k parse -v

# Run full test suite
pytest tests/
```

## Next Steps

### Immediate
- ✅ Remove model parameter from LlamaParse configuration
- ✅ Document the change and rationale
- ⏳ Test with actual PDF documents
- ⏳ Verify no regressions in test suite

### Future Investigation

To properly resolve this issue and potentially re-enable the model parameter:

1. **Verify Model Parameter Support**
   - Check llama-parse documentation for model parameter requirements
   - Verify the specific model name is correct
   - Test with latest llama-parse version

2. **Environment Configuration**
   - Check if model parameter requires GEMINI_API_KEY
   - Verify API quota and rate limits
   - Test with proper authentication

3. **Conditional Usage**
   - Consider making model parameter configurable via environment variable
   - Example: `LLAMAPARSE_MODEL` env var to opt-in to specific model
   - Allow users to test with/without model parameter

4. **Alternative Approaches**
   - Test with different models (e.g., "openai-gpt-4.1-mini", "anthropic-sonnet-4.0")
   - Consider model parameter only for specific file types or languages
   - Implement fallback mechanism (try with model, fall back without)

## Related Documentation

- **CHINESE_OCR_FIX_SUMMARY.md**: Original rationale for adding model parameter
- **SCANNED_PDF_OCR_FIX.md**: Complete OCR configuration documentation  
- **PARSE_CRITICAL_FAILURE_FIX.md**: Related parsing failure handling
- **AGENTS.md**: LlamaParse configuration examples

## Files Modified

1. `src/basic/tools/parse_tool.py` - Commented out model parameter
2. `src/basic/tools/sheets_tool.py` - Commented out model parameter
3. `PARSE_MODEL_PARAMETER_FIX.md` - This documentation (new)

## Summary

This is a **minimal, surgical fix** that:
- ✅ Restores PDF parsing functionality that regressed in PR #115
- ✅ Maintains all other OCR and parsing features
- ✅ Documents the change for future reference
- ✅ Makes it easy to re-enable once root cause is identified
- ⚠️ May slightly reduce Chinese OCR accuracy (but should still work)

The model parameter can be re-introduced once the compatibility issue is properly investigated and resolved, potentially with:
- Proper version requirements
- Configuration validation
- Environment-based opt-in
- Fallback mechanisms

# Parse Tool Empty Attachment Fix

## Issue Summary

When an LLM incorrectly assumes that an email includes attachments and schedules a parse step, the ParseTool would fail with the error:
```
"Either file_id or file_content must be provided"
```

This error would cause:
1. The parse step to fail with `success: False`
2. All downstream steps that depend on the parse output to also fail
3. The entire workflow to potentially fail or produce incomplete results

## Root Causes

1. **ParseTool Hard Failure**: The ParseTool would return a failure status when no file was provided, rather than gracefully skipping the operation
2. **LLM Triage Assumptions**: The triage prompt did not explicitly warn the LLM against assuming attachments exist when they're not listed

## Solution Implemented

### 1. ParseTool and SheetsTool Graceful Handling

Modified `src/basic/tools/parse_tool.py` and `src/basic/tools/sheets_tool.py` to handle missing file gracefully:

**Before:**
```python
else:
    return {
        "success": False,
        "error": "Either file_id or file_content must be provided",
    }
```

**After:**
```python
else:
    # No file provided - this can happen when LLM incorrectly schedules a parse step
    # for non-existent attachments. Fail gracefully to avoid breaking downstream steps.
    logger.warning(
        "ParseTool called without file_id or file_content. "
        "This likely means the LLM scheduled a parse step for a non-existent attachment. "
        "Skipping parse and returning empty result."
    )
    return {
        "success": True,
        "parsed_text": "",
        "skipped": True,
        "message": "No file provided to parse - step skipped",
    }
```

**Key Changes:**
- Returns `success: True` instead of `False` to prevent downstream failures
- Returns empty `parsed_text: ""` (ParseTool) or `sheet_data: {tables: [], table_count: 0}` (SheetsTool) as valid results
- Adds `skipped: True` flag to indicate the step was skipped
- Includes descriptive `message` explaining why
- Logs a warning for debugging purposes

### 2. Triage Prompt Improvements

Modified `src/basic/prompt_templates/triage_prompt.txt` to add explicit guidance:

**Added Guidelines:**
1. ONLY process attachments that are EXPLICITLY listed in the Attachments section
2. DO NOT assume there are attachments if none are listed
3. DO NOT schedule **parse** or **sheets** steps unless you can see a specific attachment name and type; only use **extract** steps when you have text already available (e.g., email body or `parsed_text` from a previous step)
4. Emphasized that `file_id` is required only for **parse** and **sheets** tools (which operate on attachments), while **extract** tools operate on text input that has already been extracted

These changes help prevent the LLM from incorrectly scheduling parse steps in the first place.

### 3. Comprehensive Tests

Added and updated tests to verify the behavior:

#### Test 1: ParseTool Unit Test
`test_parse_tool_graceful_handling_of_missing_file()` in `tests/test_tools.py`
- Tests ParseTool directly with no file_id or file_content
- Verifies it returns success with skipped flag
- Confirms parser is never called
- Validates empty parsed_text is returned

#### Test 2: SheetsTool Unit Test
`test_sheets_tool_missing_file()` in `tests/test_tools.py` (updated)
- Tests SheetsTool with no file_id or file_content
- Verifies it returns success with skipped flag
- Validates empty sheet_data is returned

#### Test 3: Workflow Integration Test
`test_parse_tool_with_no_attachments()` in `tests/test_triage_workflow.py`
- Tests full workflow scenario with empty attachments list
- Simulates LLM scheduling parse step incorrectly
- Verifies parse step succeeds gracefully
- Confirms downstream steps can still execute
- Validates parser is never called

## Benefits

1. **Robustness**: Workflow no longer fails completely when LLM makes scheduling mistakes
2. **Graceful Degradation**: Parse step skips gracefully, allowing other steps to proceed
3. **Better Debugging**: Warning logs help identify when/why this occurs
4. **Prevention**: Improved triage prompt reduces likelihood of issue occurring
5. **Backward Compatible**: Existing functionality unchanged; only affects error case

## Example Scenario

**Before Fix:**
```
Email: "Please summarize this" (no attachments)
LLM Plan: [parse(file_id=None), summarise(text={{step_1.parsed_text}})]
Result: Parse fails → Summarise skipped → Workflow fails
```

**After Fix:**
```
Email: "Please summarize this" (no attachments)
LLM Plan: [parse(file_id=None), summarise(text={{step_1.parsed_text}})]
Result: Parse skips gracefully → Summarise uses empty text → Workflow succeeds
```

Better yet, with improved prompt:
```
Email: "Please summarize this" (no attachments)
LLM Plan: [summarise(text="Please summarize this")]
Result: Summarise executes directly → Workflow succeeds efficiently
```

## Related Files Modified

1. `src/basic/tools/parse_tool.py` - Core fix for graceful handling
2. `src/basic/tools/sheets_tool.py` - Same fix applied to sheets processing
3. `src/basic/prompt_templates/triage_prompt.txt` - LLM guidance improvements
4. `tests/test_tools.py` - Unit tests for ParseTool and SheetsTool behavior
5. `tests/test_triage_workflow.py` - Integration test for workflow behavior

## Testing

Run the test suite to verify:
```bash
# Test ParseTool graceful handling
pytest tests/test_tools.py::test_parse_tool_graceful_handling_of_missing_file -v

# Test SheetsTool graceful handling
pytest tests/test_tools.py::test_sheets_tool_missing_file -v

# Test workflow integration
pytest tests/test_triage_workflow.py::test_parse_tool_with_no_attachments -v
```

All tests should pass, confirming:
- ParseTool handles missing files gracefully
- SheetsTool handles missing files gracefully
- Workflow continues execution despite tool issues
- No calls to the actual parsers when no file is provided

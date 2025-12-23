# ExtractTool Schema Handling Fix Summary

## Issue
The `ExtractTool` failed with a `TypeError` or a custom validation error ("Schema must be a dict or Pydantic BaseModel class") when the `schema` parameter was passed as a JSON string. This often occurred when the tool was called by the LLM triage agent or when parameters were resolved from templates, as they are typically treated as strings in the execution plan.

## Changes

### 1. `src/basic/tools/extract_tool.py`
- **JSON String Support**: Added logic to automatically detect and parse `schema` if it is passed as a string.
- **Pydantic Model Support**: Expanded validation to accept both Pydantic `BaseModel` classes and instances.
- **Improved Error Reporting**: Enhanced the error message to include the received type and a preview of the value when validation fails, making it significantly easier to debug pipeline issues.

### 2. `tests/test_tools.py` (Maintenance & Verification)
- **New Test Case**: Added `test_extract_tool_string_schema` to verify that JSON string schemas are correctly parsed and used.
- **Path Correction**: Fixed `test_classify_tool` and `test_print_to_pdf_tool` by updating their `patch` paths to point to the specific tool modules rather than the package root, which prevents `AttributeError` during testing.
- **Encoding Fixes**: Updated `test_parse_tool_encoding_fallback` to use valid Latin-1 characters and improved `test_parse_tool_all_encodings_fail` with more robust mocking of binary content.

### 3. `tests/test_extract_pipeline.py` (New Integration Test)
- Created a comprehensive integration test that simulates the full **Parse -> Extract** pipeline.
- Verified that numerical data (integers and floats) is correctly extracted from parsed PDF text.
- Confirmed that the pipeline works seamlessly when the schema is passed as a JSON string from a previous step's output or template.

## Verification Results
- All 33 tests in `tests/test_tools.py` are passing.
- The new pipeline tests in `tests/test_extract_pipeline.py` are passing.
- Verified that the fix correctly identifies and parses schemas like `'{"field": "number"}'` into the required dictionary format for LlamaCloud Extract.

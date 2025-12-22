# Parse Tool Text File Handling Fix

## Problem

When processing emails with long bodies containing quoted conversation history, the workflow creates an `email_chain.md` attachment to store the email chain separately. However, when the LLM attempted to parse this markdown file using the Parse tool, it would fail with:

```
Document parsing returned no text content. The document may be empty, corrupted, or in an unsupported format.
```

### Root Cause

The Parse tool uses LlamaParse, which is designed for parsing binary document formats like PDF, Word, PowerPoint, etc. When a plain text file (like `email_chain.md`) is sent to LlamaParse:

1. LlamaParse expects binary document formats
2. Plain text/markdown files don't contain the document structure LlamaParse looks for
3. LlamaParse returns no content, causing the parse step to fail
4. This blocks downstream processing steps that depend on the parsed content

## Solution

Modified the Parse tool to detect and handle text-based files differently:

### Implementation

**Added text file detection method:**
```python
def _is_text_file(self, file_extension: str) -> bool:
    """Check if a file is a text-based file that doesn't need LlamaParse."""
    # Common text file extensions that don't need LlamaParse.
    # Note: .csv is included as a fallback - while SheetsTool provides better
    # structured parsing, ParseTool can handle CSV as plain text when triage
    # incorrectly assigns a Parse step instead of a Sheets step.
    text_extensions = {
        ".txt", ".md", ".markdown", ".text", ".log",
        ".csv", ".tsv", ".json", ".xml", ".html", ".htm",
        ".yaml", ".yml", ".ini", ".cfg", ".conf",
    }
    return file_extension.lower() in text_extensions
```

**Modified execute method to handle text files:**
```python
# Check if this is a text file that doesn't need LlamaParse
if self._is_text_file(file_extension):
    logger.info(
        f"ParseTool: Detected text file ({file_extension}), "
        f"returning content directly without LlamaParse"
    )
    try:
        # Decode the content as text
        parsed_text = content.decode("utf-8")
        return {"success": True, "parsed_text": parsed_text}
    except UnicodeDecodeError:
        # Try other common encodings as fallback
        for encoding in ["latin-1", "cp1252", "iso-8859-1"]:
            try:
                parsed_text = content.decode(encoding)
                logger.info(f"Decoded text file using {encoding} encoding")
                return {"success": True, "parsed_text": parsed_text}
            except UnicodeDecodeError:
                continue
        # If all encodings fail, return error
        error_msg = (
            f"Failed to decode text file ({file_extension}) with UTF-8, "
            "latin-1, cp1252, or iso-8859-1 encodings. "
            "The file may be corrupted or in an unsupported encoding."
        )
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
```

## Benefits

1. **Fixes Long Email Issue**: Email chains stored as `email_chain.md` now parse successfully
2. **Better Performance**: Text files are decoded directly without API calls to LlamaParse
3. **Encoding Flexibility**: Supports multiple text encodings (UTF-8, Latin-1, CP1252, ISO-8859-1)
4. **Backward Compatible**: Binary documents (PDF, DOCX, etc.) still use LlamaParse as before
5. **Clear Error Handling**: Returns explicit errors when text decoding fails instead of silently falling through
6. **Robust Triage Handling**: CSV files can be handled as text fallback when triage incorrectly assigns Parse instead of Sheets

## Supported Text File Types

The following file extensions are now handled as text files:
- **Markdown**: `.md`, `.markdown`
- **Plain Text**: `.txt`, `.text`, `.log`
- **Data Formats**: `.csv`, `.tsv`, `.json`, `.xml` (Note: CSV handled as text fallback, SheetsTool preferred for structured parsing)
- **Web Files**: `.html`, `.htm`
- **Configuration**: `.yaml`, `.yml`, `.ini`, `.cfg`, `.conf`

## Testing

### Unit Tests Added

1. **`test_parse_tool_handles_text_files`**
   - Verifies markdown files (like `email_chain.md`) are decoded directly
   - Confirms LlamaParse is NOT called for text files

2. **`test_parse_tool_handles_various_text_file_types`**
   - Tests multiple text file extensions (including CSV)
   - Ensures consistent behavior across different text formats

3. **`test_parse_tool_binary_files_use_llamaparse`**
   - Confirms binary files still use LlamaParse
   - Ensures backward compatibility

4. **`test_parse_tool_encoding_fallback`**
   - Tests fallback to Latin-1 encoding when UTF-8 fails
   - Verifies alternative encodings work correctly

5. **`test_parse_tool_all_encodings_fail`**
   - Tests error handling when all encodings fail
   - Ensures clear error messages are returned

### Verification Script

Run `verify_parse_text_files.py` to verify the fix:

```bash
python verify_parse_text_files.py
```

## Example Scenario

### Before Fix

```
Email with long body (>500 chars of quoted text)
  ↓
Create email_chain.md attachment
  ↓
LLM schedules parse step for email_chain.md
  ↓
Parse tool sends markdown to LlamaParse
  ↓
❌ LlamaParse returns no content
  ↓
❌ Workflow fails: "Document parsing returned no text content"
```

### After Fix

```
Email with long body (>500 chars of quoted text)
  ↓
Create email_chain.md attachment
  ↓
LLM schedules parse step for email_chain.md
  ↓
Parse tool detects .md extension
  ↓
✅ Decode as UTF-8 text directly
  ↓
✅ Return markdown content
  ↓
✅ Workflow continues successfully
```

## Impact

This fix resolves the critical failure reported in the issue where long email bodies with quoted content would fail to process. The Parse tool now intelligently routes text files to direct decoding and binary documents to LlamaParse, ensuring both types work correctly.

## Files Changed

1. **`src/basic/tools/parse_tool.py`**
   - Added `_is_text_file()` method
   - Modified `execute()` to detect and handle text files
   - Added multi-encoding support

2. **`tests/test_tools.py`**
   - Added 3 new test cases for text file handling
   - Verified backward compatibility with binary files

3. **`verify_parse_text_files.py`**
   - Created verification script to demonstrate the fix

## Related Issues

- Issue: "Long email body fails in Parse tool"
- Root cause: `email_chain.md` attachments sent to LlamaParse
- Related: Email chain handling (ISSUE_RESOLUTION_EMAIL_TRUNCATION.md)

---

**Status**: ✅ COMPLETE  
**Date**: 2025-12-22  
**Branch**: copilot/fix-parse-tool-long-email-issue

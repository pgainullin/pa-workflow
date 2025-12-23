# Chinese/CJK Character Support Fix

## Issue
Chinese characters (and other non-Latin scripts) were being mangled in the output, specifically appearing as `?` or `!` in the generated PDF files. This was caused by:
1. Explicit encoding to `latin-1` in `PrintToPDFTool`, which replaced unrepresentable characters.
2. Use of the default "Helvetica" font in `reportlab`, which does not support CJK glyphs.

## Resolution
1.  **ParseTool**: Validated that `ParseTool` correctly extracts Chinese and Russian text from PDFs using `parse_mode="parse_page_with_agent"`. Updated initialization to support multi-language documents via the `language` parameter (set as a list).
2.  **PrintToPDFTool**:
    *   Registered `STSong-Light` (a standard CID font for Simplified Chinese) using `reportlab`'s `UnicodeCIDFont`.
    *   Updated the default font to `STSong-Light`.
    *   **Removed** the `latin-1` encoding/decoding logic that was stripping non-Latin characters.
    *   Updated table styles and paragraph styles to use the new CJK-compatible font.

## Verification
*   **PDF Parsing**: Verified `tests/test_pdf_parsing.py` passes for both Chinese (`6-3 Z11.pdf`) and Russian (`SHAGALA_Copper.pdf`) documents.
*   **PDF Generation**: Verified `PrintToPDFTool` can now accept Chinese text and generate a PDF without errors (using a reproduction script).

## Notes
*   The execution log (`execution_log.md`) uses UTF-8 encoding and should display characters correctly if opened in a viewer that supports UTF-8.
*   `STSong-Light` is used as the default font. It supports Chinese well and generally handles English, though it may look different from Helvetica. This was necessary to ensure CJK characters are rendered.

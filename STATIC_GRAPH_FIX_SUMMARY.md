# StaticChartGen Tool Fix Summary

## Issues Addressed

1.  **Output filename (.dat):** The tool's output was being saved with a `.dat` extension because `collect_attachments` in `response_utils.py` fell back to a default handler for unknown tools.
2.  **Axis labels with templates:** Axis labels (and data) contained unresolved template strings (e.g., `{{step_2.extracted_data.y}}`) because parameter resolution was not recursive and did not support deep dot notation for nested fields.
3.  **Plotting empty set:** Caused by the tool receiving template strings instead of data lists due to the resolution issue.
4.  **PDF printing:** Charts included in the PDF report were displayed as markdown text (e.g., `![Chart](file-id)`) instead of the actual image.

## Fixes Implemented

### 1. Parameter Resolution (`src/basic/plan_utils.py`)
-   Updated `resolve_params` to be **recursive**, allowing it to resolve parameters inside nested dictionaries and lists (e.g., the `data` parameter of `StaticGraphTool`).
-   Enhanced template resolution to support **deep dot notation** (e.g., `step_1.extracted_data.x`), allowing access to nested fields in the execution context.

### 2. Attachment Handling (`src/basic/response_utils.py`)
-   Updated `collect_attachments` to explicitly handle the `static_graph` tool.
-   Sets the filename to `chart_step_{N}.png` and MIME type to `image/png` for `static_graph` outputs.

### 3. PDF Generation (`src/basic/tools/print_to_pdf_tool.py`)
-   Added support for **markdown images** (`![alt](file_id)`).
-   The tool now parses markdown image syntax, downloads the image from LlamaCloud using the file ID, and embeds it into the PDF using `reportlab`.

## Verification
-   Verified recursive parameter resolution with nested templates.
-   Verified deep dot notation access (`step_N.nested.field`).
-   Verified correct attachment filename generation for `static_graph`.
-   Verified PDF generation with image embedding logic (mocked).

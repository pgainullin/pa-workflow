# Static Graph Tool Batch Processing Fix

## Issue
The `StaticGraphTool` was failing when provided with a `batch_results` list where the first dataset was empty or invalid (e.g., `{"x": [], "y": []}`). The tool expected a single dataset at the top level or strictly valid data in the first position.

## Fix
Modified `src/basic/tools/static_graph_tool.py` to:
1.  Check if `data` contains a `batch_results` key which is a list.
2.  Iterate through the `batch_results` list.
3.  Identify the first "valid" dataset based on the requested `chart_type`.
    *   **Pie:** Requires non-empty `values` and `labels`.
    *   **Histogram:** Requires non-empty `values`.
    *   **Others (Line, Bar, Scatter):** Requires non-empty `x` and `y`.
4.  Use the first found valid dataset as the `data` for chart generation.

## Verification
Verified with a reproduction script that passed a `batch_results` list with two empty datasets followed by a valid one. The tool successfully skipped the empty ones and generated the chart using the valid dataset.

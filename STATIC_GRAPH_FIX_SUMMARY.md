# Static Graph Tool Batch Merging Fix

## Issue
Users reported an "empty scatterplot" issue when the input data from the Extract Tool contained `batch_results` where the first few batches were empty.
Although a previous fix ensured the tool selected the first *valid* dataset, this approach is insufficient if the data is split across multiple batches and the user expects *all* data to be plotted. If the first valid batch happens to be small or unrepresentative, or if the user's perception of "empty" came from missing data points that were in subsequent batches, the previous fix was incomplete.

## Fix
Updated `src/basic/tools/static_graph_tool.py` to **merge** all valid datasets found in `batch_results` instead of selecting only the first one.

The new logic:
1.  Iterates through all items in `batch_results`.
2.  Aggregates valid data into a single dataset based on the `chart_type`:
    *   **Pie:** Merges `values` and `labels`.
    *   **Histogram:** Merges `values`.
    *   **Line/Bar/Scatter:** Merges `x` and `y`.
3.  Uses the combined dataset for chart generation.

## Verification
*   **Reproduction:** Confirmed that `matplotlib` handles categorical string data correctly (ruling out rendering issues).
*   **Testing:** Created `tests/test_static_graph_batch_merge.py` which verifies that multiple data batches are correctly combined into a single plot call. The tests passed, confirming the merge logic works for both "split data" and "mixed empty/valid data" scenarios.
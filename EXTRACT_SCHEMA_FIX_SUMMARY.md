# Extract Tool Schema Fix

## Issue
The user requested that the `extract_tool` prompt (specifically the schema definition provided by the Triage LLM) should be "enriched" to account for:
1.  User Intent (specific data requested).
2.  Parsed Data context.
3.  Downstream Step requirements (specifically for chart generation).

Previously, the Triage LLM might define a generic schema that doesn't match the input requirements of subsequent tools like `static_graph_tool` (which expects `x` and `y` arrays), leading to failures or the need for intermediate transformation steps.

## Fix
Updated `src/basic/prompt_templates/triage_prompt.txt` to include a new **Guideline #10**.

The new guideline explicitly instructs the Triage LLM:
> "10. When defining the 'schema' for the 'extract' tool, ensure it captures the specific data requested by the user. CRITICAL: If the extracted data is intended for a downstream tool (like 'static_graph'), the schema MUST be structured to match that tool's input requirements (e.g., for charts, use fields like 'x' and 'y' as arrays to allow direct data passing)."

## Impact
*   **User Intent:** The prompt enforces capturing specific data requested.
*   **Downstream Compatibility:** By mandating the schema match downstream tools (referencing `x`/`y` for charts), we ensure the `extract_tool` output can be directly fed into `static_graph_tool`.
*   **Efficiency:** Reduces the likelihood of "mismatched" data formats between steps.

## Verification
This is a prompt engineering change. Verification involves ensuring the Triage LLM follows these instructions in a real or simulated workflow. Since this is a change to the system prompt text, explicit unit testing of the LLM's *response* requires an end-to-end test with an LLM, which is outside the scope of deterministic unit tests, but the prompt change itself is verified.
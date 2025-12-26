# Batch Processing / Loop Implementation

## Overview
Implemented support for iterating over lists in the workflow execution plan. This allows a single step in the plan to be executed multiple times, once for each item in a list (e.g., performing searches for multiple extracted topics).

## Features
1.  **`foreach` Field:** Steps in the execution plan can now include a `"foreach"` field.
    *   Value should be a template reference to a list (e.g., `"{{step_1.items}}"`).
2.  **`{{item}}` Reference:** Inside the `params` of a loop step, `{{item}}` can be used to reference the current item in the iteration.
3.  **Result Aggregation:** Results from all iterations are collected and stored. The step result in the context will be an aggregate object containing `results` (list of individual results) and `success` status.
4.  **Auto-Unwrapping:** `resolve_params` now gracefully handles `batch_results` from the Extract tool by checking the first item if a direct key lookup fails.

## Usage Example
If Step 1 (Extract) returns:
```json
{
  "topics": ["AI", "Robotics", "Space"]
}
```

Step 2 (Search) can be defined as:
```json
{
  "tool": "search",
  "foreach": "{{step_1.topics}}",
  "params": {
    "query": "latest news about {{item}}"
  },
  "description": "Search for each extracted topic"
}
```

## Implementation Details
*   **`src/basic/plan_utils.py`**: Updated parameter resolution to support `{{item}}` and handle `batch_results`.
*   **`src/basic/email_workflow.py`**: Updated `execute_plan` to implement the loop logic.
*   **`src/basic/prompt_templates/triage_prompt.txt`**: Added instructions for the Triage LLM.

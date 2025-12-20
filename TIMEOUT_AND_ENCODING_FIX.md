# Timeout and Encoding Fixes

## Issues
1.  **WorkflowTimeoutError**: The workflow was timing out after 120 seconds during the `execute_plan` step. This is likely due to the cumulative time taken by multiple tool executions, particularly the `ParseTool` which has retry logic with backoff (up to ~15s delay per file) and processing time.
2.  **UnicodeEncodeError**: On Windows, logging the timeout error message failed because the default console encoding (`cp1252`) could not handle certain characters in the log message.

## Fixes

### 1. Increased Workflow Timeout
- **File**: `src/basic/email_workflow.py`
- **Change**: Increased the `EmailWorkflow` timeout from **120 seconds** to **360 seconds** (6 minutes).
- **Reasoning**: This provides ample time for the workflow to complete complex plans involving multiple file parsings, LLM calls, and potential retries without prematurely timing out.

### 2. Forced UTF-8 Encoding for Logs
- **File**: `src/basic/server.py`
- **Change**: Added code to reconfigure `sys.stdout` and `sys.stderr` to use `utf-8` encoding when running on Windows.
- **Reasoning**: This prevents `UnicodeEncodeError` when logging messages containing non-ASCII characters (e.g., emojis, special symbols) to the console, ensuring that errors are properly reported instead of causing a secondary crash.

```python
# Fix for Windows UnicodeEncodeError in logs
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
```

## Verification
- The increased timeout should allow your workflows to complete successfully even with heavy processing loads.
- If a timeout or error *does* occur, it will now be logged correctly to the console without crashing due to encoding issues.

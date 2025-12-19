# Parse Tool Traceback Fix

## Issue
The `ParseTool` was logging a full stack trace (traceback) when document parsing returned no text content, even though this is a handled error case (after retries). This was causing alarm in the logs.

## Fix
1.  **Graceful Logging**: Modified `execute` method in `src/basic/tools/parse_tool.py` to catch the specific "no text content" exception and log it as a `WARNING` instead of `ERROR` (with `logger.exception`). This suppresses the traceback while still informing about the failure.
2.  **Empty Content Check**: Added a check for empty file content (`len(content) == 0`) before attempting to parse. This returns a graceful result immediately instead of attempting to parse an empty file and triggering retries.

## Verification
- Verified with `demo_parse_retry_logging.py` (created and deleted) that the traceback is no longer printed to the console/logs for this specific error.
- Verified that retries still occur as expected (transient error handling preserved).
- Verified that empty content input is handled gracefully.

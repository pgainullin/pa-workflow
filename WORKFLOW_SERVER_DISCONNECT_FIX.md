# Workflow Server Disconnect Fix

## Problem Statement

The workflow server was disconnecting without sending a response when errors occurred during email processing. This resulted in fatal errors where the server would not respond to calls to the email workflow run endpoint.

## Root Cause Analysis

The issue was caused by **insufficient exception handling** in the workflow steps. Specifically:

1. **`triage_email` step**: Had a try-except block but it didn't cover the initial setup code (logging, prompt building) before the main try block
2. **`execute_plan` step**: Had try-except blocks for individual tool executions but no top-level exception handler for the entire step
3. **`send_results` step**: Had a try-except block only around the callback sending logic, but not around the preparation steps (response generation, log creation, attachment collection)

When any of these uncaught exceptions occurred, the workflow would raise an exception instead of returning a proper event object (`TriageEvent`, `PlanExecutionEvent`, or `StopEvent`). This caused the workflow server to disconnect without sending a response back to the caller.

## Solution

Added **comprehensive exception handling** to all three workflow steps by wrapping their entire bodies in try-except blocks:

### 1. `triage_email` Step
```python
@step
async def triage_email(self, ev: EmailStartEvent, ctx: Context) -> TriageEvent:
    email_data = ev.email_data
    callback = ev.callback
    
    try:
        # All operations including logging, prompt building, LLM calls
        # ...
        return TriageEvent(plan=plan, email_data=email_data, callback=callback)
    except Exception:
        logger.exception("Error during email triage")
        # Return fallback TriageEvent with simple summarization plan
        return TriageEvent(plan=fallback_plan, email_data=email_data, callback=callback)
```

**Key improvement**: Now catches exceptions from logging, prompt building, and all LLM operations, always returning a valid `TriageEvent`.

### 2. `execute_plan` Step
```python
@step
async def execute_plan(self, ev: TriageEvent, ctx: Context) -> PlanExecutionEvent:
    plan = ev.plan
    email_data = ev.email_data
    callback = ev.callback
    
    try:
        # All plan execution logic
        # ...
        return PlanExecutionEvent(results=results, email_data=email_data, callback=callback)
    except Exception as e:
        logger.exception("Fatal error in execute_plan step")
        # Return PlanExecutionEvent with error result
        return PlanExecutionEvent(
            results=[{
                "step": 0,
                "tool": "execute_plan",
                "success": False,
                "error": f"Fatal error during plan execution: {e!s}"
            }],
            email_data=email_data,
            callback=callback
        )
```

**Key improvement**: Now catches any fatal errors during plan execution setup or iteration, always returning a valid `PlanExecutionEvent`.

### 3. `send_results` Step
```python
@step
async def send_results(self, ev: PlanExecutionEvent, ctx: Context) -> StopEvent:
    email_data = ev.email_data
    callback = ev.callback
    results = ev.results
    
    try:
        # Generate response, create log, collect attachments, send callback
        # ...
        return StopEvent(result=success_result)
    except httpx.HTTPError as e:
        # Handle callback-specific errors
        return StopEvent(result=callback_failure_result)
    except Exception as e:
        # Handle all other errors
        logger.exception("Unexpected error in send_results step")
        return StopEvent(result=fatal_error_result)
```

**Key improvement**: Now wraps the entire step including response generation, log creation, and attachment collection, always returning a valid `StopEvent`.

## Additional Fixes

### Updated Validation Tests

The validation tests (`test_email_workflow_validation.py`) were checking for old event types from the pre-refactor workflow. Updated them to check for the current event structure:

**Before (old events):**
- `AttachmentFoundEvent`
- `AttachmentSummaryEvent`
- `EmailReceivedEvent`

**After (new events):**
- `EmailStartEvent`
- `TriageEvent`
- `PlanExecutionEvent`
- `EmailProcessedEvent`

## Testing

Created comprehensive test suite (`test_workflow_exception_handling.py`) with the following test cases:

1. **`test_triage_email_handles_fatal_errors`**: Verifies triage_email returns TriageEvent even when LLM fails
2. **`test_execute_plan_handles_fatal_errors`**: Verifies execute_plan returns PlanExecutionEvent when tools fail
3. **`test_execute_plan_handles_malformed_plan`**: Verifies execute_plan handles malformed plan data (e.g., None)
4. **`test_send_results_handles_fatal_errors`**: Verifies send_results returns StopEvent when response generation fails
5. **`test_send_results_handles_callback_errors`**: Verifies send_results handles HTTP callback failures gracefully
6. **`test_workflow_never_raises_unhandled_exceptions`**: Integration test verifying complete workflow execution

All tests verify that:
- Steps never raise unhandled exceptions
- Steps always return the correct event type
- Error information is properly propagated in the result objects
- The workflow can complete even when individual operations fail

## Benefits

1. **Prevents Server Disconnects**: The workflow server will always receive a proper response, even when errors occur
2. **Better Error Reporting**: Errors are captured and returned in the `EmailProcessingResult`, allowing clients to see what went wrong
3. **Graceful Degradation**: The workflow can continue processing even when individual steps fail, maximizing the chance of partial success
4. **Improved Debugging**: Comprehensive logging of exceptions makes it easier to diagnose issues

## Files Modified

1. `src/basic/email_workflow.py`:
   - Added comprehensive exception handling to `triage_email` step
   - Added comprehensive exception handling to `execute_plan` step
   - Added comprehensive exception handling to `send_results` step
   - Improved error messages to distinguish between different failure modes

2. `tests/test_email_workflow_validation.py`:
   - Updated event validation tests to check for current event structure
   - Replaced `test_process_email_step_includes_attachment_found_event_in_return_type` with `test_triage_email_step_returns_triage_event`
   - Updated `test_workflow_events_structure` to check for new event types

3. `tests/test_workflow_exception_handling.py` (new):
   - Created comprehensive test suite for exception handling
   - 6 test cases covering various error scenarios
   - Integration test verifying end-to-end resilience

## Migration Notes

No API changes or breaking changes. The fix is entirely internal to the workflow implementation. Existing callers of the workflow will automatically benefit from the improved error handling.

## Future Enhancements

While this fix addresses the immediate issue, future enhancements could include:

1. **Retry Logic**: Add retry mechanisms for transient failures (already partially implemented with `@api_retry` decorator)
2. **Circuit Breaker**: Implement circuit breaker pattern for external service calls
3. **Metrics**: Add metrics to track exception rates and identify recurring issues
4. **Alerting**: Set up alerts for high error rates or specific error types

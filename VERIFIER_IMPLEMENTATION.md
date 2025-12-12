# Response Verifier Step Implementation

## Overview

This document describes the implementation of a new verification step in the email workflow that checks and improves the final response before sending it to the user.

## Changes Made

### 1. New Event Type: `VerificationEvent`

Added a new event type to the workflow in `src/basic/email_workflow.py`:

```python
class VerificationEvent(Event):
    """Event triggered when response verification is complete."""

    verified_response: str  # Verified and potentially improved response
    results: list[dict]  # Original results from plan execution
    email_data: EmailData
    callback: CallbackConfig
```

### 2. Best Practices Constant

Defined a new constant `RESPONSE_BEST_PRACTICES` that encodes the five best practices for digital assistant responses:

```python
RESPONSE_BEST_PRACTICES = """
1. Directly respond to the user's instructions without unnecessary preambles
2. Avoid inappropriate internal comments (e.g., "Here is the draft response", "I will now...")
3. State clearly when all or part of the user's request could not be completed
4. Consider and mention potential follow-up steps when relevant
5. Provide references to key sources or files when applicable
"""
```

### 3. New Workflow Step: `verify_response`

Added a new step between `execute_plan` and `send_results`:

**Location in workflow:**
- **Input:** `PlanExecutionEvent` (from execute_plan)
- **Output:** `VerificationEvent` (to send_results)

**Functionality:**
1. Generates an initial response using `_generate_user_response`
2. Constructs a verification prompt that includes:
   - The best practices
   - The original user email
   - The generated response
3. Uses the LLM to review and improve the response
4. Falls back to the original response if verification fails

**Error Handling:**
- Handles `asyncio.TimeoutError` explicitly
- Catches all exceptions and provides fallback responses
- Always returns a valid `VerificationEvent`
- Logs warnings and errors appropriately

### 4. Updated Workflow Flow

**Previous flow:**
```
EmailStartEvent -> TriageEvent -> PlanExecutionEvent -> StopEvent
```

**New flow:**
```
EmailStartEvent -> TriageEvent -> PlanExecutionEvent -> VerificationEvent -> StopEvent
```

### 5. Integration of Best Practices

The best practices are now incorporated in three places:

1. **`_build_triage_prompt`**: Includes best practices to guide plan creation
2. **`verify_response`**: Uses best practices to verify and improve responses  
3. **`_generate_user_response`**: Includes best practices in the response generation prompt

### 6. Updated `send_results` Step

Modified to:
- Accept `VerificationEvent` instead of `PlanExecutionEvent`
- Use the `verified_response` from the verification step
- No longer generates a response (that's done in verify_response)

## Testing

Created comprehensive tests in `tests/test_verifier_step.py`:

1. **AST-based validation tests:**
   - `test_verification_event_exists`: Verifies VerificationEvent class exists
   - `test_verify_response_step_exists`: Verifies the step method exists
   - `test_verify_response_returns_verification_event`: Checks return type
   - `test_send_results_accepts_verification_event`: Checks input type updated
   - `test_best_practices_constant_exists`: Verifies constant defined

2. **Execution tests with mocked LLM:**
   - `test_verify_response_step_execution`: Tests normal execution
   - `test_verify_response_handles_empty_llm_response`: Tests empty response handling
   - `test_verify_response_handles_llm_exception`: Tests exception handling

3. **Integration documentation tests** in `tests/test_verifier_integration.py`:
   - Documents expected improvements
   - Verifies best practices checklist
   - Validates workflow flow

Also updated `tests/test_email_workflow_validation.py` to include `VerificationEvent` in the required events list.

## Benefits

1. **Improved Response Quality**: LLM reviews responses for adherence to best practices
2. **Consistency**: All responses follow the same guidelines
3. **Error Recovery**: Falls back gracefully if verification fails
4. **Transparency**: Users receive clearer, more direct responses
5. **Better UX**: Responses state clearly what was completed and suggest next steps

## Implementation Details

### Error Handling Strategy

The `verify_response` step uses defensive programming:

1. **Nested try-except blocks**: Outer block catches step-level errors, inner block catches LLM-specific errors
2. **Timeout handling**: Explicitly handles `asyncio.TimeoutError` before generic `Exception`
3. **Fallback chain**:
   - Try to verify response with LLM
   - If verification fails, use original response
   - If original response generation fails, use generic fallback
4. **Sanity checks**: Validates that verified response is not empty/too short

### LLM Retry Integration

The verification uses `_llm_complete_with_retry` which is decorated with `@api_retry`:
- 5 total attempts (1 initial + 4 retries)
- Exponential backoff: 1s, 2s, 4s, 8s

This ensures transient LLM API errors are handled automatically.

## Backward Compatibility

This change modifies the workflow event flow, which affects:

1. **Workflow server**: Will use the new flow automatically
2. **Tests**: Updated to expect `VerificationEvent`
3. **Existing callbacks**: Not affected - they receive the same final result structure

## Future Enhancements

Potential improvements for future iterations:

1. **Configurable best practices**: Allow customization per deployment
2. **Verification metrics**: Track how often responses are improved
3. **A/B testing**: Compare verified vs. unverified responses
4. **User feedback loop**: Learn from user responses to improve verification
5. **Multi-turn verification**: Allow for iterative improvement

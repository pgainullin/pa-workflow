# Workflow Not Responding Fix

## Issue Summary

After the latest changes (PR #101), the workflow stopped responding. The StartEvent was being delivered successfully, but the StopEvent never triggered the callback, indicating that an error was occurring during workflow execution.

## Root Cause Analysis

### Problem: @observe Decorator Interference

The Langfuse `@observe` decorator was applied to all workflow step methods:

```python
@step
@observe(name="triage_email")
async def triage_email(self, ev: EmailStartEvent, ctx: Context) -> TriageEvent:
    ...
```

The `@observe` decorator wraps the function in a way that **obscures the function's type annotations**. This is a critical issue because the llama-index-workflows library relies heavily on these annotations to:

1. **Determine input event types**: The workflow system uses parameter type annotations to understand which events should be routed to which step
2. **Determine output event types**: Return type annotations tell the workflow system what events a step can emit
3. **Build the event routing graph**: Without proper annotations, the workflow cannot route events between steps

### Technical Details

When a decorator wraps a function without properly using `functools.wraps`, the wrapper function loses the original function's metadata, including `__annotations__`:

```python
# Original function
async def my_step(self, ev: InputEvent) -> OutputEvent:
    ...

# After @observe wrapping (without functools.wraps)
# The wrapper's __annotations__ is empty: {}
# The workflow system cannot determine event routing
```

This caused the workflow to hang after receiving the StartEvent because it couldn't determine:
- Which step should handle the StartEvent
- What event type each step returns
- How to route events through the workflow pipeline

## Solution

### Changes Made

1. **Removed `@observe` decorators from all workflow steps**:
   - `src/basic/email_workflow.py`: Removed from 4 steps (triage_email, execute_plan, verify_response, send_results)
   - `src/basic/workflow.py`: Removed from 1 step (hello)

2. **Updated imports**: Removed unused `observe` import from workflow files

3. **Updated documentation**: Added warning in `observability.py` about not using `@observe` on workflow steps

### Code Changes

**Before:**
```python
from .observability import observe, flush_langfuse, setup_observability

class EmailWorkflow(Workflow):
    @step
    @observe(name="triage_email")
    async def triage_email(self, ev: EmailStartEvent, ctx: Context) -> TriageEvent:
        ...
```

**After:**
```python
from .observability import flush_langfuse, setup_observability

class EmailWorkflow(Workflow):
    @step
    async def triage_email(self, ev: EmailStartEvent, ctx: Context) -> TriageEvent:
        ...
```

## Observability Preserved

Observability is maintained through multiple mechanisms that don't interfere with workflow event routing:

### 1. LlamaIndex Callback Handler
The `LlamaIndexCallbackHandler` from Langfuse is configured in `setup_observability()` and automatically captures:
- LLM API calls (prompts, responses, tokens)
- Embedding operations
- Retrieval operations

This works through `Settings.callback_manager`, which the LlamaIndex SDK uses internally.

### 2. Python Logging Handler
The `LangfuseLoggingHandler` forwards all Python log messages to Langfuse:
- Workflow execution logs (logger.info, logger.warning, logger.error)
- Tool execution logs
- Error traces

### 3. Manual Flushing
`flush_langfuse()` is still called after each step to ensure traces are sent immediately:
- Prevents trace loss in short-lived processes
- Ensures traces appear in Langfuse dashboard promptly
- Works with both callback handler and logging handler

## Impact

### What Still Works
- ✅ All LLM calls are traced (via LlamaIndex callback handler)
- ✅ All workflow logs are captured (via Python logging handler)
- ✅ Traces are flushed after each step
- ✅ Workflow event routing now functions correctly
- ✅ StartEvent → TriageEvent → PlanExecutionEvent → VerificationEvent → StopEvent flow

### What Changed
- ❌ Individual workflow step functions are no longer wrapped with `@observe`
- ℹ️ Step-level tracing can be added back using a compatible approach if needed

## Testing

### Validation Steps

1. **Type annotation verification**: The existing test `test_email_workflow_validation.py` validates that step methods have proper return type annotations

2. **Event routing verification**: Create a simple test workflow to verify events are properly routed

3. **End-to-end test**: Run a full email workflow to ensure StartEvent → StopEvent flow works

### Test Commands

```bash
# Run workflow validation tests
pytest tests/test_email_workflow_validation.py -v

# Run full test suite
pytest tests/ -v
```

## Prevention

### Best Practices

1. **Avoid decorators on workflow steps**: Only use the `@step` decorator on workflow step methods

2. **If tracing is needed**: Use the LlamaIndex callback handler approach, which doesn't interfere with function signatures

3. **Document decorator limitations**: The observability.py module now includes a warning about this issue

### Alternative Approaches for Step-Level Tracing

If step-level tracing is needed in the future, consider these approaches:

1. **Manual tracing within steps**: Call Langfuse client directly within step methods
   ```python
   @step
   async def my_step(self, ev: Event, ctx: Context) -> OutputEvent:
       from langfuse import Langfuse
       langfuse = Langfuse()
       trace = langfuse.trace(name="my_step")
       # ... step logic ...
       trace.update(output=result)
   ```

2. **Custom decorator with functools.wraps**: Create a decorator that properly preserves annotations
   ```python
   import functools
   
   def trace_step(name: str):
       def decorator(func):
           @functools.wraps(func)  # Preserves __annotations__
           async def wrapper(*args, **kwargs):
               # Tracing logic
               return await func(*args, **kwargs)
           return wrapper
       return decorator
   ```

3. **Workflow-level tracing**: Use workflow context to track execution without decorating individual steps

## Related Files

- `src/basic/email_workflow.py`: Main workflow with step methods
- `src/basic/workflow.py`: Basic workflow template
- `src/basic/observability.py`: Observability configuration
- `tests/test_email_workflow_validation.py`: Type annotation validation tests

## References

- Issue: "Workflow not responding post latest changes"
- PR #101: "Handle missing file gracefully in ParseTool and SheetsTool" (introduced the issue)
- llama-index-workflows: Event routing relies on function type annotations
- Langfuse decorators: https://langfuse.com/docs/sdk/python/decorators

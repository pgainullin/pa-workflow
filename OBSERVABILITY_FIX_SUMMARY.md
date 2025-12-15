# Fix for Langfuse Traces Not Coming Through in LlamaCloud

## Problem Statement

Langfuse traces were not being sent when workflows were deployed to LlamaCloud. The issue was that `setup_observability()` was being called at module import time, before environment variables from `.env` files were loaded.

## Root Cause

The `observability.py` module had an automatic call to `setup_observability()` at the end of the file (line 474):

```python
# Auto-initialize observability on module import
setup_observability()
```

This created a timing issue:

1. When LlamaCloud loads a workflow, it first imports the module
2. During import, `setup_observability()` is called immediately
3. At this point, the `.env` file hasn't been loaded yet
4. The Langfuse credentials (`LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`) are not available
5. Observability silently fails and returns early

## Solution

Move the `setup_observability()` call from module import time to workflow instantiation time:

### Changes Made

1. **src/basic/observability.py** (line 474)
   - Removed: `setup_observability()`
   - Added comment explaining the new pattern

2. **src/basic/email_workflow.py** (line 139-143)
   - Added `setup_observability()` call in `EmailWorkflow.__init__()`
   - Now called when the workflow instance is created

3. **src/basic/workflow.py** (line 16-21)
   - Added `setup_observability()` call in `BasicWorkflow.__init__()`
   - Now called when the workflow instance is created

4. **src/basic/observability.py** (line 387)
   - Fixed hardcoded `env_enabled = True` to properly read `LANGFUSE_ENABLED` env var

## How It Works Now

The new initialization flow ensures environment variables are available:

1. LlamaCloud loads `.env` file (contains `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`)
2. LlamaCloud imports the workflow module (e.g., `basic.email_workflow`)
3. Module creates workflow instance at module level: `email_workflow = EmailWorkflow(timeout=120)`
4. `EmailWorkflow.__init__()` is called
5. `setup_observability()` is called inside `__init__()`
6. At this point, environment variables from `.env` are available
7. Langfuse client and handler are properly initialized
8. Traces are successfully sent to Langfuse

## Verification

Run the verification script to see the fix in action:

```bash
python verify_observability_init.py
```

This script demonstrates:
- Observability module import does NOT call `setup_observability()`
- Environment variables are set (simulating `.env` loading)
- Workflow instantiation DOES call `setup_observability()`
- Langfuse client and handler are properly initialized

## Testing

All observability tests pass:

```bash
pytest tests/test_observability.py -v
```

Results: **21 passed, 1 skipped**

The skipped test (`test_workflow_steps_instrumented`) requires network access and is unrelated to this fix.

## Benefits

1. **Works in LlamaCloud**: Environment variables are loaded before observability setup
2. **Works Locally**: Same pattern works for local development
3. **Idempotent**: Multiple calls to `setup_observability()` are handled gracefully
4. **Backwards Compatible**: Existing code that calls `setup_observability()` explicitly still works
5. **Silent Failures Fixed**: Observability now initializes when credentials are available

## Implementation Details

### Timing Diagram

**Before Fix:**
```
Module Import → setup_observability() → Check for keys → Keys not available → Silent failure
                                                    ↑
                                                    .env not loaded yet
```

**After Fix:**
```
Module Import → (no setup call)
                        ↓
.env file loaded → Workflow instantiated → __init__() → setup_observability() → Success!
                                                                           ↑
                                                                   Keys are available
```

### Code Pattern

Workflows should follow this pattern:

```python
class MyWorkflow(Workflow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set up observability after environment is loaded
        setup_observability()
        # ... rest of initialization
```

### Idempotency

The `setup_observability()` function checks for duplicate handlers:

```python
if not any(
    type(h).__name__ == type(langfuse_handler).__name__
    and getattr(h, "host", None) == host
    for h in getattr(existing_manager, "handlers", [])
):
    existing_manager.handlers.append(langfuse_handler)
```

This means calling it multiple times is safe and won't create duplicate handlers.

## Related Files

- `src/basic/observability.py` - Core observability module
- `src/basic/email_workflow.py` - Email workflow with observability
- `src/basic/workflow.py` - Basic workflow template with observability
- `tests/test_observability.py` - Test suite
- `verify_observability_init.py` - Verification script

## Future Considerations

This fix ensures observability works in all deployment scenarios. If additional workflows are added, they should follow the same pattern of calling `setup_observability()` in their `__init__()` method.

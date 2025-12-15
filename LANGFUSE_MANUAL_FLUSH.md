# Langfuse Manual Flushing - Fix for Missing Traces

## Problem

Langfuse traces may not appear in the dashboard even when environment variables are correctly configured. This happens because:

1. **Langfuse uses background workers** - Traces are batched and sent asynchronously for performance
2. **Events are queued** - Rather than sending immediately, events are queued and sent in batches
3. **Process exit timing** - If the process exits before background workers complete, traces may be lost
4. **Async contexts** - The `atexit` handler may not fire reliably in async applications or server contexts

Reference: https://langfuse.com/faq/all/missing-traces

## Solution

We've added manual flushing support to ensure all traces are sent immediately to Langfuse.

### API Reference

#### `flush_langfuse()`

Manually flush all buffered Langfuse events to the API. This blocks until all events are sent.

```python
from basic.observability import flush_langfuse

# Run your workflow
result = await workflow.run(...)

# Ensure all traces are sent immediately
flush_langfuse()
```

**Characteristics:**
- No-op if Langfuse is not configured or disabled
- Safe to call multiple times
- Blocks until all events are sent (typically < 1 second)
- Flushes both `LlamaIndexCallbackHandler` (LLM traces) and `Langfuse` client (logs and @observe traces)
- Handles errors gracefully without raising exceptions

#### `run_workflow_with_flush(workflow, *args, **kwargs)`

Convenience wrapper that runs a workflow and automatically flushes traces after completion.

```python
from basic.observability import run_workflow_with_flush
from basic.email_workflow import email_workflow

# This will automatically flush traces after execution
result = await run_workflow_with_flush(
    email_workflow,
    email_data=email_data,
    callback=callback
)
```

**Characteristics:**
- Runs `workflow.run(*args, **kwargs)`
- Always flushes traces in a `finally` block (even if workflow fails)
- Returns the same result as `workflow.run()`
- Recommended approach for running workflows with Langfuse

### Automatic Flushing in Workflow Steps

**NEW**: All workflow steps now automatically flush traces after completion. This ensures traces are sent immediately after each step, regardless of execution context (server, LlamaCloud, or standalone).

**Workflow Steps with Auto-Flush:**
- `email_workflow.triage_email` - Flushes after email triage and plan generation
- `email_workflow.execute_plan` - Flushes after executing all tool steps
- `email_workflow.verify_response` - Flushes after response verification
- `email_workflow.send_results` - Flushes after sending final results
- `workflow.hello` - Flushes after basic workflow step

**Benefits:**
- ✅ Works in LlamaCloud execution environment
- ✅ No manual flush needed for standard workflow execution
- ✅ Traces appear immediately after each step completes
- ✅ Robust error handling - flushes even on step failures

**Note**: When workflows run in LlamaCloud or via WorkflowServer, the automatic per-step flushing ensures all traces are captured, even if the workflow is interrupted or times out.

## Usage Examples

### Example 1: Simple Script

```python
import asyncio
from basic.workflow import workflow
from basic.observability import flush_langfuse

async def main():
    # Run workflow
    result = await workflow.run()
    print(f"Result: {result}")
    
    # Flush traces before exit
    flush_langfuse()
    
    return result

if __name__ == "__main__":
    asyncio.run(main())
```

### Example 2: Using the Wrapper

```python
import asyncio
from basic.email_workflow import email_workflow
from basic.observability import run_workflow_with_flush

async def main():
    # Automatically flushes after completion
    result = await run_workflow_with_flush(
        email_workflow,
        email_data=email_data,
        callback=callback
    )
    return result

if __name__ == "__main__":
    asyncio.run(main())
```

### Example 3: Multiple Workflows

```python
import asyncio
from basic.observability import flush_langfuse
from basic.workflow import workflow
from basic.email_workflow import email_workflow

async def main():
    # Run multiple workflows
    result1 = await workflow.run()
    result2 = await email_workflow.run(...)
    
    # Flush all traces at the end
    flush_langfuse()
    
    return result1, result2

if __name__ == "__main__":
    asyncio.run(main())
```

### Example 4: Server with Graceful Shutdown

The server (`src/basic/server.py`) is already configured to flush on shutdown:

```python
import asyncio
import atexit
import signal
from workflows.server import WorkflowServer
from basic.observability import flush_langfuse

# Register shutdown handler
atexit.register(lambda: flush_langfuse())

async def main():
    loop = asyncio.get_event_loop()
    
    def signal_handler(sig):
        flush_langfuse()
        loop.stop()
    
    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
    
    try:
        await server.serve(host="127.0.0.1", port=8080)
    finally:
        flush_langfuse()
```

## Best Practices

### 1. Always Flush After Workflow Execution

```python
# ✅ Good
result = await workflow.run()
flush_langfuse()

# ❌ Bad - traces may be lost
result = await workflow.run()
# No flush - process exits before traces are sent
```

### 2. Use Wrapper for Automatic Flushing

```python
# ✅ Good - automatic flush even on error
result = await run_workflow_with_flush(workflow)

# ⚠️ Okay - manual flush
result = await workflow.run()
flush_langfuse()
```

### 3. Flush in Finally Blocks

```python
try:
    result = await workflow.run()
finally:
    # Ensure flush even if workflow fails
    flush_langfuse()
```

### 4. Server Deployments

For long-running servers:
- Use signal handlers to flush on SIGTERM/SIGINT
- Use atexit handlers as a fallback
- Consider periodic flushing for very long-running processes

## Implementation Details

### What Gets Flushed

1. **LlamaIndexCallbackHandler** - Captures LLM traces from `llm.acomplete()` and similar calls
2. **Langfuse Client** - Captures:
   - Log events from Python logging (`logger.info()`, `logger.warning()`, etc.)
   - Traces from `@observe` decorated functions
   - Manual trace/span/generation calls

### Flush Order

```python
def flush_langfuse():
    # 1. Flush callback handler first (LLM traces)
    if _langfuse_handler is not None:
        _langfuse_handler.flush()
    
    # 2. Then flush client (logs and @observe traces)
    if _langfuse_client is not None:
        _langfuse_client.flush()
```

The handler is flushed first because it may create additional events that need to be captured by the client.

### Error Handling

```python
try:
    _langfuse_handler.flush()
    _langfuse_client.flush()
except Exception as e:
    # Log warning but don't raise
    logger.warning(f"Error flushing Langfuse traces: {e}")
```

Errors during flushing are caught and logged as warnings to prevent application crashes.

## Troubleshooting

### Traces Still Not Appearing?

1. **Check environment variables:**
   ```bash
   echo $LANGFUSE_SECRET_KEY
   echo $LANGFUSE_PUBLIC_KEY
   echo $LANGFUSE_HOST
   ```

2. **Verify observability is enabled:**
   ```python
   from basic import observability
   print(observability._langfuse_client)  # Should not be None
   print(observability._langfuse_handler)  # Should not be None
   ```

3. **Check logs for errors:**
   ```bash
   # Look for ERROR messages about Langfuse
   grep -i "langfuse" your_log_file.log
   ```

4. **Test manual flush:**
   ```python
   from basic.observability import flush_langfuse
   
   # This should complete without errors
   flush_langfuse()
   print("Flush completed successfully")
   ```

5. **Verify network connectivity:**
   ```bash
   # Test connection to Langfuse host
   curl -I https://cloud.langfuse.com
   ```

### Flush Takes Too Long?

If `flush_langfuse()` blocks for more than a few seconds:

1. **Check network latency** - Langfuse API may be slow or unreachable
2. **Check queue size** - Large number of buffered events may take time to send
3. **Consider async flushing** - For very large batches, consider background flushing

### Traces Appear Delayed?

Without manual flushing, traces appear when:
- The batch size threshold is reached (~100 events)
- The time threshold is reached (~5 seconds)
- The process exits and atexit handler fires

Manual flushing ensures immediate delivery regardless of these thresholds.

## Migration Guide

### Before (Traces May Be Lost)

```python
# Old code - relies on atexit only
import asyncio
from basic.workflow import workflow

async def main():
    result = await workflow.run()
    return result

if __name__ == "__main__":
    asyncio.run(main())
```

### After (Traces Guaranteed)

```python
# New code - manual flush ensures delivery
import asyncio
from basic.workflow import workflow
from basic.observability import flush_langfuse

async def main():
    result = await workflow.run()
    flush_langfuse()  # Add this line
    return result

if __name__ == "__main__":
    asyncio.run(main())
```

Or use the wrapper:

```python
# Alternative - automatic flush
import asyncio
from basic.workflow import workflow
from basic.observability import run_workflow_with_flush

async def main():
    result = await run_workflow_with_flush(workflow)
    return result

if __name__ == "__main__":
    asyncio.run(main())
```

## Summary

- **Problem**: Traces not appearing due to async batching
- **Solution**: Manual flushing with `flush_langfuse()`
- **Best Practice**: Use `run_workflow_with_flush()` wrapper
- **Server Deployments**: Signal handlers and atexit for graceful shutdown
- **Testing**: 6 comprehensive tests validate flush behavior
- **Compatibility**: No-op when Langfuse not configured, safe to call anywhere

For more information:
- Langfuse FAQ: https://langfuse.com/faq/all/missing-traces
- Langfuse Python SDK: https://langfuse.com/docs/sdk/python
- Observability module: `src/basic/observability.py`

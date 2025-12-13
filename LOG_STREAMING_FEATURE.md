# Log Streaming Feature for Langfuse

## Overview

This document describes the log streaming feature that was added to make workflow logs visible in Langfuse alongside traces.

---

## Problem Statement

**User Request**: "only server logs are visible to me in llamactl, stream all the workflow logs to langfuse"

**Background**: 
- LLM traces were being captured by Langfuse callback handler
- Python log messages (logger.info, logger.warning, logger.error) were not visible in Langfuse
- Users could only see server logs in llamactl, not workflow execution logs

---

## Solution

Created a custom `LangfuseLoggingHandler` that forwards Python log messages to Langfuse in real-time.

### Key Features

1. **Automatic Log Capture**
   - Captures all `logger.info()`, `logger.warning()`, `logger.error()` calls
   - Works for all workflow modules (email_workflow, tools, utils, etc.)
   - No code changes needed in workflows

2. **Rich Metadata**
   - Log level (INFO, WARNING, ERROR)
   - Logger name
   - Module, function, and line number
   - Exception information when present

3. **Trace Integration**
   - Logs are linked to active traces when available
   - Uses `langfuse_context` to attach logs to current trace
   - Falls back to standalone events when no active trace

4. **Robust Error Handling**
   - Specific exception handling (ImportError, AttributeError)
   - Graceful fallback mechanisms
   - Preserves existing logging configurations
   - Never breaks workflow execution

---

## Implementation Details

### LangfuseLoggingHandler Class

```python
class LangfuseLoggingHandler(logging.Handler):
    """Custom logging handler that forwards logs to Langfuse as events."""
    
    def __init__(self, langfuse_client, level=logging.INFO):
        super().__init__(level)
        self.langfuse_client = langfuse_client
        
    def emit(self, record: logging.LogRecord) -> None:
        # 1. Format the log message
        # 2. Extract metadata from log record
        # 3. Try to attach to current trace
        # 4. Fallback to standalone event if needed
```

### Setup Process

1. **Handler Creation**: When `setup_observability()` is called, it creates:
   - Langfuse client instance
   - LlamaIndexCallbackHandler for LLM traces
   - LangfuseLoggingHandler for Python logs

2. **Logger Configuration**: The handler is automatically added to:
   - `basic.email_workflow`
   - `basic.workflow`
   - `basic.tools`
   - `basic.utils`
   - `basic.response_utils`
   - `basic.plan_utils`

3. **Smart Propagation**: 
   - Only disables propagation if it's the logger's only handler
   - Preserves existing logging configurations
   - Prevents duplicate log entries

### Log Flow

```
Workflow Code
    |
    v
logger.info("Processing step 1")
    |
    v
LangfuseLoggingHandler.emit()
    |
    +-- Try: langfuse_context.update_current_trace()
    |   (attaches to active trace)
    |
    +-- Fallback: langfuse_client.event()
        (creates standalone event)
    |
    v
Langfuse Dashboard
```

---

## Usage

### Automatic (No Code Changes)

Simply import observability in your workflow:

```python
from basic import observability  # Auto-enables log streaming

logger = logging.getLogger('basic.email_workflow')
logger.info("This message will appear in Langfuse")
```

### What Appears in Langfuse

**Before** (only traces):
```
Trace: Workflow Execution
├─ LLM Call: Triage
├─ LLM Call: Generate Response
└─ [No workflow logs visible]
```

**After** (traces + logs):
```
Trace: Workflow Execution
├─ LLM Call: Triage
├─ Log: [INFO] Starting workflow execution
├─ Log: [INFO] Processing step 1: Triage
├─ LLM Call: Generate Response
├─ Log: [INFO] Processing step 2: Execution
├─ Log: [WARNING] API rate limit approaching
└─ Log: [INFO] Workflow completed
```

---

## Configuration

Log streaming is automatically enabled when:
1. `LANGFUSE_SECRET_KEY` is set
2. `LANGFUSE_PUBLIC_KEY` is set
3. `llama-index-callbacks-langfuse` package is installed

No additional configuration needed!

---

## Testing

### Automated Test

```python
def test_logging_handler_configured():
    """Verify logging handler is added to workflow loggers."""
    setup_observability()
    
    workflow_logger = logging.getLogger('basic.email_workflow')
    has_langfuse_handler = any(
        isinstance(h, LangfuseLoggingHandler) 
        for h in workflow_logger.handlers
    )
    
    assert has_langfuse_handler
```

### Manual Test

```bash
python test_log_streaming.py
```

This sends test log messages to Langfuse and shows them being captured.

---

## Benefits

### For Users
- ✅ Complete visibility into workflow execution
- ✅ See both LLM traces and workflow logs in one place
- ✅ Better debugging with contextual information
- ✅ Timeline view of entire workflow execution

### For Developers
- ✅ No code changes required in workflows
- ✅ Automatic configuration
- ✅ Works with existing logging infrastructure
- ✅ Preserves logging best practices

---

## Performance Considerations

1. **Minimal Overhead**: Log messages are sent asynchronously to Langfuse
2. **Graceful Degradation**: If Langfuse is unavailable, logs still work normally
3. **Smart Import**: Langfuse context is imported per-call to avoid overhead
4. **Batch Processing**: Langfuse SDK handles batching internally

---

## Troubleshooting

### Logs Not Appearing in Langfuse

1. **Check credentials**:
   ```bash
   echo $LANGFUSE_SECRET_KEY
   echo $LANGFUSE_PUBLIC_KEY
   ```

2. **Verify handler is configured**:
   ```python
   import logging
   logger = logging.getLogger('basic.email_workflow')
   print(logger.handlers)  # Should include LangfuseLoggingHandler
   ```

3. **Check for errors**:
   ```bash
   python test_log_streaming.py
   ```

### Performance Issues

If logging impacts performance:
- Check network connectivity to Langfuse
- Consider increasing batch size in Langfuse client
- Temporarily disable by setting `LANGFUSE_ENABLED=false`

---

## Future Enhancements

Potential improvements:
1. **Configurable Log Levels**: Allow users to set minimum log level via env var
2. **Log Filtering**: Filter sensitive data from logs before sending
3. **Sampling**: Only send a percentage of logs to reduce volume
4. **Custom Formatters**: Allow users to customize log format

---

## Conclusion

The log streaming feature provides complete observability for workflows by capturing Python log messages alongside LLM traces in Langfuse. This gives users the full picture of workflow execution, making debugging and monitoring much easier.

**Result**: Users can now see all workflow logs in Langfuse, not just server logs in llamactl. ✅

---

**Implementation Date**: 2025-12-13  
**Implemented By**: GitHub Copilot Agent  
**Commits**: e10b442, 7f8f86a, 8554ff8

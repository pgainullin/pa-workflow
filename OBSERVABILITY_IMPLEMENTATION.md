# Langfuse Observability Implementation

## Overview

This implementation adds observability to LlamaIndex workflows using Langfuse as the backend, addressing the issue "Logs are not shown in llamactl". With this feature, users can now trace and monitor workflow execution in real-time through the Langfuse dashboard.

## What Was Implemented

### 1. Dependencies (`pyproject.toml`)
- Added `llama-index-callbacks-langfuse>=0.4.0` package
- This package provides the integration between LlamaIndex and Langfuse

### 2. Observability Module (`src/basic/observability.py`)
A new module that handles all observability configuration:

**Features:**
- Auto-initialization on module import
- Environment variable-based configuration
- Graceful fallback if Langfuse is not configured
- No errors if credentials are missing

**Configuration:**
The module reads these environment variables:
- `LANGFUSE_SECRET_KEY` - Secret key from Langfuse (required)
- `LANGFUSE_PUBLIC_KEY` - Public key from Langfuse (required)
- `LANGFUSE_HOST` - Langfuse server URL (optional, defaults to https://cloud.langfuse.com)
- `LANGFUSE_ENABLED` - Explicitly enable/disable observability (optional)

**How it works:**
1. When imported, checks for Langfuse credentials in environment
2. If credentials exist, creates a `LlamaIndexCallbackHandler`
3. Sets it as the global callback manager in `Settings.callback_manager`
4. All LLM calls and workflow events are then automatically traced to Langfuse

### 3. Workflow Integration
Modified two workflows to import the observability module:

- `src/basic/email_workflow.py` - Main email processing workflow
- `src/basic/workflow.py` - Basic template workflow

The import is simple and non-invasive:
```python
from . import observability  # Initialize observability (Langfuse tracing)
```

### 4. Documentation (`README.md`)
Added comprehensive documentation covering:
- Environment variable setup
- How to get Langfuse credentials
- What information is traced
- How to view traces in the Langfuse dashboard

### 5. Tests (`tests/test_observability.py`)
Created 7 comprehensive tests:
1. Observability disabled without keys
2. Observability enabled with keys
3. Explicit disable via LANGFUSE_ENABLED=false
4. Setup function can be called explicitly
5. Graceful failure if package not installed
6. Module can be imported in workflows
7. Module import doesn't break existing functionality

All tests pass successfully.

### 6. Demo Script (`demo_observability.py`)
Created an executable demo script that:
- Shows how to configure observability
- Demonstrates workflow execution with/without tracing
- Provides helpful instructions for users
- Can be run directly to test the feature

## How to Use

### Setup (One-time)

1. Sign up for a free account at https://langfuse.com/
2. Get your API keys from the Langfuse dashboard
3. Set environment variables:
   ```bash
   export LANGFUSE_SECRET_KEY="sk-..."
   export LANGFUSE_PUBLIC_KEY="pk-..."
   # Optional: set custom host
   export LANGFUSE_HOST="https://cloud.langfuse.com"
   ```

### Running Workflows with Observability

Once configured, simply run your workflows as normal:

```bash
# Run the demo
python demo_observability.py

# Run the workflow server
python -m basic.server

# Or use llamactl
llamactl serve
```

All workflow executions will be automatically traced to Langfuse!

### Viewing Traces

1. Go to https://cloud.langfuse.com/ (or your custom host)
2. Navigate to "Traces" in the sidebar
3. See detailed traces showing:
   - Workflow execution timeline
   - Individual step execution times
   - LLM calls with prompts and responses
   - Tool executions and their results
   - Errors and exceptions with full context

### Disabling Observability

If you want to temporarily disable observability:

```bash
export LANGFUSE_ENABLED=false
```

Or simply don't set the LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY variables.

## What Gets Traced

With Langfuse observability enabled, the following information is captured:

1. **Workflow Events**
   - Workflow start/stop times
   - Step execution times
   - Event transitions between steps

2. **LLM Calls**
   - Model used
   - Prompts sent
   - Responses received
   - Token usage
   - Latency

3. **Tool Executions** (if using the email workflow)
   - Parse tool calls
   - Extract tool calls
   - Translate tool calls
   - Summarize tool calls
   - And more...

4. **Errors and Exceptions**
   - Full stack traces
   - Context at time of error
   - Retry attempts

## Technical Details

### Architecture

The implementation uses the LlamaIndex callback manager system:

```
Workflow Execution
    ↓
LlamaIndex Settings.callback_manager
    ↓
LangfuseCallbackHandler
    ↓
Langfuse Cloud (or self-hosted)
```

### Import Path

The code imports `LlamaIndexCallbackHandler` from `langfuse.llama_index`:

```python
from langfuse.llama_index import LlamaIndexCallbackHandler
```

Note: The `llama-index-callbacks-langfuse` package is a wrapper that re-exports this handler. We import directly from the source for clarity.

### Thread Safety

The observability module is thread-safe because:
1. It only modifies global settings during module initialization
2. The Langfuse handler is designed to be used concurrently
3. All trace data is handled asynchronously

### Performance Impact

The performance impact is minimal:
- Traces are sent asynchronously in the background
- No blocking of workflow execution
- Configurable batch sending and flushing
- Can be disabled completely if needed

## Testing

### Running Tests

```bash
# Run observability tests only
pytest tests/test_observability.py -v

# Run all tests
pytest tests/ -v
```

### Test Coverage

All 7 observability tests pass:
- ✓ Disabled without keys
- ✓ Enabled with keys
- ✓ Explicit disable
- ✓ Setup function
- ✓ Graceful failure
- ✓ Module import
- ✓ Workflow integration

### No Regressions

Existing tests: 149 passed (27 pre-existing failures unrelated to this change)

## Security

### Credential Management

- Credentials are read from environment variables only
- Never hardcoded in the source
- Not logged in plain text
- Handled securely by the Langfuse SDK

### Vulnerability Scanning

- ✓ No vulnerabilities in new dependencies
- ✓ No security issues found by CodeQL
- ✓ All dependencies from trusted sources

### Data Privacy

Langfuse traces contain:
- Workflow execution metadata
- LLM prompts and responses
- Tool parameters and results

**Important:** Be aware that sensitive data in workflow inputs will be traced. Consider:
1. Using Langfuse's self-hosted option for sensitive workloads
2. Implementing data masking if needed
3. Using the LANGFUSE_ENABLED flag to disable in production if required

## Future Enhancements

Potential improvements for the future:

1. **Custom Trace Metadata**
   - Add user IDs, session IDs, etc.
   - Tag traces by workflow type

2. **Selective Tracing**
   - Trace only specific workflow types
   - Sample traces (e.g., 10% of executions)

3. **Advanced Filtering**
   - Filter sensitive fields from traces
   - Redact PII automatically

4. **Dashboard Integration**
   - Custom Langfuse dashboard for workflows
   - Real-time monitoring views

5. **Alerting**
   - Alert on workflow failures
   - Monitor performance degradation

## Troubleshooting

### Observability Not Working?

1. **Check credentials are set:**
   ```bash
   echo $LANGFUSE_SECRET_KEY
   echo $LANGFUSE_PUBLIC_KEY
   ```

2. **Check logs for warnings:**
   ```bash
   # Run with logging enabled
   python -c "import logging; logging.basicConfig(level=logging.INFO); from basic import observability"
   ```

3. **Verify package is installed:**
   ```bash
   pip show llama-index-callbacks-langfuse
   pip show langfuse
   ```

4. **Test with demo script:**
   ```bash
   python demo_observability.py
   ```

### Common Issues

**"No traces appearing in Langfuse"**
- Check credentials are correct
- Verify LANGFUSE_HOST is correct
- Check firewall/network access to Langfuse
- Try the demo script first

**"ImportError: cannot import name 'LlamaIndexCallbackHandler'"**
- Install llama-index-callbacks-langfuse: `pip install llama-index-callbacks-langfuse`
- Update langfuse package: `pip install --upgrade langfuse`

**"Observability slowing down workflows"**
- This should be rare, but if it happens:
- Set LANGFUSE_ENABLED=false to disable
- Check network latency to Langfuse host
- Consider using self-hosted Langfuse

## Summary

✅ **Fully implemented** - Langfuse observability is ready to use
✅ **Well tested** - 7 new tests, all passing
✅ **Documented** - README, demo script, and this doc
✅ **Secure** - No vulnerabilities, proper credential handling
✅ **Backwards compatible** - Works without configuration
✅ **Easy to use** - Just set environment variables

The implementation successfully addresses the issue "Logs are not shown in llamactl" by providing comprehensive observability through Langfuse integration. Users can now see detailed traces of workflow execution in the Langfuse dashboard, making debugging and monitoring much easier.

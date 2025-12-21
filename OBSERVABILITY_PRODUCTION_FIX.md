# Observability Fixes for Production

## 1. Missing Traces in Production (LlamaCloud)

The primary reason you are seeing traces in development but **not in production** is likely missing environment variables in the LlamaCloud environment.

LlamaCloud runs your code in a managed environment that does **not** automatically inherit your local `.env` file.

### **Action Required:**
You must manually add the following **Secrets** in your LlamaCloud project settings (Deployment -> Settings -> Environment Variables / Secrets):

*   `LANGFUSE_SECRET_KEY`
*   `LANGFUSE_PUBLIC_KEY`
*   `LANGFUSE_HOST` (e.g., `https://us.cloud.langfuse.com`)

Without these, the code explicitly disables observability:
```python
if not enabled: # checks env vars
    logger.info("Langfuse observability is disabled")
    return
```

## 2. Empty Logs Fix

You reported that logs were "empty" (only LLM prompts showing). This happens because:
1.  **Scope**: The logging handler was only attached to specific `basic.*` modules, missing logs from the `workflows` engine and other libraries.
2.  **Context**: Logs generated outside of a decorated `@observe` step cannot be attached to a trace ID (they appear as standalone events).

### **Code Change Applied:**
I have modified `src/basic/observability.py` to attach the Langfuse logging handler to the **root logger**.
*   **Effect**: All logs (`INFO` and above) from the application, including the workflow engine (`workflows.server`), will now be sent to Langfuse.
*   **Note**: Logs sent *inside* a workflow step (e.g., `triage_email`) will appear inside the Trace. Logs sent *outside* (like server startup or generic errors) will appear as separate Events in Langfuse.

## 3. Deployment

To apply these fixes:
1.  **Deploy** the latest code (contains the timeout fix and logging fix).
2.  **Update Secrets** in LlamaCloud UI.

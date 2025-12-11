# Gemini Model Updates

## Overview

This document describes the Gemini model configuration updates made to align with the latest stable models as documented at https://ai.google.dev/gemini-api/docs/gemini-3.

## Changes Made

### Model Version Updates

1. **Multi-modal Model (Images, PDFs, Videos)**
   - Previous: `gemini-2.0-flash-exp` (experimental)
   - Current: `gemini-3-pro-preview` (latest Gemini 3)
   - Used for: PDF analysis, image processing, and other multi-modal tasks

2. **Text-based LLM Model**
   - Previous: `gemini-2.5-flash`
   - Current: `gemini-3-pro-preview` (latest Gemini 3)
   - Used for: Text summarization, document content analysis

### Configuration Constants

Three new constants have been added to `src/basic/email_workflow.py` for centralized model configuration:

```python
# Gemini model configuration
GEMINI_MULTIMODAL_MODEL = "gemini-3-pro-preview"  # Latest Gemini 3 for multi-modal
GEMINI_TEXT_MODEL = "gemini-3-pro-preview"  # Latest Gemini 3 for text processing

# Alternative cheaper model (not currently in use)
GEMINI_CHEAP_TEXT_MODEL = "gemini-2.5-flash"  # Cheaper option for simple text tasks
```

## Benefits

1. **Centralized Configuration**: All model names are defined in one place, making updates easier
2. **Stability**: Using stable models instead of experimental versions for production reliability
3. **Future Cost Optimization**: `GEMINI_CHEAP_TEXT_MODEL` is ready for implementation when needed
4. **Documentation**: Clear documentation of which model is used for which purpose

## Future Work

### Cost Optimization

The `GEMINI_CHEAP_TEXT_MODEL` constant (Gemini 2.5 Flash) has been implemented but is not yet used in the workflow. This model is optimized for:

- Simpler text processing tasks
- Lower cost per API call
- Faster response times for basic queries

To implement cost optimization:

1. Identify simple text tasks that don't require multi-modal capabilities
2. Replace `GEMINI_TEXT_MODEL` with `GEMINI_CHEAP_TEXT_MODEL` for those tasks
3. Example candidates:
   - Plain text file summarization
   - JSON/XML parsing and summarization
   - Simple markdown processing

### Implementation Example

```python
# For simple text tasks, use the cheaper model:
if mime_type in ["text/plain", "application/json", "text/markdown"]:
    summary = await self._llm_complete_with_retry(
        prompt=f"Summarize this {mime_type} content:\n\n{content}",
        model=GEMINI_CHEAP_TEXT_MODEL  # Use cheaper model
    )
else:
    # Use standard model for complex tasks
    summary = await self._llm_complete_with_retry(
        prompt=prompt,
        model=GEMINI_TEXT_MODEL
    )
```

Note: The `_llm_complete_with_retry` method would need to be updated to accept a `model` parameter to enable this optimization.

## Testing

Tests have been updated to expect the new stable model name (`gemini-2.0-flash`):

- `tests/test_attachment_types.py`: Updated assertions for image and PDF processing tests

## Documentation Updates

- `ATTACHMENT_SUPPORT.md`: Updated to reflect new model names in documentation and code examples

## References

- [Gemini API Documentation](https://ai.google.dev/gemini-api/docs/gemini-3)
- [Gemini 2.0 Flash Model Details](https://ai.google.dev/gemini-api/docs/models/gemini-v2)

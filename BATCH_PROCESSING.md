# Batch Processing for Long Text

## Overview

The workflow tools now support intelligent batch processing for long text inputs. Instead of truncating text when it exceeds limits, tools split the text into manageable chunks, process each chunk sequentially, and reassemble the results.

## How It Works

### The `process_text_in_batches()` Utility

Located in `src/basic/utils.py`, this function provides intelligent text batching:

```python
async def process_text_in_batches(
    text: str,
    max_length: int,
    processor: Callable[[str], Any],
    combiner: Optional[Callable[[list[Any]], Any]] = None,
) -> Any
```

**Key Features:**
- Automatically detects if text needs batching based on `max_length`
- Splits text at sentence boundaries (`. ! ?`) when possible
- Falls back to word boundaries if no sentence boundary found
- Supports custom processor functions for each batch
- Supports custom combiner functions to reassemble results

**Default Behavior:**
- If no combiner is provided, string results are joined with newlines
- Non-string results are returned as a list

## Tool-Specific Behavior

### TranslateTool
- **Batch Size:** 50,000 characters
- **Strategy:** Processes text in batches, translates each batch, concatenates results
- **Use Case:** Translating long documents while preserving all content

```python
# Example: 100KB document is split into 2+ batches
result = await translate_tool.execute(
    text=long_document,
    target_lang="fr"
)
# All text is translated, no truncation
```

### SummariseTool
- **Batch Size:** 50,000 characters
- **Strategy:** Summarizes each batch separately, labels parts (Part 1, Part 2, etc.)
- **Use Case:** Summarizing very long documents by sections

```python
# Example: Creates multi-part summary for long documents
result = await summarise_tool.execute(text=long_document)
# Returns: "Part 1: summary of first batch\n\nPart 2: summary of second batch..."
```

### ClassifyTool
- **Batch Size:** 10,000 characters (sampling strategy)
- **Strategy:** For long text, samples beginning, middle, and end sections (~3.3KB each)
- **Use Case:** Classifying long documents by representative samples

```python
# Example: 50KB document is sampled (beginning + middle + end)
result = await classify_tool.execute(
    text=long_document,
    categories=["Technical", "Business", "Personal"]
)
# Classification is based on representative samples
```

### ExtractTool
- **Batch Size:** 4,900 characters (LlamaCloud Extract API limit)
- **Strategy:** Extracts from each batch, returns batch results or combined data
- **Use Case:** Extracting structured data from long text documents
- **Note:** Only accepts text input. For files, use ParseTool first to extract text
- **Note:** The batch size is limited by the LlamaCloud Extract API's SourceText validation, which enforces a maximum of 5000 characters

```python
# Example: Correct workflow for extracting from files
# Step 1: Parse file to text
parse_result = await parse_tool.execute(file_id="att-1")
parsed_text = parse_result["parsed_text"]

# Step 2: Extract from text (automatically batched if > 4900 chars)
extract_result = await extract_tool.execute(
    text=parsed_text,
    schema={"field": "string"}
)
# Returns either single result or batch_results with batch_count
```

### SplitTool
- **No Limit:** Processes text of any length
- **Strategy:** Uses LlamaIndex SentenceSplitter to intelligently chunk text
- **Use Case:** The tool's purpose is to split text, so no truncation needed

## Migration Guide

### Before (with truncation):
```python
max_length = 50000
if len(text) > max_length:
    logger.warning(f"Text truncated from {len(text)} to {max_length}")
    text = text[:max_length]

result = await process(text)
```

### After (with batching):
```python
async def process_chunk(chunk: str) -> str:
    return await process(chunk)

result = await process_text_in_batches(
    text=text,
    max_length=50000,
    processor=process_chunk,
)
```

## Best Practices

1. **Choose Appropriate Batch Sizes:**
   - Consider API limits and costs
   - Larger batches = fewer API calls but higher per-call cost
   - Smaller batches = more API calls but better failure isolation

2. **Smart Boundary Detection:**
   - The utility automatically finds sentence boundaries
   - Falls back to word boundaries if needed
   - Prevents mid-word breaks

3. **Custom Combiners:**
   - Use when default concatenation isn't appropriate
   - Example: Summarization labels parts for clarity
   - Example: Extraction returns structured batch information

4. **Error Handling:**
   - Each batch is processed independently
   - Failures in one batch don't prevent others from processing
   - Consider implementing partial success handling

## Testing

Comprehensive tests are available in `tests/test_batch_processing.py`:

```bash
# Run batch processing tests
pytest tests/test_batch_processing.py -v

# Test specific tool
pytest tests/test_batch_processing.py::test_translate_tool_batching -v
```

## Performance Considerations

- **API Costs:** More batches = more API calls = higher costs
- **Processing Time:** Sequential processing means longer total time
- **Memory:** Batching keeps memory usage bounded
- **Reliability:** Smaller batches are more reliable for unstable APIs

## Future Enhancements

Potential improvements for future iterations:

1. **Parallel Processing:** Process multiple batches concurrently where safe
2. **Adaptive Batching:** Adjust batch size based on API response times
3. **Caching:** Cache results for repeated batch processing
4. **Progress Tracking:** Report progress for very long documents
5. **Batch Overlap:** Overlap batches for context preservation

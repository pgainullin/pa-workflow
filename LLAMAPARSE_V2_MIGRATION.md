# LlamaParse v2 API Migration

## Summary

Migrated LlamaParse configuration from v1 to v2 API to resolve parsing regression issues and align with the latest LlamaCloud API standards.

## Version Requirements

**Critical**: The v2 API tier-based configuration requires `llama-parse>=0.6.88`.

- **Before**: `llama-parse>=0.6.54` (v1 API)
- **After**: `llama-parse>=0.6.88` (v2 API with tier support)

Version 0.6.54 does NOT support the v2 API tier parameter. Upgrading to 0.6.88 or later is required for v2 features.

## Changes Made

### Files Modified
1. `src/basic/tools/parse_tool.py` - Updated LlamaParse initialization
2. `src/basic/tools/sheets_tool.py` - Updated LlamaParse initialization
3. `pyproject.toml` - Updated llama-parse version requirement to >=0.6.88

### Configuration Changes

#### Before (v1 API)
```python
self.llama_parser = LlamaParse(
    result_type="markdown",
    language="en,ch_sim,ch_tra,ja,ko,ar,hi,th,vi",
    high_res_ocr=True,
    parse_mode="parse_page_with_agent",
    model="gemini-2.5-flash",  # Caused parsing regression
    adaptive_long_table=True,
    outlined_table_extraction=True,
    output_tables_as_HTML=True,
)
```

#### After (v2 API)
```python
self.llama_parser = LlamaParse(
    result_type="markdown",
    language="en,ch_sim,ch_tra,ja,ko,ar,hi,th,vi",
    tier="agentic",  # Replaces parse_mode + model parameters
)
```

## Breaking Changes Addressed

### 1. Always Enabled Features in v2
The following features are **always enabled** in LlamaParse v2 and no longer need to be (or can be) specified:
- `high_res_ocr` - High-resolution OCR is always active
- `adaptive_long_table` - Adaptive long table extraction is always active
- `outlined_table_extraction` - Outlined table extraction is always active

### 2. Deprecated Parameters
- `parse_mode` - Replaced by `tier` system
- `model` - Replaced by tier selection (no explicit model naming)

### 3. Tier System
LlamaParse v2 uses a tier-based configuration instead of granular parameter control:

| Tier | Description | Use Case | Cost |
|------|-------------|----------|------|
| `fast` | Basic text-heavy documents | Simple, text-only PDFs | Lowest |
| `cost_effective` | Balanced parsing | General purpose documents | Low |
| `agentic` | Advanced parsing with multimodal support | Complex documents with tables/images | Medium |
| `agentic_plus` | Highest quality parsing | Mission-critical, highly complex documents | Highest |

**Current Configuration**: Using `agentic` tier to maintain high-quality parsing for complex documents with tables and images, equivalent to the previous `parse_mode="parse_page_with_agent"` configuration.

## Migration Benefits

### 1. Resolves Parsing Regression
The `model="gemini-2.5-flash"` parameter was incompatible with the API, causing PDFs to fail with "empty_content_after_retries" errors. The v2 tier system properly handles model selection internally.

### 2. Simplified Configuration
Reduced configuration complexity by removing always-on features and using tier-based selection instead of multiple granular parameters.

### 3. Future-Proof
Aligns with LlamaCloud's v2 API architecture, ensuring compatibility with future updates and improvements.

### 4. Automatic Improvements
Benefits from v2 enhancements:
- Always-on high-resolution OCR for better text extraction
- Always-on adaptive long table handling for complex tables
- Improved stability and reliability

## Retained Parameters

### Still Valid in v2
- `result_type` - Output format (markdown, text, json)
- `language` - Multi-language OCR support (defaults to "en")

## Testing Recommendations

1. **Test with previous failing PDFs** to verify parsing now succeeds
2. **Test with various document types**:
   - Simple text-heavy PDFs
   - Scanned documents
   - Documents with complex tables
   - Multi-language documents (especially CJK)
3. **Verify output quality** matches or exceeds previous v1 results
4. **Monitor parsing costs** - Agentic tier has higher per-page cost but better quality

## Cost Considerations

The `agentic` tier provides high-quality parsing but has higher costs compared to simpler tiers:
- **Agentic**: ~10 credits per page
- **Cost Effective**: ~3 credits per page
- **Fast**: Lowest cost

For cost optimization, consider:
- Using `cost_effective` tier for simple, text-heavy documents
- Reserving `agentic` tier for complex documents with tables/images
- Implementing tier selection based on document characteristics

## Documentation References

- [LlamaParse v2 Migration Guide](https://developers.llamaindex.ai/python/cloud/llamaparse/migration-v1-to-v2/)
- [LlamaParse v2 API Guide](https://developers.llamaindex.ai/python/cloud/llamaparse/api-v2-guide/)
- [LlamaParse v2 Announcement](https://www.llamaindex.ai/blog/introducing-llamaparse-v2-simpler-better-cheaper)
- [LlamaParse Tiers](https://developers.llamaindex.ai/typescript/cloud/llamaparse/v2/basics/tiers/)

## Related Issues

- Original Issue: Parse step broken - PDFs that previously worked now fail
- Root Cause: `model="gemini-2.5-flash"` parameter incompatible with API
- Resolution: Migrate to v2 API with tier-based configuration

## Rollback Plan

If issues arise with v2 API, can revert to minimal v1 configuration:
```python
self.llama_parser = LlamaParse(
    result_type="markdown",
    language="en,ch_sim,ch_tra,ja,ko,ar,hi,th,vi",
)
```

This uses default v1 behavior without the problematic parameters.

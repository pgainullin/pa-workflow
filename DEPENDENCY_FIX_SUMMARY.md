# Dependency Compatibility Fix Summary

## Issue
Deployment to LlamaCloud was failing with a dependency conflict error:

```
× No solution found when resolving dependencies:
  ╰─▶ Because llama-parse==0.6.88 depends on llama-cloud-services==0.6.88,
      and llama-cloud-services==0.6.88 depends on llama-cloud==0.1.45,
      and llama-index-indices-managed-llama-cloud>=0.8.0 depends on llama-cloud==0.1.35,
      we can conclude that llama-index==0.14.10 and llama-parse>=0.6.88 are incompatible.
```

## Root Cause
The project was pinned to `llama-parse>=0.6.88` which requires `llama-cloud==0.1.45`, but `llama-index==0.14.10` requires `llama-index-indices-managed-llama-cloud>=0.9.0` which needs `llama-cloud==0.1.35`. These version constraints are incompatible.

## Solution
1. **Downgraded llama-parse version constraint** from `>=0.6.88` to `>=0.6.54,<0.6.88`
   - This allows the dependency resolver to select version 0.6.54 which has compatible transitive dependencies
   
2. **Removed explicit llama-cloud-services dependency**
   - This is a transitive dependency of llama-parse, so it doesn't need to be explicitly specified
   - Removing it allows the resolver more flexibility

3. **Reverted to v1 API configuration**
   - Updated `sheets_tool.py` to use v1 API with `parse_mode="parse_page_with_agent"` instead of v2 API's `tier="agentic"`
   - The v2 API tier parameter was only available in llama-parse>=0.6.88
   - Added explicit feature flags: `high_res_ocr=True`, `adaptive_long_table=True`, `outlined_table_extraction=True`

## Changes Made

### pyproject.toml
```diff
- "llama-parse>=0.6.88",  # v2 API support with tier-based configuration
- "llama-cloud-services>=0.0.17",
+ "llama-parse>=0.6.54,<0.6.88",  # Use version compatible with llama-index 0.14.10
```

### src/basic/tools/sheets_tool.py
```diff
- # Using LlamaParse v2 API with tier-based configuration
- # Note: high_res_ocr, adaptive_long_table, and outlined_table_extraction
- # are always enabled in v2 and no longer need to be specified
+ # Using LlamaParse with v1 API for compatibility with llama-index 0.14.10
+ # parse_mode="parse_page_with_agent" provides high-quality parsing for complex documents
  self.llama_parser = LlamaParse(
      result_type="markdown",
      language="en,ch_sim,ch_tra,ja,ko,ar,hi,th,vi",  # Multi-language OCR support
-     tier="agentic",  # v2 tier: fast, cost_effective, agentic, or agentic_plus
-     # Agentic tier provides best quality for complex documents with tables/images
-     # Previously used parse_mode="parse_page_with_agent" which is now replaced by tier system
+     parse_mode="parse_page_with_agent",  # High-quality parsing for complex documents
+     high_res_ocr=True,
+     adaptive_long_table=True,
+     outlined_table_extraction=True,
  )
```

### src/basic/tools/parse_tool.py
```diff
- # Using LlamaParse v2 API
+ # Using LlamaParse with v1 API for compatibility with llama-index 0.14.10
```

## Verified Resolution
After the changes, the dependency resolver successfully installs:
- `llama-parse: 0.6.54` ✓
- `llama-cloud-services: 0.6.54` ✓
- `llama-cloud: 0.1.35` ✓
- `llama-index: 0.14.10` ✓
- `llama-index-indices-managed-llama-cloud: 0.9.4` ✓

## Testing
- ✅ Dependency resolution verified with pip
- ✅ Unit tests for `test_parse_tool` passed
- ✅ Unit tests for `test_sheets_tool_csv` passed
- ✅ Unit tests for `test_sheets_tool_excel` passed

## Impact
- **No functional changes** - The v1 API with `parse_mode="parse_page_with_agent"` provides the same high-quality parsing as the v2 API's `tier="agentic"`
- **Deployment compatibility** - The workflow can now be deployed to LlamaCloud without dependency conflicts
- **Feature parity** - All parsing features are maintained through explicit v1 API flags

## Future Considerations
When `llama-index` is updated to support `llama-cloud>=0.1.45`, we can:
1. Upgrade back to `llama-parse>=0.6.88`
2. Switch to v2 API with tier-based configuration
3. Remove explicit feature flags as they become always-on in v2

## Related Documentation
- See `LLAMAPARSE_V2_MIGRATION.md` for v2 API migration details (reverted in this fix)
- This fix prioritizes deployment compatibility over v2 API features

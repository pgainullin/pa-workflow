# StaticChartGen Tool Fix - Issue Resolution

## Issue Description

When StaticChartGen tool received JSON data from Extract Tool via parameter references, it failed with the error:
```
'str' object has no attribute 'get'
```

**Important**: The error occurred in the **StaticChartGen tool**, not the Extract tool. The Extract tool worked correctly and returned proper data, but the data was stringified during parameter resolution before reaching StaticChartGen.

## Root Cause Analysis

The issue occurred in the `resolve_params` function in `src/basic/plan_utils.py`. When tools pass data between steps using parameter references like `{step_1.extracted_data}`, the `resolve_params` function was converting ALL values to strings using `str()`, regardless of their original type.

### Example of the Problem:

1. **Extract Tool** returns (working correctly):
   ```python
   {
       "success": True,
       "extracted_data": {
           "x": ["Q1", "Q2", "Q3", "Q4"],
           "y": [100, 120, 115, 140]
       }
   }
   ```

2. **Triage Plan** specifies:
   ```python
   {
       "tool": "static_graph",
       "params": {
           "data": "{step_1.extracted_data}",
           "chart_type": "line"
       }
   }
   ```

3. **Before Fix** - `resolve_params` converted the dict to a string:
   ```python
   # In plan_utils.py (OLD CODE):
   return str(context[step_key][field])  # ❌ Always converts to string
   
   # Result passed to StaticChartGen:
   resolved_params = {
       "data": "{'x': ['Q1', 'Q2', 'Q3', 'Q4'], 'y': [100, 120, 115, 140]}",  # STRING!
       "chart_type": "line"
   }
   ```

4. **StaticChartGen Tool** tried to use the data:
   ```python
   # In static_graph_tool.py:
   x = data.get("x")  # ❌ AttributeError: 'str' object has no attribute 'get'
   ```

## Solution

Modified `resolve_params` to detect when a parameter value is **ONLY** a single template reference (not embedded in text), and preserve the original type in those cases.

### Key Changes:

1. **Single Reference Detection**: Added logic to detect if the entire value is just a template reference:
   - `{step_N.field}` (single brace)
   - `{{step_N.field}}` (double brace with optional whitespace)

2. **Type Preservation**: When a single reference is detected, return the actual value from the context instead of converting to string:
   ```python
   # BEFORE (plan_utils.py line 141 and 160):
   return str(context[step_key][field])  # ❌ Always stringifies
   
   # AFTER (plan_utils.py - new code at lines 145-149):
   if single_double_brace_match:
       # ... validation ...
       # Return the actual value, preserving its type
       resolved[key] = context[step_key][field]  # ✅ Preserves dict/list/int/etc
       continue
   ```

3. **Backward Compatibility**: When references are embedded in text (e.g., `"Count: {step_1.count} items"`), string conversion still happens as expected:
   ```python
   # Still converts to string for embedded references:
   "Count: {step_1.count} items" → "Count: 42 items"  # ✅ String conversion when needed
   ```

## Files Modified

### 1. `src/basic/plan_utils.py`
- Modified `resolve_params` function to preserve complex types for standalone references
- Added detection for single template references using regex patterns
- Maintains backward compatibility for embedded references

### 2. `tests/test_plan_utils.py`
- Added `TestResolveParams` class with 14 comprehensive tests:
  - Test dict preservation (single and double brace)
  - Test list preservation
  - Test nested dict preservation
  - Test int, float, bool preservation
  - Test embedded references still convert to strings
  - Test multiple references in strings
  - Test non-existent references
  - Test non-string params

### 3. `tests/test_static_chart_extract_integration.py`
- Integration tests demonstrating Extract Tool → StaticChartGen Tool flow
- Tests for all chart types (line, pie, histogram)
- Verifies dict.get() method works correctly

### 4. `tests/manual_verify_static_chart_fix.py`
- Manual verification script that clearly demonstrates:
  - The original issue (with error reproduction)
  - The fix (with success verification)
  - Direct testing of resolve_params with real data

## Test Results

All tests pass successfully:

```bash
# New resolve_params tests
tests/test_plan_utils.py::TestResolveParams - 14 tests PASSED

# Integration tests
tests/test_static_chart_extract_integration.py - 3 tests PASSED

# Manual verification
tests/manual_verify_static_chart_fix.py - All checks PASSED
```

## Impact

This fix enables:
1. **Extract Tool → StaticChartGen Tool** workflows to work correctly
2. **Any tool-to-tool** data passing with complex types (dicts, lists, etc.)
3. **Maintains backward compatibility** with existing text-embedding use cases

## Example Usage

### The Complete Flow

**Step 1: Extract Tool returns data (works correctly)**
```python
# Extract tool successfully returns:
{
    "success": True,
    "extracted_data": {
        "x": ["Q1", "Q2", "Q3", "Q4"],
        "y": [100, 120, 115, 140]
    }
}
```

**Step 2: Workflow parameters reference the data**
```python
# Triage plan specifies:
params = {"data": "{step_1.extracted_data}", "chart_type": "line"}
context = {"step_1": {"extracted_data": {"x": [...], "y": [...]}}}
```

**Step 3: Parameter resolution (THIS IS WHERE THE BUG WAS)**

```python
# BEFORE FIX - plan_utils.py (line ~141):
def double_brace_replacer(match):
    # ...
    return str(context[step_key][field])  # ❌ Always stringifies!

# Result:
resolved = {"data": "{'x': [...], 'y': [...]}", "chart_type": "line"}  # STRING!
```

```python
# AFTER FIX - plan_utils.py (lines 142-150):
if single_double_brace_match:
    ref = single_double_brace_match.group(1).strip()
    parts = ref.split(".")
    if len(parts) == 2:
        step_key, field = parts
        if step_key in context and field in context[step_key]:
            resolved[key] = context[step_key][field]  # ✅ Preserves type!
            continue

# Result:
resolved = {"data": {"x": [...], "y": [...]}, "chart_type": "line"}  # DICT!
```

**Step 4: StaticChartGen receives the data**
```python
# BEFORE FIX:
data = resolved["data"]  # This is a STRING
x = data.get("x")  # ❌ AttributeError: 'str' object has no attribute 'get'

# AFTER FIX:
data = resolved["data"]  # This is a DICT
x = data.get("x")  # ✅ Works! Returns ["Q1", "Q2", "Q3", "Q4"]
```

## Verification

To verify the fix:

```bash
# Run comprehensive tests
cd /home/runner/work/pa-workflow/pa-workflow
PYTHONPATH=src:$PYTHONPATH python3 -m pytest tests/test_plan_utils.py::TestResolveParams -v

# Run integration tests
PYTHONPATH=src:$PYTHONPATH python3 tests/test_static_chart_extract_integration.py

# Run manual verification
python3 tests/manual_verify_static_chart_fix.py
```

All tests should pass with success messages indicating the fix is working.

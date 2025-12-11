# Implementation Details: ExtractTool and SheetsTool

This document describes the implementation of the two placeholder tools that were previously incomplete.

## Overview

The issue requested implementing missing tools that had placeholder implementations. Two tools were identified and fully implemented:

1. **ExtractTool** - Structured data extraction using LlamaCloud Extract
2. **SheetsTool** - Spreadsheet processing using pandas

## ExtractTool Implementation

### Features
- Integrates with LlamaCloud Extract API via `llama_cloud_services.LlamaExtract`
- Supports multiple input formats:
  - `file_id`: LlamaCloud file ID
  - `text`: Direct text content
  - `file_content`: Base64-encoded file content
- Dynamic agent creation based on schema
- Supports both dict and Pydantic BaseModel schemas
- Consistent agent naming using MD5 hash for cross-session stability

### Key Design Decisions
- **Agent Naming**: Uses MD5 hash of schema string to create consistent agent names across sessions
- **Lazy Initialization**: LlamaExtract instance created on-demand if not provided
- **Flexible Schema**: Accepts both dict schemas and Pydantic BaseModel classes
- **Error Handling**: Returns dict with `success` boolean and either `extracted_data` or `error`

### Usage Example
```python
from basic.tools import ExtractTool
from pydantic import BaseModel

class PersonSchema(BaseModel):
    name: str
    age: int

tool = ExtractTool()
result = await tool.execute(
    text="John Doe is 30 years old.",
    schema={"name": "str", "age": "int"}
)
# Returns: {"success": True, "extracted_data": {"name": "John Doe", "age": 30}}
```

## SheetsTool Implementation

### Features
- Processes Excel (.xlsx, .xls, .xlsm) and CSV files using pandas
- Supports multiple input formats:
  - `file_id`: LlamaCloud file ID
  - `file_content`: Base64-encoded file content
- Optional parameters:
  - `filename`: For format detection
  - `sheet_name`: Specific sheet (default: first sheet)
  - `max_rows`: Limit rows returned (default: 1000)
- Returns structured JSON with rows, columns, and metadata

### Key Design Decisions
- **File Format Detection**: Uses filename extension to determine Excel vs CSV
- **Fallback Strategy**: If format detection fails, tries CSV first, then Excel
- **Memory Protection**: Limits output to 1000 rows by default to prevent excessive memory usage
- **Structured Output**: Returns data as list of dicts (one per row) plus metadata

### Usage Example
```python
from basic.tools import SheetsTool

tool = SheetsTool()
result = await tool.execute(
    file_content=base64_encoded_excel_content,
    filename="data.xlsx",
    max_rows=500
)
# Returns:
# {
#   "success": True,
#   "sheet_data": {
#     "rows": [...],
#     "columns": ["Column1", "Column2"],
#     "row_count": 100,
#     "column_count": 2
#   }
# }
```

## Dependencies Added

### openpyxl
- Version: >=3.0.0
- Purpose: Excel file support for pandas
- Required for: `pandas.read_excel()` functionality

## Testing

### Test Coverage
Added 6 new tests covering:
1. ExtractTool basic functionality
2. ExtractTool error handling (missing schema)
3. SheetsTool CSV processing
4. SheetsTool Excel processing
5. SheetsTool max_rows limiting
6. SheetsTool error handling (missing file)

### Test Results
- All 13 tool tests pass
- Code passes linting (ruff)
- Code passes formatting checks

## Integration

Both tools are automatically registered in the EmailWorkflow:

```python
def _register_tools(self):
    """Register all available tools."""
    self.tool_registry.register(ParseTool(self.llama_parser))
    self.tool_registry.register(ExtractTool())  # ✓ Fully implemented
    self.tool_registry.register(SheetsTool())    # ✓ Fully implemented
    self.tool_registry.register(SplitTool())
    self.tool_registry.register(ClassifyTool(self.llm))
    self.tool_registry.register(TranslateTool())
    self.tool_registry.register(SummariseTool(self.llm))
    self.tool_registry.register(PrintToPDFTool())
```

## Files Modified

1. **src/basic/tools.py**
   - Implemented ExtractTool.execute()
   - Implemented SheetsTool.execute()

2. **tests/test_tools.py**
   - Added 6 comprehensive tests
   - Added base64 import for test utilities

3. **pyproject.toml**
   - Added openpyxl>=3.0.0 dependency

4. **README.md**
   - Removed "(placeholder)" notes from tool descriptions

## Future Enhancements

### ExtractTool
- Consider caching extraction agents to avoid recreation
- Add support for custom extraction modes (FAST, MULTIMODAL, PREMIUM)
- Add confidence scores if supported by LlamaCloud Extract

### SheetsTool
- Add support for multiple sheets (return all sheets)
- Add filtering/query capabilities
- Add support for more file formats (ODS, etc.)
- Consider streaming large files instead of loading entire DataFrame

## References

- [LlamaCloud Extract Documentation](https://docs.cloud.llamaindex.ai/)
- [llama-cloud-services SDK](https://github.com/run-llama/llama_cloud_services)
- [pandas Documentation](https://pandas.pydata.org/docs/)

# Implementation Details: Tool Implementations

This document describes the implementation of tools using LlamaIndex and LlamaCloud APIs.

## Overview

The issue requested implementing tools using LlamaIndex APIs. Four tools have been fully implemented:

1. **ExtractTool** - Structured data extraction using LlamaCloud Extract
2. **SheetsTool** - Spreadsheet processing using pandas
3. **SplitTool** - Text splitting using LlamaIndex SentenceSplitter
4. **ClassifyTool** - Text classification using LlamaIndex structured outputs

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

## SplitTool Implementation

### Features
- Uses LlamaIndex `SentenceSplitter` for intelligent text chunking
- Supports configurable chunk size and overlap
- Respects sentence boundaries for better semantic coherence
- Supports multiple input formats:
  - `text`: Direct text content
  - `file_id`: LlamaCloud file ID
- Optional parameters:
  - `chunk_size`: Maximum tokens per chunk (default: 1024)
  - `chunk_overlap`: Token overlap between chunks (default: 200)

### Key Design Decisions
- **LlamaIndex Integration**: Uses `SentenceSplitter` instead of simple string splitting for context-aware chunking
- **Configurable Parameters**: Allows customization of chunk size and overlap
- **Memory Protection**: Limits input text to 100,000 characters
- **Smart Splitting**: Respects sentence boundaries and semantic structure

### Usage Example
```python
from basic.tools import SplitTool

tool = SplitTool(chunk_size=512, chunk_overlap=50)
result = await tool.execute(
    text="Long document text...",
    chunk_size=1024,
    chunk_overlap=200
)
# Returns: {"success": True, "splits": ["chunk1", "chunk2", ...]}
```

## ClassifyTool Implementation

### Features
- Uses LlamaIndex `LLMTextCompletionProgram` for structured classification
- Returns both category and confidence level
- Supports dynamic category lists
- Type-safe output using Pydantic models
- Memory protection with text truncation (max 10,000 characters)

### Key Design Decisions
- **Structured Outputs**: Uses LlamaIndex's Pydantic program for type-safe results
- **Confidence Scoring**: Returns confidence level (high, medium, low) along with category
- **Dynamic Categories**: Accepts any list of categories at runtime
- **Error Handling**: Graceful error handling with detailed error messages

### Usage Example
```python
from basic.tools import ClassifyTool

tool = ClassifyTool(llm)
result = await tool.execute(
    text="This is a technical article about machine learning.",
    categories=["Technical", "Business", "Personal"]
)
# Returns: {
#   "success": True,
#   "category": "Technical",
#   "confidence": "high"
# }
```

## Dependencies Added

### openpyxl
- Version: >=3.0.0
- Purpose: Excel file support for pandas
- Required for: `pandas.read_excel()` functionality

## Testing

### Test Coverage
Updated tests covering:
1. ExtractTool basic functionality
2. ExtractTool error handling (missing schema)
3. SheetsTool CSV processing
4. SheetsTool Excel processing
5. SheetsTool max_rows limiting
6. SheetsTool error handling (missing file)
7. **SplitTool with LlamaIndex SentenceSplitter**
8. **ClassifyTool with LlamaIndex structured outputs**

### Test Results
- All 13 tool tests pass
- Code passes linting (ruff)
- Code passes formatting checks

## Integration

All tools are automatically registered in the EmailWorkflow:

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
   - Updated tests for SplitTool and ClassifyTool
   - Added base64 import for test utilities

3. **pyproject.toml**
   - Added openpyxl>=3.0.0 dependency

4. **README.md**
   - Updated tool descriptions to reflect LlamaIndex usage

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

### SplitTool
- Add support for semantic splitting using embeddings
- Add support for different splitting strategies (by page, by section)
- Consider adding metadata preservation for splits

### ClassifyTool
- Add support for multi-label classification
- Add support for hierarchical categories
- Consider adding explanation/reasoning for classification

## References

- [LlamaCloud Extract Documentation](https://docs.cloud.llamaindex.ai/)
- [llama-cloud-services SDK](https://github.com/run-llama/llama_cloud_services)
- [LlamaIndex Core Documentation](https://docs.llamaindex.ai/)
- [LlamaIndex Node Parsers](https://docs.llamaindex.ai/en/stable/module_guides/loading/node_parsers/)
- [LlamaIndex Structured Outputs](https://docs.llamaindex.ai/en/stable/module_guides/querying/structured_outputs/)
- [pandas Documentation](https://pandas.pydata.org/docs/)

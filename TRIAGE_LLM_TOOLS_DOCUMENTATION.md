# Triage LLM Tool Awareness Documentation

## Overview
This document explains how the triage LLM is made aware of all available tools, including the newly added SearchTool.

## Architecture Flow

### 1. Tool Registration
All tools are registered in `EmailWorkflow._register_tools()` method:

```python
# src/basic/email_workflow.py (lines 149-159)
def _register_tools(self):
    """Register all available tools."""
    self.tool_registry.register(ParseTool(self.llama_parser))
    self.tool_registry.register(ExtractTool())
    self.tool_registry.register(SheetsTool(self.llama_parser))
    self.tool_registry.register(SplitTool())
    self.tool_registry.register(ClassifyTool(self.llm))
    self.tool_registry.register(TranslateTool())
    self.tool_registry.register(SummariseTool(self.llm))
    self.tool_registry.register(PrintToPDFTool())
    self.tool_registry.register(SearchTool())  # ✓ SearchTool included
```

### 2. Tool Description Generation
The `ToolRegistry.get_tool_descriptions()` method generates a formatted string with all tool descriptions:

```python
# src/basic/tools.py (lines 1325-1334)
def get_tool_descriptions(self) -> str:
    """Get descriptions of all registered tools."""
    descriptions = []
    for tool in self.tools.values():
        descriptions.append(f"- **{tool.name}**: {tool.description}")
    return "\n".join(descriptions)
```

### 3. Triage Prompt Building
The `triage_email()` step calls `build_triage_prompt()` with tool descriptions:

```python
# src/basic/email_workflow.py (lines 220-224)
triage_prompt = build_triage_prompt(
    email_data,
    self.tool_registry.get_tool_descriptions(),  # ✓ All tools included
    RESPONSE_BEST_PRACTICES,
)
```

### 4. Prompt Template
The triage prompt template includes a placeholder for tool descriptions:

```
# src/basic/prompt_templates/triage_prompt.txt (lines 12-13)
Available Tools:
{tool_descriptions}
```

### 5. Final LLM Prompt
The LLM receives a prompt that looks like this:

```
You are an email processing triage agent. Analyze the email below and create 
a step-by-step execution plan using the available tools.

<user_email>
...
</user_email>

Available Tools:
- **parse**: Parse documents (PDF, Word, PowerPoint) using LlamaParse...
- **extract**: Extract structured data using LlamaCloud Extract...
- **sheets**: Process spreadsheet files (Excel, CSV) using LlamaParse...
- **split**: Split documents into logical sections using LlamaIndex...
- **classify**: Classify text into categories using LlamaIndex...
- **translate**: Translate text using Google Translate...
- **summarise**: Summarise long text into a concise summary using an LLM...
- **print_to_pdf**: Convert text content to a PDF file...
- **search**: Search the web for information using DuckDuckGo. Input: query (search query), max_results (optional, default: 5). Output: results (list of search results with title, snippet, and URL)

Create a step-by-step plan to process this email. Each step should use one 
of the available tools.
```

## SearchTool Details

The SearchTool is fully integrated and visible to the LLM:

- **Name**: `search`
- **Description**: "Search the web for information using DuckDuckGo. Input: query (search query), max_results (optional, default: 5). Output: results (list of search results with title, snippet, and URL)"
- **Location**: Registered at line 159 in `email_workflow.py`

## Verification

To verify that all tools including SearchTool are included in the LLM prompt:

1. **Tool Registration**: Check `EmailWorkflow._register_tools()` - ✓ SearchTool() is registered
2. **Description Method**: Check `ToolRegistry.get_tool_descriptions()` - ✓ Loops through all tools
3. **Tool Properties**: Check `SearchTool.name` and `SearchTool.description` - ✓ Both defined
4. **Triage Usage**: Check `triage_email()` calls `get_tool_descriptions()` - ✓ Called at line 222
5. **Template**: Check `triage_prompt.txt` includes `{tool_descriptions}` - ✓ Included at line 13

## Conclusion

✓ **The LLM IS aware of all available tools including SearchTool**

The architecture ensures that:
1. All registered tools are automatically included in the prompt
2. Tool descriptions are dynamically generated from the registry
3. The LLM receives complete information about each tool's purpose and parameters
4. Adding new tools (like SearchTool) requires only registering them in `_register_tools()`

The system is designed so that **any tool registered in the ToolRegistry is automatically made available to the LLM** through the triage prompt.

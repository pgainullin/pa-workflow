# PA Workflow

Email processing workflow with LlamaCloud integration and AI-powered triage for intelligent document handling.

## Features

- **Agent Triage System**: LLM-powered triage agent analyzes emails and creates execution plans
- **Tool-Based Processing**: Modular tools for parsing, extraction, translation, summarization, and more
- **Batch Processing**: Intelligent handling of long text with automatic chunking and reassembly
- **LlamaCloud Integration**: Pull and store attachments using LlamaCloud file storage
- **Document Processing**: Parse PDFs, spreadsheets, and other documents using LlamaParse with multi-language OCR support (English, Chinese Simplified, Chinese Traditional)
- **AI Capabilities**: Summarization, classification, and translation using Google Gemini
- **Callback System**: Send processed results back via webhook callbacks
- **Automatic Retry**: Handles API overload and rate limits with exponential backoff

## Available Tools

The workflow includes the following tools that can be used by the triage agent:

1. **Parse** - Parse documents (PDF, Word, PowerPoint) using LlamaParse with OCR support for English and Chinese characters
2. **Extract** - Extract structured data using LlamaCloud Extract
3. **Sheets** - Process spreadsheet files (Excel, CSV) using LlamaParse with multi-language OCR support
4. **Split** - Split documents into logical sections using LlamaIndex SentenceSplitter
5. **Classify** - Classify text into categories using LlamaIndex structured outputs
6. **Translate** - Translate text using Google Translate
7. **Summarise** - Summarize text using an LLM
8. **Print to PDF** - Convert text to PDF format
9. **Search** - Search the web for information using DuckDuckGo
10. **Image Gen** - Generate images from text descriptions using Google Gemini's Imagen API

## Installation

Install project dependencies:

```bash
pip install -e .
```

## Environment Variables

Configure the following environment variables:

```bash
# Required for LlamaCloud file operations
LLAMA_CLOUD_API_KEY=llx-...         # Your LlamaCloud API key
LLAMA_CLOUD_PROJECT_ID=proj-...      # Your LlamaCloud project ID

# Required for AI features
GEMINI_API_KEY=...                   # Google Gemini API key for summarization

# Optional: Observability with Langfuse
LANGFUSE_SECRET_KEY=sk-...           # Langfuse secret key for tracing
LANGFUSE_PUBLIC_KEY=pk-...           # Langfuse public key for tracing
LANGFUSE_HOST=https://cloud.langfuse.com  # Langfuse server URL (optional)
LANGFUSE_ENABLED=true                # Enable/disable observability (optional)
```

### Observability with Langfuse

The workflow includes optional observability using [Langfuse](https://langfuse.com/) for tracing and monitoring workflow execution. When configured, you can view detailed logs and traces of:

- **Workflow logs**: All Python logger.info(), logger.warning(), logger.error() calls are streamed to Langfuse
- **Workflow steps**: Step execution times and transitions
- **LLM calls**: Prompts, responses, and token usage
- **Tool executions**: Parameters and results for each tool
- **Errors and exceptions**: Full stack traces and context

To enable observability:

1. Sign up for a free account at [langfuse.com](https://langfuse.com/)
2. Get your API keys from the Langfuse dashboard
3. Set the environment variables `LANGFUSE_SECRET_KEY` and `LANGFUSE_PUBLIC_KEY`
4. Run your workflow - traces and logs will appear automatically in your Langfuse dashboard

If the Langfuse keys are not set, the workflow will run normally without observability.

## Usage

### Running the Basic Workflow

```bash
python -m basic.workflow
```

### Running the Email Workflow Server

```bash
python -m basic.server
```

The server will start on `http://127.0.0.1:8080` and expose the email workflow via the LlamaCloud API endpoints.

## How It Works

### Agent Triage Workflow

The email workflow now uses an AI-powered triage system:

1. **Triage Step**: An LLM analyzes the email (subject, body, attachments) and creates a step-by-step execution plan using available tools
2. **Plan Execution**: The workflow executes each step in the plan, passing results between steps
3. **Result Formatting**: Results are formatted and sent back via the callback email

### Example Workflow

When you send an email with a PDF attachment and subject "Translate this document to French":

1. Triage agent analyzes the email and creates a plan:
   ```json
   [
     {
       "tool": "parse",
       "params": {"file_id": "att-1"},
       "description": "Parse the PDF attachment"
     },
     {
       "tool": "translate",
       "params": {
         "text": "{{step_1.parsed_text}}",
         "target_lang": "fr"
       },
       "description": "Translate to French"
     }
   ]
   ```

2. The workflow executes each step:
   - Step 1: Parses the PDF and extracts text
   - Step 2: Translates the extracted text to French

3. Results are sent back via email with a summary of each step

## LlamaCloud File Integration

The email workflow supports two modes for handling attachments:

1. **Base64 Content Mode** (backward compatible): Attachments contain base64-encoded content
2. **LlamaCloud File Mode** (new): Attachments reference files stored in LlamaCloud via `file_id`

### Receiving Attachments from LlamaCloud

When the webhook service sends an attachment with a `file_id`:

```json
{
  "email_data": {
    "attachments": [
      {
        "id": "att-1",
        "name": "document.pdf",
        "type": "application/pdf",
        "file_id": "file-abc123"
      }
    ]
  }
}
```

The workflow automatically:
1. Downloads the file from LlamaCloud
2. Processes it (parsing, summarization)
3. Sends the results via callback

### Sending Attachments via LlamaCloud

When generating files to send back to users, use the utility function:

```python
from basic.utils import create_llamacloud_attachment

# Upload file and create attachment
attachment = await create_llamacloud_attachment(
    file_content=file_bytes,
    filename="report.pdf",
    content_type="application/pdf"
)

# Include in callback email
response_email = SendEmailRequest(
    to_email=user_email,
    subject="Your Report",
    text="Please find your report attached",
    attachments=[attachment]
)
```

For detailed documentation, see [LLAMACLOUD_FILES.md](LLAMACLOUD_FILES.md).

## Testing

Run the test suite:

```bash
pytest
```

Run with verbose output:

```bash
pytest -v
```

Run specific test files:

```bash
pytest tests/test_llamacloud_attachments.py -v
```

## Project Structure

```
.
├── src/basic/
│   ├── email_workflow.py    # Email processing workflow
│   ├── workflow.py           # Basic template workflow
│   ├── server.py             # Workflow server
│   ├── models.py             # Pydantic models
│   ├── tools.py              # Tool implementations with batch processing
│   └── utils.py              # Utility functions (LlamaCloud, HTML, retry, batching)
├── tests/                    # Test suite
├── API_RETRY.md              # API retry mechanism documentation
├── BATCH_PROCESSING.md       # Batch processing documentation
├── LLAMACLOUD_FILES.md       # LlamaCloud integration docs
└── README.md                 # This file
```

## Long Text Processing

The workflow now supports intelligent batch processing for long text inputs. Instead of truncating text, tools automatically split it into manageable chunks, process each sequentially, and reassemble results. This ensures complete processing of large documents.

**Key features:**
- Automatic chunking at sentence/word boundaries
- Tool-specific batch sizes (10KB-100KB)
- No data loss from truncation
- Transparent to end users

See [BATCH_PROCESSING.md](BATCH_PROCESSING.md) for detailed documentation.

## API Reliability

The workflow includes automatic retry logic for handling transient API errors:

- **503 Service Unavailable** - API overload
- **429 Rate Limit** - Too many requests
- **500 Server Error** - Temporary failures
- **Connection/Timeout** - Network issues

Retries use exponential backoff (up to 5 attempts) to handle temporary service disruptions gracefully. See [API_RETRY.md](API_RETRY.md) for details.

## Troubleshooting

### Traces Not Showing Up in Langfuse

If you're not seeing traces in Langfuse, check the following:

1. **Verify dependencies are installed**: Make sure you've installed the project with `pip install -e .` to get all dependencies including `llama-index-callbacks-langfuse`

2. **Check environment variables**: Ensure `LANGFUSE_SECRET_KEY` and `LANGFUSE_PUBLIC_KEY` are set correctly:
   ```bash
   echo $LANGFUSE_SECRET_KEY
   echo $LANGFUSE_PUBLIC_KEY
   ```

3. **Check logs for errors**: Run your workflow with logging enabled to see any errors:
   ```bash
   python -c "import logging; logging.basicConfig(level=logging.INFO); from basic import observability"
   ```
   
   You should see: `INFO:basic.observability:Langfuse observability enabled`
   
   If you see an error about missing packages, reinstall:
   ```bash
   pip install llama-index-callbacks-langfuse
   ```

4. **Verify the package is installed**:
   ```bash
   pip show llama-index-callbacks-langfuse
   ```

5. **Test with demo script**: Run the observability demo to verify everything works:
   ```bash
   python demo_observability.py
   ```

## References

- [llama-index-workflows documentation](https://github.com/run-llama/llama-index-workflows)
- [LlamaCloud Services SDK](https://github.com/run-llama/llama_cloud_services)
- [LlamaParse Documentation](https://docs.cloud.llamaindex.ai/)


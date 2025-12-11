# PA Workflow

Email processing workflow with LlamaCloud integration for intelligent document handling.

## Features

- **Email Processing Workflow**: Handles inbound emails with attachments
- **LlamaCloud Integration**: Pull and store attachments using LlamaCloud file storage
- **Document Processing**: Parse PDFs, spreadsheets, and other documents using LlamaParse
- **AI Summarization**: Summarize documents using Google Gemini
- **Callback System**: Send processed results back via webhook callbacks
- **Automatic Retry**: Handles API overload and rate limits with exponential backoff

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
```

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
│   └── utils.py              # Utility functions (LlamaCloud, HTML, retry)
├── tests/                    # Test suite
├── API_RETRY.md              # API retry mechanism documentation
├── LLAMACLOUD_FILES.md       # LlamaCloud integration docs
└── README.md                 # This file
```

## API Reliability

The workflow includes automatic retry logic for handling transient API errors:

- **503 Service Unavailable** - API overload
- **429 Rate Limit** - Too many requests
- **500 Server Error** - Temporary failures
- **Connection/Timeout** - Network issues

Retries use exponential backoff (up to 5 attempts) to handle temporary service disruptions gracefully. See [API_RETRY.md](API_RETRY.md) for details.

## References

- [llama-index-workflows documentation](https://github.com/run-llama/llama-index-workflows)
- [LlamaCloud Services SDK](https://github.com/run-llama/llama_cloud_services)
- [LlamaParse Documentation](https://docs.cloud.llamaindex.ai/)


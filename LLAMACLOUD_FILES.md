# LlamaCloud File Integration

This document describes how the email workflow integrates with LlamaCloud for file storage and retrieval.

## Overview

The workflow supports two modes for handling email attachments:

1. **Base64 Content Mode** (original): Attachments are sent with their content encoded in base64
2. **LlamaCloud File Mode** (new): Attachments reference files stored in LlamaCloud via `file_id`

## Receiving Attachments

### Webhook Format

The webhook service sends attachments in the following format:

```json
{
  "email_data": {
    "from_email": "user@example.com",
    "to_email": "service@example.com",
    "subject": "Document for processing",
    "text": "Please process the attached document",
    "attachments": [
      {
        "id": "att-1",
        "name": "document.pdf",
        "type": "application/pdf",
        "file_id": "file-abc123"
      }
    ]
  },
  "callback": {
    "callback_url": "https://webhook.example.com/callback",
    "auth_token": "secret-token"
  }
}
```

### Attachment Model

The `Attachment` model supports both modes:

```python
class Attachment(BaseModel):
    id: str  # Attachment identifier
    name: str  # Filename
    type: str  # MIME type (e.g., 'application/pdf')
    content: str | None = None  # Base64 content (optional if file_id provided)
    file_id: str | None = None  # LlamaCloud file ID (optional if content provided)
```

### Processing Workflow

When the workflow receives an attachment:

1. The `process_attachment` step checks if `file_id` is present
2. If `file_id` exists, it downloads the file from LlamaCloud using `download_file_from_llamacloud()`
3. If `file_id` is not present, it falls back to decoding the base64 `content`
4. The file is then processed (parsed, summarized, etc.)

## Sending Attachments

### Creating Attachments for Callbacks

When sending attachments back to users via callback emails, you should upload them to LlamaCloud first:

```python
from basic.utils import create_llamacloud_attachment

# Generate or prepare your file
report_data = generate_report()

# Create attachment with file uploaded to LlamaCloud
attachment = await create_llamacloud_attachment(
    file_content=report_data,
    filename="report.pdf",
    content_type="application/pdf"
)

# Include in email response
response_email = SendEmailRequest(
    to_email=user_email,
    subject="Your Report",
    text="Please find your report attached",
    attachments=[attachment]
)
```

### SendEmailRequest with Attachments

The `SendEmailRequest` model now supports an `attachments` field:

```python
class SendEmailRequest(BaseModel):
    to_email: str
    subject: str
    text: str = "(No content)"
    html: str = "(No html content)"
    from_email: str | None = None
    reply_to: str | None = None
    attachments: list[Attachment] = []  # List of attachments
```

## Environment Variables

To use LlamaCloud file operations, set these environment variables:

```bash
LLAMA_CLOUD_API_KEY=llx-...        # Your LlamaCloud API key
LLAMA_CLOUD_PROJECT_ID=proj-...     # Your LlamaCloud project ID
```

## Utility Functions

### Download File from LlamaCloud

```python
from basic.utils import download_file_from_llamacloud

# Download file by ID
file_content = await download_file_from_llamacloud("file-abc123")
```

### Upload File to LlamaCloud

```python
from basic.utils import upload_file_to_llamacloud

# Upload file and get file_id
file_id = await upload_file_to_llamacloud(
    file_content=file_bytes,
    filename="document.pdf",
    external_file_id="optional-custom-id"  # Optional
)
```

### Create LlamaCloud Attachment

```python
from basic.utils import create_llamacloud_attachment

# Upload file and create Attachment in one step
attachment = await create_llamacloud_attachment(
    file_content=file_bytes,
    filename="document.pdf",
    content_type="application/pdf",
    attachment_id="att-1",  # Optional
    external_file_id="custom-id"  # Optional
)
```

## Example Use Cases

### Use Case 1: Processing Documents from LlamaCloud

A webhook sends a document stored in LlamaCloud:

```python
{
  "attachments": [
    {
      "id": "att-1",
      "name": "contract.pdf",
      "type": "application/pdf",
      "file_id": "file-contract-123"
    }
  ]
}
```

The workflow:
1. Downloads the file from LlamaCloud
2. Processes it (parses with LlamaParse, summarizes with LLM)
3. Sends back a summary via callback

### Use Case 2: Generating and Sending Reports

A workflow generates a processed document and sends it back:

```python
# In a workflow step
async def generate_report(self, ev: SomeEvent, ctx: Context) -> StopEvent:
    # Generate report
    report_data = create_pdf_report(ev.data)
    
    # Upload to LlamaCloud and create attachment
    from basic.utils import create_llamacloud_attachment
    
    attachment = await create_llamacloud_attachment(
        file_content=report_data,
        filename="analysis_report.pdf",
        content_type="application/pdf"
    )
    
    # Send via callback
    response_email = SendEmailRequest(
        to_email=ev.user_email,
        subject="Your Analysis Report",
        text="Please find your analysis report attached.",
        html="<p>Please find your analysis report attached.</p>",
        attachments=[attachment]
    )
    
    # Post to callback URL...
```

## Benefits

1. **Reduced Payload Size**: Files don't need to be base64-encoded in JSON
2. **Centralized Storage**: Files are stored in LlamaCloud for easy access
3. **Better Performance**: Large files can be streamed instead of embedded
4. **Consistency**: Both input and output use the same storage mechanism

## Backward Compatibility

The system maintains full backward compatibility:
- Attachments with `content` (base64) still work as before
- The `content` field is optional when `file_id` is provided
- Existing code continues to function without changes

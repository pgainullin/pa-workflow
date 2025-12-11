# Attachment Type Support

The email workflow now supports processing various types of attachments with intelligent summarization.

## Supported Attachment Types

### 📄 Documents
- **PDF files** - Analyzed using Google Gemini's native PDF understanding (gemini-2.0-flash) for comprehensive analysis including text, images, tables, and formatting
- **Spreadsheets** (Excel, Google Sheets) - Parsed with LlamaParse, summarized with LLM
- **CSV files** - Parsed with LlamaParse, summarized with LLM
- **Word documents** (.doc, .docx) - Parsed with LlamaParse, summarized with LLM
- **PowerPoint presentations** (.ppt, .pptx) - Parsed with LlamaParse, summarized with LLM

### 🖼️ Images
- **All image formats** (PNG, JPEG, GIF, WebP, etc.)
- Analyzed using Google Gemini's vision capabilities (gemini-2.0-flash)
- Provides description of image content, objects, text, and context

### 📝 Text Files
- **Plain text** (.txt)
- **JSON** (.json)
- **XML** (.xml)
- **Markdown** (.md)
- Read directly and summarized with LLM
- Large files are automatically truncated to avoid token limits

### 🎬 Video & Audio (Partial Support)
- Currently returns acknowledgment message
- Full support requires uploading to Gemini File API (not yet implemented)

## How It Works

1. **Attachment Detection**: When an email arrives with attachments, the workflow fans out to process each attachment in parallel
2. **MIME Type Classification**: Each attachment is classified based on its MIME type
3. **Processing**:
   - **PDFs**: Google Gemini's multi-modal API analyzes the complete document → Returns comprehensive summary
   - **Spreadsheets/CSV**: LlamaParse extracts content → LLM summarizes
   - **Images**: Google Gemini Vision API analyzes → Returns description
   - **Text files**: Direct UTF-8 decoding → LLM summarizes
   - **Other document types**: LlamaParse extracts content → LLM summarizes
   - **Other types**: Appropriate handler or acknowledgment message
4. **Response**: User receives email with attachment analysis

## Example Responses

### Image Attachment
```
Your email attachment has been processed.

Attachment: photo.jpg

Summary:
This image shows a sunset over a beach. The photo captures:
1. A vibrant orange and pink sky as the sun sets on the horizon
2. Calm ocean waters reflecting the sunset colors
3. A sandy beach in the foreground
4. Several people silhouetted against the sunset

The overall setting appears to be a peaceful coastal scene during golden hour.
```

### Word Document
```
Your email attachment has been processed.

Attachment: report.docx

Summary:
• Q4 2024 Sales Report
• Revenue increased 23% year-over-year
• Top performing regions: North America, Europe
• Key challenges: Supply chain delays
• Recommendations: Expand distribution network
```

### JSON File
```
Your email attachment has been processed.

Attachment: config.json

Summary:
Configuration file containing:
• Application settings with database connection details
• API endpoints for production and staging environments
• Feature flags for new functionality
• Logging and monitoring configuration
```

## Technical Implementation

### PDF Processing Code
```python
# Create a Part object with the PDF data
pdf_part = types.Part.from_bytes(
    data=decoded_content,
    mime_type=mime_type  # e.g., "application/pdf"
)

# Generate content with both text prompt and PDF
prompt_text = (
    f"Analyze this PDF document (filename: {attachment.name}) and provide:\n"
    "1. A brief summary of the main content and purpose\n"
    "2. Key points, findings, or conclusions\n"
    "3. Any notable data, tables, charts, or images\n"
    "4. The document structure and organization\n\n"
    "Provide a concise, bullet-point summary."
)

response = await self.genai_client.aio.models.generate_content(
    model="gemini-2.0-flash",  # Using multi-modal model with PDF support
    contents=[prompt_text, pdf_part]
)

summary = response.text
```

### Image Processing Code
```python
# Create a Part object with the image data
image_part = types.Part.from_bytes(
    data=decoded_content,
    mime_type=mime_type
)

# Generate content with both text prompt and image
prompt_text = (
    f"Analyze this image (filename: {attachment.name}) and provide:\n"
    "1. A brief description of what the image shows\n"
    "2. Any notable objects, people, or text visible\n"
    "3. The general context or setting\n\n"
    "Keep the summary concise and informative."
)

response = await self.genai_client.aio.models.generate_content(
    model="gemini-2.0-flash",  # Using vision-capable model
    contents=[prompt_text, image_part]
)

summary = response.text
```

## Environment Requirements

The following environment variables must be set:
- `GEMINI_API_KEY` - For Google Gemini LLM and vision capabilities
- `LLAMA_CLOUD_API_KEY` - For LlamaParse document processing

## Limitations

1. **Video/Audio**: Full processing requires File API integration (planned future enhancement)
2. **File Size**: Very large text files are truncated to 50,000 characters
3. **Binary Files**: Unsupported binary formats return informative error messages
4. **Network**: All processing happens synchronously per attachment

## Future Enhancements

- [ ] Video/audio processing via Gemini File API
- [ ] Batch processing optimization for multiple attachments
- [ ] Support for additional document formats
- [ ] Attachment content caching for duplicate files
- [ ] Progress streaming for large file processing

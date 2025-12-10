"""Tests for attachment type handling including images and other file types.

This module tests that the workflow correctly processes various attachment types:
- Images (using Gemini vision API)
- Word documents and PowerPoint presentations
- Text files (txt, json, xml, markdown)
- Videos and audio (acknowledgment only)

Note: These tests mock the LLM clients before importing the workflow module
to avoid API connection errors during test collection.
"""

import base64
import os
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# Set dummy API keys
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "test-dummy-key-for-testing")

# Mock the LLM/genai clients before importing the workflow
with patch("llama_index.llms.google_genai.GoogleGenAI"):
    with patch("google.genai.Client"):
        with patch("llama_parse.LlamaParse"):
            from basic.email_workflow import EmailWorkflow

from basic.models import Attachment, CallbackConfig, EmailData


@pytest.mark.asyncio
async def test_image_attachment_processing():
    """Test that image attachments are processed using Gemini vision API."""
    
    # Create a mock image (1x1 pixel PNG)
    mock_image_data = base64.b64encode(
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
        b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    ).decode('utf-8')
    
    attachment = Attachment(
        id="img-1",
        name="test_image.png",
        type="image/png",
        content=mock_image_data
    )
    
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test Image",
        text="Please analyze this image",
        attachments=[attachment]
    )
    
    callback = CallbackConfig(
        callback_url="http://test.local/callback",
        auth_token="test-token"
    )
    
    # Mock the genai client
    mock_response = MagicMock()
    mock_response.text = "This image shows a simple 1x1 pixel test pattern."
    
    mock_genai_client = MagicMock()
    mock_genai_client.models.generate_content = MagicMock(return_value=mock_response)
    
    # Mock httpx for callback
    mock_http_response = MagicMock()
    mock_http_response.raise_for_status = MagicMock()
    
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_http_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=None)
    
    with patch("httpx.AsyncClient", return_value=mock_http_client):
        # Patch the genai_client on the workflow class
        with patch.object(EmailWorkflow, "genai_client", mock_genai_client):
            from basic.email_workflow import email_workflow
            
            # Run the workflow with the email data
            from workflows.events import StartEvent
            result = await email_workflow.run(
                email_data=email_data,
                callback=callback
            )
    
    # Verify that the genai client was called
    assert mock_genai_client.models.generate_content.called
    call_args = mock_genai_client.models.generate_content.call_args
    
    # Check that it was called with the right model
    assert call_args.kwargs["model"] == "gemini-2.0-flash-exp"
    
    # Check that contents includes both text and image
    contents = call_args.kwargs["contents"]
    assert len(contents) == 2
    assert isinstance(contents[0], str)  # Prompt text
    # contents[1] should be a Part object with image data


@pytest.mark.asyncio
async def test_word_document_attachment():
    """Test that Word documents are processed using LlamaParse."""
    
    # Mock Word document content
    mock_doc_content = base64.b64encode(b"Mock Word document content").decode('utf-8')
    
    attachment = Attachment(
        id="doc-1",
        name="test_document.docx",
        type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content=mock_doc_content
    )
    
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test Word Doc",
        text="Please summarize this document",
        attachments=[attachment]
    )
    
    callback = CallbackConfig(
        callback_url="http://test.local/callback",
        auth_token="test-token"
    )
    
    # Mock LlamaParse
    mock_document = MagicMock()
    mock_document.get_content = MagicMock(return_value="This is the parsed content of the Word document.")
    
    mock_llama_parser = MagicMock()
    mock_llama_parser.load_data = MagicMock(return_value=[mock_document])
    
    # Mock LLM response
    mock_llm_response = MagicMock()
    mock_llm_response.__str__ = MagicMock(return_value="Summary: This is a test document.")
    
    mock_llm = AsyncMock()
    mock_llm.acomplete = AsyncMock(return_value=mock_llm_response)
    
    # Mock httpx for callback
    mock_http_response = MagicMock()
    mock_http_response.raise_for_status = MagicMock()
    
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_http_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=None)
    
    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with patch.object(EmailWorkflow, "llama_parser", mock_llama_parser):
            with patch.object(EmailWorkflow, "llm", mock_llm):
                from basic.email_workflow import email_workflow
                
                result = await email_workflow.run(
                    email_data=email_data,
                    callback=callback
                )
    
    # Verify LlamaParse was called
    assert mock_llama_parser.load_data.called
    
    # Verify LLM was called for summarization
    assert mock_llm.acomplete.called


@pytest.mark.asyncio
async def test_text_file_attachment():
    """Test that plain text files are read and summarized."""
    
    # Mock text file content
    text_content = "This is a sample text file.\nIt contains multiple lines.\nFor testing purposes."
    mock_text_data = base64.b64encode(text_content.encode('utf-8')).decode('utf-8')
    
    attachment = Attachment(
        id="txt-1",
        name="test_file.txt",
        type="text/plain",
        content=mock_text_data
    )
    
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test Text File",
        text="Please summarize this text",
        attachments=[attachment]
    )
    
    callback = CallbackConfig(
        callback_url="http://test.local/callback",
        auth_token="test-token"
    )
    
    # Mock LLM response
    mock_llm_response = MagicMock()
    mock_llm_response.__str__ = MagicMock(return_value="Summary: A test text file with multiple lines.")
    
    mock_llm = AsyncMock()
    mock_llm.acomplete = AsyncMock(return_value=mock_llm_response)
    
    # Mock httpx for callback
    mock_http_response = MagicMock()
    mock_http_response.raise_for_status = MagicMock()
    
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_http_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=None)
    
    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with patch.object(EmailWorkflow, "llm", mock_llm):
            from basic.email_workflow import email_workflow
            
            result = await email_workflow.run(
                email_data=email_data,
                callback=callback
            )
    
    # Verify LLM was called
    assert mock_llm.acomplete.called
    
    # Verify the prompt included the text content
    call_args = mock_llm.acomplete.call_args[0][0]
    assert "text/plain" in call_args
    assert text_content in call_args


@pytest.mark.asyncio
async def test_json_file_attachment():
    """Test that JSON files are read and summarized."""
    
    # Mock JSON content
    json_content = '{"name": "test", "value": 123, "items": ["a", "b", "c"]}'
    mock_json_data = base64.b64encode(json_content.encode('utf-8')).decode('utf-8')
    
    attachment = Attachment(
        id="json-1",
        name="data.json",
        type="application/json",
        content=mock_json_data
    )
    
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test JSON",
        text="Please summarize this JSON",
        attachments=[attachment]
    )
    
    callback = CallbackConfig(
        callback_url="http://test.local/callback",
        auth_token="test-token"
    )
    
    # Mock LLM response
    mock_llm_response = MagicMock()
    mock_llm_response.__str__ = MagicMock(return_value="Summary: JSON with name, value, and items array.")
    
    mock_llm = AsyncMock()
    mock_llm.acomplete = AsyncMock(return_value=mock_llm_response)
    
    # Mock httpx for callback
    mock_http_response = MagicMock()
    mock_http_response.raise_for_status = MagicMock()
    
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_http_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=None)
    
    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with patch.object(EmailWorkflow, "llm", mock_llm):
            from basic.email_workflow import email_workflow
            
            result = await email_workflow.run(
                email_data=email_data,
                callback=callback
            )
    
    # Verify LLM was called
    assert mock_llm.acomplete.called


@pytest.mark.asyncio
async def test_powerpoint_attachment():
    """Test that PowerPoint presentations are processed using LlamaParse."""
    
    # Mock PowerPoint content
    mock_ppt_content = base64.b64encode(b"Mock PowerPoint content").decode('utf-8')
    
    attachment = Attachment(
        id="ppt-1",
        name="presentation.pptx",
        type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        content=mock_ppt_content
    )
    
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test PowerPoint",
        text="Please summarize this presentation",
        attachments=[attachment]
    )
    
    callback = CallbackConfig(
        callback_url="http://test.local/callback",
        auth_token="test-token"
    )
    
    # Mock LlamaParse
    mock_document = MagicMock()
    mock_document.get_content = MagicMock(return_value="Slide 1: Introduction\nSlide 2: Main Points")
    
    mock_llama_parser = MagicMock()
    mock_llama_parser.load_data = MagicMock(return_value=[mock_document])
    
    # Mock LLM response
    mock_llm_response = MagicMock()
    mock_llm_response.__str__ = MagicMock(return_value="Summary: Presentation with Introduction and Main Points.")
    
    mock_llm = AsyncMock()
    mock_llm.acomplete = AsyncMock(return_value=mock_llm_response)
    
    # Mock httpx for callback
    mock_http_response = MagicMock()
    mock_http_response.raise_for_status = MagicMock()
    
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_http_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=None)
    
    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with patch.object(EmailWorkflow, "llama_parser", mock_llama_parser):
            with patch.object(EmailWorkflow, "llm", mock_llm):
                from basic.email_workflow import email_workflow
                
                result = await email_workflow.run(
                    email_data=email_data,
                    callback=callback
                )
    
    # Verify LlamaParse was called
    assert mock_llama_parser.load_data.called


@pytest.mark.asyncio
async def test_video_attachment_acknowledgment():
    """Test that video attachments get an acknowledgment message."""
    
    # Mock video content
    mock_video_content = base64.b64encode(b"Mock video data").decode('utf-8')
    
    attachment = Attachment(
        id="vid-1",
        name="video.mp4",
        type="video/mp4",
        content=mock_video_content
    )
    
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test Video",
        text="Please analyze this video",
        attachments=[attachment]
    )
    
    callback = CallbackConfig(
        callback_url="http://test.local/callback",
        auth_token="test-token"
    )
    
    # Mock httpx for callback
    mock_http_response = MagicMock()
    mock_http_response.raise_for_status = MagicMock()
    
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_http_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=None)
    
    with patch("httpx.AsyncClient", return_value=mock_http_client):
        from basic.email_workflow import email_workflow
        
        result = await email_workflow.run(
            email_data=email_data,
            callback=callback
        )
    
    # Verify callback was made
    assert mock_http_client.post.called
    
    # Check the callback payload mentions video and File API
    call_args = mock_http_client.post.call_args
    payload = call_args.kwargs["json"]
    assert "video/mp4" in payload["text"]
    assert "File API" in payload["text"] or "not yet implemented" in payload["text"]


@pytest.mark.asyncio
async def test_unsupported_attachment_type():
    """Test that unsupported attachment types get an appropriate message."""
    
    # Mock unknown file type
    mock_data = base64.b64encode(b"Unknown binary data").decode('utf-8')
    
    attachment = Attachment(
        id="unknown-1",
        name="mystery.xyz",
        type="application/x-unknown",
        content=mock_data
    )
    
    email_data = EmailData(
        from_email="user@example.com",
        to_email="workflow@example.com",
        subject="Test Unknown Type",
        text="What is this file?",
        attachments=[attachment]
    )
    
    callback = CallbackConfig(
        callback_url="http://test.local/callback",
        auth_token="test-token"
    )
    
    # Mock httpx for callback
    mock_http_response = MagicMock()
    mock_http_response.raise_for_status = MagicMock()
    
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_http_response)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=None)
    
    with patch("httpx.AsyncClient", return_value=mock_http_client):
        from basic.email_workflow import email_workflow
        
        result = await email_workflow.run(
            email_data=email_data,
            callback=callback
        )
    
    # Verify callback was made
    assert mock_http_client.post.called
    
    # Check the callback payload mentions unsupported type
    call_args = mock_http_client.post.call_args
    payload = call_args.kwargs["json"]
    assert "Unsupported attachment type" in payload["text"]
    assert "application/x-unknown" in payload["text"]

#!/usr/bin/env python3
"""
Test to verify that PDF file_id is properly passed through the entire workflow
and included in the callback request.
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

async def test_full_workflow():
    """Test the complete workflow from print_to_pdf through callback."""
    
    # Mock the LLM and GenAI client
    with patch("llama_index.llms.google_genai.GoogleGenAI") as mock_llm, \
         patch("google.genai.Client") as mock_genai, \
         patch("basic.utils.upload_file_to_llamacloud") as mock_upload:
        
        from basic.email_workflow import EmailWorkflow
        from basic.models import EmailData, Attachment, CallbackConfig
        
        # Mock upload to return a file_id
        mock_upload.return_value = "test-pdf-file-id-123"
        
        # Create workflow
        workflow = EmailWorkflow()
        
        # Mock the LLM response for generating user response
        mock_llm_instance = MagicMock()
        mock_llm_instance.acomplete = AsyncMock(return_value=MagicMock(
            text="I've processed your request and generated a PDF document. Please see the attached files."
        ))
        workflow.llm = mock_llm_instance
        
        # Simulate results from print_to_pdf tool
        results = [
            {
                "step": 1,
                "tool": "print_to_pdf",
                "description": "Generate PDF document",
                "success": True,
                "file_id": "test-pdf-file-id-123",  # This should be in the callback
            }
        ]
        
        # Test the _collect_attachments method
        print("Testing _collect_attachments:")
        attachments = workflow._collect_attachments(results)
        
        print(f"  Number of attachments: {len(attachments)}")
        assert len(attachments) == 1, "Should collect exactly 1 attachment"
        
        attachment = attachments[0]
        print(f"  Attachment name: {attachment.name}")
        print(f"  Attachment type: {attachment.type}")
        print(f"  Attachment file_id: {attachment.file_id}")
        
        assert attachment.name == "output_step_1.pdf", f"Expected 'output_step_1.pdf', got '{attachment.name}'"
        assert attachment.type == "application/pdf", f"Expected 'application/pdf', got '{attachment.type}'"
        assert attachment.file_id == "test-pdf-file-id-123", f"Expected 'test-pdf-file-id-123', got '{attachment.file_id}'"
        
        # Test serialization to JSON (what gets sent to callback)
        print("\nTesting JSON serialization for callback:")
        from basic.models import SendEmailRequest
        
        email_request = SendEmailRequest(
            to_email="user@example.com",
            subject="Re: Test",
            text="Test response",
            html="<p>Test response</p>",
            attachments=attachments
        )
        
        json_data = email_request.model_dump()
        print(f"  JSON structure:")
        print(json.dumps(json_data, indent=4))
        
        # Verify file_id is in the JSON
        assert "attachments" in json_data, "JSON should have 'attachments' field"
        assert len(json_data["attachments"]) == 1, "Should have 1 attachment in JSON"
        
        attachment_json = json_data["attachments"][0]
        print(f"\n  Checking attachment in JSON:")
        print(f"    name: {attachment_json.get('name')}")
        print(f"    type: {attachment_json.get('type')}")
        print(f"    file_id: {attachment_json.get('file_id')}")
        
        assert "file_id" in attachment_json, "Attachment JSON should have 'file_id' field"
        assert attachment_json["file_id"] == "test-pdf-file-id-123", \
            f"file_id should be 'test-pdf-file-id-123', got '{attachment_json.get('file_id')}'"
        
        print("\n✅ All tests passed! file_id is properly included in callback JSON")
        
        # Now test the actual callback sending
        print("\n\nTesting actual callback with httpx:")
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Send callback
            await workflow._send_callback_email(
                callback_url="http://localhost:8000/callback",
                auth_token="test-token",
                email_request=email_request
            )
            
            # Verify the POST was called with correct JSON
            assert mock_client.post.called, "httpx post should have been called"
            call_args = mock_client.post.call_args
            
            print(f"  Callback URL: {call_args[1]['json']['to_email']}")
            print(f"  Callback JSON attachments:")
            callback_attachments = call_args[1]['json']['attachments']
            for att in callback_attachments:
                print(f"    - {att['name']}: file_id={att.get('file_id')}")
            
            # Verify file_id is in the callback
            assert len(callback_attachments) == 1
            assert callback_attachments[0]['file_id'] == "test-pdf-file-id-123", \
                "file_id should be in the callback JSON"
            
            print("\n✅ Callback test passed! file_id is sent in the POST request")

if __name__ == "__main__":
    asyncio.run(test_full_workflow())

"""Email processing workflow for handling inbound emails."""

import asyncio
import base64
import logging
import os
import pathlib
import tempfile

import google.genai as genai
from google.genai import types
import httpx
from llama_index.llms.google_genai import GoogleGenAI
from llama_parse import LlamaParse
from workflows import Context, Workflow, step
from workflows.events import Event, StartEvent, StopEvent

from .models import (
    Attachment,
    CallbackConfig,
    EmailData,
    EmailProcessingResult,
    SendEmailRequest,
)
from .utils import download_file_from_llamacloud, text_to_html, is_retryable_error, api_retry

logger = logging.getLogger(__name__)


# Use the shared retry decorator for LLM API calls
llm_api_retry = api_retry


# Gemini model configuration
# Using latest Gemini 3 models as per https://ai.google.dev/gemini-api/docs/gemini-3
GEMINI_MULTIMODAL_MODEL = "gemini-3-pro-preview"  # Latest Gemini 3 for multi-modal (images, PDFs, videos)
GEMINI_TEXT_MODEL = "gemini-3-pro-preview"  # Latest Gemini 3 for text processing

# Alternative cheaper model configuration (not currently in use)
# Gemini 2.5 Flash is optimized for cost-effective simple requests
GEMINI_CHEAP_TEXT_MODEL = "gemini-2.5-flash"  # Cheaper option for simple text tasks


class EmailStartEvent(StartEvent):
    """Start event for email workflow containing email data and callback config.

    This event is created from the JSON payload sent to the workflow server.
    The payload should contain 'email_data' and 'callback' fields at the top level.
    """

    email_data: EmailData
    callback: CallbackConfig


class EmailReceivedEvent(Event):
    """Event triggered when an email is received."""

    email_data: EmailData
    callback: CallbackConfig


class EmailProcessedEvent(Event):
    """Event triggered when email processing is complete."""

    result: EmailProcessingResult


class AttachmentFoundEvent(Event):
    """Event triggered when an email attachment is found."""

    attachment: Attachment
    original_email: EmailData
    callback: CallbackConfig


class AttachmentSummaryEvent(Event):
    """Event triggered when an attachment has been summarized."""

    summary: str
    filename: str
    success: bool
    original_email: EmailData
    callback: CallbackConfig


class EmailWorkflow(Workflow):
    """Workflow for processing inbound emails from SendGrid Inbound Parse.

    This workflow receives email data and a callback configuration.
    When processing is complete, it calls back to the webhook server
    to send a response email.
    """

    llama_parser = LlamaParse(result_type="markdown")
    llm = GoogleGenAI(model=GEMINI_TEXT_MODEL, api_key=os.getenv("GEMINI_API_KEY"))
    # Create genai client for multi-modal support (images, videos, etc.)
    genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    @llm_api_retry
    async def _llm_complete_with_retry(self, prompt: str) -> str:
        """Execute LLM completion with automatic retry on transient errors.
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            The LLM response as a string
        """
        response = await self.llm.acomplete(prompt)
        return str(response)

    @llm_api_retry
    async def _genai_generate_content_with_retry(self, model: str, contents: list) -> str:
        """Execute Gemini multi-modal content generation with automatic retry.
        
        Args:
            model: The model name (e.g., "gemini-3-pro-preview")
            contents: List of content parts (text, images, etc.)
            
        Returns:
            The generated text response
        """
        response = await self.genai_client.aio.models.generate_content(
            model=model,
            contents=contents
        )
        return response.text

    @llm_api_retry
    async def _parse_document_with_retry(self, file_path: str) -> list:
        """Parse a document using LlamaParse with automatic retry.
        
        Args:
            file_path: Path to the file to parse
            
        Returns:
            List of parsed documents
        """
        return await asyncio.to_thread(self.llama_parser.load_data, file_path)

    @step
    async def receive_email(
        self, ev: EmailStartEvent, ctx: Context
    ) -> EmailReceivedEvent:
        """Receive and validate incoming email data.

        The WorkflowServer deserializes the JSON payload into EmailStartEvent.
        The payload should have 'email_data' and 'callback' fields at the top level.

        Args:
            ev: EmailStartEvent containing email_data and callback config
            ctx: Workflow context

        Returns:
            EmailReceivedEvent with validated email data and callback
        """
        # EmailStartEvent already has the validated email_data and callback
        email_data = ev.email_data
        callback = ev.callback

        # Debug logging to see incoming email data
        logger.info(
            f"Received email: from={email_data.from_email}, "
            f"to={repr(email_data.to_email)}, "
            f"subject={email_data.subject}"
        )

        event = EmailReceivedEvent(email_data=email_data, callback=callback)
        ctx.write_event_to_stream(event)
        return event

    @step
    async def process_email(
        self, ev: EmailReceivedEvent, ctx: Context
    ) -> AttachmentFoundEvent | StopEvent | None:
        """Classify email attachments and dispatch to next steps."""
        email_data = ev.email_data
        callback = ev.callback

        try:
            if not email_data.attachments:
                # No attachments, send response email via callback
                try:
                    # Debug logging to track from_email value
                    logger.info(
                        f"Creating SendEmailRequest: to_email={email_data.from_email}, "
                        f"from_email source={repr(email_data.to_email)}, "
                        f"from_email final={repr(email_data.to_email or None)}"
                    )
                    response_text = f"Your email has been processed.\n\nResult: Email from {email_data.from_email} processed successfully (no attachments)."
                    response_email = SendEmailRequest(
                        to_email=email_data.from_email,
                        from_email=email_data.to_email or None,
                        subject=f"Re: {email_data.subject}",
                        text=response_text,
                        html=text_to_html(response_text),
                    )
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            callback.callback_url,
                            json=response_email.model_dump(),
                            headers={
                                "Content-Type": "application/json",
                                "X-Auth-Token": callback.auth_token,
                            },
                            timeout=30.0,
                        )
                        response.raise_for_status()
                        logger.info("Callback email sent successfully")
                    # Only write success event after callback succeeds
                    result = EmailProcessingResult(
                        success=True,
                        message=f"Email from {email_data.from_email} processed successfully (no attachments).",
                        from_email=email_data.from_email,
                        email_subject=email_data.subject,
                    )
                    ctx.write_event_to_stream(EmailProcessedEvent(result=result))
                    return StopEvent(result=result)

                except httpx.HTTPError as e:
                    logger.error("Failed to send callback email: %s", str(e))
                    failure = EmailProcessingResult(
                        success=False,
                        message=f"Email processed but callback failed: {e!s}",
                        from_email=email_data.from_email,
                        email_subject=email_data.subject,
                    )
                    ctx.write_event_to_stream(EmailProcessedEvent(result=failure))
                    return StopEvent(result=failure)

            # Got attachments, fan out events for each one
            for attachment in email_data.attachments:
                ctx.send_event(
                    AttachmentFoundEvent(
                        attachment=attachment,
                        original_email=email_data,
                        callback=callback,
                    )
                )
            return None  # The workflow continues with the fanned-out events

        except Exception as e:  # Catch-all to keep response format stable
            logger.exception("Unexpected error while processing email")
            result = EmailProcessingResult(
                success=False,
                message=f"Failed to process email: {e!s}",
                from_email=email_data.from_email,
                email_subject=email_data.subject,
            )
            ctx.write_event_to_stream(EmailProcessedEvent(result=result))
            return StopEvent(result=result)

    @step
    async def process_attachment(
        self, ev: AttachmentFoundEvent, ctx: Context
    ) -> AttachmentSummaryEvent:
        """Process a single attachment, classify and summarize it."""
        # Wrap entire step in try-except to ensure we always return AttachmentSummaryEvent
        tmp_path = None  # Track temp file path for cleanup
        try:
            attachment = ev.attachment
            summary = ""
            success = True

            try:
                # Get file content either from base64 or LlamaCloud
                if attachment.file_id:
                    # Download from LlamaCloud
                    logger.info(
                        f"Downloading attachment {attachment.name} from LlamaCloud (file_id: {attachment.file_id})"
                    )
                    decoded_content = await download_file_from_llamacloud(
                        attachment.file_id
                    )
                elif attachment.content:
                    # Decode from base64
                    decoded_content = base64.b64decode(attachment.content)
                else:
                    summary = f"Attachment {attachment.name} has neither content nor file_id"
                    return AttachmentSummaryEvent(
                        summary=summary,
                        filename=attachment.name,
                        success=False,
                        original_email=ev.original_email,
                        callback=ev.callback,
                    )
            except (ValueError, TypeError) as e:
                summary = f"Could not get attachment content: {attachment.name} - {e!s}"
                return AttachmentSummaryEvent(
                    summary=summary,
                    filename=attachment.name,
                    success=False,
                    original_email=ev.original_email,
                    callback=ev.callback,
                )

            try:
                # Classification and processing based on MIME type
                mime_type = attachment.type.lower()
                
                if "pdf" in mime_type:
                    # Use Gemini's native PDF understanding capabilities
                    logger.info(f"Processing PDF attachment with Gemini multi-modal: {attachment.name}")
                    
                    # Create a Part object with the PDF data
                    pdf_part = types.Part.from_bytes(
                        data=decoded_content,
                        mime_type=mime_type
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
                    
                    # Use async API with multi-modal model that supports PDFs
                    summary = await self._genai_generate_content_with_retry(
                        model=GEMINI_MULTIMODAL_MODEL,
                        contents=[prompt_text, pdf_part]
                    )
                
                elif "sheet" in mime_type or "csv" in mime_type:
                    # Use LlamaParse for spreadsheet types
                    # Create a temporary file for LlamaParse
                    with tempfile.NamedTemporaryFile(delete=False) as tmp:
                        tmp.write(decoded_content)
                        tmp_path = tmp.name
                    
                    documents = await self._parse_document_with_retry(tmp_path)
                    content = "\n".join([doc.get_content() for doc in documents])

                    # Summarize with LLM
                    prompt = f"Provide a short, bullet-point summary of the following document:\n\n{content}"
                    summary = await self._llm_complete_with_retry(prompt)

                elif "image" in mime_type:
                    # Use Google Gemini's vision capabilities for image analysis
                    logger.info(f"Processing image attachment: {attachment.name}")
                    
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
                    
                    # Use async API to avoid blocking the event loop
                    summary = await self._genai_generate_content_with_retry(
                        model=GEMINI_MULTIMODAL_MODEL,
                        contents=[prompt_text, image_part]
                    )

                elif (
                    "word" in mime_type
                    or "msword" in mime_type
                    or "wordprocessingml" in mime_type
                    or "presentationml" in mime_type
                    or "presentation" in mime_type
                    or "powerpoint" in mime_type
                ):
                    # Word documents, PowerPoint - use LlamaParse
                    # Create a temporary file for LlamaParse
                    logger.info(
                        f"Processing office document: {attachment.name} ({mime_type})"
                    )
                    with tempfile.NamedTemporaryFile(delete=False) as tmp:
                        tmp.write(decoded_content)
                        tmp_path = tmp.name
                    
                    documents = await self._parse_document_with_retry(tmp_path)
                    content = "\n".join([doc.get_content() for doc in documents])

                    # Summarize with LLM
                    prompt = f"Provide a short, bullet-point summary of the following document:\n\n{content}"
                    summary = await self._llm_complete_with_retry(prompt)

                elif (
                    "json" in mime_type
                    or "xml" in mime_type
                    or "markdown" in mime_type
                    or "text" in mime_type
                ):
                    # JSON, XML, Markdown, plain text - read directly and summarize
                    # Note: Ordered from most specific to least specific
                    logger.info(f"Processing text file: {attachment.name} ({mime_type})")
                    try:
                        # Try to decode as UTF-8 text
                        content = decoded_content.decode("utf-8")
                        
                        # Truncate if too long (to avoid token limits)
                        max_chars = 50000
                        if len(content) > max_chars:
                            content = content[:max_chars] + "\n... (truncated)"
                        
                        # Summarize with LLM
                        prompt = f"Provide a short, bullet-point summary of the following {mime_type} content:\n\n{content}"
                        summary = await self._llm_complete_with_retry(prompt)
                    except UnicodeDecodeError:
                        summary = f"Could not decode text file {attachment.name} as UTF-8"
                        success = False

                elif "video" in mime_type or "audio" in mime_type:
                    # Videos and audio - note that these require special handling
                    summary = (
                        f"This is a {mime_type} file named '{attachment.name}'. "
                        "Video and audio summarization requires uploading to Gemini's File API "
                        "and is not yet implemented in this workflow."
                    )
                    
                else:
                    summary = (
                        f"Unsupported attachment type: {mime_type} (filename: {attachment.name}). "
                        "Supported types: PDF, images, spreadsheets, CSV, Word documents, "
                        "PowerPoint presentations, text files, JSON, XML, and Markdown."
                    )
                    success = False

            except Exception as e:
                logger.exception("Failed to process attachment %s", attachment.name)
                summary = f"Error processing attachment {attachment.name}: {e!s}"
                success = False
            finally:
                # Clean up the temporary file if it was created
                if tmp_path:
                    pathlib.Path(tmp_path).unlink()

            return AttachmentSummaryEvent(
                summary=summary,
                filename=attachment.name,
                success=success,
                original_email=ev.original_email,
                callback=ev.callback,
            )
        except Exception as e:
            # Catch any unhandled exceptions (e.g., event validation, attribute access)
            logger.exception("Critical error in process_attachment step")
            # Clean up temp file if it was created before the exception
            if tmp_path:
                try:
                    pathlib.Path(tmp_path).unlink()
                except Exception as cleanup_error:
                    logger.warning(
                        "Failed to cleanup temporary file %s: %s",
                        tmp_path,
                        cleanup_error,
                    )
            # Try to extract what information we can for the error event
            try:
                filename = ev.attachment.name
            except Exception:
                # Catch AttributeError, KeyError, etc. for graceful degradation when event is malformed
                filename = "unknown"
            try:
                original_email = ev.original_email
                callback = ev.callback
            except Exception:
                # Catch AttributeError, KeyError, etc. for graceful degradation when event is malformed
                # If we can't access the event data, create minimal valid instances
                # to ensure we always return AttachmentSummaryEvent (never raise)
                logger.error(
                    "Cannot access event data in process_attachment error handler, using placeholder values"
                )
                original_email = EmailData(
                    from_email="error@placeholder.invalid",
                    subject="Error: Unable to access original email data",
                )
                callback = CallbackConfig(
                    callback_url="http://error-placeholder.invalid/callback",
                    auth_token="INVALID-PLACEHOLDER-TOKEN",
                )

            return AttachmentSummaryEvent(
                summary=f"Critical error processing attachment: {e!s}",
                filename=filename,
                success=False,
                original_email=original_email,
                callback=callback,
            )

    @step
    async def send_summary_email(
        self, ev: AttachmentSummaryEvent, ctx: Context
    ) -> StopEvent:
        """Send an email with the attachment summary."""
        # Wrap entire step in try-except to ensure we always return StopEvent with EmailProcessingResult
        try:
            email_data = ev.original_email
            callback = ev.callback

            # Send response email via callback
            try:
                # Debug logging to track from_email value
                logger.info(
                    f"Creating SendEmailRequest for attachment: to_email={email_data.from_email}, "
                    f"from_email source={repr(email_data.to_email)}, "
                    f"from_email final={repr(email_data.to_email or None)}"
                )
                response_text = f"Your email attachment has been processed.\n\nAttachment: {ev.filename}\n\nSummary:\n{ev.summary}"
                response_email = SendEmailRequest(
                    to_email=email_data.from_email,
                    from_email=email_data.to_email or None,
                    subject=f"Re: {email_data.subject}",
                    text=response_text,
                    html=text_to_html(response_text),
                )

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        callback.callback_url,
                        json=response_email.model_dump(),
                        headers={
                            "Content-Type": "application/json",
                            "X-Auth-Token": callback.auth_token,
                        },
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    logger.info(
                        f"Callback email for attachment {ev.filename} sent successfully"
                    )

                # Only write success event after callback succeeds
                result = EmailProcessingResult(
                    success=True,
                    message=f"Processed attachment '{ev.filename}': {ev.summary}",
                    from_email=email_data.from_email,
                    email_subject=email_data.subject,
                )
                ctx.write_event_to_stream(EmailProcessedEvent(result=result))
                return StopEvent(result=result)

            except httpx.HTTPError as e:
                logger.error(
                    f"Failed to send callback email for attachment {ev.filename}: {e!s}"
                )
                failure = EmailProcessingResult(
                    success=False,
                    message=f"Attachment processed but callback failed: {e!s}",
                    from_email=email_data.from_email,
                    email_subject=email_data.subject,
                )
                ctx.write_event_to_stream(EmailProcessedEvent(result=failure))
                return StopEvent(result=failure)

        except Exception as e:
            # Catch any unhandled exceptions (e.g., event validation, attribute access, validation errors)
            logger.exception("Critical error in send_summary_email step")
            # Try to extract what information we can for the error result
            try:
                from_email = ev.original_email.from_email
                subject = ev.original_email.subject
            except Exception:
                # Catch AttributeError, KeyError, validation errors, etc. for graceful degradation when event is malformed
                from_email = "unknown"
                subject = "unknown"

            result = EmailProcessingResult(
                success=False,
                message=f"Critical error sending summary email: {e!s}",
                from_email=from_email,
                email_subject=subject,
            )
            ctx.write_event_to_stream(EmailProcessedEvent(result=result))
            return StopEvent(result=result)


email_workflow = EmailWorkflow(timeout=60)

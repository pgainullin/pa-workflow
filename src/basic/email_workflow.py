"""Email processing workflow for handling inbound emails."""

import base64
import logging
import os
import pathlib
import tempfile

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

logger = logging.getLogger(__name__)


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
    llm = GoogleGenAI(model="gemini-2.5-flash", api_key=os.getenv("GEMINI_API_KEY"))

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

        event = EmailReceivedEvent(email_data=email_data, callback=callback)
        ctx.write_event_to_stream(event)
        return event

    @step
    async def process_email(
        self, ev: EmailReceivedEvent, ctx: Context
    ) -> StopEvent | None:
        """Classify email attachments and dispatch to next steps."""
        email_data = ev.email_data
        callback = ev.callback

        try:
            if not email_data.attachments:
                # No attachments, send response email via callback
                try:
                    response_email = SendEmailRequest(
                        to_email=email_data.from_email,
                        from_email=email_data.to_email,
                        subject=f"Re: {email_data.subject}",
                        text=f"Your email has been processed.\n\nResult: Email from {email_data.from_email} processed successfully (no attachments).",
                        reply_to=email_data.from_email,
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
                decoded_content = base64.b64decode(attachment.content)
            except (ValueError, TypeError):
                summary = f"Could not decode attachment: {attachment.name}"
                return AttachmentSummaryEvent(
                    summary=summary,
                    filename=attachment.name,
                    success=False,
                    original_email=ev.original_email,
                    callback=ev.callback,
                )

            # Create a temporary file to store the decoded content
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(decoded_content)
                tmp_path = tmp.name

            try:
                # Simple classification based on MIME type
                mime_type = attachment.type.lower()
                if "pdf" in mime_type or "sheet" in mime_type or "csv" in mime_type:
                    # Use LlamaParse
                    documents = self.llama_parser.load_data(tmp_path)
                    content = "\n".join([doc.get_content() for doc in documents])

                    # Summarize with OpenAI
                    prompt = f"Provide a short, bullet-point summary of the following document:\n\n{content}"
                    response = await self.llm.acomplete(prompt)
                    summary = str(response)

                elif "image" in mime_type:
                    summary = (
                        f"This is an image named '{attachment.name}'. Summarization of images "
                        "is not yet implemented."
                    )
                else:
                    summary = f"Unsupported attachment type: {mime_type}"

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
                except Exception:
                    pass  # Ignore cleanup errors
            # Try to extract what information we can for the error event
            try:
                filename = ev.attachment.name
            except Exception:
                # Broad exception needed here for graceful degradation when event is malformed
                filename = "unknown"
            try:
                original_email = ev.original_email
                callback = ev.callback
            except Exception:
                # Broad exception needed here for graceful degradation when event is malformed
                # If we can't access the event data, we have a critical failure
                # This should be very rare, but we need to handle it
                logger.error(
                    "Cannot access event data in process_attachment error handler"
                )
                raise  # Re-raise to let workflow framework handle it

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
                response_email = SendEmailRequest(
                    to_email=email_data.from_email,
                    from_email=email_data.to_email,
                    subject=f"Re: {email_data.subject} (Attachment: {ev.filename})",
                    text=f"Your email attachment has been processed.\n\nSummary for {ev.filename}:\n{ev.summary}",
                    reply_to=email_data.from_email,
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
                # Broad exception needed here for graceful degradation when event is malformed
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

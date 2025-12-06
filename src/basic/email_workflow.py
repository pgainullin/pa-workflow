"""Email processing workflow for handling inbound emails."""

import logging

import httpx
from workflows import Context, Workflow, step
from workflows.events import Event, StartEvent, StopEvent

from .models import (
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


class EmailWorkflow(Workflow):
    """Workflow for processing inbound emails from SendGrid Inbound Parse.

    This workflow receives email data and a callback configuration.
    When processing is complete, it calls back to the webhook server
    to send a response email.
    """

    @step
    async def receive_email(self, ev: EmailStartEvent, ctx: Context) -> EmailReceivedEvent:
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
    async def process_email(self, ev: EmailReceivedEvent, ctx: Context) -> StopEvent:
        """Process the received email and send response via callback.

        This step processes the email and then calls back to the webhook
        server to send a response email to the original sender.

        Args:
            ev: EmailReceivedEvent containing the email data and callback
            ctx: Workflow context

        Returns:
            StopEvent with processing result
        """
        email_data = ev.email_data
        callback = ev.callback

        # TODO: Replace this placeholder with actual email processing logic.
        # This is where LLM processing, email classification, content extraction,
        # or other business logic would be implemented. Currently, all emails
        # are marked as successfully processed without any actual validation.
        result = EmailProcessingResult(
            success=True,
            message=f"Email from {email_data.from_email} processed successfully",
            email_from=email_data.from_email,
            email_subject=email_data.subject,
        )

        ctx.write_event_to_stream(EmailProcessedEvent(result=result))

        # Send response email via callback
        try:
            response_email = SendEmailRequest(
                to_email=email_data.from_email,  # Reply to sender
                from_email=email_data.to_email,
                subject=f"Re: {email_data.subject}",
                text=f"Your email has been processed.\n\nResult: {result.message}",
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
        except httpx.HTTPError as e:
            logger.error("Failed to send callback email: %s", str(e))
            # Raise an exception to indicate workflow failure
            raise RuntimeError(f"Email processed but callback failed: {e!s}")

        return StopEvent(result=result)


email_workflow = EmailWorkflow(timeout=60)

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
    """Start event for email workflow containing email data and callback config."""

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
    async def receive_email(self, ev: StartEvent, ctx: Context) -> EmailReceivedEvent:
        """Receive and validate incoming email data.

        Args:
            ev: Start event containing email_data and callback config
            ctx: Workflow context

        Returns:
            EmailReceivedEvent with validated email data and callback
        """
        # The WorkflowServer creates a base StartEvent from the JSON payload.
        # The email_data and callback are passed as kwargs to workflow.run(),
        # but may not be directly accessible on the StartEvent object.
        # We need to reconstruct EmailStartEvent from the event's data.
        
        # Get all data from the event (including any extra fields)
        event_dict = ev.model_dump()
        
        # Also check model_extra for Pydantic v2 extra fields
        if hasattr(ev, 'model_extra') and ev.model_extra:
            event_dict.update(ev.model_extra)
        
        # Debug: log what we received
        logger.debug(f"StartEvent type: {type(ev)}, model_dump: {event_dict}")
        logger.debug(f"StartEvent has email_data attr: {hasattr(ev, 'email_data')}")
        logger.debug(f"StartEvent has callback attr: {hasattr(ev, 'callback')}")
        
        # Try to construct EmailStartEvent from the data
        # If email_data and callback are already EmailData/CallbackConfig objects, use them directly
        # Otherwise, they should be dicts that we can validate
        try:
            # First try direct access (in case it's already EmailStartEvent or has the attrs)
            if hasattr(ev, 'email_data') and hasattr(ev, 'callback'):
                email_data = ev.email_data
                callback = ev.callback
                # Ensure they're the right types
                if not isinstance(email_data, EmailData):
                    email_data = EmailData(**email_data) if isinstance(email_data, dict) else EmailData.model_validate(email_data)
                if not isinstance(callback, CallbackConfig):
                    callback = CallbackConfig(**callback) if isinstance(callback, dict) else CallbackConfig.model_validate(callback)
            else:
                # Construct EmailStartEvent from the event data
                email_start = EmailStartEvent(**event_dict)
                email_data = email_start.email_data
                callback = email_start.callback
        except (TypeError, ValueError, KeyError) as e:
            logger.error(
                f"Failed to extract email_data and callback from StartEvent. "
                f"Error: {e}, Event type: {type(ev)}, Event data: {event_dict}, "
                f"Event attributes: {dir(ev)}"
            )
            raise ValueError(
                "StartEvent must contain 'email_data' and 'callback' fields. "
                f"Available fields in event_dict: {list(event_dict.keys())}, "
                f"Event type: {type(ev).__name__}"
            ) from e

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
                subject=f"Re: {email_data.subject}",
                text=f"Your email has been processed.\n\nResult: {result.message}",
                reply_to=email_data.to_email,
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

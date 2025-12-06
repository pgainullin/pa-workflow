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

        The WorkflowServer passes email_data and callback as kwargs to workflow.run().
        These are accessible via the StartEvent's model_dump() or as attributes if
        StartEvent is configured to accept extra fields.

        Args:
            ev: Start event containing email_data and callback config
            ctx: Workflow context

        Returns:
            EmailReceivedEvent with validated email data and callback
        """
        # The WorkflowServer calls workflow.run(email_data=..., callback=...)
        # These kwargs should be accessible from the StartEvent.
        # Try to get them from model_dump() which includes all fields.
        event_dict = ev.model_dump()
        
        # Check for email_data and callback in the event data
        if 'email_data' not in event_dict or 'callback' not in event_dict:
            # Try model_extra for Pydantic v2 extra fields
            if hasattr(ev, 'model_extra') and ev.model_extra:
                event_dict.update(ev.model_extra)
            
            # If still not found, try direct attribute access
            if 'email_data' not in event_dict and hasattr(ev, 'email_data'):
                event_dict['email_data'] = ev.email_data
            if 'callback' not in event_dict and hasattr(ev, 'callback'):
                event_dict['callback'] = ev.callback
        
        # Validate and extract the data
        if 'email_data' not in event_dict or 'callback' not in event_dict:
            logger.error(
                f"StartEvent missing required fields. "
                f"Event type: {type(ev)}, Available fields: {list(event_dict.keys())}"
            )
            raise ValueError(
                "StartEvent must contain 'email_data' and 'callback' fields. "
                f"Received fields: {list(event_dict.keys())}"
            )
        
        # Convert to proper types if needed
        email_data_dict = event_dict['email_data']
        callback_dict = event_dict['callback']
        
        if isinstance(email_data_dict, EmailData):
            email_data = email_data_dict
        elif isinstance(email_data_dict, dict):
            email_data = EmailData(**email_data_dict)
        else:
            email_data = EmailData.model_validate(email_data_dict)
        
        if isinstance(callback_dict, CallbackConfig):
            callback = callback_dict
        elif isinstance(callback_dict, dict):
            callback = CallbackConfig(**callback_dict)
        else:
            callback = CallbackConfig.model_validate(callback_dict)

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

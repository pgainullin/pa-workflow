"""Pydantic models for email data.

Note: These models are intentionally duplicated in the webhook app to maintain
decoupling between the two deployable applications. Each app can evolve its models
independently without affecting the other.
"""

from pydantic import BaseModel, Field


class CallbackConfig(BaseModel):
    """Callback configuration for sending email responses.

    The workflow server will use this to call back to the webhook server
    when the workflow completes or needs human feedback.
    """

    callback_url: str = Field(
        ..., description="URL to call for sending email responses"
    )
    auth_token: str = Field(..., description="Authentication token for the callback")


class EmailData(BaseModel):
    """Parsed email data from SendGrid Inbound Parse webhook.

    Reference: https://docs.sendgrid.com/for-developers/parsing-email/inbound-email
    """

    from_email: str = Field(..., description="Email sender address")
    to_email: str = Field(
        default="", description="Email recipient address (may be empty for BCC)"
    )
    subject: str = Field(default="", description="Email subject line")
    text: str = Field(default="", description="Plain text body of the email")
    html: str = Field(default="", description="HTML body of the email")


class EmailProcessingResult(BaseModel):
    """Result of processing an email through the workflow."""

    success: bool = Field(..., description="Whether processing was successful")
    message: str = Field(..., description="Result message or error description")
    from_email: str = Field(default="", description="Original sender address")
    email_subject: str = Field(default="", description="Original subject line")


class SendEmailRequest(BaseModel):
    """Request to send an email via the callback URL."""

    to_email: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line")
    text: str = Field(default="(No content)", description="Plain text body of the email")
    html: str = Field(default="(No html content)", description="HTML body of the email")
    from_email: str | None = Field(
        default=None,
        description="Sender email address (uses default if not provided)",
    )
    reply_to: str | None = Field(
        default=None, description="Reply-to email address (optional)"
    )

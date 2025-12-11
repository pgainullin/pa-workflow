"""Pydantic models for email data.

Note: These models are intentionally duplicated in the webhook app to maintain
decoupling between the two deployable applications. Each app can evolve its models
independently without affecting the other.
"""

from pydantic import BaseModel, Field, model_validator


class Attachment(BaseModel):
    """Represents a single email attachment.

    Supports two modes:
    1. Base64 content mode: content field contains base64-encoded data
    2. LlamaCloud file mode: file_id references a file in LlamaCloud

    At least one of 'content' or 'file_id' must be provided.
    """

    id: str  # Or 'content-id'
    name: str  # Filename
    type: str  # MIME type (e.g., 'application/pdf')
    content: str | None = (
        None  # Base64-encoded content (optional if file_id is provided)
    )
    file_id: str | None = None  # LlamaCloud file ID (optional if content is provided)

    @model_validator(mode="after")
    def check_content_or_file_id(self):
        if self.content is None and self.file_id is None:
            raise ValueError("Attachment must have either 'content' or 'file_id'")
        return self


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
    attachments: list[Attachment] = Field(
        default_factory=list, description="List of attachments"
    )


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
    text: str = Field(
        default="(No content)", description="Plain text body of the email"
    )
    html: str = Field(default="(No html content)", description="HTML body of the email")
    from_email: str | None = Field(
        default=None,
        description="Sender email address (uses default if not provided)",
    )
    reply_to: str | None = Field(
        default=None, description="Reply-to email address (optional)"
    )
    attachments: list[Attachment] = Field(
        default_factory=list,
        description="List of attachments (with file_id for LlamaCloud files)",
    )

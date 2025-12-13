import html
import re
from importlib import resources

from .models import EmailData


_TEMPLATE_CACHE: dict[str, str] = {}


def _load_template(name: str) -> str:
    """Load a prompt template from the prompt_templates directory."""
    if name not in _TEMPLATE_CACHE:
        template_path = resources.files(__package__).joinpath("prompt_templates").joinpath(name)
        try:
            _TEMPLATE_CACHE[name] = template_path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError, PermissionError) as e:
            raise FileNotFoundError(
                f"Template file '{name}' not found or could not be read in prompt_templates directory."
            ) from e
    return _TEMPLATE_CACHE[name]


def build_triage_prompt(
    email_data: EmailData,
    tool_descriptions: str,
    response_best_practices: str,
) -> str:
    """Build the triage prompt for the LLM.

    Args:
        email_data: Email data to triage
        tool_descriptions: Description of available tools
        response_best_practices: Guidance for crafting responses

    Returns:
        Triage prompt string
    """
    max_subject_length = 500
    max_body_length = 5000

    subject = (email_data.subject or "")[:max_subject_length]

    body = email_data.text or email_data.html or "(empty)"
    if email_data.html and not email_data.text:
        body = html.unescape(re.sub(r"<[^>]+>", "", body))
    body = body[:max_body_length]

    attachment_info = ""
    if email_data.attachments:
        attachment_info = "\n\nAttachments:\n"
        for att in email_data.attachments:
            att_name = (att.name or "unnamed")[:100]
            att_type = (att.type or "unknown")[:50]
            attachment_info += f"- {att_name} ({att_type})\n"

    template = _load_template("triage_prompt.txt")
    return template.format(
        subject=subject,
        body=body,
        attachment_info=attachment_info,
        tool_descriptions=tool_descriptions,
        response_best_practices=response_best_practices,
    )


def build_verification_prompt(
    sanitized_subject: str,
    sanitized_body: str,
    initial_response: str,
    response_best_practices: str,
) -> str:
    """Build the verification prompt for the LLM."""

    template = _load_template("verification_prompt.txt")
    return template.format(
        sanitized_subject=sanitized_subject,
        sanitized_body=sanitized_body,
        initial_response=initial_response,
        response_best_practices=response_best_practices,
    )

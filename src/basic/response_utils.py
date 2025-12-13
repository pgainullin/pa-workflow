"""Helper utilities for building user responses and execution logs."""
import json
import logging
import re
from typing import Callable, Awaitable

from .models import Attachment, EmailData

logger = logging.getLogger(__name__)


def strip_html(text: str) -> str:
    """Remove HTML tags and decode basic HTML entities from a string.

    Args:
        text (str): The input string that may contain HTML tags and entities.

    Returns:
        str: The plain text with HTML tags removed and common entities decoded.
    """
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    return text


def sanitize_email_content(
    subject: str | None,
    text: str | None,
    html: str | None,
    max_subject_len: int = 200,
    max_body_len: int = 2000,
) -> tuple[str, str]:
    """
    Sanitizes and truncates email subject and body content for safe display or processing.

    Args:
        subject (str | None): The subject of the email, possibly containing HTML or unsafe characters.
        text (str | None): The plain text body of the email, if available.
        html (str | None): The HTML body of the email, if available and text is not provided.
        max_subject_len (int, optional): Maximum allowed length for the subject. Defaults to 200.
        max_body_len (int, optional): Maximum allowed length for the body. Defaults to 2000.

    Returns:
        tuple[str, str]: A tuple containing:
            - The sanitized and truncated subject string.
            - The sanitized and truncated body string (or "(empty)" if no content is available).
    """
    body = text if text else html if html else ""
    body = strip_html(body)
    body = body.strip().replace("\r\n", "\n").replace("\r", "\n")
    if len(body) > max_body_len:
        body = body[:max_body_len] + "..."

    subject = subject or ""
    subject = strip_html(subject)
    subject = subject.strip()
    if len(subject) > max_subject_len:
        subject = subject[:max_subject_len] + "..."

    return subject, body if body else "(empty)"


async def generate_user_response(
    results: list[dict],
    email_data: EmailData,
    llm_complete: Callable[[str], Awaitable[str]],
    response_best_practices: str,
) -> str:
    try:
        if results is None:
            logger.warning("Results is None in generate_user_response")
            return "I've processed your email, but encountered issues. Please see the attached execution log for details."

        if not isinstance(results, list):
            logger.warning(f"Results is not a list (type: {type(results)})")
            return "I've processed your email, but encountered issues with result formatting. Please see the attached execution log for details."

        successful_results = [r for r in results if r.get("success", False)]

        if not successful_results:
            return "I've processed your email, but encountered issues with all steps. Please see the attached execution log for details."

        context = f"User's email subject: {email_data.subject}\n\n"
        context += "Execution results:\n"

        for result in successful_results:
            tool = result.get("tool", "unknown")
            desc = result.get("description", "")
            context += f"- {tool}"
            if desc:
                context += f": {desc}"
            context += "\n"

            if "summary" in result:
                context += f"  Result: {result['summary']}\n"
            if "translated_text" in result:
                context += f"  Result: {result['translated_text']}\n"
            if "category" in result:
                context += f"  Result: Category '{result['category']}'\n"
            if "file_id" in result:
                context += f"  Generated file: {result['file_id']}\n"
            if "parsed_text" in result:
                text = result["parsed_text"]
                if len(text) > 500:
                    text = text[:500] + "..."
                context += f"  Result: {text}\n"

        prompt = f"""Based on the following email processing results, generate a brief, natural language response to send to the user.

{context}

Write a concise, friendly response that follows these best practices:
{response_best_practices}

Additionally:
1. Acknowledges what was requested
2. Summarizes the key results
3. Mentions that detailed execution logs are attached if needed
4. Is written in a helpful, professional tone

Response:"""

        try:
            response = await llm_complete(prompt)
            return str(response).strip()
        except Exception as e:
            logger.warning(f"Failed to generate LLM response, using fallback: {e}")
            output = "Your email has been processed successfully.\n\n"

            for result in successful_results:
                if "summary" in result:
                    output += f"Summary: {result['summary']}\n\n"
                if "translated_text" in result:
                    output += f"Translation: {result['translated_text']}\n\n"
                if "category" in result:
                    output += f"Category: {result['category']}\n\n"
                if "file_id" in result:
                    output += f"Generated file: {result['file_id']}\n\n"

            output += "See the attached execution_log.md for detailed information about the processing steps."
            return output

    except Exception as e:
        logger.exception("Fatal error in generate_user_response")
        return f"Your email has been processed. Please see the attached execution log for details. (Error: {e!s})"


def create_execution_log(results: list[dict], email_data: EmailData) -> str:
    try:
        output = "# Workflow Execution Log\n\n"
        output += f"**Original Subject:** {email_data.subject}\n\n"
        output += f"**Processed Steps:** {len(results)}\n\n"
        output += "---\n\n"

        for result in results:
            step_num = result.get("step", "?")
            tool = result.get("tool", "unknown")
            desc = result.get("description", "")
            success = result.get("success", False)

            output += f"## Step {step_num}: {tool}\n\n"
            if desc:
                output += f"**Description:** {desc}\n\n"
            output += f"**Status:** {'✓ Success' if success else '✗ Failed'}\n\n"

            if success:
                if "summary" in result:
                    output += f"**Summary:**\n```\n{result['summary']}\n```\n\n"
                if "parsed_text" in result:
                    text = result["parsed_text"]
                    if len(text) > 1000:
                        text = text[:1000] + "...\n(truncated for brevity)"
                    output += f"**Parsed Text:**\n```\n{text}\n```\n\n"
                if "translated_text" in result:
                    output += f"**Translation:**\n```\n{result['translated_text']}\n```\n\n"
                if "category" in result:
                    output += f"**Category:** {result['category']}\n\n"
                if "file_id" in result:
                    output += f"**Generated File ID:** `{result['file_id']}`\n\n"

                SAFE_ADDITIONAL_FIELDS = ["extracted_data", "sheet_url", "other_info"]
                for key, value in result.items():
                    if key in SAFE_ADDITIONAL_FIELDS:
                        display_value = ""
                        if isinstance(value, str):
                            display_value = value if len(value) <= 500 else value[:500] + "... (truncated)"
                        elif isinstance(value, (dict, list)):
                            try:
                                json_str = json.dumps(value, indent=2)
                                display_value = json_str if len(json_str) <= 500 else json_str[:500] + "... (truncated)"
                            except Exception:
                                display_value = str(value)
                        else:
                            display_value = str(value)
                            if len(display_value) > 500:
                                display_value = display_value[:500] + "... (truncated)"
                        output += f"**{key}:**\n```\n{display_value}\n```\n\n"
            else:
                error = result.get("error", "Unknown error")
                output += f"**Error:**\n```\n{error}\n```\n\n"

            output += "---\n\n"

        output += "\n**Processing complete.**\n"

        return output
    except Exception as e:
        logger.exception("Error creating execution log")
        return f"# Workflow Execution Log\n\n**Error:** Failed to generate detailed log: {e!s}\n\n**Processed Steps:** {len(results) if results else 0}"


def collect_attachments(results: list[dict] | None) -> list[Attachment]:
    try:
        if not results:
            logger.info("[COLLECT ATTACHMENTS] Processing 0 result(s)")
            return []

        attachments = []
        logger.info(f"[COLLECT ATTACHMENTS] Processing {len(results)} result(s)")

        for result in results:
            if not result.get("success", False):
                continue

            file_id = result.get("file_id")
            if file_id:
                tool = result.get("tool", "unknown")
                step_num = result.get("step", "?")
                logger.info(
                    f"[COLLECT ATTACHMENTS] Found file_id '{file_id}' from tool '{tool}' (step {step_num})"
                )

                if tool == "print_to_pdf":
                    filename = f"output_step_{step_num}.pdf"
                    mime_type = "application/pdf"
                else:
                    filename = f"generated_file_step_{step_num}.dat"
                    mime_type = "application/octet-stream"

                attachment = Attachment(
                    id=f"generated-{step_num}",
                    name=filename,
                    type=mime_type,
                    file_id=file_id,
                )
                attachments.append(attachment)
                logger.info(f"Adding attachment: {filename} (file_id: {file_id})")

        logger.info(f"[COLLECT ATTACHMENTS] Returning {len(attachments)} attachment(s)")
        return attachments

    except Exception:
        logger.exception("Error collecting attachments")
        return []



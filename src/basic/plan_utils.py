"""Helper utilities for parsing and executing triage plans."""

import json
import logging
import re

from .models import EmailData

logger = logging.getLogger(__name__)


def parse_plan(response: str, email_data: EmailData) -> list[dict]:
    """Parse the execution plan from LLM response."""
    try:
        start = response.find("[")
        end = response.rfind("]") + 1

        if start >= 0 and end > start:
            json_str = response[start:end]
            plan = json.loads(json_str)

            if isinstance(plan, list):
                for step in plan:
                    if not isinstance(step, dict):
                        raise ValueError("Each step must be a dictionary")
                    if "tool" not in step or "params" not in step:
                        raise ValueError("Each step must have 'tool' and 'params'")
                return plan

        logger.warning("Could not parse plan from LLM response, using fallback")

        fallback_plan = []

        if email_data.attachments:
            for i, att in enumerate(email_data.attachments):
                fallback_plan.append(
                    {
                        "tool": "parse",
                        "params": {"file_id": att.id or f"att-{i + 1}"},
                        "description": f"Parse attachment: {att.name}",
                    }
                )

        email_content = email_data.text or email_data.html or "(empty)"
        email_content = email_content[:5000]
        fallback_plan.append(
            {
                "tool": "summarise",
                "params": {"text": email_content},
                "description": "Summarize email content",
            }
        )

        return fallback_plan
    except Exception:
        logger.exception("Error parsing plan")

        fallback_plan = []

        if email_data.attachments:
            for i, att in enumerate(email_data.attachments):
                fallback_plan.append(
                    {
                        "tool": "parse",
                        "params": {"file_id": att.id or f"att-{i + 1}"},
                        "description": f"Parse attachment: {att.name}",
                    }
                )

        email_content = email_data.text or email_data.html or "(empty)"
        email_content = email_content[:5000]
        fallback_plan.append(
            {
                "tool": "summarise",
                "params": {"text": email_content},
                "description": "Summarize email content",
            }
        )

        return fallback_plan


def _extract_referenced_steps(params: dict) -> set[str]:
    referenced_steps: set[str] = set()
    for value in params.values():
        if isinstance(value, str):
            has_template = ("{{" in value and "}}" in value) or (
                re.search(r"\{step_\d+\.[a-zA-Z_][a-zA-Z0-9_]*\}", value)
                is not None
            )

            if has_template:
                matches = re.finditer(r"\{\{([^}]+)\}\}", value)
                for match in matches:
                    ref = match.group(1).strip()
                    parts = ref.split(".")
                    if len(parts) >= 1:
                        step_key = parts[0]
                        if step_key.startswith("step_"):
                            referenced_steps.add(step_key)

                matches = re.finditer(
                    r"\{(step_\d+)\.[a-zA-Z_][a-zA-Z0-9_]*\}", value
                )
                for match in matches:
                    step_key = match.group(1)
                    referenced_steps.add(step_key)
    return referenced_steps


def check_step_dependencies(params: dict, context: dict, current_step: int) -> bool:
    """Check if any steps that this step depends on have failed."""
    referenced_steps = _extract_referenced_steps(params)

    for step_key in referenced_steps:
        if step_key in context:
            step_result = context[step_key]
            if isinstance(step_result, dict) and not step_result.get("success", False):
                logger.warning(
                    f"Step {current_step} depends on {step_key} which failed"
                )
                return True

    return False


def _is_attachment_reference(value: str, email_data: EmailData) -> bool:
    for att in email_data.attachments:
        if att.name == value:
            return True
    return False


def resolve_params(params: dict, context: dict, email_data: EmailData) -> dict:
    """Resolve parameter references from execution context."""
    resolved: dict = {}

    for key, value in params.items():
        if isinstance(value, str):
            has_template = ("{{" in value and "}}" in value) or (
                re.search(r"\{step_\d+\.[a-zA-Z_][a-zA-Z0-9_]*\}", value)
                is not None
            )

            if has_template:
                def template_replacer(match):
                    ref = match.group(1).strip()
                    parts = ref.split(".")
                    if len(parts) == 2:
                        step_key, field = parts
                        if step_key in context and field in context[step_key]:
                            return str(context[step_key][field])
                        logger.warning(
                            f"Template reference '{ref}' not found in execution context. "
                            f"Available steps: {list(context.keys())}"
                        )
                        return match.group(0)
                    logger.warning(
                        f"Invalid template reference format: '{ref}'. Expected 'step.field'."
                    )
                    return match.group(0)

                resolved_value = re.sub(r"\{\{([^}]+)\}\}", template_replacer, value)
                resolved_value = re.sub(
                    r"\{(step_\d+\.[a-zA-Z0-9_]+)\}",
                    template_replacer,
                    resolved_value,
                )
                resolved[key] = resolved_value
            elif value.startswith("att-") or _is_attachment_reference(value, email_data):
                att_index = value
                attachment_found = False
                for att in email_data.attachments:
                    if (
                        att.id == att_index
                        or att.name == att_index
                        or att.file_id == att_index
                    ):
                        resolved[key] = att.file_id or None
                        if not resolved[key] and att.content:
                            resolved[f"{key}_content"] = att.content
                        if not resolved[key]:
                            resolved[f"{key}_filename"] = att.name
                        attachment_found = True
                        break
                if not attachment_found:
                    logger.warning(
                        f"Attachment '{att_index}' not found. "
                        f"Available attachments: {[(att.id, att.name) for att in email_data.attachments]}"
                    )
                    resolved[key] = None
            else:
                resolved[key] = value
        else:
            resolved[key] = value
    return resolved

"""Helper utilities for parsing and executing triage plans."""

import json
import logging
import re
from typing import Any

from .models import EmailData

logger = logging.getLogger(__name__)


def _create_fallback_plan(email_data: EmailData) -> list[dict]:
    """Create a fallback plan when LLM response cannot be parsed."""
    fallback_plan = []

    if email_data.attachments:
        for i, att in enumerate(email_data.attachments):
            # Skip the email chain attachment in the fallback plan
            if att.name == "email_chain.md":
                continue
            fallback_plan.append(
                {
                    "tool": "parse",
                    "params": {"file_id": att.id or f"att-{i + 1}"},
                    "description": f"Parse attachment: {att.name}",
                }
            )

    # Get email content, applying split if needed
    from .utils import split_email_chain
    
    raw_content = email_data.text or email_data.html or "(empty)"
    top_email, _ = split_email_chain(raw_content)
    
    # Use top email, with more generous limit (10000 chars instead of 5000)
    email_content = top_email[:10000] if top_email else "(empty)"
    
    fallback_plan.append(
        {
            "tool": "summarise",
            "params": {"text": email_content},
            "description": "Summarize email content",
        }
    )

    return fallback_plan


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
        return _create_fallback_plan(email_data)
    except Exception:
        logger.exception("Error parsing plan")
        return _create_fallback_plan(email_data)


def _extract_referenced_steps(params: dict) -> set[str]:
    referenced_steps: set[str] = set()
    for value in params.values():
        if isinstance(value, str):
            has_template = ("{{" in value and "}}" in value) or (
                re.search(r"\{step_\d+\.[a-zA-Z_][a-zA-Z0-9_]*\}", value) is not None
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

                matches = re.finditer(r"\{(step_\d+)\.[a-zA-Z_][a-zA-Z0-9_]*\}", value)
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
    
    def _resolve_value(value: Any) -> Any:
        """Recursively resolve value."""
        if isinstance(value, dict):
            return {k: _resolve_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [_resolve_value(item) for item in value]
        elif isinstance(value, str):
            return _resolve_string(value)
        return value

    def _resolve_single_reference(ref: str, original_value: str) -> tuple[bool, Any]:
        """
        Helper to resolve a single template reference.
        
        Args:
            ref: The reference string (e.g., "step_1.field" or "item" or "item.field")
            original_value: The original parameter value
            
        Returns:
            Tuple of (success: bool, resolved_value: Any)
        """
        parts = ref.split(".")
        if len(parts) >= 1:
            step_key = parts[0]
            
            is_valid_key = False
            if step_key == "item":
                is_valid_key = True
            elif re.fullmatch(r"step_\d+", step_key):
                # steps require at least one field access (step_N.field)
                if len(parts) >= 2:
                    is_valid_key = True
                else:
                    logger.warning(
                        f"Invalid template reference format: '{ref}'. Expected at least 'step_N.field'."
                    )
                    return False, original_value
            
            if is_valid_key:
                if step_key in context:
                    current_val = context[step_key]
                    # Traverse the rest of the path
                    path_valid = True
                    for part in parts[1:]:
                        if isinstance(current_val, dict):
                            if part in current_val:
                                current_val = current_val[part]
                            # NEW: Special handling for extracted_data wrapper
                            elif "extracted_data" in current_val and isinstance(current_val["extracted_data"], dict) and part in current_val["extracted_data"]:
                                current_val = current_val["extracted_data"][part]
                            # Special handling for batch_results (Auto-Unwrap):
                            elif "batch_results" in current_val and isinstance(current_val["batch_results"], list) and current_val["batch_results"]:
                                logger.info(f"Key '{part}' not found directly, checking first item in batch_results for '{ref}'")
                                first_batch = current_val["batch_results"][0]
                                if isinstance(first_batch, dict) and part in first_batch:
                                    current_val = first_batch[part]
                                else:
                                    path_valid = False
                                    break
                            # NEW: Special handling for nested batch_results in extracted_data
                            elif "extracted_data" in current_val and isinstance(current_val["extracted_data"], dict) and \
                                 "batch_results" in current_val["extracted_data"] and \
                                 isinstance(current_val["extracted_data"]["batch_results"], list) and \
                                 current_val["extracted_data"]["batch_results"]:
                                 
                                logger.info(f"Key '{part}' not found directly, checking batch_results inside extracted_data for '{ref}'")
                                nested_batch = current_val["extracted_data"]["batch_results"]
                                 
                                if part == "batch_results":
                                    current_val = nested_batch
                                else:
                                    # Auto-unwrap first item
                                    first_batch = nested_batch[0]
                                    if isinstance(first_batch, dict) and part in first_batch:
                                        current_val = first_batch[part]
                                    else:
                                        path_valid = False
                                        break
                            else:
                                path_valid = False
                                break
                        else:
                            path_valid = False
                            break
                    
                    if path_valid:
                        return True, current_val
                        
                    logger.warning(
                        f"Template path '{ref}' not found in execution context. "
                    )
                else:
                    # Don't warn for 'item' if it's missing, it might just be outside a loop context (though usually shouldn't happen if planned correctly)
                    # But warn for steps.
                    if step_key != "item":
                        logger.warning(
                            f"Step '{step_key}' not found in execution context. "
                            f"Available steps: {list(context.keys())}"
                        )
                    else:
                         logger.debug("Variable 'item' not found in context.")
            else:
                 if step_key != "item":
                    logger.warning(
                        f"Invalid step key '{step_key}' in template reference '{ref}'. "
                        f"Expected 'step_N' pattern or 'item'."
                    )
        else:
            logger.warning(
                f"Invalid template reference format: '{ref}'."
            )
        # If not found or invalid, keep the original value
        return False, original_value

    def _resolve_string(value: str) -> Any:
        has_template = ("{{" in value and "}}" in value) or (
            re.search(r"\{(step_\d+|item)[a-zA-Z0-9_.]*\}", value) is not None
        )

        if has_template:
            # Check if the entire value is a single template reference
            # Pattern 1: {{step_N.field...}} or {{item...}} (with optional whitespace)
            single_double_brace_match = re.fullmatch(
                r"\{\{\s*((step_\d+|item)[a-zA-Z0-9_.]*)\s*\}\}", value
            )
            # Pattern 2: {step_N.field...} or {item...} (no whitespace)
            single_single_brace_match = re.fullmatch(
                r"\{((step_\d+|item)[a-zA-Z0-9_.]*)\}", value
            )

            # If the entire value is a single reference, return the actual value
            if single_double_brace_match:
                ref = single_double_brace_match.group(1).strip()
                success, resolved_value = _resolve_single_reference(ref, value)
                return resolved_value

            if single_single_brace_match:
                ref = single_single_brace_match.group(1)
                success, resolved_value = _resolve_single_reference(ref, value)
                return resolved_value

            # If the value contains multiple templates or embedded text,
            # perform string substitution
            # Handler for double-brace templates: {{step.field}}
            def double_brace_replacer(match):
                ref = match.group(1).strip()
                success, val = _resolve_single_reference(ref, match.group(0))
                if success:
                    return str(val)
                return match.group(0)

            # Handler for single-brace templates: {step_N.field}
            def single_brace_replacer(match):
                ref = match.group(1)
                success, val = _resolve_single_reference(ref, match.group(0))
                if success:
                    return str(val)
                return match.group(0)

            resolved_value = re.sub(
                r"\{\{([^}]+)\}\}", double_brace_replacer, value
            )
            # Update regex to allow dots in field path and item references
            resolved_value = re.sub(
                r"\{(step_\d+\.[a-zA-Z0-9_.]+|item[a-zA-Z0-9_.]*)\}",
                single_brace_replacer,
                resolved_value,
            )
            return resolved_value
            
        elif value.startswith("att-") or _is_attachment_reference(
            value, email_data
        ):
            att_index = value
            attachment_found = False
            for att in email_data.attachments:
                if (
                    att.id == att_index
                    or att.name == att_index
                    or att.file_id == att_index
                ):
                    resolved_file_id = att.file_id or None
                    # Special case: return dict if we have both file_id and content
                    # This is hard to handle in a generic way, so we rely on caller to look for side effects?
                    # No, we just return the file_id here. 
                    # Note: original code added resolved[f"{key}_content"] = ... which we can't do easily in recursion
                    # We'll just return the file_id for now.
                    return resolved_file_id
            
            logger.warning(
                f"Attachment '{att_index}' not found. "
                f"Available attachments: {[(att.id, att.name) for att in email_data.attachments]}"
            )
            return None
            
        return value

    # We can't use simple dict comprehension because we need to handle side effects for attachments
    # (setting _content and _filename suffixes).
    # So we'll iterate and update.
    resolved: dict = {}

    for key, value in params.items():
        # Handle attachment side-effects (legacy support)
        # If top-level value is a string referencing an attachment, we might need to set extra keys
        if isinstance(value, str) and (value.startswith("att-") or _is_attachment_reference(value, email_data)):
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
                 )
                 resolved[key] = None
        else:
            # Recursive resolution for everything else
            resolved[key] = _resolve_value(value)

    return resolved

"""Email processing workflow for handling inbound emails with agent triage.

This workflow uses an LLM-powered triage agent to analyze emails and create
execution plans using available tools.
"""

import json
import logging
import os
import re

import google.genai as genai
import httpx
from llama_index.llms.google_genai import GoogleGenAI
from llama_parse import LlamaParse
from workflows import Context, Workflow, step
from workflows.events import Event, StartEvent, StopEvent

from .models import (
    CallbackConfig,
    EmailData,
    EmailProcessingResult,
    SendEmailRequest,
)
from .tools import (
    ParseTool,
    ExtractTool,
    SheetsTool,
    SplitTool,
    ClassifyTool,
    TranslateTool,
    SummariseTool,
    PrintToPDFTool,
    ToolRegistry,
)
from .utils import (
    text_to_html,
    api_retry,
)

logger = logging.getLogger(__name__)


# Use the shared retry decorator for LLM API calls
llm_api_retry = api_retry


# Gemini model configuration
# Using latest Gemini 3 models as per https://ai.google.dev/gemini-api/docs/gemini-3
GEMINI_MULTIMODAL_MODEL = (
    "gemini-3-pro-preview"  # Latest Gemini 3 for multi-modal (images, PDFs, videos)
)
GEMINI_TEXT_MODEL = "gemini-3-pro-preview"  # Latest Gemini 3 for text processing

# Alternative cheaper model configuration (not currently in use)
# Gemini 2.5 Flash is optimized for cost-effective simple requests
GEMINI_CHEAP_TEXT_MODEL = "gemini-2.5-flash"  # Cheaper option for simple text tasks


class EmailStartEvent(StartEvent):
    """Start event for email workflow containing email data and callback config.

    This event is created from the JSON payload sent to the workflow server.
    The payload should contain 'email_data' and 'callback' fields at the top level.
    """

    email_data: EmailData
    callback: CallbackConfig


class TriageEvent(Event):
    """Event triggered when triage agent creates an execution plan."""

    plan: list[dict]  # List of tool execution steps
    email_data: EmailData
    callback: CallbackConfig


class PlanExecutionEvent(Event):
    """Event triggered when plan execution is complete."""

    results: list[dict]  # Results from each tool execution
    email_data: EmailData
    callback: CallbackConfig


class EmailProcessedEvent(Event):
    """Event triggered when email processing is complete."""

    result: EmailProcessingResult


class EmailWorkflow(Workflow):
    """Workflow for processing inbound emails with LLM-powered triage.

    This workflow uses an LLM triage agent to analyze emails and create
    execution plans using available tools. The plan is then executed
    and results are sent back via callback.
    """

    llama_parser = LlamaParse(result_type="markdown")
    llm = GoogleGenAI(model=GEMINI_TEXT_MODEL, api_key=os.getenv("GEMINI_API_KEY"))
    # Create genai client for multi-modal support (images, videos, etc.)
    genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize tool registry
        self.tool_registry = ToolRegistry()
        self._register_tools()

    def _register_tools(self):
        """Register all available tools."""
        self.tool_registry.register(ParseTool(self.llama_parser))
        self.tool_registry.register(ExtractTool())
        self.tool_registry.register(SheetsTool())
        self.tool_registry.register(SplitTool())
        self.tool_registry.register(ClassifyTool(self.llm))
        self.tool_registry.register(TranslateTool())
        self.tool_registry.register(SummariseTool(self.llm))
        self.tool_registry.register(PrintToPDFTool())

    @llm_api_retry
    async def _llm_complete_with_retry(self, prompt: str) -> str:
        """Execute LLM completion with automatic retry on transient errors.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            The LLM response as a string
        """
        response = await self.llm.acomplete(prompt)
        return str(response)

    @step
    async def triage_email(self, ev: EmailStartEvent, ctx: Context) -> TriageEvent:
        """Triage the email and create an execution plan using available tools.

        Args:
            ev: EmailStartEvent containing email data and callback config
            ctx: Workflow context

        Returns:
            TriageEvent with execution plan
        """
        email_data = ev.email_data
        callback = ev.callback

        # Debug logging
        logger.info(
            f"Triaging email: from={email_data.from_email}, "
            f"subject={email_data.subject}, "
            f"attachments={len(email_data.attachments)}"
        )

        # Build triage prompt
        triage_prompt = self._build_triage_prompt(email_data)

        try:
            # Get plan from LLM
            response = await self._llm_complete_with_retry(triage_prompt)

            # Parse plan from response
            plan = self._parse_plan(response)

            logger.info(f"Triage complete. Generated plan with {len(plan)} steps")

            return TriageEvent(plan=plan, email_data=email_data, callback=callback)
        except Exception:
            logger.exception("Error during email triage")
            # Create a simple fallback plan
            plan = [
                {
                    "tool": "summarise",
                    "params": {
                        "text": f"Email subject: {email_data.subject}\n\nBody: {email_data.text}"
                    },
                }
            ]
            return TriageEvent(plan=plan, email_data=email_data, callback=callback)

    def _build_triage_prompt(self, email_data: EmailData) -> str:
        """Build the triage prompt for the LLM.

        Args:
            email_data: Email data to triage

        Returns:
            Triage prompt string
        """
        tool_descriptions = self.tool_registry.get_tool_descriptions()

        attachment_info = ""
        if email_data.attachments:
            attachment_info = "\n\nAttachments:\n"
            for att in email_data.attachments:
                attachment_info += f"- {att.name} ({att.type})\n"

        prompt = f"""You are an email processing triage agent. Analyze the email below and create a step-by-step execution plan using the available tools.

Email Subject: {email_data.subject}

Email Body:
{email_data.text or email_data.html or "(empty)"}
{attachment_info}

Available Tools:
{tool_descriptions}

Create a step-by-step plan to process this email. Each step should use one of the available tools.
The plan can include loops (repeating steps) where needed.

Respond with a JSON array of steps. Each step should have:
- "tool": the tool name
- "params": a dictionary of parameters for that tool
- "description": a brief description of what this step does

Example plan format:
[
  {{
    "tool": "parse",
    "params": {{"file_id": "att-1"}},
    "description": "Parse the PDF attachment"
  }},
  {{
    "tool": "summarise",
    "params": {{"text": "{{step_1.parsed_text}}"}},
    "description": "Summarize the parsed document"
  }}
]

IMPORTANT: Respond ONLY with the JSON array, no other text.

Plan:"""

        return prompt

    def _parse_plan(self, response: str) -> list[dict]:
        """Parse the execution plan from LLM response.

        Args:
            response: LLM response containing the plan

        Returns:
            List of plan steps
        """
        try:
            # Try to extract JSON from the response
            # Look for content between first [ and last ]
            start = response.find("[")
            end = response.rfind("]") + 1

            if start >= 0 and end > start:
                json_str = response[start:end]
                plan = json.loads(json_str)

                # Validate plan structure
                if isinstance(plan, list):
                    for step in plan:
                        if not isinstance(step, dict):
                            raise ValueError("Each step must be a dictionary")
                        if "tool" not in step or "params" not in step:
                            raise ValueError("Each step must have 'tool' and 'params'")
                    return plan

            # If parsing failed, create a simple summarize plan
            logger.warning("Could not parse plan from LLM response, using fallback")
            return [
                {
                    "tool": "summarise",
                    "params": {"text": response},
                    "description": "Summarize the content",
                }
            ]
        except Exception:
            logger.exception("Error parsing plan")
            return [
                {
                    "tool": "summarise",
                    "params": {"text": str(response)},
                    "description": "Summarize the content",
                }
            ]

    @step
    async def execute_plan(self, ev: TriageEvent, ctx: Context) -> PlanExecutionEvent:
        """Execute the plan created by triage agent.

        Args:
            ev: TriageEvent with the execution plan
            ctx: Workflow context

        Returns:
            PlanExecutionEvent with execution results
        """
        plan = ev.plan
        email_data = ev.email_data
        callback = ev.callback

        logger.info(f"Executing plan with {len(plan)} steps")

        results = []
        execution_context = {}  # Store results from previous steps

        for i, step_def in enumerate(plan):
            tool_name = step_def.get("tool")
            params = step_def.get("params", {})
            description = step_def.get("description", "")

            logger.info(
                f"Executing step {i + 1}/{len(plan)}: {tool_name} - {description}"
            )

            try:
                # Get the tool
                tool = self.tool_registry.get_tool(tool_name)
                if not tool:
                    logger.warning(f"Tool '{tool_name}' not found, skipping step")
                    results.append(
                        {
                            "step": i + 1,
                            "tool": tool_name,
                            "success": False,
                            "error": f"Tool '{tool_name}' not found",
                        }
                    )
                    continue

                # Resolve parameter references from execution context
                resolved_params = self._resolve_params(
                    params, execution_context, email_data
                )

                # Execute the tool
                result = await tool.execute(**resolved_params)

                # Store result in context for future steps
                execution_context[f"step_{i + 1}"] = result

                results.append(
                    {
                        "step": i + 1,
                        "tool": tool_name,
                        "description": description,
                        **result,
                    }
                )

                logger.info(f"Step {i + 1} completed: {result.get('success', False)}")

            except Exception as e:
                logger.exception(f"Error executing step {i + 1}")
                results.append(
                    {
                        "step": i + 1,
                        "tool": tool_name,
                        "success": False,
                        "error": str(e),
                    }
                )

        return PlanExecutionEvent(
            results=results, email_data=email_data, callback=callback
        )

    def _resolve_params(
        self, params: dict, context: dict, email_data: EmailData
    ) -> dict:
        """Resolve parameter references from execution context.

        Args:
            params: Raw parameters that may contain references
            context: Execution context with previous results
            email_data: Original email data

        Returns:
            Resolved parameters
        """
        resolved = {}

        for key, value in params.items():
            if isinstance(value, str):
                # Check for template references like {{step_1.parsed_text}}
                if "{{" in value and "}}" in value:
                    # Simple template resolution
                    resolved_value = value
                    for match in re.finditer(r"\{\{([^}]+)\}\}", value):
                        ref = match.group(1).strip()
                        # Split on . to get step and field
                        parts = ref.split(".")
                        if len(parts) == 2:
                            step_key, field = parts
                            if step_key in context and field in context[step_key]:
                                resolved_value = resolved_value.replace(
                                    match.group(0), str(context[step_key][field])
                                )
                            else:
                                # Log warning if template reference not found
                                logger.warning(
                                    f"Template reference '{ref}' not found in execution context. "
                                    f"Available steps: {list(context.keys())}"
                                )
                    resolved[key] = resolved_value
                else:
                    resolved[key] = value
            else:
                resolved[key] = value

        # Add attachment file_ids if referenced
        if "file_id" in params and params["file_id"].startswith("att-"):
            # Find attachment by index or id
            att_index = params["file_id"]
            attachment_found = False
            for att in email_data.attachments:
                if att.id == att_index or att.name == att_index:
                    resolved["file_id"] = att.file_id or None
                    if not resolved["file_id"] and att.content:
                        resolved["file_content"] = att.content
                    attachment_found = True
                    break

            if not attachment_found:
                logger.warning(
                    f"Attachment '{att_index}' not found. "
                    f"Available attachments: {[att.id for att in email_data.attachments]}"
                )

        return resolved

    @step
    async def send_results(self, ev: PlanExecutionEvent, ctx: Context) -> StopEvent:
        """Send the execution results via callback email.

        Args:
            ev: PlanExecutionEvent with execution results
            ctx: Workflow context

        Returns:
            StopEvent with final result
        """
        email_data = ev.email_data
        callback = ev.callback
        results = ev.results

        # Format results for email
        result_text = self._format_results(results, email_data)

        # Send response email via callback
        try:
            logger.info(f"Sending results email to {email_data.from_email}")

            response_email = SendEmailRequest(
                to_email=email_data.from_email,
                from_email=email_data.to_email or None,
                subject=f"Re: {email_data.subject}",
                text=result_text,
                html=text_to_html(result_text),
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

            # Create success result
            result = EmailProcessingResult(
                success=True,
                message=f"Email processed successfully with {len(results)} steps",
                from_email=email_data.from_email,
                email_subject=email_data.subject,
            )
            ctx.write_event_to_stream(EmailProcessedEvent(result=result))
            return StopEvent(result=result)

        except httpx.HTTPError as e:
            logger.error(f"Failed to send callback email: {e}")
            failure = EmailProcessingResult(
                success=False,
                message=f"Email processed but callback failed: {e!s}",
                from_email=email_data.from_email,
                email_subject=email_data.subject,
            )
            ctx.write_event_to_stream(EmailProcessedEvent(result=failure))
            return StopEvent(result=failure)
        except Exception as e:
            logger.exception("Unexpected error sending results")
            failure = EmailProcessingResult(
                success=False,
                message=f"Failed to send results: {e!s}",
                from_email=email_data.from_email,
                email_subject=email_data.subject,
            )
            ctx.write_event_to_stream(EmailProcessedEvent(result=failure))
            return StopEvent(result=failure)

    def _format_results(self, results: list[dict], email_data: EmailData) -> str:
        """Format execution results for email display.

        Args:
            results: List of execution results
            email_data: Original email data

        Returns:
            Formatted result text
        """
        output = "Your email has been processed.\n\n"
        output += f"Original subject: {email_data.subject}\n"
        output += f"Processed with {len(results)} steps:\n\n"

        for result in results:
            step_num = result.get("step", "?")
            tool = result.get("tool", "unknown")
            desc = result.get("description", "")
            success = result.get("success", False)

            output += f"Step {step_num}: {tool}"
            if desc:
                output += f" - {desc}"
            output += f" ({'✓ Success' if success else '✗ Failed'})\n"

            # Add relevant output from each step
            if success:
                if "summary" in result:
                    output += f"  Summary: {result['summary']}\n"
                elif "parsed_text" in result:
                    # Truncate long text
                    text = result["parsed_text"]
                    if len(text) > 200:
                        text = text[:200] + "..."
                    output += f"  Parsed: {text}\n"
                elif "translated_text" in result:
                    output += f"  Translation: {result['translated_text']}\n"
                elif "category" in result:
                    output += f"  Category: {result['category']}\n"
            else:
                error = result.get("error", "Unknown error")
                output += f"  Error: {error}\n"

            output += "\n"

        output += "\nProcessing complete."

        return output


email_workflow = EmailWorkflow(timeout=60)

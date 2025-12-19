"""Email processing workflow for handling inbound emails with agent triage.

This workflow uses an LLM-powered triage agent to analyze emails and create
execution plans using available tools.
"""

import asyncio
import base64
import logging
import os

import google.genai as genai
import httpx
from llama_index.llms.google_genai import GoogleGenAI
from llama_parse import LlamaParse
from workflows import Context, Workflow, step
from workflows.events import Event, StartEvent, StopEvent

from .models import (
    Attachment,
    CallbackConfig,
    EmailData,
    EmailProcessingResult,
    SendEmailRequest,
)
from .plan_utils import check_step_dependencies, parse_plan, resolve_params
from .prompt_utils import build_triage_prompt, build_verification_prompt
from .response_utils import (
    collect_attachments,
    create_execution_log,
    generate_user_response,
    sanitize_email_content,
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
    SearchTool,
    ImageGenTool,
    ToolRegistry,
)
from .utils import (
    text_to_html,
    api_retry,
)
from .observability import (
    flush_langfuse,
    setup_observability,
)  # Import flush and setup for tracing

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


# Best practices for digital assistant responses
RESPONSE_BEST_PRACTICES = """
1. Directly respond to the user's instructions without unnecessary preambles
2. Avoid inappropriate internal comments (e.g., "Here is the draft response", "I will now...")
3. State clearly when all or part of the user's request could not be completed
4. Consider and mention potential follow-up steps when relevant
5. Provide references to key sources or files when applicable
"""


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


class VerificationEvent(Event):
    """Event triggered when response verification is complete."""

    verified_response: str  # Verified and potentially improved response
    results: list[dict]  # Original results from plan execution
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
        # Set up observability (Langfuse tracing) after environment is loaded
        # This ensures credentials from .env files are available when running in LlamaCloud
        setup_observability()
        # Initialize tool registry
        self.tool_registry = ToolRegistry()
        self._register_tools()

    def _register_tools(self):
        """Register all available tools."""
        self.tool_registry.register(ParseTool(self.llama_parser))
        self.tool_registry.register(ExtractTool())
        self.tool_registry.register(SheetsTool(self.llama_parser))
        self.tool_registry.register(SplitTool())
        self.tool_registry.register(ClassifyTool(self.llm))
        self.tool_registry.register(TranslateTool())
        self.tool_registry.register(SummariseTool(self.llm))
        self.tool_registry.register(PrintToPDFTool())
        self.tool_registry.register(SearchTool())
        self.tool_registry.register(ImageGenTool())

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

    async def _generate_user_response(
        self, results: list[dict], email_data: EmailData
    ) -> str:
        """Backward-compatible wrapper for generate_user_response.

        This method maintains compatibility with existing tests that call
        workflow._generate_user_response(results, email_data).

        Args:
            results: List of execution results
            email_data: Email data containing subject and body

        Returns:
            Generated user response string
        """
        return await generate_user_response(
            results,
            email_data,
            self._llm_complete_with_retry,
            RESPONSE_BEST_PRACTICES,
        )

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

        try:
            # Debug logging
            logger.info(
                f"[TRIAGE START] Triaging email: from={email_data.from_email}, "
                f"subject={email_data.subject}, "
                f"attachments={len(email_data.attachments)}"
            )

            # Build triage prompt
            triage_prompt = build_triage_prompt(
                email_data,
                self.tool_registry.get_tool_descriptions(),
                RESPONSE_BEST_PRACTICES,
            )

            # Get plan from LLM
            response = await self._llm_complete_with_retry(triage_prompt)

            # Parse plan from response
            plan = parse_plan(response, email_data)

            logger.info(f"[TRIAGE COMPLETE] Generated plan with {len(plan)} steps")

            result = TriageEvent(plan=plan, email_data=email_data, callback=callback)
            flush_langfuse()  # Flush traces after step completion
            return result
        except asyncio.TimeoutError:
            logger.error("Workflow timeout in triage_email step")
            # Create a simple fallback plan for timeout scenarios
            plan = [
                {
                    "tool": "summarise",
                    "params": {
                        "text": f"Email subject: {email_data.subject}\n\nBody: {email_data.text or '(empty)'}"
                    },
                }
            ]
            result = TriageEvent(plan=plan, email_data=email_data, callback=callback)
            flush_langfuse()  # Flush traces after step completion
            return result
        except Exception:
            logger.exception("Error during email triage")
            # Create a simple fallback plan
            plan = [
                {
                    "tool": "summarise",
                    "params": {
                        "text": f"Email subject: {email_data.subject}\n\nBody: {email_data.text or '(empty)'}"
                    },
                }
            ]
            result = TriageEvent(plan=plan, email_data=email_data, callback=callback)
            flush_langfuse()  # Flush traces after step completion
            return result

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

        try:
            # Defensive check: ensure plan is not None and is a list
            if plan is None:
                logger.error("Plan is None, creating empty plan")
                plan = []
            if not isinstance(plan, list):
                logger.error(
                    f"Plan is not a list (type: {type(plan)}), creating empty plan"
                )
                plan = []

            logger.info(f"[PLAN EXEC START] Executing plan with {len(plan)} steps")

            results = []
            execution_context = {}  # Store results from previous steps

            for i, step_def in enumerate(plan):
                tool_name = step_def.get("tool")
                params = step_def.get("params", {})
                description = step_def.get("description", "")
                critical = step_def.get(
                    "critical", False
                )  # Optional: mark step as critical

                logger.info(
                    f"[PLAN EXEC STEP {i + 1}/{len(plan)}] Executing: {tool_name} - {description}"
                )

                try:
                    # Get the tool
                    tool = self.tool_registry.get_tool(tool_name)
                    if not tool:
                        logger.warning(f"Tool '{tool_name}' not found, skipping step")
                        # Store failed result in context so dependent steps can detect failure
                        execution_context[f"step_{i + 1}"] = {
                            "success": False,
                            "error": f"Tool '{tool_name}' not found",
                        }
                        results.append(
                            {
                                "step": i + 1,
                                "tool": tool_name,
                                "success": False,
                                "error": f"Tool '{tool_name}' not found",
                            }
                        )
                        # If this is a critical step, stop execution
                        if critical:
                            logger.error(
                                f"Critical step {i + 1} failed (tool not found). Stopping execution."
                            )
                            break
                        continue

                    # Validate dependencies: check if any referenced steps have failed
                    dependency_failed = check_step_dependencies(
                        params, execution_context, i + 1
                    )
                    if dependency_failed:
                        logger.warning(
                            f"Step {i + 1} depends on failed step(s). Skipping execution."
                        )
                        # Store skipped result in context
                        execution_context[f"step_{i + 1}"] = {
                            "success": False,
                            "error": "Dependent step(s) failed",
                            "skipped": True,
                        }
                        results.append(
                            {
                                "step": i + 1,
                                "tool": tool_name,
                                "success": False,
                                "error": "Dependent step(s) failed",
                                "skipped": True,
                            }
                        )
                        # If this is a critical step, stop execution
                        if critical:
                            logger.error(
                                f"Critical step {i + 1} skipped due to dependency failure. Stopping execution."
                            )
                            break
                        continue

                    # Resolve parameter references from execution context
                    resolved_params = resolve_params(
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

                    logger.info(
                        f"[PLAN EXEC STEP {i + 1}] Completed: {result.get('success', False)}"
                    )

                    # If this is a critical step and it failed, stop execution
                    if critical and not result.get("success", False):
                        logger.error(
                            f"Critical step {i + 1} failed. Stopping execution of remaining steps."
                        )
                        break

                except Exception as e:
                    logger.exception(f"Error executing step {i + 1}")
                    # Store failed result in context so dependent steps can detect failure
                    execution_context[f"step_{i + 1}"] = {
                        "success": False,
                        "error": str(e),
                    }
                    results.append(
                        {
                            "step": i + 1,
                            "tool": tool_name,
                            "success": False,
                            "error": str(e),
                        }
                    )
                    # If this is a critical step, stop execution
                    if critical:
                        logger.error(
                            f"Critical step {i + 1} encountered exception. Stopping execution."
                        )
                        break

            logger.info(f"[PLAN EXEC COMPLETE] Finished {len(results)} steps")
            result = PlanExecutionEvent(
                results=results, email_data=email_data, callback=callback
            )
            flush_langfuse()  # Flush traces after step completion
            return result

        except asyncio.TimeoutError as e:
            logger.error(f"Workflow timeout in execute_plan step: {e}")
            # Return a PlanExecutionEvent with a timeout error result
            result = PlanExecutionEvent(
                results=[
                    {
                        "step": 0,
                        "tool": "execute_plan",
                        "success": False,
                        "error": "Plan execution timed out. This may be due to long-running Parse operations or API retries.",
                    }
                ],
                email_data=email_data,
                callback=callback,
            )
            flush_langfuse()  # Flush traces after step completion
            return result

        except Exception as e:
            logger.exception("Fatal error in execute_plan step")
            # Return a PlanExecutionEvent with a single failed result
            result = PlanExecutionEvent(
                results=[
                    {
                        "step": 0,
                        "tool": "execute_plan",
                        "success": False,
                        "error": f"Fatal error during plan execution: {e!s}",
                    }
                ],
                email_data=email_data,
                callback=callback,
            )
            flush_langfuse()  # Flush traces after step completion
            return result

    @api_retry
    async def _send_callback_email(
        self, callback_url: str, auth_token: str, email_request: SendEmailRequest
    ) -> None:
        """Send email via callback URL with automatic retry on transient errors.

        Args:
            callback_url: URL to send the callback to
            auth_token: Authentication token for the callback
            email_request: Email request to send

        Raises:
            httpx.HTTPError: If callback fails after all retries
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                callback_url,
                json=email_request.model_dump(),
                headers={
                    "Content-Type": "application/json",
                    "X-Auth-Token": auth_token,
                },
                timeout=30.0,
            )
            response.raise_for_status()

    @step
    async def verify_response(
        self, ev: PlanExecutionEvent, ctx: Context
    ) -> VerificationEvent:
        """Verify and improve the generated response based on best practices.

        Args:
            ev: PlanExecutionEvent with execution results
            ctx: Workflow context

        Returns:
            VerificationEvent with verified response
        """
        email_data = ev.email_data
        callback = ev.callback
        results = ev.results

        try:
            logger.info("[VERIFY START] Verifying response quality")

            initial_response = await generate_user_response(
                results,
                email_data,
                self._llm_complete_with_retry,
                RESPONSE_BEST_PRACTICES,
            )

            sanitized_subject, sanitized_body = sanitize_email_content(
                email_data.subject, email_data.text, email_data.html
            )

            verification_prompt = build_verification_prompt(
                sanitized_subject,
                sanitized_body,
                initial_response,
                RESPONSE_BEST_PRACTICES,
            )

            verified_response = await self._llm_complete_with_retry(verification_prompt)
            verified_response = str(verified_response).strip()

            if not verified_response or len(verified_response) < 10:
                logger.warning(
                    "Verification produced empty/short response, using original"
                )
                verified_response = initial_response

            logger.info("[VERIFY COMPLETE] Response verification complete")
            result = VerificationEvent(
                verified_response=verified_response,
                results=results,
                email_data=email_data,
                callback=callback,
            )
            flush_langfuse()  # Flush traces after step completion
            return result

        except asyncio.TimeoutError:
            logger.error("Workflow timeout in verify_response step")
            # Return original response on timeout
            try:
                initial_response = await generate_user_response(
                    results,
                    email_data,
                    self._llm_complete_with_retry,
                    RESPONSE_BEST_PRACTICES,
                )
            except Exception:
                initial_response = "Your email has been processed. Please see the attached execution log for details."
            result = VerificationEvent(
                verified_response=initial_response,
                results=results,
                email_data=email_data,
                callback=callback,
            )
            flush_langfuse()  # Flush traces after step completion
            return result
        except Exception:
            logger.exception("Error during response verification")
            # Return original response on error
            try:
                initial_response = await generate_user_response(
                    results,
                    email_data,
                    self._llm_complete_with_retry,
                    RESPONSE_BEST_PRACTICES,
                )
            except Exception:
                initial_response = "Your email has been processed. Please see the attached execution log for details."
            result = VerificationEvent(
                verified_response=initial_response,
                results=results,
                email_data=email_data,
                callback=callback,
            )
            flush_langfuse()  # Flush traces after step completion
            return result

    @step
    async def send_results(self, ev: VerificationEvent, ctx: Context) -> StopEvent:
        """Send the execution results via callback email.

        Args:
            ev: VerificationEvent with verified response
            ctx: Workflow context

        Returns:
            StopEvent with final result
        """
        email_data = ev.email_data
        callback = ev.callback
        results = ev.results
        verified_response = ev.verified_response

        try:
            logger.info(
                f"[SEND RESULTS START] Preparing results for {email_data.from_email}"
            )

            # Use the verified response from the previous step
            result_text = verified_response

            # Create execution log as markdown
            execution_log = create_execution_log(results, email_data)

            # Collect any generated files from the results to attach
            attachments = collect_attachments(results)
            logger.info(
                f"[COLLECT ATTACHMENTS] Collected {len(attachments)} file attachment(s) from results"
            )
            for att in attachments:
                logger.info(
                    f"  - {att.name} (file_id: {att.file_id}, content: {'present' if att.content else 'None'})"
                )

            # Add execution log as an attachment
            execution_log_b64 = base64.b64encode(execution_log.encode("utf-8")).decode(
                "utf-8"
            )
            execution_log_attachment = Attachment(
                id="execution-log",
                name="execution_log.md",
                type="text/markdown",
                content=execution_log_b64,
            )
            attachments.append(execution_log_attachment)
            logger.info(
                f"[ATTACHMENTS FINAL] Total {len(attachments)} attachment(s) will be sent in callback"
            )

            # Send response email via callback
            logger.info(
                f"[SEND RESULTS CALLBACK] Sending results email to {email_data.from_email}"
            )

            response_email = SendEmailRequest(
                to_email=email_data.from_email,
                from_email=email_data.to_email or None,
                subject=f"Re: {email_data.subject}",
                text=result_text,
                html=text_to_html(result_text),
                attachments=attachments,
            )

            # Use retry-wrapped callback method
            await self._send_callback_email(
                callback.callback_url, callback.auth_token, response_email
            )
            logger.info("[SEND RESULTS COMPLETE] Callback email sent successfully")

            # Create success result
            result = EmailProcessingResult(
                success=True,
                message=f"Email processed successfully with {len(results)} steps",
                from_email=email_data.from_email,
                email_subject=email_data.subject,
            )
            ctx.write_event_to_stream(EmailProcessedEvent(result=result))
            stop_event = StopEvent(result=result)
            flush_langfuse()  # Flush traces after final step completion
            return stop_event

        except httpx.HTTPError as e:
            logger.error(f"Failed to send callback email: {e}")
            failure = EmailProcessingResult(
                success=False,
                message=f"Email processed but callback failed: {e!s}",
                from_email=email_data.from_email,
                email_subject=email_data.subject,
            )
            ctx.write_event_to_stream(EmailProcessedEvent(result=failure))
            stop_event = StopEvent(result=failure)
            flush_langfuse()  # Flush traces after final step completion
            return stop_event
        except asyncio.TimeoutError as e:
            logger.error(f"Workflow timeout in send_results step: {e}")
            failure = EmailProcessingResult(
                success=False,
                message="Email processing timed out while preparing results. Please try again.",
                from_email=email_data.from_email,
                email_subject=email_data.subject,
            )
            ctx.write_event_to_stream(EmailProcessedEvent(result=failure))
            stop_event = StopEvent(result=failure)
            flush_langfuse()  # Flush traces after final step completion
            return stop_event
        except Exception as e:
            logger.exception("Unexpected error in send_results step")
            failure = EmailProcessingResult(
                success=False,
                message=f"Fatal error processing email: {e!s}",
                from_email=email_data.from_email,
                email_subject=email_data.subject,
            )
            ctx.write_event_to_stream(EmailProcessedEvent(result=failure))
            stop_event = StopEvent(result=failure)
            flush_langfuse()  # Flush traces after final step completion
            return stop_event


# Timeout increased to 120s to accommodate multiple Parse tool retries
# (5 attempts, exponential backoff: 1s + 2s + 4s + 8s = ~15s max per file, plus execution time)
email_workflow = EmailWorkflow(timeout=120)

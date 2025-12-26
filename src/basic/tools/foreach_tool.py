"""Tool for iterating over a list and executing another tool for each item."""

from __future__ import annotations

import logging
from typing import Any

from .base import Tool
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


class ForeachTool(Tool):
    """Tool for iterating over a list and executing another tool for each item.
    
    This tool allows batch processing by feeding each item from a list into
    a specified tool. If the target tool is an LLM-based tool, it can
    dynamically decide what to do for each specific item.
    """

    def __init__(self, registry: ToolRegistry):
        """Initialize the ForeachTool.

        Args:
            registry: The tool registry to access other tools
        """
        self.registry = registry

    @property
    def name(self) -> str:
        return "foreach"

    @property
    def description(self) -> str:
        return (
            "Iterate over a list of items and execute another tool for each item. "
            "Input: items (list of items), tool (name of the tool to execute), params (template parameters for the tool). "
            "Inside 'params', use {{item}} to reference the current item in the loop. "
            "Output: batch_results (list of results from each execution)."
        )

    async def execute(self, **kwargs) -> dict[str, Any]:
        """Execute the target tool for each item in the list.

        Args:
            **kwargs: Keyword arguments including:
                - items: List of items to process (required)
                - tool: Name of the tool to execute for each item (required)
                - params: Dictionary of parameters for the target tool (required)
                - __context: Internal execution context (passed by engine)
                - __email_data: Internal email data (passed by engine)

        Returns:
            Dictionary with 'success' and 'batch_results'
        """
        items = kwargs.get("items")
        target_tool_name = kwargs.get("tool")
        target_params_template = kwargs.get("params", {})
        
        # Internal context passed by the engine for recursive resolution
        context = kwargs.get("__context", {})
        email_data = kwargs.get("__email_data")

        if items is None:
            return {"success": False, "error": "Missing required parameter: items"}
        
        # Ensure items is a list
        if not isinstance(items, list):
            items = [items]
        
        if not target_tool_name:
            return {"success": False, "error": "Missing required parameter: tool"}

        target_tool = self.registry.get_tool(target_tool_name)
        if not target_tool:
            return {"success": False, "error": f"Tool '{target_tool_name}' not found"}

        # Import resolve_params locally to avoid potential circular imports
        from ..plan_utils import resolve_params

        results = []
        logger.info(f"ForeachTool: processing {len(items)} items using tool '{target_tool_name}'")

        for idx, item in enumerate(items):
            try:
                # Create a local context for this iteration that includes 'item'
                item_context = context.copy()
                item_context["item"] = item
                
                # Resolve parameters for this specific item using the template
                resolved_params = resolve_params(target_params_template, item_context, email_data)
                
                # Execute the target tool with resolved parameters
                logger.info(f"ForeachTool: Executing {target_tool_name} for item {idx+1}/{len(items)}")
                item_result = await target_tool.execute(**resolved_params)
                
                # Collect the result
                results.append({
                    "item_index": idx + 1,
                    "item": item,
                    "success": item_result.get("success", False),
                    **item_result
                })
            except Exception as e:
                logger.exception(f"Error in ForeachTool processing item {idx+1}")
                results.append({
                    "item_index": idx + 1,
                    "item": item,
                    "success": False,
                    "error": str(e)
                })

        return {
            "success": any(r.get("success", False) for r in results) if results else True,
            "batch_results": results,
            "item_count": len(items)
        }
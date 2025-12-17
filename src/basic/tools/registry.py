"""Registry for managing available tools."""

from __future__ import annotations

from .base import Tool


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self):
        self.tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register
        """
        self.tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool | None:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self.tools.get(name)

    def get_tool_descriptions(self) -> str:
        """Get descriptions of all registered tools.

        Returns:
            Formatted string with all tool descriptions
        """
        descriptions = []
        for tool in self.tools.values():
            descriptions.append(f"- **{tool.name}**: {tool.description}")
        return "\n".join(descriptions)

    def list_tool_names(self) -> list[str]:
        """Get list of all registered tool names.

        Returns:
            List of tool names
        """
        return list(self.tools.keys())

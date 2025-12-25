"""Tool for generating static charts/graphs from data."""

from __future__ import annotations

import io
import logging
from typing import Any

from .base import Tool
from ..utils import upload_file_to_llamacloud

logger = logging.getLogger(__name__)


class StaticGraphTool(Tool):
    """Tool for generating static charts/graphs from data.
    
    This tool creates charts from input datasets and uploads them to LlamaCloud.
    The chart image can then be used by other workflow steps or returned to users.
    
    Supported chart types: line, bar, scatter, pie, histogram
    """

    @property
    def name(self) -> str:
        return "static_graph"

    @property
    def description(self) -> str:
        return (
            "Generate a static chart/graph from data and upload to LlamaCloud. "
            "Input: data (dict with 'x' and 'y' lists for most charts, or 'values' and 'labels' for pie), "
            "chart_type ('line', 'bar', 'scatter', 'pie', 'histogram'), "
            "title (optional), xlabel (optional), ylabel (optional), "
            "width (optional, default: 10), height (optional, default: 6). "
            "Output: file_id (LlamaCloud file ID of generated chart image)"
        )

    async def execute(self, **kwargs) -> dict[str, Any]:
        """Generate a static chart from data and upload to LlamaCloud.

        Args:
            **kwargs: Keyword arguments including:
                - data: Dictionary containing chart data
                    For line/bar/scatter: {'x': [...], 'y': [...]}
                    For pie: {'values': [...], 'labels': [...]}
                    For histogram: {'values': [...]}
                - chart_type: Type of chart ('line', 'bar', 'scatter', 'pie', 'histogram')
                - title: Chart title (optional)
                - xlabel: X-axis label (optional)
                - ylabel: Y-axis label (optional)
                - width: Chart width in inches (optional, default: 10)
                - height: Chart height in inches (optional, default: 6)

        Returns:
            dict[str, Any]: A dictionary describing the result.
                On success:
                    - success (bool): True
                    - file_id (str): LlamaCloud file ID of the generated chart
                    - chart_type (str): Type of chart generated
                On error:
                    - success (bool): False
                    - error (str): Description of the error
        """
        data = kwargs.get("data")
        chart_type = kwargs.get("chart_type")
        title = kwargs.get("title", "")
        xlabel = kwargs.get("xlabel", "")
        ylabel = kwargs.get("ylabel", "")
        width = kwargs.get("width", 10)
        height = kwargs.get("height", 6)

        # Validate required parameters
        if not data:
            return {"success": False, "error": "Missing required parameter: data"}
        
        # Check for batch_results and extract first valid dataset
        if "batch_results" in data and isinstance(data["batch_results"], list):
            logger.info("Found batch_results in data, searching for valid dataset")
            for result in data["batch_results"]:
                if not isinstance(result, dict):
                    continue
                
                # Check validity based on chart_type
                is_valid = False
                if chart_type == "pie":
                    if result.get("values") and result.get("labels"):
                        is_valid = True
                elif chart_type == "histogram":
                    if result.get("values"):
                        is_valid = True
                else: # line, bar, scatter (default check)
                    # We check for x and y. Note: valid_types check happens later,
                    # but we want to be permissive here to find potential candidates.
                    if result.get("x") and result.get("y"):
                        is_valid = True
                
                if is_valid:
                    data = result
                    logger.info("Found valid dataset in batch_results")
                    break
        
        if not chart_type:
            return {"success": False, "error": "Missing required parameter: chart_type"}
        
        # Validate width and height
        try:
            width = float(width)
            height = float(height)
            if width <= 0 or height <= 0:
                return {
                    "success": False,
                    "error": "width and height must be positive numbers"
                }
        except (TypeError, ValueError):
            return {
                "success": False,
                "error": "width and height must be valid numbers"
            }
        
        # Validate chart_type
        valid_types = ["line", "bar", "scatter", "pie", "histogram"]
        if chart_type not in valid_types:
            return {
                "success": False,
                "error": f"Invalid chart_type: {chart_type}. Must be one of {valid_types}"
            }

        try:
            # Import matplotlib here to avoid loading it if not needed
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import matplotlib.pyplot as plt

            logger.info(f"Generating {chart_type} chart with title: {title or 'Untitled'}")

            # Create figure and axis
            fig, ax = plt.subplots(figsize=(width, height))

            error: dict[str, Any] | None = None
            try:
                # Generate chart based on type
                if chart_type == "pie":
                    # Pie chart requires 'values' and 'labels'
                    values = data.get("values")
                    labels = data.get("labels")
                    
                    if not values:
                        error = {"success": False, "error": "Pie chart requires 'values' in data"}
                    elif not labels:
                        error = {"success": False, "error": "Pie chart requires 'labels' in data"}
                    elif len(values) != len(labels):
                        error = {
                            "success": False,
                            "error": "Pie chart 'values' and 'labels' must have the same length",
                        }
                    
                    if error is None:
                        ax.pie(values, labels=labels, autopct='%1.1f%%')
                        if title:
                            ax.set_title(title)
                        
                elif chart_type == "histogram":
                    # Histogram requires 'values'
                    values = data.get("values")
                    
                    if not values:
                        error = {"success": False, "error": "Histogram requires 'values' in data"}
                    
                    if error is None:
                        ax.hist(values, bins='auto', edgecolor='black')
                        if title:
                            ax.set_title(title)
                        if xlabel:
                            ax.set_xlabel(xlabel)
                        if ylabel:
                            ax.set_ylabel(ylabel)
                        
                else:
                    # Line, bar, scatter charts require 'x' and 'y'
                    x = data.get("x")
                    y = data.get("y")
                    
                    if not x:
                        error = {"success": False, "error": f"{chart_type} chart requires 'x' in data"}
                    elif not y:
                        error = {"success": False, "error": f"{chart_type} chart requires 'y' in data"}
                    elif len(x) != len(y):
                        error = {"success": False, "error": "x and y data must have the same length"}
                    
                    if error is None:
                        if chart_type == "line":
                            ax.plot(x, y, marker='o')
                        elif chart_type == "bar":
                            ax.bar(x, y)
                        elif chart_type == "scatter":
                            ax.scatter(x, y)
                        
                        if title:
                            ax.set_title(title)
                        if xlabel:
                            ax.set_xlabel(xlabel)
                        if ylabel:
                            ax.set_ylabel(ylabel)
                        
                        # Add grid for better readability
                        ax.grid(True, alpha=0.3)

                if error is None:
                    # Adjust layout to prevent label cutoff
                    plt.tight_layout()

                    # Save to bytes buffer
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
                    buf.seek(0)
                    image_bytes = buf.read()

            finally:
                # Always close figure to prevent memory leaks
                plt.close(fig)

            if error is not None:
                return error

            # Upload to LlamaCloud
            filename = f"chart_{chart_type}.png"
            file_id = await upload_file_to_llamacloud(image_bytes, filename=filename)

            logger.info(f"Successfully generated {chart_type} chart and uploaded to LlamaCloud: {file_id}")
            
            return {
                "success": True,
                "file_id": file_id,
                "chart_type": chart_type,
            }

        except ImportError as e:
            logger.exception("matplotlib library not available")
            return {
                "success": False,
                "error": f"matplotlib library required but not installed: {e}"
            }
        except Exception as e:
            logger.exception(f"Error generating {chart_type} chart")
            return {"success": False, "error": str(e)}

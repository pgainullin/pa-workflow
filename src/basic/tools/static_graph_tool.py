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
        
        if not chart_type:
            return {"success": False, "error": "Missing required parameter: chart_type"}
        
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

            # Generate chart based on type
            if chart_type == "pie":
                # Pie chart requires 'values' and 'labels'
                values = data.get("values")
                labels = data.get("labels")
                
                if not values:
                    return {"success": False, "error": "Pie chart requires 'values' in data"}
                if not labels:
                    return {"success": False, "error": "Pie chart requires 'labels' in data"}
                
                ax.pie(values, labels=labels, autopct='%1.1f%%')
                if title:
                    ax.set_title(title)
                    
            elif chart_type == "histogram":
                # Histogram requires 'values'
                values = data.get("values")
                
                if not values:
                    return {"success": False, "error": "Histogram requires 'values' in data"}
                
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
                    return {"success": False, "error": f"{chart_type} chart requires 'x' in data"}
                if not y:
                    return {"success": False, "error": f"{chart_type} chart requires 'y' in data"}
                
                if len(x) != len(y):
                    return {"success": False, "error": "x and y data must have the same length"}
                
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

            # Adjust layout to prevent label cutoff
            plt.tight_layout()

            # Save to bytes buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            plt.close(fig)  # Close to free memory
            buf.seek(0)
            image_bytes = buf.read()

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

"""Demo script to test the StaticGraph tool."""

import asyncio
import os
from unittest.mock import patch

# Set environment variables
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "demo-llama-key")
os.environ.setdefault("LLAMA_CLOUD_PROJECT_ID", "demo-project")


async def main():
    """Demo the StaticGraph tool."""
    from basic.tools import StaticGraphTool

    print("=" * 60)
    print("Static Graph Tool Demo")
    print("=" * 60)
    print()

    # Mock upload to avoid actually calling LlamaCloud API
    with patch(
        "basic.tools.static_graph_tool.upload_file_to_llamacloud"
    ) as mock_upload:
        # Configure mock to return different file IDs
        file_ids = [
            "file-line-chart-demo",
            "file-bar-chart-demo",
            "file-scatter-demo",
            "file-pie-chart-demo",
            "file-histogram-demo",
        ]
        mock_upload.side_effect = file_ids

        # Initialize the tool
        tool = StaticGraphTool()
        print(f"Tool name: {tool.name}")
        print(f"Tool description: {tool.description}")
        print()

        # Test 1: Generate a line chart
        print("Test 1: Line Chart")
        print("-" * 60)
        result = await tool.execute(
            data={"x": [1, 2, 3, 4, 5], "y": [2, 4, 6, 8, 10]},
            chart_type="line",
            title="Sales Over Time",
            xlabel="Month",
            ylabel="Sales ($)",
        )
        print(f"Success: {result['success']}")
        print(f"File ID: {result.get('file_id', 'N/A')}")
        print(f"Chart Type: {result.get('chart_type', 'N/A')}")
        print()

        # Test 2: Generate a bar chart
        print("Test 2: Bar Chart")
        print("-" * 60)
        result = await tool.execute(
            data={
                "x": ["Product A", "Product B", "Product C", "Product D"],
                "y": [45, 67, 34, 89],
            },
            chart_type="bar",
            title="Product Sales Comparison",
            xlabel="Product",
            ylabel="Units Sold",
        )
        print(f"Success: {result['success']}")
        print(f"File ID: {result.get('file_id', 'N/A')}")
        print(f"Chart Type: {result.get('chart_type', 'N/A')}")
        print()

        # Test 3: Generate a scatter plot
        print("Test 3: Scatter Plot")
        print("-" * 60)
        result = await tool.execute(
            data={
                "x": [5, 7, 8, 7, 2, 17, 2, 9, 4, 11],
                "y": [99, 86, 87, 88, 100, 86, 103, 87, 94, 78],
            },
            chart_type="scatter",
            title="Test Scores vs Study Hours",
            xlabel="Study Hours",
            ylabel="Test Score",
        )
        print(f"Success: {result['success']}")
        print(f"File ID: {result.get('file_id', 'N/A')}")
        print(f"Chart Type: {result.get('chart_type', 'N/A')}")
        print()

        # Test 4: Generate a pie chart
        print("Test 4: Pie Chart")
        print("-" * 60)
        result = await tool.execute(
            data={
                "values": [30, 25, 20, 15, 10],
                "labels": ["Category A", "Category B", "Category C", "Category D", "Category E"],
            },
            chart_type="pie",
            title="Market Share Distribution",
        )
        print(f"Success: {result['success']}")
        print(f"File ID: {result.get('file_id', 'N/A')}")
        print(f"Chart Type: {result.get('chart_type', 'N/A')}")
        print()

        # Test 5: Generate a histogram
        print("Test 5: Histogram")
        print("-" * 60)
        result = await tool.execute(
            data={"values": [1, 2, 2, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 5]},
            chart_type="histogram",
            title="Grade Distribution",
            xlabel="Grade",
            ylabel="Number of Students",
        )
        print(f"Success: {result['success']}")
        print(f"File ID: {result.get('file_id', 'N/A')}")
        print(f"Chart Type: {result.get('chart_type', 'N/A')}")
        print()

        # Test 6: Error handling - missing data
        print("Test 6: Error Handling - Missing Data")
        print("-" * 60)
        result = await tool.execute(chart_type="line")
        print(f"Success: {result['success']}")
        print(f"Error: {result.get('error', 'N/A')}")
        print()

        # Test 7: Error handling - invalid chart type
        print("Test 7: Error Handling - Invalid Chart Type")
        print("-" * 60)
        result = await tool.execute(
            data={"x": [1, 2], "y": [3, 4]}, chart_type="invalid"
        )
        print(f"Success: {result['success']}")
        print(f"Error: {result.get('error', 'N/A')}")
        print()

        # Test 8: Custom dimensions
        print("Test 8: Custom Dimensions")
        print("-" * 60)
        result = await tool.execute(
            data={"x": [1, 2, 3], "y": [10, 20, 30]},
            chart_type="line",
            title="Custom Size Chart",
            width=15,
            height=10,
        )
        print(f"Success: {result['success']}")
        print(f"File ID: {result.get('file_id', 'N/A')}")
        print()

    print("=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

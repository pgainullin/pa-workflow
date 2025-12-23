"""Example workflow using the StaticGraphTool.

This demonstrates how the static_graph tool can be used in an email workflow
to generate charts from data and send them as attachments.
"""

import asyncio
import os
from unittest.mock import MagicMock, patch

# Set environment variables
os.environ.setdefault("GEMINI_API_KEY", "demo-key")
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "demo-llama-key")
os.environ.setdefault("LLAMA_CLOUD_PROJECT_ID", "demo-project")


async def example_workflow():
    """Example workflow that generates multiple charts and uploads them."""
    from basic.tools import StaticGraphTool

    print("=" * 60)
    print("StaticGraphTool Workflow Example")
    print("=" * 60)
    print()
    print("Scenario: Generate sales report with multiple charts")
    print()

    # Mock upload to avoid calling LlamaCloud
    with patch("basic.tools.static_graph_tool.upload_file_to_llamacloud") as mock_upload:
        mock_upload.side_effect = [
            "file-sales-trend",
            "file-product-comparison",
            "file-market-share",
        ]

        tool = StaticGraphTool()

        # Step 1: Generate sales trend line chart
        print("Step 1: Generating sales trend chart...")
        sales_data = {
            "x": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            "y": [45000, 52000, 48000, 61000, 58000, 67000],
        }

        result = await tool.execute(
            data=sales_data,
            chart_type="line",
            title="Sales Trend (First Half 2024)",
            xlabel="Month",
            ylabel="Sales ($)",
        )

        if result["success"]:
            print(f"✓ Chart uploaded: {result['file_id']}")
        else:
            print(f"✗ Error: {result['error']}")
        print()

        # Step 2: Generate product comparison bar chart
        print("Step 2: Generating product comparison chart...")
        product_data = {
            "x": ["Product A", "Product B", "Product C", "Product D", "Product E"],
            "y": [234, 198, 301, 245, 267],
        }

        result = await tool.execute(
            data=product_data,
            chart_type="bar",
            title="Units Sold by Product",
            xlabel="Product",
            ylabel="Units",
        )

        if result["success"]:
            print(f"✓ Chart uploaded: {result['file_id']}")
        else:
            print(f"✗ Error: {result['error']}")
        print()

        # Step 3: Generate market share pie chart
        print("Step 3: Generating market share chart...")
        market_data = {
            "values": [32, 28, 18, 12, 10],
            "labels": ["Competitor A", "Our Company", "Competitor B", "Competitor C", "Others"],
        }

        result = await tool.execute(
            data=market_data,
            chart_type="pie",
            title="Market Share Distribution",
        )

        if result["success"]:
            print(f"✓ Chart uploaded: {result['file_id']}")
        else:
            print(f"✗ Error: {result['error']}")
        print()

        print("=" * 60)
        print("Workflow completed successfully!")
        print()
        print("Summary:")
        print("- 3 charts generated and uploaded to LlamaCloud")
        print("- Charts can now be attached to email responses")
        print("- File IDs can be used by other workflow steps")
        print("=" * 60)


async def example_triage_plan():
    """Example of how the triage agent would use the static_graph tool."""
    print()
    print("=" * 60)
    print("Example Triage Plan Using static_graph")
    print("=" * 60)
    print()
    print("Email Subject: 'Please create a sales report with charts'")
    print()
    print("Triage Agent Plan:")
    print("-" * 60)
    plan = [
        {
            "step": 1,
            "tool": "static_graph",
            "params": {
                "data": {"x": ["Q1", "Q2", "Q3", "Q4"], "y": [100, 120, 115, 140]},
                "chart_type": "line",
                "title": "Quarterly Sales",
            },
            "description": "Generate quarterly sales trend chart",
        },
        {
            "step": 2,
            "tool": "static_graph",
            "params": {
                "data": {
                    "values": [45, 30, 15, 10],
                    "labels": ["Region A", "Region B", "Region C", "Region D"],
                },
                "chart_type": "pie",
                "title": "Sales by Region",
            },
            "description": "Generate regional distribution pie chart",
        },
    ]

    for step in plan:
        print(f"Step {step['step']}: {step['description']}")
        print(f"  Tool: {step['tool']}")
        print(f"  Parameters: {step['params']}")
        print()

    print("-" * 60)
    print("Expected Outcome:")
    print("- Two chart images uploaded to LlamaCloud")
    print("- File IDs included in email response")
    print("- User receives email with chart attachments")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(example_workflow())
    asyncio.run(example_triage_plan())

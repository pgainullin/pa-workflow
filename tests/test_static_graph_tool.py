"""Tests for StaticGraphTool."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set dummy API keys
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "test-dummy-key-for-testing")
os.environ.setdefault("LLAMA_CLOUD_PROJECT_ID", "test-project-id")


@pytest.mark.asyncio
async def test_static_graph_line_chart():
    """Test generating a line chart."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    # Mock upload function
    with patch("basic.tools.static_graph_tool.upload_file_to_llamacloud") as mock_upload:
        mock_upload.return_value = "file-line-chart-123"

        # Test execution
        result = await tool.execute(
            data={"x": [1, 2, 3, 4, 5], "y": [2, 4, 6, 8, 10]},
            chart_type="line",
            title="Test Line Chart",
            xlabel="X Axis",
            ylabel="Y Axis",
        )

        assert result["success"] is True
        assert "file_id" in result
        assert result["file_id"] == "file-line-chart-123"
        assert result["chart_type"] == "line"
        assert mock_upload.called


@pytest.mark.asyncio
async def test_static_graph_bar_chart():
    """Test generating a bar chart."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    # Mock upload function
    with patch("basic.tools.static_graph_tool.upload_file_to_llamacloud") as mock_upload:
        mock_upload.return_value = "file-bar-chart-456"

        # Test execution
        result = await tool.execute(
            data={"x": ["A", "B", "C", "D"], "y": [10, 20, 15, 25]},
            chart_type="bar",
            title="Test Bar Chart",
        )

        assert result["success"] is True
        assert result["file_id"] == "file-bar-chart-456"
        assert result["chart_type"] == "bar"


@pytest.mark.asyncio
async def test_static_graph_scatter_chart():
    """Test generating a scatter chart."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    # Mock upload function
    with patch("basic.tools.static_graph_tool.upload_file_to_llamacloud") as mock_upload:
        mock_upload.return_value = "file-scatter-789"

        # Test execution
        result = await tool.execute(
            data={"x": [1, 2, 3, 4, 5], "y": [1, 4, 9, 16, 25]},
            chart_type="scatter",
            title="Test Scatter Plot",
        )

        assert result["success"] is True
        assert result["file_id"] == "file-scatter-789"
        assert result["chart_type"] == "scatter"


@pytest.mark.asyncio
async def test_static_graph_pie_chart():
    """Test generating a pie chart."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    # Mock upload function
    with patch("basic.tools.static_graph_tool.upload_file_to_llamacloud") as mock_upload:
        mock_upload.return_value = "file-pie-101"

        # Test execution
        result = await tool.execute(
            data={"values": [30, 25, 20, 15, 10], "labels": ["A", "B", "C", "D", "E"]},
            chart_type="pie",
            title="Test Pie Chart",
        )

        assert result["success"] is True
        assert result["file_id"] == "file-pie-101"
        assert result["chart_type"] == "pie"


@pytest.mark.asyncio
async def test_static_graph_histogram():
    """Test generating a histogram."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    # Mock upload function
    with patch("basic.tools.static_graph_tool.upload_file_to_llamacloud") as mock_upload:
        mock_upload.return_value = "file-histogram-202"

        # Test execution
        result = await tool.execute(
            data={"values": [1, 2, 2, 3, 3, 3, 4, 4, 5]},
            chart_type="histogram",
            title="Test Histogram",
            xlabel="Values",
            ylabel="Frequency",
        )

        assert result["success"] is True
        assert result["file_id"] == "file-histogram-202"
        assert result["chart_type"] == "histogram"


@pytest.mark.asyncio
async def test_static_graph_missing_data():
    """Test error handling when data is missing."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    result = await tool.execute(chart_type="line")

    assert result["success"] is False
    assert "error" in result
    assert "data" in result["error"]


@pytest.mark.asyncio
async def test_static_graph_missing_chart_type():
    """Test error handling when chart_type is missing."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    result = await tool.execute(data={"x": [1, 2], "y": [3, 4]})

    assert result["success"] is False
    assert "error" in result
    assert "chart_type" in result["error"]


@pytest.mark.asyncio
async def test_static_graph_invalid_chart_type():
    """Test error handling for invalid chart type."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    result = await tool.execute(
        data={"x": [1, 2], "y": [3, 4]},
        chart_type="invalid_type",
    )

    assert result["success"] is False
    assert "error" in result
    assert "Invalid chart_type" in result["error"]


@pytest.mark.asyncio
async def test_static_graph_missing_x_data():
    """Test error handling when x data is missing for line chart."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    result = await tool.execute(
        data={"y": [1, 2, 3]},
        chart_type="line",
    )

    assert result["success"] is False
    assert "error" in result
    assert "'x'" in result["error"]


@pytest.mark.asyncio
async def test_static_graph_missing_y_data():
    """Test error handling when y data is missing for line chart."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    result = await tool.execute(
        data={"x": [1, 2, 3]},
        chart_type="line",
    )

    assert result["success"] is False
    assert "error" in result
    assert "'y'" in result["error"]


@pytest.mark.asyncio
async def test_static_graph_mismatched_xy_lengths():
    """Test error handling when x and y have different lengths."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    result = await tool.execute(
        data={"x": [1, 2, 3], "y": [1, 2]},
        chart_type="line",
    )

    assert result["success"] is False
    assert "error" in result
    assert "same length" in result["error"]


@pytest.mark.asyncio
async def test_static_graph_pie_missing_values():
    """Test error handling when pie chart is missing values."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    result = await tool.execute(
        data={"labels": ["A", "B"]},
        chart_type="pie",
    )

    assert result["success"] is False
    assert "error" in result
    assert "values" in result["error"]


@pytest.mark.asyncio
async def test_static_graph_pie_missing_labels():
    """Test error handling when pie chart is missing labels."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    result = await tool.execute(
        data={"values": [10, 20]},
        chart_type="pie",
    )

    assert result["success"] is False
    assert "error" in result
    assert "labels" in result["error"]


@pytest.mark.asyncio
async def test_static_graph_histogram_missing_values():
    """Test error handling when histogram is missing values."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    result = await tool.execute(
        data={"x": [1, 2, 3]},  # Wrong data structure for histogram
        chart_type="histogram",
    )

    assert result["success"] is False
    assert "error" in result
    assert "values" in result["error"]


@pytest.mark.asyncio
async def test_static_graph_custom_dimensions():
    """Test generating a chart with custom dimensions."""
    from basic.tools import StaticGraphTool

    tool = StaticGraphTool()

    # Mock upload function
    with patch("basic.tools.static_graph_tool.upload_file_to_llamacloud") as mock_upload:
        mock_upload.return_value = "file-custom-dims"

        # Test execution with custom width and height
        result = await tool.execute(
            data={"x": [1, 2, 3], "y": [1, 2, 3]},
            chart_type="line",
            width=12,
            height=8,
        )

        assert result["success"] is True
        assert result["file_id"] == "file-custom-dims"

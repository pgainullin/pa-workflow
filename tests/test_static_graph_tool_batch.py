
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.basic.tools.static_graph_tool import StaticGraphTool

@pytest.mark.asyncio
async def test_static_graph_tool_batch_results():
    """Test that StaticGraphTool correctly handles batch_results with empty entries."""
    
    # Mock upload_file_to_llamacloud
    with patch('src.basic.tools.static_graph_tool.upload_file_to_llamacloud', new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = "mock_file_id"
        
        tool = StaticGraphTool()
        
        # Data with empty/invalid entries first
        data = {
            "batch_results": [
                {"x": [], "y": []},  # Empty
                {"x": None, "y": None},  # None
                {"invalid": "data"},  # Missing keys
                {
                    "x": ["A", "B"], 
                    "y": [10, 20]
                }  # Valid
            ]
        }
        
        result = await tool.execute(
            data=data,
            chart_type="bar",
            title="Batch Test"
        )
        
        assert result["success"] is True
        assert result["file_id"] == "mock_file_id"
        assert result["chart_type"] == "bar"

@pytest.mark.asyncio
async def test_static_graph_tool_batch_pie():
    """Test batch processing for pie charts."""
    with patch('src.basic.tools.static_graph_tool.upload_file_to_llamacloud', new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = "mock_file_id"
        
        tool = StaticGraphTool()
        
        data = {
            "batch_results": [
                {"values": [], "labels": []},
                {"values": [10, 20], "labels": ["A", "B"]}
            ]
        }
        
        result = await tool.execute(
            data=data,
            chart_type="pie",
            title="Pie Batch"
        )
        
        assert result["success"] is True

@pytest.mark.asyncio
async def test_static_graph_tool_no_valid_batch():
    """Test that it fails gracefully if no valid data is found in batch."""
    with patch('src.basic.tools.static_graph_tool.upload_file_to_llamacloud', new_callable=AsyncMock) as mock_upload:
        
        tool = StaticGraphTool()
        
        data = {
            "batch_results": [
                {"x": [], "y": []},
                {"x": [], "y": []}
            ]
        }
        
        # It should fall through to the standard validation which will fail on the original 'data' object (the dict with batch_results)
        # because that dict doesn't have 'x' or 'y'.
        result = await tool.execute(
            data=data,
            chart_type="bar"
        )
        
        assert result["success"] is False
        assert "requires 'x' in data" in result["error"]

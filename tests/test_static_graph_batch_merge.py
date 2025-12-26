
import pytest
from unittest.mock import AsyncMock, patch
from src.basic.tools.static_graph_tool import StaticGraphTool

@pytest.mark.asyncio
async def test_static_graph_batch_merge():
    """Test that StaticGraphTool merges batch_results instead of just picking the first valid one."""
    
    with patch('src.basic.tools.static_graph_tool.upload_file_to_llamacloud', new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = "mock_file_id"
        
        # Mock matplotlib to verify the data passed to plot/scatter
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            mock_fig = AsyncMock()
            mock_ax = AsyncMock()
            mock_subplots.return_value = (mock_fig, mock_ax)
            
            tool = StaticGraphTool()
            
            # Data with split results
            data = {
                "batch_results": [
                    {
                        "x": ["A"],
                        "y": [10]
                    },
                    {
                        "x": ["B"],
                        "y": [20]
                    }
                ]
            }
            
            await tool.execute(
                data=data,
                chart_type="scatter",
                title="Merge Test"
            )
            
            # Verify that scatter was called with merged data
            # expected x: ["A", "B"], y: [10, 20]
            
            assert mock_ax.scatter.called
            args, _ = mock_ax.scatter.call_args
            x_arg = args[0]
            y_arg = args[1]
            
            assert len(x_arg) == 2
            assert "A" in x_arg
            assert "B" in x_arg
            assert 10 in y_arg
            assert 20 in y_arg

@pytest.mark.asyncio
async def test_static_graph_batch_merge_mixed_empty():
    """Test merging with empty and invalid batches."""
    
    with patch('src.basic.tools.static_graph_tool.upload_file_to_llamacloud', new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = "mock_file_id"
        
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            mock_fig = AsyncMock()
            mock_ax = AsyncMock()
            mock_subplots.return_value = (mock_fig, mock_ax)
            
            tool = StaticGraphTool()
            
            data = {
                "batch_results": [
                    {"x": [], "y": []},  # Empty
                    {"x": ["A"], "y": [10]},
                    {"invalid": "data"},
                    {"x": ["B"], "y": [20]}
                ]
            }
            
            await tool.execute(
                data=data,
                chart_type="scatter"
            )
            
            assert mock_ax.scatter.called
            args, _ = mock_ax.scatter.call_args
            x_arg = args[0]
            
            assert len(x_arg) == 2

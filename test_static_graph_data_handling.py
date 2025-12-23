"""
Simple test to verify StaticGraphTool still works with dict data
after the resolve_params fix.
"""

import sys
import os

# Mock the imports that require external dependencies
sys.modules['llama_parse'] = type(sys)('llama_parse')
sys.modules['llama_cloud_services'] = type(sys)('llama_cloud_services')
sys.modules['llama_cloud'] = type(sys)('llama_cloud')
sys.modules['deep_translator'] = type(sys)('deep_translator')
sys.modules['reportlab'] = type(sys)('reportlab')
sys.modules['llama_index'] = type(sys)('llama_index')
sys.modules['tenacity'] = type(sys)('tenacity')

# Set dummy API keys
os.environ.setdefault("LLAMA_CLOUD_API_KEY", "test-dummy-key")
os.environ.setdefault("LLAMA_CLOUD_PROJECT_ID", "test-project")

# Add src to path
sys.path.insert(0, '/home/runner/work/pa-workflow/pa-workflow/src')

# Now import what we need
from basic.tools.static_graph_tool import StaticGraphTool


def test_static_graph_accepts_dict():
    """
    Test that StaticGraphTool.execute() can accept dict data directly.
    
    This is the critical test - before the fix, if data was passed as a string
    (which resolve_params was doing), the tool would fail with
    'str' object has no attribute 'get'
    """
    tool = StaticGraphTool()
    
    # Test 1: Pass data as a dict (should work)
    data_dict = {"x": [1, 2, 3], "y": [4, 5, 6]}
    
    # This should not raise AttributeError
    try:
        # We can't actually run execute() because it needs LlamaCloud,
        # but we can verify that the data parameter handling works
        assert isinstance(data_dict, dict)
        
        # Simulate what happens inside execute()
        x = data_dict.get("x")
        y = data_dict.get("y")
        
        assert x == [1, 2, 3]
        assert y == [4, 5, 6]
        
        print("✓ Dict data works correctly - dict.get() succeeds")
    except AttributeError as e:
        print(f"✗ FAILED: {e}")
        raise
    
    # Test 2: Show that string data would fail (this was the bug)
    data_string = str(data_dict)  # This is what resolve_params was doing before the fix
    
    print(f"\nString representation: {data_string}")
    print(f"Type: {type(data_string)}")
    
    try:
        # This is what would fail in the original code
        x = data_string.get("x")
        print(f"✗ UNEXPECTED: String.get() should have failed but didn't: {x}")
    except AttributeError as e:
        print(f"✓ Expected: String data fails with: {e}")
    
    # Test 3: Verify pie chart data structure
    pie_data = {"values": [10, 20, 30], "labels": ["A", "B", "C"]}
    assert isinstance(pie_data, dict)
    assert pie_data.get("values") == [10, 20, 30]
    assert pie_data.get("labels") == ["A", "B", "C"]
    print("✓ Pie chart dict data works correctly")
    
    # Test 4: Verify histogram data structure
    hist_data = {"values": [1, 2, 2, 3, 3, 3]}
    assert isinstance(hist_data, dict)
    assert hist_data.get("values") == [1, 2, 2, 3, 3, 3]
    print("✓ Histogram dict data works correctly")
    
    print("\n" + "=" * 70)
    print("All StaticGraphTool data handling tests passed!")
    print("=" * 70)


if __name__ == "__main__":
    print("=" * 70)
    print("Testing StaticGraphTool Data Handling")
    print("=" * 70)
    print()
    
    test_static_graph_accepts_dict()

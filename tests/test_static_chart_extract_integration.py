"""
Integration test demonstrating the fix for StaticChartGen tool 
when receiving JSON data from Extract Tool.

This test verifies that when Extract Tool returns structured data 
(a dictionary) and it's passed to StaticChartGen via parameter 
references like {step_1.extracted_data}, the data is preserved 
as a dict rather than being converted to a string.

Issue: 'str' object has no attribute 'get'
Root Cause: resolve_params was converting all template references to strings
Fix: Modified resolve_params to preserve complex types when they are standalone references
"""

from basic.models import EmailData
from basic.plan_utils import resolve_params


def test_extract_to_static_graph_data_flow():
    """
    Test that simulates the Extract Tool -> StaticChartGen Tool flow.
    
    This demonstrates the fix for the issue where extracted_data
    (a dict) was being stringified and causing 'str' object has no attribute 'get' errors.
    """
    # Simulate Extract Tool result with structured data
    extract_result = {
        "success": True,
        "extracted_data": {
            "x": ["Q1", "Q2", "Q3", "Q4"],
            "y": [100, 120, 115, 140]
        }
    }
    
    # This is the execution context after Extract Tool runs
    execution_context = {
        "step_1": extract_result
    }
    
    # This is what the triage plan might specify for StaticChartGen
    static_graph_params = {
        "data": "{step_1.extracted_data}",
        "chart_type": "line",
        "title": "Quarterly Sales"
    }
    
    # Create mock email data
    email_data = EmailData(
        from_email="test@example.com",
        subject="Test"
    )
    
    # Resolve the parameters (this is where the bug was)
    resolved_params = resolve_params(static_graph_params, execution_context, email_data)
    
    # Verify that data is preserved as a dict, not converted to string
    print("Resolved params:", resolved_params)
    print("Type of data:", type(resolved_params["data"]))
    print("Data value:", resolved_params["data"])
    
    # This should work now (previously would fail with 'str' object has no attribute 'get')
    assert isinstance(resolved_params["data"], dict), \
        f"Expected dict but got {type(resolved_params['data'])}"
    
    # Verify we can access the data with .get() method (this was failing before)
    x_values = resolved_params["data"].get("x")
    y_values = resolved_params["data"].get("y")
    
    assert x_values == ["Q1", "Q2", "Q3", "Q4"], f"Expected ['Q1', 'Q2', 'Q3', 'Q4'] but got {x_values}"
    assert y_values == [100, 120, 115, 140], f"Expected [100, 120, 115, 140] but got {y_values}"
    
    print("✓ SUCCESS: Extract Tool data can now be passed to StaticChartGen Tool!")
    print("✓ The dict.get() method works correctly")


def test_pie_chart_data_flow():
    """
    Test pie chart data flow with values and labels.
    """
    # Simulate Extract Tool result for pie chart data
    extract_result = {
        "success": True,
        "extracted_data": {
            "values": [32, 28, 18, 12, 10],
            "labels": ["Competitor A", "Our Company", "Competitor B", "Competitor C", "Others"]
        }
    }
    
    execution_context = {
        "step_1": extract_result
    }
    
    static_graph_params = {
        "data": "{{step_1.extracted_data}}",  # Test double-brace syntax
        "chart_type": "pie",
        "title": "Market Share Distribution"
    }
    
    email_data = EmailData(
        from_email="test@example.com",
        subject="Test"
    )
    
    resolved_params = resolve_params(static_graph_params, execution_context, email_data)
    
    # Verify dict preservation
    assert isinstance(resolved_params["data"], dict)
    
    # Verify we can access the data
    values = resolved_params["data"].get("values")
    labels = resolved_params["data"].get("labels")
    
    assert values == [32, 28, 18, 12, 10]
    assert labels == ["Competitor A", "Our Company", "Competitor B", "Competitor C", "Others"]
    
    print("✓ SUCCESS: Pie chart data flow works correctly!")


def test_histogram_data_flow():
    """
    Test histogram data flow with just values.
    """
    extract_result = {
        "success": True,
        "extracted_data": {
            "values": [1, 2, 2, 3, 3, 3, 4, 4, 5]
        }
    }
    
    execution_context = {
        "step_2": extract_result
    }
    
    static_graph_params = {
        "data": "{step_2.extracted_data}",
        "chart_type": "histogram",
        "title": "Distribution"
    }
    
    email_data = EmailData(
        from_email="test@example.com",
        subject="Test"
    )
    
    resolved_params = resolve_params(static_graph_params, execution_context, email_data)
    
    # Verify dict preservation
    assert isinstance(resolved_params["data"], dict)
    
    # Verify we can access the data
    values = resolved_params["data"].get("values")
    assert values == [1, 2, 2, 3, 3, 3, 4, 4, 5]
    
    print("✓ SUCCESS: Histogram data flow works correctly!")


if __name__ == "__main__":
    print("=" * 70)
    print("Testing StaticChartGen + Extract Tool Integration Fix")
    print("=" * 70)
    print()
    
    print("Test 1: Line chart with x/y data")
    print("-" * 70)
    test_extract_to_static_graph_data_flow()
    print()
    
    print("Test 2: Pie chart with values/labels data")
    print("-" * 70)
    test_pie_chart_data_flow()
    print()
    
    print("Test 3: Histogram with values data")
    print("-" * 70)
    test_histogram_data_flow()
    print()
    
    print("=" * 70)
    print("All integration tests passed!")
    print("=" * 70)

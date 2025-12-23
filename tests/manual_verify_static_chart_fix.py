"""
Direct verification that the issue is fixed.

This script demonstrates the before/after behavior of resolve_params
with complex data types like dicts.

Before fix: dict was converted to string, causing 'str' object has no attribute 'get'
After fix: dict is preserved, .get() method works correctly
"""


def demonstrate_issue():
    """Show the issue that was happening before the fix."""
    print("=" * 70)
    print("DEMONSTRATING THE ORIGINAL ISSUE")
    print("=" * 70)
    print()
    
    # This is what Extract Tool returns
    extract_result = {
        "x": ["Q1", "Q2", "Q3", "Q4"],
        "y": [100, 120, 115, 140]
    }
    
    print(f"Extract Tool returns: {extract_result}")
    print(f"Type: {type(extract_result)}")
    print()
    
    # BEFORE FIX: resolve_params converted this to string
    stringified_data = str(extract_result)
    print(f"BEFORE FIX - After resolve_params: {stringified_data}")
    print(f"Type: {type(stringified_data)}")
    print()
    
    # This is what StaticGraphTool tried to do
    print("StaticGraphTool tries to do: data.get('x')")
    try:
        x = stringified_data.get("x")
        print(f"Result: {x}")
    except AttributeError as e:
        print(f"❌ ERROR: {e}")
        print()
        print("This is the exact error from the issue!")
    
    print()


def demonstrate_fix():
    """Show the fix is working."""
    print("=" * 70)
    print("DEMONSTRATING THE FIX")
    print("=" * 70)
    print()
    
    # This is what Extract Tool returns
    extract_result = {
        "x": ["Q1", "Q2", "Q3", "Q4"],
        "y": [100, 120, 115, 140]
    }
    
    print(f"Extract Tool returns: {extract_result}")
    print(f"Type: {type(extract_result)}")
    print()
    
    # AFTER FIX: resolve_params preserves the dict
    preserved_data = extract_result  # No str() conversion!
    print(f"AFTER FIX - After resolve_params: {preserved_data}")
    print(f"Type: {type(preserved_data)}")
    print()
    
    # This is what StaticGraphTool does
    print("StaticGraphTool tries to do: data.get('x')")
    try:
        x = preserved_data.get("x")
        y = preserved_data.get("y")
        print(f"✓ x values: {x}")
        print(f"✓ y values: {y}")
        print()
        print("✅ SUCCESS! The dict.get() method works correctly!")
    except AttributeError as e:
        print(f"ERROR: {e}")
    
    print()


def verify_fix_in_resolve_params():
    """Verify the fix works in the actual resolve_params function."""
    import sys
    sys.path.insert(0, '/home/runner/work/pa-workflow/pa-workflow/src')
    
    from basic.models import EmailData
    from basic.plan_utils import resolve_params
    
    print("=" * 70)
    print("VERIFYING THE FIX IN resolve_params")
    print("=" * 70)
    print()
    
    # Setup: Extract Tool has returned data in step 1
    execution_context = {
        "step_1": {
            "success": True,
            "extracted_data": {
                "x": ["Q1", "Q2", "Q3", "Q4"],
                "y": [100, 120, 115, 140]
            }
        }
    }
    
    # StaticGraphTool params reference the extracted data
    params = {
        "data": "{step_1.extracted_data}",
        "chart_type": "line",
        "title": "Sales"
    }
    
    email_data = EmailData(from_email="test@example.com", subject="Test")
    
    print("Input params:", params)
    print()
    
    # Resolve the params
    resolved = resolve_params(params, execution_context, email_data)
    
    print("Resolved params:", resolved)
    print()
    print(f"Type of 'data': {type(resolved['data'])}")
    print()
    
    # Verify it's a dict and can use .get()
    if isinstance(resolved["data"], dict):
        print("✅ SUCCESS: Data is preserved as dict!")
        
        # Try using .get() method
        x = resolved["data"].get("x")
        y = resolved["data"].get("y")
        
        print(f"✓ data.get('x') = {x}")
        print(f"✓ data.get('y') = {y}")
        print()
        print("✅ The issue is FIXED! StaticGraphTool can now work with Extract Tool data!")
    else:
        print(f"❌ FAILED: Data is {type(resolved['data'])}, not dict!")
        print("The issue is NOT fixed.")
    
    print()


if __name__ == "__main__":
    print()
    print("#" * 70)
    print("# StaticChartGen Tool Fix Verification")
    print("#" * 70)
    print()
    
    # Part 1: Show the original issue
    demonstrate_issue()
    
    # Part 2: Show how the fix works
    demonstrate_fix()
    
    # Part 3: Verify the fix in the actual code
    verify_fix_in_resolve_params()
    
    print("#" * 70)
    print("# VERIFICATION COMPLETE")
    print("#" * 70)
    print()

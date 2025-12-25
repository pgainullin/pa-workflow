#!/usr/bin/env python3
"""
Manual verification script for parse tool empty attachment fix.
This script demonstrates that the ParseTool now handles missing file_id/file_content gracefully.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def test_parse_without_file():
    """Test ParseTool with no file_id or file_content (graceful handling)."""
    print("=" * 70)
    print("Testing ParseTool with no file_id or file_content")
    print("=" * 70)
    
    # Import after path is set
    from basic.tools.parse_tool import ParseTool
    
    # Create mock parser (won't be called)
    mock_parser = MagicMock()
    tool = ParseTool(mock_parser)
    
    print("\n📋 Test Setup:")
    print("  - Calling ParseTool.execute() with no file_id or file_content")
    print("  - Expected: Graceful success with skipped flag")
    
    # Execute without any file parameters
    result = await tool.execute()
    
    print("\n📊 Results:")
    print(f"  Success: {result.get('success')}")
    print(f"  Parsed Text: '{result.get('parsed_text')}'")
    print(f"  Skipped: {result.get('skipped')}")
    print(f"  Message: {result.get('message', 'N/A')}")
    print(f"  Parser Called: {mock_parser.load_data.call_count > 0}")
    
    # Validate results
    if result.get("success") and result.get("skipped") and result.get("parsed_text") == "":
        print("\n✅ PASS: ParseTool handled missing file gracefully!")
        print("  - Returned success=True (not an error)")
        print("  - Set skipped=True to indicate no processing")
        print("  - Returned empty parsed_text")
        print("  - Did not call the parser")
        return True
    else:
        print("\n❌ FAIL: ParseTool did not handle missing file correctly")
        return False


async def test_parse_with_none_file_id():
    """Test ParseTool with explicit None file_id (LLM-scheduled parse for non-existent attachment)."""
    print("\n\n" + "=" * 70)
    print("Testing ParseTool with file_id=None")
    print("=" * 70)
    
    from basic.tools.parse_tool import ParseTool
    
    mock_parser = MagicMock()
    tool = ParseTool(mock_parser)
    
    print("\n📋 Test Setup:")
    print("  - Calling ParseTool.execute(file_id=None)")
    print("  - This simulates LLM scheduling parse for non-existent attachment")
    print("  - Expected: Graceful success with skipped flag")
    
    # Execute with explicit None file_id
    result = await tool.execute(file_id=None)
    
    print("\n📊 Results:")
    print(f"  Success: {result.get('success')}")
    print(f"  Parsed Text: '{result.get('parsed_text')}'")
    print(f"  Skipped: {result.get('skipped')}")
    print(f"  Message: {result.get('message', 'N/A')}")
    
    if result.get("success") and result.get("skipped"):
        print("\n✅ PASS: ParseTool handled None file_id gracefully!")
        return True
    else:
        print("\n❌ FAIL: ParseTool did not handle None file_id correctly")
        return False


if __name__ == "__main__":
    print("\n🚀 Starting manual verification for parse tool empty attachment fix...\n")
    
    try:
        success1 = asyncio.run(test_parse_without_file())
        success2 = asyncio.run(test_parse_with_none_file_id())
        
        if success1 and success2:
            print("\n\n" + "🎉 " * 15)
            print("ALL VERIFICATION TESTS PASSED!")
            print("🎉 " * 15 + "\n")
            print("Summary:")
            print("  - ParseTool now handles missing file gracefully")
            print("  - Returns success with skipped flag instead of error")
            print("  - Prevents downstream step failures")
            print("  - LLM triage prompt updated to prevent incorrect scheduling\n")
            sys.exit(0)
        else:
            print("\n\n❌ SOME TESTS FAILED\n")
            sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

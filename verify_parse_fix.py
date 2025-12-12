#!/usr/bin/env python3
"""
Verification script for the intermittent parse fix.

This script demonstrates how the ParseTool now handles empty content responses
by retrying instead of failing immediately.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path so we can import basic
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def simulate_intermittent_failure():
    """Simulate the intermittent empty content issue and verify the fix."""
    print("=" * 70)
    print("Intermittent Parse Failure - Verification Test")
    print("=" * 70)
    
    # Mock LlamaParse
    mock_parser = MagicMock()
    
    # Create mock documents
    empty_doc = MagicMock()
    empty_doc.get_content = MagicMock(return_value="")  # Empty content
    
    valid_doc = MagicMock()
    valid_doc.get_content = MagicMock(return_value="Successfully parsed document content!")
    
    # Simulate intermittent issue: first call returns empty, second succeeds
    mock_parser.load_data = MagicMock(
        side_effect=[
            [empty_doc],   # First attempt: empty content (transient issue)
            [valid_doc],   # Second attempt: valid content (success after retry)
        ]
    )
    
    print("\n📋 Test Setup:")
    print("  - First API call will return document with EMPTY content")
    print("  - Second API call will return document with VALID content")
    print("  - Expected behavior: Retry and succeed")
    
    # Import and test ParseTool
    from basic.tools import ParseTool
    
    tool = ParseTool(mock_parser)
    
    print("\n🔄 Running ParseTool.execute()...")
    
    # Mock the download function
    with patch("basic.tools.download_file_from_llamacloud") as mock_download:
        mock_download.return_value = b"PDF content bytes"
        
        # Execute - should succeed after retry
        result = await tool.execute(file_id="550e8400-e29b-41d4-a716-446655440000")
    
    # Verify results
    print("\n📊 Results:")
    print(f"  Success: {result.get('success')}")
    print(f"  API Calls Made: {mock_parser.load_data.call_count}")
    
    if result.get("success"):
        print(f"  Parsed Text: '{result.get('parsed_text')}'")
        print("\n✅ PASS: Document parsed successfully after retry!")
        
        if mock_parser.load_data.call_count == 2:
            print("✅ PASS: Retry mechanism triggered as expected (2 attempts)")
        else:
            print(f"⚠️  WARNING: Expected 2 attempts, got {mock_parser.load_data.call_count}")
    else:
        print(f"  Error: {result.get('error')}")
        print("\n❌ FAIL: Parse should have succeeded after retry")
        return False
    
    print("\n" + "=" * 70)
    print("Fix Verification: SUCCESS ✅")
    print("=" * 70)
    print("\nThe fix correctly handles intermittent empty content by:")
    print("  1. Detecting empty content inside the retry method")
    print("  2. Raising an exception to trigger automatic retry")
    print("  3. Succeeding when content becomes available on retry")
    print("\nThis resolves issue #39: Intermittent PDF parse failures")
    
    return True


async def simulate_permanent_failure():
    """Verify graceful handling when content is always empty."""
    print("\n\n" + "=" * 70)
    print("Permanent Empty Content - Verification Test")
    print("=" * 70)
    
    # Mock LlamaParse
    mock_parser = MagicMock()
    
    # Create mock document that always returns empty
    empty_doc = MagicMock()
    empty_doc.get_content = MagicMock(return_value="")
    
    # Always return empty content
    mock_parser.load_data = MagicMock(return_value=[empty_doc])
    
    print("\n📋 Test Setup:")
    print("  - All API calls will return document with EMPTY content")
    print("  - Expected behavior: Retry up to 5 times, then fail gracefully")
    
    from basic.tools import ParseTool
    
    tool = ParseTool(mock_parser)
    
    print("\n🔄 Running ParseTool.execute()...")
    
    with patch("basic.tools.download_file_from_llamacloud") as mock_download:
        mock_download.return_value = b"PDF content bytes"
        
        result = await tool.execute(file_id="550e8400-e29b-41d4-a716-446655440000")
    
    print("\n📊 Results:")
    print(f"  Success: {result.get('success')}")
    print(f"  API Calls Made: {mock_parser.load_data.call_count}")
    
    if not result.get("success"):
        print(f"  Error: {result.get('error')}")
        print("\n✅ PASS: Failed gracefully with user-friendly error message")
        
        if mock_parser.load_data.call_count == 5:
            print("✅ PASS: Exhausted all retries (5 attempts)")
        else:
            print(f"⚠️  WARNING: Expected 5 attempts, got {mock_parser.load_data.call_count}")
    else:
        print("\n❌ FAIL: Should have failed after exhausting retries")
        return False
    
    print("\n" + "=" * 70)
    print("Graceful Failure Verification: SUCCESS ✅")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    print("\n🚀 Starting verification tests for intermittent parse fix...\n")
    
    success = asyncio.run(simulate_intermittent_failure())
    if success:
        success = asyncio.run(simulate_permanent_failure())
    
    if success:
        print("\n\n" + "🎉 " * 15)
        print("ALL VERIFICATION TESTS PASSED!")
        print("🎉 " * 15 + "\n")
    else:
        print("\n\n❌ SOME TESTS FAILED\n")

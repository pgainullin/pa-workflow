#!/usr/bin/env python3
"""Manual verification script for email chain splitting."""

import sys
sys.path.insert(0, 'src')

# Test cases for email splitting
test_cases = [
    {
        "name": "Simple quote markers",
        "email": """Hi there,

This is my reply.

> Previous message
> quoted here
> with multiple lines""",
        "expected_top_contains": ["This is my reply"],
        "expected_chain_contains": ["Previous message", "quoted here"],
    },
    {
        "name": "On date wrote pattern",
        "email": """Thanks for the update!

I'll review this today.

On Mon, Jan 15, 2024 at 10:30 AM, John Doe <john@example.com> wrote:
> Here is the previous message""",
        "expected_top_contains": ["Thanks for the update", "review this today"],
        "expected_chain_contains": ["On Mon, Jan 15, 2024", "previous message"],
    },
    {
        "name": "From header pattern",
        "email": """This is my response.

From: sender@example.com
Sent: Monday, January 15, 2024
To: recipient@example.com
Subject: Original Subject

Original message content here.""",
        "expected_top_contains": ["This is my response"],
        "expected_chain_contains": ["From: sender@example.com", "Original message"],
    },
    {
        "name": "No quoted content",
        "email": """This is a simple email
with no quoted content
just multiple lines.""",
        "expected_top_contains": ["simple email", "multiple lines"],
        "expected_chain_contains": [],
    },
]


def verify_split(name, email, expected_top_contains, expected_chain_contains):
    """Verify email splitting works correctly."""
    from basic.utils import split_email_chain
    
    print(f"\n{'='*60}")
    print(f"Test: {name}")
    print(f"{'='*60}")
    
    top, chain = split_email_chain(email)
    
    print(f"\n--- Top Email ({len(top)} chars) ---")
    print(top[:200] if len(top) > 200 else top)
    if len(top) > 200:
        print("... (truncated)")
    
    print(f"\n--- Email Chain ({len(chain)} chars) ---")
    print(chain[:200] if len(chain) > 200 else chain)
    if len(chain) > 200:
        print("... (truncated)")
    
    # Verify expectations
    success = True
    
    for expected in expected_top_contains:
        if expected not in top:
            print(f"\n❌ FAIL: Expected '{expected}' in top email")
            success = False
    
    for expected in expected_chain_contains:
        if expected not in chain:
            print(f"\n❌ FAIL: Expected '{expected}' in email chain")
            success = False
    
    # Check that chain is empty when no quotes expected
    if len(expected_chain_contains) == 0 and chain != "":
        print(f"\n❌ FAIL: Expected empty chain but got {len(chain)} chars")
        success = False
    
    if success:
        print(f"\n✅ PASS: {name}")
    
    return success


def main():
    """Run all verification tests."""
    print("Email Chain Splitting Verification")
    print("="*60)
    
    results = []
    for test_case in test_cases:
        result = verify_split(**test_case)
        results.append((test_case["name"], result))
    
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

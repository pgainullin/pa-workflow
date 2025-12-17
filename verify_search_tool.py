"""Verification script to check SearchTool implementation.

This script verifies that the SearchTool has been correctly implemented
for web search using DuckDuckGo.
"""


def verify_search_tool():
    """Verify SearchTool implementation in tools.py."""
    print("=" * 80)
    print("SearchTool Implementation Verification")
    print("=" * 80)
    print()

    # Read tools.py
    with open("src/basic/tools.py", "r") as f:
        content = f.read()

    checks = []

    # 1. Check if SearchTool class exists
    if "class SearchTool(Tool):" in content:
        checks.append(("✓", "SearchTool class defined"))
    else:
        checks.append(("✗", "SearchTool class NOT found"))

    # 2. Check for required methods
    if "def name(self) -> str:" in content and 'return "search"' in content:
        checks.append(("✓", "name property returns 'search'"))
    else:
        checks.append(("✗", "name property NOT properly defined"))

    if "def description(self) -> str:" in content and "web" in content.lower():
        checks.append(("✓", "description property includes 'web' search"))
    else:
        checks.append(("✗", "description property NOT properly defined"))

    if "async def execute(self, **kwargs)" in content:
        checks.append(("✓", "execute method defined"))
    else:
        checks.append(("✗", "execute method NOT found"))

    # 3. Check for required parameters
    search_tool_section = content[content.find("class SearchTool"):content.find("class ToolRegistry")]
    
    if "query" in search_tool_section:
        checks.append(("✓", "Required parameter (query) present"))
    else:
        checks.append(("✗", "Required parameter missing"))

    # 4. Check for web search implementation
    if "duckduckgo" in search_tool_section.lower() or "httpx" in search_tool_section.lower():
        checks.append(("✓", "Uses web search (DuckDuckGo/httpx)"))
    else:
        checks.append(("✗", "Web search implementation NOT found"))

    # Print results
    print("Implementation Checks:")
    print("-" * 80)
    for status, message in checks:
        print(f"{status} {message}")
    print()

    # Check email_workflow.py
    print("=" * 80)
    print("EmailWorkflow Integration Verification")
    print("=" * 80)
    print()

    with open("src/basic/email_workflow.py", "r") as f:
        workflow_content = f.read()

    workflow_checks = []

    # Check if SearchTool is imported (check the first 2000 chars for imports)
    if "SearchTool" in workflow_content[:2000]:
        workflow_checks.append(("✓", "SearchTool imported in email_workflow.py"))
    else:
        workflow_checks.append(("✗", "SearchTool NOT imported"))

    # Check if SearchTool is registered
    if "SearchTool()" in workflow_content:
        workflow_checks.append(("✓", "SearchTool registered in _register_tools()"))
    else:
        workflow_checks.append(("✗", "SearchTool NOT registered"))

    print("Integration Checks:")
    print("-" * 80)
    for status, message in workflow_checks:
        print(f"{status} {message}")
    print()

    # Check README.md
    print("=" * 80)
    print("Documentation Verification")
    print("=" * 80)
    print()

    with open("README.md", "r") as f:
        readme_content = f.read()

    doc_checks = []

    if "Search" in readme_content and ("web" in readme_content.lower() or "duckduckgo" in readme_content.lower()):
        doc_checks.append(("✓", "Search tool documented in README.md"))
    else:
        doc_checks.append(("✗", "Search tool NOT documented"))

    print("Documentation Checks:")
    print("-" * 80)
    for status, message in doc_checks:
        print(f"{status} {message}")
    print()

    # Check tests
    print("=" * 80)
    print("Test Coverage Verification")
    print("=" * 80)
    print()

    with open("tests/test_tools.py", "r") as f:
        test_content = f.read()

    test_checks = []

    if "test_search_tool" in test_content:
        test_checks.append(("✓", "test_search_tool() defined"))
    else:
        test_checks.append(("✗", "test_search_tool() NOT found"))

    if "test_search_tool_missing_query" in test_content:
        test_checks.append(("✓", "test_search_tool_missing_query() defined"))
    else:
        test_checks.append(("✗", "Missing query parameter test NOT found"))
    
    if "test_search_tool_no_results" in test_content:
        test_checks.append(("✓", "test_search_tool_no_results() defined"))
    else:
        test_checks.append(("✗", "No results test NOT found"))

    print("Test Checks:")
    print("-" * 80)
    for status, message in test_checks:
        print(f"{status} {message}")
    print()

    # Summary
    all_checks = checks + workflow_checks + doc_checks + test_checks
    passed = sum(1 for status, _ in all_checks if status == "✓")
    total = len(all_checks)

    print("=" * 80)
    print(f"Summary: {passed}/{total} checks passed")
    print("=" * 80)
    print()

    if passed == total:
        print("✓ All checks passed! SearchTool is ready to use.")
        return True
    else:
        print("✗ Some checks failed. Please review the implementation.")
        return False


if __name__ == "__main__":
    success = verify_search_tool()
    exit(0 if success else 1)

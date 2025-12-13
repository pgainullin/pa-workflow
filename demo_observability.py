#!/usr/bin/env python
"""Demo script showing Langfuse observability in action.

NOTE: This script is for development and demonstration purposes only.
      It modifies sys.path to import from the local 'src' directory.
      When the package is installed via pip, imports work normally without path manipulation.

This script demonstrates how to use the Langfuse observability integration
to trace workflow execution. It runs a simple workflow and shows how the
traces appear in Langfuse.

Prerequisites:
    1. Sign up for a free account at https://langfuse.com/
    2. Get your API keys from the Langfuse dashboard
    3. Set environment variables:
       export LANGFUSE_SECRET_KEY="sk-..."
       export LANGFUSE_PUBLIC_KEY="pk-..."
       
Usage:
    # With observability enabled (requires Langfuse keys)
    python demo_observability.py
    
    # With observability disabled
    LANGFUSE_ENABLED=false python demo_observability.py
"""

import asyncio
import os
import sys

# Add src directory to path (for development/demo purposes only)
# When installed via pip, the 'basic' module is directly importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


async def main():
    """Run a demo workflow with observability."""
    print("=" * 60)
    print("Langfuse Observability Demo")
    print("=" * 60)
    
    # Check if observability is configured
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    enabled = os.getenv("LANGFUSE_ENABLED", "true").lower() not in ("false", "0", "no")
    
    if secret_key and public_key and enabled:
        print("\n✓ Langfuse observability is ENABLED")
        print(f"  Host: {os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')}")
        print("\n  You can view traces in your Langfuse dashboard:")
        print("  https://cloud.langfuse.com/")
    else:
        print("\n✓ Langfuse observability is DISABLED")
        print("\n  To enable observability:")
        print("  1. Sign up at https://langfuse.com/")
        print("  2. Get your API keys from the dashboard")
        print("  3. Set environment variables:")
        print("     export LANGFUSE_SECRET_KEY='sk-...'")
        print("     export LANGFUSE_PUBLIC_KEY='pk-...'")
    
    print("\n" + "=" * 60)
    print("Running BasicWorkflow...")
    print("=" * 60 + "\n")
    
    # Import and run the workflow
    from basic.workflow import workflow
    
    # Run the workflow
    result = await workflow.run()
    
    print(f"\n✓ Workflow completed successfully!")
    print(f"  Result: {result}")
    
    if secret_key and public_key and enabled:
        print("\n" + "=" * 60)
        print("Check your Langfuse dashboard to see the trace!")
        print("=" * 60)
        print("\nThe trace will show:")
        print("  - Workflow execution timeline")
        print("  - Step-by-step events")
        print("  - Any LLM calls made (if applicable)")
        print("  - Execution times and metadata")


if __name__ == "__main__":
    asyncio.run(main())

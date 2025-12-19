#!/usr/bin/env python
"""Test to verify if @observe decorator is compatible with workflows library.

This test checks if the Langfuse @observe decorator interferes with
the workflows library's ability to properly route events.
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import asyncio
from workflows import Workflow, step, Context
from workflows.events import StartEvent, StopEvent, Event


# Test 1: Workflow WITHOUT @observe decorator (control)
class TestEventWithout(Event):
    data: str


class WorkflowWithoutObserve(Workflow):
    @step
    async def first_step(self, ev: StartEvent, ctx: Context) -> TestEventWithout:
        print("[WITHOUT] First step executed")
        return TestEventWithout(data="step1 complete")

    @step
    async def second_step(self, ev: TestEventWithout, ctx: Context) -> StopEvent:
        print(f"[WITHOUT] Second step executed with: {ev.data}")
        return StopEvent(result="Success without observe")


# Test 2: Workflow WITH @observe decorator (test case)
class TestEventWith(Event):
    data: str


# Try to import observe decorator
try:
    from basic.observability import observe, setup_observability
    
    # Set up observability (will be no-op if langfuse not configured)
    setup_observability(enabled=False)  # Disable to avoid needing credentials
    
    class WorkflowWithObserve(Workflow):
        @step
        @observe(name="first_step")
        async def first_step(self, ev: StartEvent, ctx: Context) -> TestEventWith:
            print("[WITH] First step executed")
            return TestEventWith(data="step1 complete")

        @step
        @observe(name="second_step")
        async def second_step(self, ev: TestEventWith, ctx: Context) -> StopEvent:
            print(f"[WITH] Second step executed with: {ev.data}")
            return StopEvent(result="Success with observe")

    OBSERVE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import observe decorator: {e}")
    WorkflowWithObserve = None
    OBSERVE_AVAILABLE = False


async def test_without_observe():
    """Test workflow without @observe decorator."""
    print("\n" + "=" * 60)
    print("TEST 1: Workflow WITHOUT @observe decorator")
    print("=" * 60)
    
    try:
        workflow = WorkflowWithoutObserve(timeout=10)
        result = await workflow.run()
        print(f"✓ Result: {result}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_with_observe():
    """Test workflow with @observe decorator."""
    print("\n" + "=" * 60)
    print("TEST 2: Workflow WITH @observe decorator")
    print("=" * 60)
    
    if not OBSERVE_AVAILABLE:
        print("⊘ Skipping - observe decorator not available")
        return None
    
    try:
        workflow = WorkflowWithObserve(timeout=10)
        result = await workflow.run()
        print(f"✓ Result: {result}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\nTesting @observe decorator compatibility with workflows library")
    print("=" * 60)
    
    # Test without observe
    result1 = await test_without_observe()
    
    # Test with observe
    result2 = await test_with_observe()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Without @observe: {'PASS' if result1 else 'FAIL'}")
    if result2 is not None:
        print(f"With @observe:    {'PASS' if result2 else 'FAIL'}")
        
        if result1 and not result2:
            print("\n⚠ ISSUE DETECTED: @observe decorator breaks workflow execution!")
        elif result1 and result2:
            print("\n✓ @observe decorator is compatible with workflows")
    else:
        print(f"With @observe:    SKIPPED")
    
    return result1 and (result2 if result2 is not None else True)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

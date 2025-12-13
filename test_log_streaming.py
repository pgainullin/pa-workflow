#!/usr/bin/env python3
"""Test script to demonstrate workflow log streaming to Langfuse."""

import logging
import os
import sys

sys.path.insert(0, 'src')

# Configure test credentials (use your real credentials to see logs in Langfuse)
os.environ['LANGFUSE_SECRET_KEY'] = os.getenv('LANGFUSE_SECRET_KEY', 'sk-test-key')
os.environ['LANGFUSE_PUBLIC_KEY'] = os.getenv('LANGFUSE_PUBLIC_KEY', 'pk-test-key')
os.environ['LANGFUSE_HOST'] = os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')

# Import observability to enable log streaming
from basic import observability

# Get a workflow logger
logger = logging.getLogger('basic.email_workflow')

print("=" * 60)
print("Testing Log Streaming to Langfuse")
print("=" * 60)
print()

# Test different log levels
logger.info("Starting workflow execution")
logger.info("Processing step 1: Triage")
logger.warning("API rate limit approaching")
logger.info("Processing step 2: Execution")
logger.info("Processing step 3: Verification")

try:
    # Simulate an error
    raise ValueError("Simulated error for testing")
except Exception as e:
    logger.error(f"Error occurred: {e}", exc_info=True)

logger.info("Workflow execution completed")

print()
print("=" * 60)
print("✓ Log messages sent to Langfuse")
print("  Check your Langfuse dashboard to see the logs")
print("=" * 60)

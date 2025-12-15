"""Workflow server using WorkflowServer from workflows.server.

This module starts the workflow server that exposes the email workflow
via the predefined LlamaCloud API endpoints.

Usage:
    Run directly: python -m workflow.server
    Or use llamactl: llamactl serve
"""

import asyncio
import atexit
import logging
import signal

from workflows.server import WorkflowServer

from basic.email_workflow import email_workflow
from basic.observability import flush_langfuse
from basic.workflow import workflow as basic_workflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the workflow server
server = WorkflowServer()

# Register the email workflow
server.add_workflow("email", email_workflow)

# Register the BasicWorkflow
server.add_workflow("BasicWorkflow", basic_workflow)


def shutdown_handler():
    """Flush Langfuse traces on server shutdown."""
    logger.info("Server shutting down, flushing Langfuse traces...")
    flush_langfuse()
    logger.info("Langfuse traces flushed")


# Register shutdown handler
atexit.register(shutdown_handler)


async def main():
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler(sig):
        logger.info(f"Received signal {sig}, shutting down...")
        flush_langfuse()
        loop.stop()

    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

    try:
        await server.serve(host="127.0.0.1", port=8080)
    finally:
        # Ensure flush on exit
        flush_langfuse()


# def main() -> None:
#     """Start the workflow server."""
#     logger.info("Starting workflow server...")
#     server.start()


if __name__ == "__main__":
    asyncio.run(main())

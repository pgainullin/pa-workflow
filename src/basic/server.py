"""Workflow server using WorkflowServer from workflows.server.

This module starts the workflow server that exposes the email workflow
via the predefined LlamaCloud API endpoints.

Usage:
    Run directly: python -m workflow.server
    Or use llamactl: llamactl serve
"""

import logging

from workflows.server import WorkflowServer

from pa_workflow.email_workflow import email_workflow
from pa_workflow.workflow import workflow as basic_workflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the workflow server
server = WorkflowServer()

# Register the email workflow
server.add_workflow("email", email_workflow)

# Register the BasicWorkflow
server.add_workflow("BasicWorkflow", basic_workflow)


def main() -> None:
    """Start the workflow server."""
    logger.info("Starting workflow server...")
    server.start()


if __name__ == "__main__":
    main()

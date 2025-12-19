from workflows import Workflow, step, Context
from workflows.events import StartEvent, StopEvent, Event
import asyncio

from basic.observability import (
    flush_langfuse,
    setup_observability,
)  # Import flush and setup for tracing


class Start(StartEvent):
    pass


class Hello(Event):
    message: str


class BasicWorkflow(Workflow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set up observability (Langfuse tracing) after environment is loaded
        # This ensures credentials from .env files are available when running in LlamaCloud
        setup_observability()

    @step
    async def hello(self, event: Start, context: Context) -> StopEvent:
        context.write_event_to_stream(
            Hello(message="🦙 Hello from the basic template.")
        )
        await asyncio.sleep(0)
        result = StopEvent(result=("Edit src/basic/workflow.py to get started."))
        flush_langfuse()  # Flush traces after step completion
        return result


workflow = BasicWorkflow(timeout=None)


if __name__ == "__main__":

    async def main() -> None:
        print(await BasicWorkflow().run())

    asyncio.run(main())

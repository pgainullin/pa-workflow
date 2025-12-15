from workflows import Workflow, step, Context
from workflows.events import StartEvent, StopEvent, Event
import asyncio

from basic import observability  # noqa: F401 - Import for side effect: enables Langfuse tracing
from basic.observability import (
    observe,
    flush_langfuse,
)  # Import observe decorator and flush for tracing


class Start(StartEvent):
    pass


class Hello(Event):
    message: str


class BasicWorkflow(Workflow):
    @step
    @observe(name="hello")
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

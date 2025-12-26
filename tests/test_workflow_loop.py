import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from workflows import Context
from src.basic.email_workflow import EmailWorkflow, TriageEvent, PlanExecutionEvent
from src.basic.models import EmailData, CallbackConfig

@pytest.mark.asyncio
async def test_workflow_foreach_loop():
    # Mock dependencies
    with patch("src.basic.email_workflow.setup_observability"), \
         patch("src.basic.email_workflow.flush_langfuse"), \
         patch("src.basic.email_workflow.resolve_params") as mock_resolve:
        
        workflow = EmailWorkflow()
        workflow.tool_registry = MagicMock()
        
        # Mock SearchTool
        mock_tool = AsyncMock()
        mock_tool.execute.side_effect = lambda query: {"success": True, "result": f"Result for {query}"}
        workflow.tool_registry.get_tool.return_value = mock_tool
        
        # Mock resolve_params behavior
        def resolve_side_effect(params, context, email_data):
            if "items" in params: # Resolving foreach
                return {"items": ["apple", "banana"]}
            if "query" in params: # Resolving tool params
                # Verify 'item' is in context
                item = context.get("item")
                return {"query": item}
            return params
            
        mock_resolve.side_effect = resolve_side_effect
        
        # Define Plan
        plan = [
            {
                "tool": "search",
                "foreach": "{{step_0.items}}", # Mock ref
                "params": {"query": "{{item}}"},
                "description": "Search for fruits"
            }
        ]
        
        email_data = EmailData(from_email="test@test.com", subject="Test", body="Body")
        callback = CallbackConfig(callback_url="http://cb", auth_token="token")
        
        ev = TriageEvent(plan=plan, email_data=email_data, callback=callback)
        ctx = MagicMock(spec=Context)
        
        # Execute
        result_event = await workflow.execute_plan(ev, ctx)
        
        # Verify
        assert isinstance(result_event, PlanExecutionEvent)
        results = result_event.results
        
        # Should have 2 results (one for apple, one for banana)
        assert len(results) == 2
        assert results[0]["step"] == "1.1"
        assert results[0]["result"] == "Result for apple"
        assert results[1]["step"] == "1.2"
        assert results[1]["result"] == "Result for banana"
        
        # Verify tool calls
        assert mock_tool.execute.call_count == 2
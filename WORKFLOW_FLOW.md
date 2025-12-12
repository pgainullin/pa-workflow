# Email Workflow Visualization

## Workflow Event Flow

```
┌─────────────────────┐
│  EmailStartEvent    │
│                     │
│ - email_data        │
│ - callback          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   triage_email      │ [TRIAGE START/COMPLETE]
│                     │
│ Analyzes email      │
│ Creates plan        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   TriageEvent       │
│                     │
│ - plan              │
│ - email_data        │
│ - callback          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   execute_plan      │ [PLAN EXEC START/COMPLETE]
│                     │
│ Executes tools      │
│ Collects results    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ PlanExecutionEvent  │
│                     │
│ - results           │
│ - email_data        │
│ - callback          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  verify_response    │ [VERIFY START/COMPLETE] ⭐ NEW
│                     │
│ Generates response  │
│ LLM verification    │
│ Applies best        │
│ practices           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ VerificationEvent   │ ⭐ NEW
│                     │
│ - verified_response │
│ - results           │
│ - email_data        │
│ - callback          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   send_results      │ [SEND RESULTS START/COMPLETE]
│                     │
│ Creates email       │
│ Sends via callback  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│     StopEvent       │
│                     │
│ - result            │
└─────────────────────┘
```

## Best Practices Flow

The RESPONSE_BEST_PRACTICES constant is used in three places:

```
RESPONSE_BEST_PRACTICES
         │
         ├──> _build_triage_prompt
         │    (Guides plan creation)
         │
         ├──> verify_response
         │    (Verifies response quality)
         │
         └──> _generate_user_response
              (Guides initial response generation)
```

## Best Practices Checklist

✅ **1. Direct Responses**
   - No unnecessary preambles
   - Get straight to the point

✅ **2. No Internal Comments**
   - Avoid: "Here is the draft response"
   - Avoid: "I will now..."

✅ **3. Clear Status Communication**
   - Explicitly state if request couldn't be completed
   - Don't leave users guessing

✅ **4. Follow-up Suggestions**
   - Consider next steps
   - Mention them when relevant

✅ **5. Source References**
   - Reference files/documents processed
   - Point to execution log when needed

## Error Handling in verify_response

```
verify_response (outer try-catch)
    │
    ├─> Generate initial response
    │
    ├─> Build verification prompt
    │
    └─> Verify with LLM (inner try-catch)
        │
        ├─> Success: Use verified response
        │
        ├─> Empty/short: Use original response
        │
        └─> Exception: Use original response

Fallback on outer exception:
    └─> Try to generate initial response
        ├─> Success: Use it
        └─> Exception: Use generic message
```

## Timeout Handling

All workflow steps handle `asyncio.TimeoutError` explicitly:

1. **triage_email**: Returns fallback plan
2. **execute_plan**: Returns error result
3. **verify_response**: Returns original response ⭐ NEW
4. **send_results**: Returns failure result

Workflow timeout is 120 seconds to accommodate:
- Parse tool retries (5 attempts × ~15s max)
- LLM API calls
- Verification step ⭐ NEW

Updated todo list

Read 

Read 

A filter is not called by the model. It runs after each response and looks for a tag in the model's output. So you need to instruct the model, through the system prompt, to emit that exact tag.

**1. Enable the filter**
- In Admin Panel → Functions, turn the filter on.
- Set it **Global**, or attach it to the specific model in Workspace → Models → Filters.
- Set the `api_token` valve to the gateway's token.

**2. Add this to the model's system prompt** (Workspace → Models → edit → System Prompt):

```
When you have finished evaluating the student's work and decided the final grade,
end your reply with exactly one tag in this format, on its own line:

<grade score="X" max="Y"/>

Rules:
- X and Y are integers (for example: <grade score="8" max="10"/>).
- Emit the tag only once, when the final grade is decided. Never emit it for partial or tentative grades.
- Do not mention, explain, or wrap the tag in code blocks. It is removed automatically before the student sees it.
- Also state the grade and feedback in normal text before the tag.
```

**Constraints from the filter code**
- The regex requires double quotes and integers only, with `<grade score="N" max="N"/>`. Decimals such as `7.5` won't match.
- It inspects only the last message, so the tag must be in the final reply.
- It posts `chat_id` plus the scores to `gateway_url`. The default `http://lti-gateway:8090/api/scores` only works if OpenWebUI shares a Docker network with the gateway.

**Optional hardening:** if you need decimal grades, change the regex to `(\d+(?:\.\d+)?)`. The `requests.post` is also uncaught, so a gateway failure would break the chat response. Wrap it in `try/except` if you want it to fail quietly.
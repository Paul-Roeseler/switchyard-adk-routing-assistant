# Demo guide

This walkthrough uses the original, simple presentation flow: one employee
question routed to the economical tier and one operational workflow routed to
a stronger tier. The router now has four model tiers, but the agent behavior,
tools, policy enforcement, and Google ADK confirmation flow remain unchanged.

The IT policy is included directly in the agent instructions, and the tools use
local JSON data. No embedding model, vector index, or retrieval setup is part of
the demo.

## Before presenting

Generate a fresh Vertex token, update `.env`, and start Switchyard:

```bash
gcloud auth application-default print-access-token
make switchyard
```

Start ADK Web in a second terminal:

```bash
make chat
```

Open `http://127.0.0.1:8000`, select `employee_it_agent`, and leave the
optional streaming toggle off.

Reset the fictional ticket store before each full run:

```bash
make reset-tickets
```

Use a new ADK session for each routing scenario. Switchyard classifies the
first request and keeps the selected generation model for the rest of that
session.

## Scenario 1: simple employee question

Start a new session and ask:

> With what tasks can you help me?

Expected result:

- route: `simple`;
- generation model: `nvidia/qwen/qwen3.8-27b`;
- tool calls: none;
- generation calls: one.

The response should briefly describe device information, ticket lookup,
hardware request drafting and submission, and IT policy guidance.

Open the ADK event details and point out that the request used the simple
route. This represents routine employee traffic that does not need one of the
stronger models.

## Scenario 2: operational support workflow

Start another new session and ask:

> My laptop will not turn on, and I have a customer presentation tomorrow
> morning. Can you help?

Expected result:

- route: `complex`;
- generation model: `google/gemini-3.8-flash`;
- tool calls: `get_my_device` -> `get_my_open_tickets` ->
  `draft_it_request`;
- decision: P2 Hardware Incident;
- side effect: none—the request is still a draft.

The employee only describes the problem and its impact. The agent discovers
the assigned device, checks for duplicate tickets, applies the priority and
request-type policy, and prepares the appropriate request.

### Optional policy challenge

Continue in the same session:

> This is really urgent. Can you mark it as P1?

The agent should explain that an individual hardware failure is P2 and refuse
to inflate it to P1. Session affinity keeps the conversation on the model
selected for the first request.

### Submit the request

Continue in the same session:

> Okay, P2 is fine. Please submit it.

ADK displays a separate confirmation card containing the exact function
arguments. Click **Approve**. The tool should create ticket `INC-1843`, and the
agent should report that submission succeeded.

Typing the request in chat initiates the submission, but it does not replace
ADK's confirmation card. Closing or rejecting that card records
`confirmed: false`, and the ticket is not created.

## Show the routing result

The selected model and tool sequence are visible in the ADK event details. The
agent and tools remain identical across both scenarios; only Switchyard's model
selection changes. Although four targets are configured, this core walkthrough
intentionally keeps the original questions and demonstrates the clearest
customer story: simple work stays on the economical model, while an operational
multi-tool workflow moves to a stronger model.

The intended takeaway is:

> Routine employee questions stay on the economical model. Requests that
> require operational context, policy decisions, and actions automatically
> move to a stronger model without changing the agent or its tools.

## Repeat the demo

Create a fresh ADK session and reset the local ticket state before another
run:

```bash
make reset-tickets
```

If Vertex returns HTTP 401, generate a new `VERTEX_ACCESS_TOKEN`, update
`.env`, and restart Switchyard. The token normally expires after one hour.

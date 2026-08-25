# Demo guide

This walkthrough demonstrates one simple employee question routed to the
lower-cost model and one operational workflow routed to the stronger model.
It also shows multi-step tool use, session affinity, policy enforcement, and
Google ADK's standard confirmation control.

## Before presenting

Generate a fresh Vertex token, update `.env`, and restart Switchyard:

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

Reset the fictional ticket store and Switchyard statistics before each full
run:

```bash
make reset-tickets
curl -X POST http://127.0.0.1:4000/v1/stats/reset
```

Use a new ADK session for each routing scenario. Switchyard classifies the
first request and keeps the selected generation model for the rest of that
session.

## Scenario 1: simple employee question

Start a new session and ask:

> With what tasks can you help me?

Expected result:

- classifier: `gcp/google/gemini-3.6-flash`;
- generation model: `nvidia/zai-org/glm-5.2`;
- tool calls: none;
- generation calls: one.

The response should briefly describe device information, ticket lookup,
hardware request drafting and submission, and IT policy guidance.

Open the ADK event details and point out that the recorded model is GLM-5.2.
This represents routine employee traffic that does not need the stronger
model.

## Scenario 2: operational support workflow

Start another new session and ask:

> My laptop will not turn on, and I have a customer presentation tomorrow
> morning. Can you help?

Expected result:

- classifier: `gcp/google/gemini-3.6-flash`;
- generation model: `google/gemini-3.1-pro-preview`;
- tool calls: `get_my_device` -> `get_my_open_tickets` ->
  `draft_it_request`;
- generation calls: three;
- decision: P2 Hardware Incident;
- side effect: none—the request is still a draft.

The employee only describes the problem and its impact. The agent discovers
the assigned device, checks for duplicate tickets, applies the priority and
request-type policy, and prepares the appropriate request.

### Optional policy challenge

Continue in the same session:

> This is really urgent. Can you mark it as P1?

The agent should explain that an individual hardware failure is P2 and refuse
to inflate it to P1. The conversation remains on Gemini Pro because of session
affinity.

### Submit the request

Continue in the same session:

> Okay, P2 is fine. Please submit it.

ADK displays a separate confirmation card containing the exact function
arguments. Click **Approve**. The tool should create ticket `INC-1843` and the
agent should report that submission succeeded.

Typing the request in chat initiates the submission, but it does not replace
ADK's confirmation card. Closing or rejecting that card records
`confirmed: false`, and the ticket is not created.

## Show the routing result

The selected model and tool sequence are visible in the ADK event details.
Switchyard also exposes aggregate model, tier, token, and latency statistics:

```bash
curl -s http://127.0.0.1:4000/v1/stats | python3 -m json.tool
```

One complex user request produces several strong-model calls because ADK runs
the model again after each tool result. The statistics count those model calls,
not only the number of user messages.

The intended takeaway is:

> Routine employee questions stay on the lower-cost model. Requests that
> require operational context, policy decisions, and actions automatically
> move to the stronger model without changing the agent or its tools.

## Repeat the demo

Create a fresh ADK session and reset the local ticket state before another
run:

```bash
make reset-tickets
```

If Vertex returns HTTP 401, generate a new `VERTEX_ACCESS_TOKEN`, update
`.env`, and restart Switchyard. The token normally expires after one hour.

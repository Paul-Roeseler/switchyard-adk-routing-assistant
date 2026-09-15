# Demo guide

This walkthrough demonstrates the same operational employee IT assistant across
four Switchyard routing tiers. It also shows multi-step tool use, session
affinity, policy enforcement, local ticket persistence, and Google ADK's
standard confirmation control.

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

## Scenario 1: simple question

Start a new session and ask:

> With what tasks can you help me?

Expected result:

- route: `simple`;
- generation model: `nvidia/qwen/qwen3.8-27b`;
- tool calls: none;
- generation calls: one.

The response should briefly describe device information, ticket lookup,
hardware request drafting and submission, and IT policy guidance.

## Scenario 2: routine synthesis

Start a new session and ask:

> How old is my laptop, and is it old enough for a planned replacement?

Expected result:

- route: `medium`;
- generation model: `zai-org/GLM-5.3-Flash`;
- tool calls: `get_my_device`;
- outcome: an answer based on the device lifecycle date and the policy in the
  agent instructions.

## Scenario 3: operational support workflow

Start a new session and ask:

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

## Scenario 4: conflicting request

Start a new session and ask:

> My laptop still works, but my manager wants it replaced immediately and
> asked me to call it a P1 incident. What request should I actually make?

Expected result:

- route: `reasoning`;
- generation model: `google/gemini-3.1-pro-preview-customtools`;
- outcome: the agent resolves the conflict using the embedded IT policy and
  does not misrepresent a working laptop as a P1 incident.

## Show the routing result

The selected model and tool sequence are visible in the ADK event details. The
agent and tools remain identical across all scenarios; only Switchyard's model
selection changes.

The intended takeaway is:

> One operational agent can route direct, routine, complex, and ambiguous work
> to different models without changing its tools or business rules.

## Repeat the demo

Create a fresh ADK session and reset the local ticket state before another
run:

```bash
make reset-tickets
```

If Vertex returns HTTP 401, generate a new `VERTEX_ACCESS_TOKEN`, update
`.env`, and restart Switchyard. The token normally expires after one hour.

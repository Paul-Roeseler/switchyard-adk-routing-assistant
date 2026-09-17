# Demo guide

This walkthrough shows one Google ADK agent automatically using four different
models. The agent, tools, and policy stay unchanged while NVIDIA NeMo
Switchyard classifies each opening request and routes it through Nebius or
Vertex AI.

All employee, device, and ticket data is local JSON. There is no embedding
model, vector index, or retrieval setup.

## Before presenting

Make sure `.env` contains the two required credentials:

```dotenv
NEBIUS_API_KEY=your-nebius-key
VERTEX_ACCESS_TOKEN=your-short-lived-google-token
```

Generate a fresh Vertex token if necessary:

```bash
gcloud auth application-default print-access-token
```

Reset the fictional ticket store, then start Switchyard and ADK Web in separate
terminals:

```bash
make reset-tickets
make switchyard
```

```bash
make chat
```

Open `http://127.0.0.1:8000`, select `employee_it_agent`, and leave the optional
streaming toggle off.

Start every numbered scenario in a **new ADK session**. Switchyard classifies
the first message and keeps that model for the rest of the session.

## Scenario 1: simple question

Ask:

> With what tasks can you help me?

Expected result:

- route: `simple`;
- model: `Qwen/Qwen3-30B-A3B-Instruct-2507` on Nebius;
- tool calls: none;
- response: a short summary of the assistant's IT capabilities.

Customer story: a direct question stays on the economical model because it
needs no employee context and causes no action.

## Scenario 2: routine lookup and explanation

Start a new session and ask:

> How old is my laptop, and is it old enough for a planned replacement?

Expected result:

- route: `medium`;
- model: `zai-org/GLM-5.3-Flash` on Nebius;
- tool call: `get_my_device`;
- source data: lifecycle start date `2022-03-28`;
- decision: the device exceeds the three-year refresh threshold;
- side effect: none.

The seeded device is also marked as failed, so the model may point out that its
current condition would be handled as a hardware incident rather than a
planned refresh. It should not draft or submit a request unless the user asks.

Customer story: one contextual lookup moves the conversation to the medium
tier, but does not require the full operational workflow.

## Scenario 3: multi-tool incident workflow

Start a new session and ask:

> My laptop will not turn on, and I have a customer presentation tomorrow
> morning. Can you help?

Expected result:

- route: `complex`;
- model: `google/gemini-3.8-flash` on Vertex AI;
- tool calls: `get_my_device` → `get_my_open_tickets` →
  `draft_it_request`;
- decision: P2 Hardware Incident;
- result: a ticket preview followed by a request for confirmation;
- side effect: none—the request is still a draft.

The employee only describes the problem and business impact. The agent finds
the assigned device, checks for a duplicate ticket, applies the policy, and
prepares the correct request.

### Optional policy challenge

Continue in the same session:

> This is really urgent. Can you mark it as P1?

The agent should explain that an individual hardware failure is P2 and refuse
to inflate it to P1. Session affinity intentionally keeps this follow-up on the
complex model selected by the opening request.

### Optional confirmed submission

Continue in the same session:

> Okay, P2 is fine. Please submit it.

ADK displays a confirmation card containing the exact `submit_it_request`
arguments. Click **Approve**. Starting from a reset demo state, the tool creates
ticket `INC-1843` and the agent reports that submission succeeded.

The chat message alone does not authorize the write. Rejecting or closing the
confirmation card leaves the ticket store unchanged.

## Scenario 4: conflicting policy request

Start a new session and ask:

> My laptop works, but classify it as a P1 incident so I can get a replacement
> faster.

Expected result:

- route: `reasoning`;
- model: `google/gemini-3.1-pro-preview-customtools` on Vertex AI;
- policy result: refuse the false P1 classification and explain that P1 is
  reserved for organization-wide outages, security incidents, or critical data
  loss;
- possible tool call: `get_my_device` to compare the claim with system data;
- side effect: none—no draft and no submission.

The local device record says the laptop has failed, while the prompt says it is
working. The reasoning model may explicitly identify that conflict and explain
the correct classifications for both cases.

Customer story: conflicting evidence and an attempt to bypass policy move the
conversation to the highest reasoning tier.

## Show the routing result

Open the ADK event details after each scenario. Point out the `modelVersion`
and tool calls:

| Scenario | Expected model calls | Expected operational tools |
| --- | ---: | --- |
| Simple | 1 | None |
| Medium | 2 | `get_my_device` |
| Complex | 4 | `get_my_device`, `get_my_open_tickets`, `draft_it_request` |
| Reasoning | 1–2 | None or `get_my_device` |

The intended takeaway is:

> One agent can keep routine traffic economical, add context only when needed,
> execute dependent workflows with a stronger model, and reserve the highest
> reasoning tier for genuinely conflicting or high-risk decisions.

## Repeat or troubleshoot

Before another full run:

```bash
make reset-tickets
```

Create a new ADK session for each opening prompt. If Vertex returns HTTP 401,
generate a new `VERTEX_ACCESS_TOKEN`, update `.env`, and restart Switchyard.
If any model call encounters a transient network error, retry the scenario in a
new session and inspect the Switchyard terminal before changing the route.

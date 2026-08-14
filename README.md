# Employee IT assistant prototype

This is a small Google ADK agent for one fictional employee. It answers IT
policy questions, combines policy with current device and ticket data, and can
prepare a support-request draft through a multi-step tool loop.

```text
ADK Web + SQLite session history
             |
             v
      knowledge_agent
       |           |
       |           +-- model calls --> Switchyard llm_classifier
       |                                |-- simple --> GLM-5.2
       |                                `-- other  --> Gemini 3.6 Flash
       |
       +-- search_it_kb --> Vertex AI embedding --> local document index
       +-- get_my_device -------------------------> local demo JSON
       +-- get_my_open_tickets -------------------> local demo JSON
       `-- draft_it_request ----------------------> preview only
```

## What is implemented

The ADK root agent is in [`knowledge_agent/agent.py`](knowledge_agent/agent.py).
It is intentionally just an instruction, one routed model, and four Python
tools. ADK owns the agent loop: after each tool result, the model can make the
next dependent tool call or produce the final answer.

Conversation memory is ADK session history. `include_contents="default"`
includes prior messages and tool results on later turns, while the development
server stores sessions in `.adk/sessions.db`. Continue in the same Web session
to test a follow-up such as “What asset tag did you find?” This is not
cross-session semantic memory.

[`config/routes.yaml`](config/routes.yaml) defines one Switchyard
`llm_classifier` route named `employee-it` (the installed server implements
this as its deterministic classifier strategy):

- simple requests use `nvidia/zai-org/glm-5.2` on NVIDIA Inference Hub;
- medium, complex, and reasoning requests use `gemini-3.6-flash` through the
  Gemini Developer API's OpenAI-compatible endpoint;
- classifier or provider errors propagate; LiteLLM retries are disabled;
- session affinity keeps a multi-step tool loop on one selected model.

Switchyard requires a target for a context-window overflow eviction. That is
the only configured retry path; there is no quota, authentication, or service
fallback in this prototype.

## Data

The knowledge base contains two unmodified documents from NVIDIA's Build an
Agent workshop:

- `hardware-refresh.md`
- `help-and-support.md`

They are pinned to revision
`ac389a0ce6452d4b69af73f75806543fdc652b95`. See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for attribution and license
details.

[`data/employee_it.json`](data/employee_it.json) contains one fictional
employee, one failed laptop, and one unrelated open software ticket. It is not
NVIDIA or L'Oréal data.

The two documents are split into 17 sections and embedded with Vertex AI
`gemini-embedding-2` at 768 dimensions. The generated local index is
`data/embeddings.json`.

## Setup

Vertex embeddings use Application Default Credentials. Generation uses the two
API keys in `.env`.

```bash
gcloud config set project model-routing-505414
gcloud auth application-default login
gcloud auth application-default set-quota-project model-routing-505414

cp .env.example .env  # only when .env does not already exist
# Add GOOGLE_API and INFERENCE_HUB_API to .env.

make setup
make embed             # only needed to create or rebuild the document index
```

Start the two local processes in separate terminals:

```bash
make switchyard
```

```bash
make chat
```

Then open `http://127.0.0.1:8000` and select `knowledge_agent`. Both servers bind
to localhost and are development-only. Leave ADK Web's optional streaming
toggle off (the default); the current streaming reconstruction does not retain
Gemini's tool signature across a multi-step call.

## Demo questions

Use a fresh ADK session for each independent difficulty example. Switchyard
pins the first model selected for a session so all calls in that tool loop stay
on the same provider.

### Simple: policy only

> How long do I have to return my old laptop after a hardware refresh?

Expected tool path: `search_it_kb`.

### Medium: policy plus device data

> Is my assigned laptop eligible for a hardware refresh, and what information
> do I need to submit?

Expected tool path: `get_my_device` and `search_it_kb`.

In the same session, ask “What asset tag and lifecycle date did you find?” to
demonstrate conversational memory.

### Hard: dependent multi-step workflow

> My laptop will not power on and I need it for work today. Check my device and
> open tickets, decide whether this should be a refresh request or an incident,
> assign the correct priority, and draft the request without creating a
> duplicate.

Expected path: `get_my_device` -> `search_it_kb` ->
`get_my_open_tickets` -> `draft_it_request`.

The grounded result should be a P2 Hardware Incident. The existing Software
ticket is unrelated, and the draft tool returns `submitted: false`.

Switchyard's routing counters are available while it runs:

```bash
curl -s http://127.0.0.1:4000/v1/stats | python3 -m json.tool
```

The actual tool order is chosen by the model and is visible in the ADK trace.

# Switchyard ADK routing assistant

A minimal Google ADK employee IT assistant that demonstrates cost-aware model
routing with NVIDIA NeMo Switchyard. Simple requests use a lower-cost model;
complex requests use a stronger model and can complete a confirmed multi-step
ticket workflow.

```text
ADK Web + SQLite conversation history
              |
              v
     employee_it_agent
        |           |
        |           `-- model calls --> Switchyard llm_classifier
        |                                |-- classifier --> Gemini 3.6 Flash
        |                                |-- simple -----> GLM-5.2
        |                                `-- complex ----> Gemini 3.1 Pro
        |
        +-- get_my_device -------------------------> local demo JSON
        +-- get_my_open_tickets -------------------> local demo JSON
        +-- draft_it_request ----------------------> preview only
        `-- submit_it_request --> ADK confirmation --> local ticket store
```

The few IT rules required by the demo are written directly in the agent
instruction. There is no RAG pipeline, embedding model, vector database, or
custom routing implementation.

## Quick start

Create `.env` and add the two provider credentials and your Google Cloud
project:

```bash
cp .env.example .env
gcloud auth application-default login
gcloud auth application-default print-access-token
```

Paste the generated token and your other values into `.env`:

```dotenv
VERTEX_ACCESS_TOKEN=your-short-lived-token
INFERENCE_HUB_API=your-nvidia-key
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
```

Then install and test the demo:

```bash
make setup
make test
```

Start the two local processes in separate terminals:

```bash
make switchyard
```

```bash
make chat
```

Open `http://127.0.0.1:8000` and select `employee_it_agent`. Both servers bind
to localhost and are development-only. Leave ADK Web's optional streaming
toggle off; its current stream reconstruction does not retain Gemini tool
signatures across multi-step calls.

`VERTEX_ACCESS_TOKEN` normally expires after one hour. Generate a new value,
update `.env`, and restart Switchyard when it expires.

## Demo flow

Use a fresh ADK session for each routing example. Switchyard keeps the model it
selects for the first request throughout that conversation.

### Simple request

> Which laptop is assigned to me?

Expected tool path: `get_my_device`. This should route to the weak model.

### Complex one-turn request

> My laptop will not power on and I need it for a customer presentation
> tomorrow. Check my device and open tickets, decide whether this is a refresh
> or incident, assign the correct priority, and prepare the request without
> creating a duplicate.

Expected tool path: `get_my_device` -> `get_my_open_tickets` ->
`draft_it_request`. This should route to the strong model.

The result should be a P2 Hardware Incident. The existing Software ticket is
unrelated, and the draft returns `submitted: false`.

Then ask:

> Submit that ticket.

ADK Web shows a confirmation dialog with the exact tool arguments before any
write occurs. Approving it calls `submit_it_request`, creates a local ticket,
and returns its ID. Run `make reset-tickets` before repeating the demo.

## Agent and tools

[`employee_it_agent/agent.py`](employee_it_agent/agent.py) defines one ADK
agent and its small IT policy. It has four Python tools from
[`employee_it_agent/tools.py`](employee_it_agent/tools.py):

- `get_my_device` reads the current employee's device;
- `get_my_open_tickets` checks unresolved requests;
- `draft_it_request` prepares a side-effect-free preview;
- `submit_it_request` writes the approved ticket to the local demo store.

ADK owns the multi-step tool loop. The submission tool uses ADK's native
`require_confirmation` control, so approval is enforced by ADK rather than by
the selected model's prompt alone.

Conversation memory is ADK session history. `include_contents="default"`
includes previous messages and tool results, and the development server stores
sessions in `.adk/sessions.db`. This is not cross-session semantic memory.

The agent calls the fixed local endpoint `http://127.0.0.1:4000/v1`.
`switchyard.yaml` only describes Switchyard's outbound provider connections.

## Switchyard routing

[`switchyard.yaml`](switchyard.yaml) uses Switchyard's stock `llm_classifier`
route:

- classifier: `gcp/google/gemini-3.6-flash` through NVIDIA Inference Hub;
- weak/simple target: `nvidia/zai-org/glm-5.2` through Inference Hub;
- strong target: `google/gemini-3.1-pro-preview` through Google Cloud Vertex AI.

The packaged `general` profile sends SIMPLE requests to the weak target and
MEDIUM, COMPLEX, and REASONING requests to the strong target. A valid
abstention or a result below the confidence threshold also selects the strong
target. Provider failures propagate because `fail_open` is disabled.

Session affinity keeps every model call in one ADK tool loop on the model
selected for its first request. Restarting Switchyard clears that affinity.

The YAML contains a commented Claude Opus replacement for the strong target.
To demonstrate a provider change, comment the Gemini Pro block, uncomment the
Opus block, and restart Switchyard.

## Credentials and portability

| Purpose | Credential |
| --- | --- |
| Classifier, GLM-5.2, optional Claude Opus | `INFERENCE_HUB_API` |
| Gemini 3.1 Pro | `VERTEX_ACCESS_TOKEN` plus `GOOGLE_CLOUD_PROJECT` |

Changing a generation provider only requires editing the model, base URL, and
key in `switchyard.yaml`; the ADK agent and tools stay unchanged. Replacement
models must support the OpenAI-compatible message and tool-call format. The
classifier must also support Switchyard's structured classification request.

The two local servers have no inbound authentication and must not be exposed
directly to a network. A deployed version should use workload identity or a
token-refreshing gateway instead of the manually refreshed Vertex token.

## Demo data

[`data/employee_it.json`](data/employee_it.json) contains one fictional
employee, one failed laptop, and one unrelated open software ticket. It is not
NVIDIA or customer data. Submitted tickets are written to the ignored runtime
copy `.adk/employee_it.json`, leaving the tracked seed unchanged.

The project is licensed under Apache-2.0; see [`LICENSE`](LICENSE).

## Inspect routing

Switchyard exposes request, token, tier, and latency counters:

```bash
curl -s http://127.0.0.1:4000/v1/stats | python3 -m json.tool
```

The actual tool order appears in the ADK trace. The Switchyard terminal also
prints `classifier_signals=...` for each newly classified conversation.

# Switchyard ADK routing assistant

A small Google ADK employee IT assistant that demonstrates capability-tier
routing across four models with NVIDIA NeMo Switchyard. The routing layer is
one native Switchyard v0.2 TOML file; there is no custom Switchyard server or
runtime code.

```text
ADK Web + SQLite session history
             |
             v
    employee_it_agent
       |           |
       |           +-- model calls --> switchyard-server v0.2
       |                                |-- simple    --> Llama 3.1 8B
       |                                |-- medium    --> GLM-5.2
       |                                |-- complex   --> Gemini 3.6 Flash
       |                                `-- reasoning --> Gemini 3.1 Pro
       |
       +-- search_it_kb --> Vertex AI embedding --> local document index
       +-- get_my_device -------------------------> local demo JSON
       +-- get_my_open_tickets -------------------> local demo JSON
       `-- draft_it_request ----------------------> preview only
```

Relay is intentionally not part of this demo. ADK calls Switchyard's native
OpenAI-compatible endpoint directly.

## Quick start

You need Python 3.12 or 3.13, `uv`, Rust/Cargo 1.96.1 or newer, and the Google
Cloud CLI. Vertex embeddings use Application Default Credentials. Model
generation uses a short-lived Vertex OAuth token and the NVIDIA API key in
`.env`.

```bash
gcloud config set project model-routing-505414
gcloud auth application-default login
gcloud auth application-default set-quota-project model-routing-505414

cp .env.example .env  # only when .env does not already exist
# Add VERTEX_ACCESS_TOKEN and INFERENCE_HUB_API to .env.
# Generate the Vertex token immediately before the demo and paste it into .env:
gcloud auth application-default print-access-token

make setup             # installs Python deps and switchyard-server 0.2.0
make embed             # creates or rebuilds the local document index
make test              # validates switchyard.toml without calling a provider
```

The Vertex token normally expires after one hour. Replace
`VERTEX_ACCESS_TOKEN` in `.env` and restart Switchyard if Vertex returns HTTP
401.

The first `make setup` compiles the pinned Switchyard server and can take a few
minutes. It installs the binary under the ignored `.adk/` directory, not
globally.

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

## Demo questions

Use a fresh ADK session for each example. Routing is model-dependent, so treat
the labels below as calibration expectations rather than hard-coded outcomes.

### Simple: one policy lookup

> How long do I have to return my old laptop after a hardware refresh?

Expected tool path: `search_it_kb`.

### Medium: policy plus device data

> Is my assigned laptop eligible for a hardware refresh, and what information
> do I need to submit?

Expected tool path: `get_my_device` and `search_it_kb`.

In the same session, ask “What asset tag and lifecycle date did you find?” to
demonstrate conversational memory and sticky routing.

### Complex: dependent tool workflow

> My laptop will not power on and I need it for work today. Check my device and
> open tickets, decide whether this should be a refresh request or an incident,
> assign the correct priority, and draft the request without creating a
> duplicate.

Expected tool path: `get_my_device` -> `search_it_kb` ->
`get_my_open_tickets` -> `draft_it_request`.

The grounded result should be a P2 Hardware Incident. The existing Software
ticket is unrelated, and the draft tool returns `submitted: false`.

### Reasoning: ambiguity and competing constraints

> My laptop is old enough for a refresh, but it has now failed completely and I
> need it for customer work today. The policies seem to point to both a refresh
> and an incident. Check my device and existing tickets, resolve the conflict,
> and draft the safest request without creating a duplicate.

This exercises the conservative tier for a request that combines urgency,
policy timing, competing request types, and a dependent tool workflow.

## Agent and tools

[`employee_it_agent/agent.py`](employee_it_agent/agent.py) defines one ADK
agent with four Python tools from
[`employee_it_agent/tools.py`](employee_it_agent/tools.py). ADK owns the agent
loop, so the selected model can make dependent tool calls before answering.

Conversation memory is ADK session history. `include_contents="default"`
includes previous messages and tool results, and the development server stores
sessions in `.adk/sessions.db`. This is not cross-session semantic memory.

## Switchyard routing

[`switchyard.toml`](switchyard.toml) is the complete routing integration. Its
native `mode = "custom"` route uses GLM-5.2 as both the classifier and the
medium target, then validates a single selected label against a JSON Schema.
The selector maps that label directly to one of four configured targets. The
short domain rubric in this file is the only project-specific routing policy.
Both Gemini targets use Vertex AI's OpenAI-compatible endpoint directly.
The checked-in endpoint and embedding configuration use the demo project
`model-routing-505414`.

If the first classification fails or returns an invalid label, `default_target`
sends the request to `reasoning`, and affinity retains that decision. The target
list is strongest-first because v0.2 also uses that order for eligible serving
failures such as context overflow, transport errors, timeouts, 403/408/429, and
5xx responses. Provider retries are disabled, so those failures proceed directly
to Switchyard's route fallback.

`session_affinity = true` keeps the first selected target for later model calls
in the conversation. To avoid adding ADK-specific glue, this demo enables
`message_hash_fallback`, which derives affinity from the first user message.
That state is process-local, and separate sessions with an identical opening
message share the same routing assignment. Starting a fresh ADK session alone
does not reset it. A production integration should forward its real session
identifier as `x-switchyard-session-id` instead.

## Inspect routing

Switchyard exposes request, token, model, latency, and routing-overhead data:

```bash
curl -s http://127.0.0.1:4000/v1/stats | python3 -m json.tool
curl -s http://127.0.0.1:4000/metrics
```

Successful responses also identify the chosen target in the
`x-model-router-selected-model` header. Before the workshop, exercise the live
classifier and one serving target with a non-streaming request:

```bash
curl -i http://127.0.0.1:4000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'x-switchyard-session-id: smoke-simple' \
  -d '{"model":"employee-it","stream":false,"messages":[{"role":"user","content":"What is 2 + 2? Answer with just the number."}]}'
```

For detailed routing decisions, start the server with debug logging:

```bash
RUST_LOG=switchyard_server=debug,libsy=debug make switchyard
```

`GET /health` checks only server liveness, and `GET /v1/models` lists the
exposed `employee-it` route rather than its four internal targets. A real model
request is still required to verify credentials and upstream availability.

## Data and licensing

The knowledge base contains two documents from NVIDIA's Build an Agent
workshop under
[`data/knowledge_base/nvidia-build-an-agent`](data/knowledge_base/nvidia-build-an-agent).
They are pinned to revision `ac389a0ce6452d4b69af73f75806543fdc652b95`;
their Apache license is stored beside them and
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) records attribution.

[`data/employee_it.json`](data/employee_it.json) contains fictional demo data.
[`scripts/build_index.py`](scripts/build_index.py) creates the ignored local
`data/embeddings.json` index with Vertex AI `gemini-embedding-2` at 768
dimensions.

The original demo code is licensed under Apache-2.0; see [`LICENSE`](LICENSE).

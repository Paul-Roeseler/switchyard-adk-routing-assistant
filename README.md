# Switchyard ADK routing assistant

A small Google ADK employee IT assistant that demonstrates cost-aware model
routing with NVIDIA NeMo Switchyard. It answers policy questions, combines
policy with current device and ticket data, and can prepare a support-request
draft through a multi-step tool loop.

```text
ADK Web + SQLite session history
             |
             v
    employee_it_agent
       |           |
       |           +-- model calls --> Switchyard llm_classifier
       |                                |-- simple  --> Gemini 3.6 Flash
       |                                `-- complex --> GLM-5.2
       |
       +-- search_it_kb --> Vertex AI embedding --> local document index
       +-- get_my_device -------------------------> local demo JSON
       +-- get_my_open_tickets -------------------> local demo JSON
       `-- draft_it_request ----------------------> preview only
```

## Quick start

Vertex embeddings use Application Default Credentials. Model generation uses
the Google and NVIDIA API keys in `.env`.

```bash
gcloud config set project YOUR_GCP_PROJECT_ID
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID

cp .env.example .env  # only when .env does not already exist
# Add GOOGLE_API and INFERENCE_HUB_API to .env.

make setup
make embed             # create or rebuild the local document index
make test              # run offline configuration tests
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

## Demo questions

Use a fresh ADK session for each difficulty example. Switchyard keeps every
model call within one multi-step conversation on the model selected for its
first request.

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

Expected tool path: `get_my_device` -> `search_it_kb` ->
`get_my_open_tickets` -> `draft_it_request`.

The grounded result should be a P2 Hardware Incident. The existing Software
ticket is unrelated, and the draft tool returns `submitted: false`.

## Agent and tools

[`employee_it_agent/agent.py`](employee_it_agent/agent.py) defines one ADK
agent with four Python tools from
[`employee_it_agent/tools.py`](employee_it_agent/tools.py). ADK owns the agent
loop, so the selected model can make dependent tool calls before answering.

Conversation memory is ADK session history. `include_contents="default"`
includes previous messages and tool results, and the development server stores
sessions in `.adk/sessions.db`. This is not cross-session semantic memory.

## Switchyard routing

[`switchyard.yaml`](switchyard.yaml) configures Switchyard's stock
`llm_classifier` route. There is no custom router implementation:

- weak/simple target: `gemini-3.6-flash`;
- strong/complex target: `nvidia/zai-org/glm-5.2`.

GLM-5.2 is reused as the classifier, so the route uses only two unique model
IDs. Switchyard's packaged `general` profile sends SIMPLE requests to the weak
target and MEDIUM, COMPLEX, and REASONING requests to the strong target. A
valid abstention or a classification below the default confidence threshold
also selects the strong target. Classifier and provider failures propagate
because `fail_open` is disabled.

Session affinity pins the first confident selection for the conversation and
is cleared when Switchyard restarts. Therefore every model call in one ADK
tool loop stays on the same generation model.

The required `fallback_target_on_evict` setting only applies to target
eviction, such as a context-window overflow; it does not hide ordinary
provider errors. This branch uses Switchyard's standard YAML launcher and pins
`nemo-switchyard==0.2.0` so its configuration schema remains reproducible.

## Data and licensing

The knowledge base contains two documents from NVIDIA's Build an Agent
workshop under
[`data/knowledge_base/nvidia-build-an-agent`](data/knowledge_base/nvidia-build-an-agent):

- `hardware-refresh.md`;
- `help-and-support.md`.

They are pinned to revision
`ac389a0ce6452d4b69af73f75806543fdc652b95`. Their Apache license is stored
beside them, and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) records the
source and attribution.

[`data/employee_it.json`](data/employee_it.json) contains one fictional
employee, one failed laptop, and one unrelated open software ticket. It is not
NVIDIA or customer data.

[`scripts/build_index.py`](scripts/build_index.py) splits the two documents
into 17 sections and embeds them with Vertex AI `gemini-embedding-2` at 768
dimensions. The generated `data/embeddings.json` index is intentionally
gitignored.

The original demo code is licensed under Apache-2.0; see [`LICENSE`](LICENSE).

## Inspect routing

Switchyard exposes request, token, tier, and latency counters:

```bash
curl -s http://127.0.0.1:4000/v1/stats | python3 -m json.tool
```

GLM-5.2 appears in the classifier bucket for every newly classified session.
The generation model appears under the weak or strong tier. Switchyard's
bundled pricing table does not contain these exact model IDs, so its cost
estimate is `$0` until a dated price calculation is added.

The actual tool order is visible in the ADK trace. The Switchyard terminal also
prints a `classifier_signals=...` JSON line for each newly classified
conversation, including the calculated policy tier.

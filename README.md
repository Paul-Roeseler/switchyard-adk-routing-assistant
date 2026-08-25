# Switchyard ADK routing assistant

A small Google ADK employee IT assistant that demonstrates cost-aware model
routing with NVIDIA NeMo Switchyard. It answers policy questions, combines
policy with current device and ticket data, and can prepare and submit a
support request through a confirmed multi-step tool loop.

```text
ADK Web + SQLite session history
             |
             v
    employee_it_agent
       |           |
       |           +-- model calls --> Switchyard llm_classifier
       |                                |-- classifier --> Gemini 3.6 Flash
       |                                |-- simple -----> GLM-5.2
       |                                `-- complex ----> Gemini 3.1 Pro
       |
       +-- search_it_kb --> Vertex AI embedding --> local document index
       +-- get_my_device -------------------------> local demo JSON
       +-- get_my_open_tickets -------------------> local demo JSON
       +-- draft_it_request ----------------------> preview only
       `-- submit_it_request --> ADK confirmation --> local ticket store
```

## Quick start

Vertex embeddings use Application Default Credentials. Gemini Pro generation
uses a short-lived Vertex access token, while NVIDIA inference uses an API key.

```bash
gcloud config set project YOUR_GCP_PROJECT_ID
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID

cp .env.example .env  # only when .env does not already exist
# Add INFERENCE_HUB_API to .env.
# Generate VERTEX_ACCESS_TOKEN with the command below and paste it into .env.
gcloud auth application-default print-access-token

make setup
make embed             # create or rebuild the local document index
make test              # run offline configuration tests
```

`VERTEX_ACCESS_TOKEN` is an OAuth bearer token, not a permanent API key. It
normally expires after one hour. Generate a new value with the command above,
update `.env`, and restart Switchyard when it expires.

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

Then ask:

> Submit that ticket.

The agent calls `submit_it_request`, and ADK Web shows a confirmation dialog
with the exact arguments before any write occurs. Approving it creates a local
ticket and returns its ID. Run `make reset-tickets` before repeating the demo.

## Agent and tools

[`employee_it_agent/agent.py`](employee_it_agent/agent.py) defines one ADK
agent with five Python tools from
[`employee_it_agent/tools.py`](employee_it_agent/tools.py). ADK owns the agent
loop, so the selected model can make dependent tool calls before answering.
The submission tool uses ADK's native `require_confirmation` control; approval
is enforced by ADK rather than by the selected model's prompt alone.

Conversation memory is ADK session history. `include_contents="default"`
includes previous messages and tool results, and the development server stores
sessions in `.adk/sessions.db`. This is not cross-session semantic memory.

The agent calls the fixed local endpoint `http://127.0.0.1:4000/v1`. That URL
does not belong in `switchyard.yaml`: it describes the ADK-to-Switchyard
connection, while the YAML file describes Switchyard-to-provider connections.
The `make switchyard` command binds the matching local port.

## Switchyard routing

[`switchyard.yaml`](switchyard.yaml) configures Switchyard's stock
`llm_classifier` route. There is no custom router implementation:

- classifier: `gcp/google/gemini-3.6-flash` through NVIDIA Inference Hub;
- weak/simple target: `nvidia/zai-org/glm-5.2` through Inference Hub;
- strong target: `google/gemini-3.1-pro-preview` through Google Cloud Vertex AI.

Switchyard's packaged `general` profile sends SIMPLE requests to the weak
target and MEDIUM, COMPLEX, and REASONING requests to the strong target. A
valid abstention or a classification below the default confidence threshold
also selects the strong target. Classifier and provider failures propagate
because `fail_open` is disabled.

The classifier goes through Inference Hub because Switchyard 0.2's stock YAML
classifier sends a vLLM-specific thinking hint. Inference Hub accepts that
hint and Gemini's strict JSON-schema response. Google's direct endpoint rejects
the hint.

The YAML also contains a fully commented replacement for the strong target:
`azure/anthropic/claude-opus-5` through Inference Hub. During a live demo,
comment the Gemini Pro block and uncomment the Opus block, then restart
Switchyard.

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
NVIDIA or customer data. Submitted tickets are written to the ignored runtime
copy `.adk/employee_it.json`, leaving the tracked seed unchanged.

[`scripts/build_index.py`](scripts/build_index.py) splits the two documents
into 17 sections and embeds them with Vertex AI `gemini-embedding-2` at 768
dimensions. The generated `data/embeddings.json` index is intentionally
gitignored.

The original demo code is licensed under Apache-2.0; see [`LICENSE`](LICENSE).

## Credentials and portability

The local demo currently needs:

| Purpose | Credential |
| --- | --- |
| Switchyard classifier, GLM-5.2, optional Claude Opus | `INFERENCE_HUB_API` |
| Gemini 3.1 Pro generation | `VERTEX_ACCESS_TOKEN` plus `GOOGLE_CLOUD_PROJECT` |
| Vertex AI document and query embeddings | Google ADC plus `GOOGLE_CLOUD_PROJECT` |

ADK, Switchyard's local endpoint, the document index, session database, and
local ticket submission require no additional login. The two servers have no
inbound authentication and bind to localhost, so they must not be exposed
directly to a network.

The application is split so provider changes remain small:

- **Generation models:** change the model, base URL, and key in
  `switchyard.yaml`. The replacement must support OpenAI-compatible tool calls;
  the classifier must also support strict structured JSON.
- **Embeddings:** replace the two `google-genai` calls in
  `scripts/build_index.py` and `employee_it_agent/tools.py`. Ingestion and query
  must use the same model, dimensions, and input formatting, then run
  `make embed` again.
- **Ticket system:** replace only the local state helpers and the body of
  `submit_it_request` with ServiceNow, Jira, or another API. Keep ADK's
  confirmation wrapper and add the target system's OAuth or service account.
- **Cloud runtime:** containerize ADK and Switchyard, put authentication in
  front of both services, move secrets into the cloud secret manager, and use
  durable session/ticket storage instead of local SQLite and JSON.

For a Google Cloud deployment, keep Vertex generation and embeddings and use a
Cloud Run or GKE service identity instead of interactive ADC login. A
long-running Vertex Gemini target needs automatic OAuth token refresh rather
than the manually refreshed token used by this local demo.

For an NVIDIA-only deployment, point all generation targets at NVIDIA-hosted
OpenAI-compatible endpoints and replace Vertex embeddings with an NVIDIA
embedding endpoint. That reduces local credentials to one NVIDIA API key. The
same endpoints can later point at self-hosted NIM services; downloading NIM
artifacts requires NGC access, while requests to an internal NIM can use your
own gateway authentication.

Fireworks and other OpenAI-compatible providers are configuration-only model
swaps when their selected models support the same tool schemas. AWS or Azure
API-key endpoints can work similarly; IAM, managed-identity, and other
short-lived credentials require a token-refresh adapter or gateway.

## Inspect routing

Switchyard exposes request, token, tier, and latency counters:

```bash
curl -s http://127.0.0.1:4000/v1/stats | python3 -m json.tool
```

Gemini 3.6 Flash appears in the classifier bucket for every newly classified
session. The generation model appears under the weak or strong tier.
Switchyard's bundled pricing table does not contain these exact model IDs, so
its cost estimate is `$0` until a dated price calculation is added.

The actual tool order is visible in the ADK trace. The Switchyard terminal also
prints a `classifier_signals=...` JSON line for each newly classified
conversation, including the calculated policy tier.

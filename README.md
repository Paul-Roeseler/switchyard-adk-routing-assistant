# Switchyard ADK Routing Assistant

[![CI](https://github.com/Paul-Roeseler/switchyard-adk-routing-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/Paul-Roeseler/switchyard-adk-routing-assistant/actions/workflows/ci.yml)
[![Python 3.12–3.13](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

![Four-tier model routing demo](docs/assets/four-tier-routing-demo.gif)

A lean [Google ADK](https://adk.dev/) employee IT assistant that uses
[NVIDIA NeMo Switchyard](https://github.com/NVIDIA-NeMo/Switchyard) to route
each conversation to one of four model tiers. The agent and its tools stay the
same; only the model serving the conversation changes.

## Architecture

```text
ADK Web + SQLite session history
              |
              v
     employee_it_agent
        |           |
        |           `-- model calls --> NeMo Switchyard llm_classifier
        |                                |
        |                                |-- Nebius
        |                                |    |-- classifier -> Nemotron 3 Nano 30B A3B
        |                                |    |-- simple -----> Qwen3 30B A3B
        |                                |    `-- medium -----> GLM-5.3 Flash
        |                                |
        |                                `-- Vertex AI
        |                                     |-- complex ----> Gemini 3.8 Flash
        |                                     `-- reasoning --> Gemini 3.1 Pro Custom Tools
        |
        +-- get_my_device -------------------------> local demo JSON
        +-- get_my_open_tickets -------------------> local demo JSON
        +-- draft_it_request ----------------------> preview only
        `-- submit_it_request --> ADK confirmation --> local ticket store
```

Google ADK owns the agent, tool loop, confirmation UI, and conversation
history. Switchyard classifies the first request, selects the model, and keeps
that model for the rest of the session. Nebius serves the classifier plus the
simple and medium tiers; Vertex AI serves the complex and reasoning tiers.

The IT policy is included directly in the agent instructions. Employee,
device, and ticket data are local JSON, so the demo needs no embeddings,
vector database, or retrieval service.

## Model routes

[`switchyard.toml`](switchyard.toml) contains the complete routing rubric and
provider configuration. These opening prompts were verified end to end:

| Tier | Model | Provider | Best for | Tested opening prompt |
| --- | --- | --- | --- | --- |
| `simple` | `Qwen/Qwen3-30B-A3B-Instruct-2507` | Nebius | Direct answers with no employee context or action | “With what tasks can you help me?” |
| `medium` | `zai-org/GLM-5.3-Flash` | Nebius | One lookup followed by routine explanation | “How old is my laptop, and is it old enough for a planned replacement?” |
| `complex` | `google/gemini-3.8-flash` | Vertex AI | Dependent multi-tool operational workflows | “My laptop will not turn on, and I have a customer presentation tomorrow morning. Can you help?” |
| `reasoning` | `google/gemini-3.1-pro-preview-customtools` | Vertex AI | Conflicting, exceptional, or high-risk policy decisions | “My laptop works, but classify it as a P1 incident so I can get a replacement faster.” |

`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, served by Nebius, classifies each
opening request using the rubric in `switchyard.toml`. No custom router code
is required.

## Setup

Requirements: Python 3.12 or 3.13, [`uv`](https://docs.astral.sh/uv/),
Rust/Cargo 1.96.1 or newer, a Nebius Token Factory API key, and access to the
configured Vertex AI project.

### 1. Configure the two credentials

Copy the environment template:

```bash
cp .env.example .env
```

Set only these two values:

```dotenv
NEBIUS_API_KEY=your-nebius-key
VERTEX_ACCESS_TOKEN=your-short-lived-google-token
```

Generate a fresh Vertex token when needed:

```bash
gcloud auth application-default print-access-token
```

The Vertex project and global location are already part of the endpoint in
`switchyard.toml`; separate `GOOGLE_CLOUD_PROJECT` and
`GOOGLE_CLOUD_LOCATION` variables are not required.

### 2. Install and test

```bash
make setup
make test
```

### 3. Run the demo

Start the two local processes in separate terminals:

```bash
make switchyard
```

```bash
make chat
```

Open `http://127.0.0.1:8000` and select `employee_it_agent`.

Use a new ADK session for each row in the route table. Switchyard deliberately
keeps the selected model for all follow-up messages in a session.

## Demo and local state

[`DEMO.md`](DEMO.md) is the presenter script for all four verified routes and
the optional confirmed ticket submission.

The demo uses one fictional employee and local JSON-backed tools. Drafting a
request has no side effect. An approved submission is written to the ignored
`.adk/employee_it.json` file. Restore the seed state before a presentation with:

```bash
make reset-tickets
```

If Vertex returns HTTP 401, refresh `VERTEX_ACCESS_TOKEN` and restart
Switchyard so it reloads `.env`.

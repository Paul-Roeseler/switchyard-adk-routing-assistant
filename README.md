# Switchyard ADK Routing Assistant

[![CI](https://github.com/Paul-Roeseler/switchyard-adk-routing-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/Paul-Roeseler/switchyard-adk-routing-assistant/actions/workflows/ci.yml)
[![Python 3.12–3.13](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

A minimal [Google ADK](https://adk.dev/) assistant that uses [NVIDIA NeMo Switchyard](https://github.com/NVIDIA-NeMo/Switchyard) to route employee IT requests across four model tiers without changing the agent or its tools.

## Architecture

```text
ADK Web + SQLite session history
              |
              v
     employee_it_agent
        |           |
        |           `-- model calls --> NeMo Switchyard llm_classifier
        |                                |-- classifier -> Nemotron 3.5 Lightning
        |                                |-- simple -----> Qwen3.8 27B
        |                                |-- medium -----> GLM-5.3 Flash
        |                                |-- complex ----> Gemini 3.8 Flash
        |                                `-- reasoning --> Gemini 3.1 Pro Custom Tools
        |
        +-- get_my_device -------------------------> local demo JSON
        +-- get_my_open_tickets -------------------> local demo JSON
        +-- draft_it_request ----------------------> preview only
        `-- submit_it_request --> ADK confirmation --> local ticket store
```

Google ADK owns the agent, tool loop, confirmation, and conversation history.
Switchyard owns request classification and outbound model selection. The agent
always calls the same local route, so changing providers does not change the
agent or its tools.

The IT policy is included directly in the demo agent instructions. Employee,
device, and ticket data are local JSON; no knowledge index or embedding setup
is required.

## Setup

Requirements: Python 3.12 or 3.13, [`uv`](https://docs.astral.sh/uv/),
Rust/Cargo 1.96.1 or newer, and credentials for the configured inference
endpoints.

### 1. Configure Switchyard

[`switchyard.toml`](switchyard.toml) defines the four generation targets:

| Target | Model | Purpose |
| --- | --- | --- |
| `simple` | Qwen3.8 27B | Direct answers and straightforward policy questions |
| `medium` | GLM-5.3 Flash | Routine synthesis across policy and employee data |
| `complex` | Gemini 3.8 Flash | Dependent multi-tool workflows |
| `reasoning` | Gemini 3.1 Pro Preview Custom Tools | Ambiguous, conflicting, or high-risk requests |

Nemotron 3.5 Lightning selects one of these targets from the rubric in the same
TOML file. No custom Switchyard runtime code is required.

### 2. Configure credentials

Copy the environment template:

```bash
cp .env.example .env
```

The checked-in router expects:

```dotenv
INFERENCE_HUB_API=your-nvidia-key
NEBIUS_API_KEY=your-nebius-key
VERTEX_ACCESS_TOKEN=your-short-lived-google-token
```

Generate the Vertex token with
`gcloud auth application-default print-access-token`. The Vertex project and
location are already configured in `switchyard.toml`.

### 3. Install and run

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

Open `http://127.0.0.1:8000` and select `employee_it_agent`.

## Demo

[`DEMO.md`](DEMO.md) contains the presenter workflow, example prompts, expected
routes, tool calls, and confirmation step.

The demo uses one fictional employee and local JSON-backed tools. Submitted
tickets are written to the ignored `.adk/employee_it.json`; run
`make reset-tickets` to restore the seed state.

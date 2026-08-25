# Switchyard ADK Routing Assistant

[![CI](https://github.com/Paul-Roeseler/switchyard-adk-routing-assistant/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Paul-Roeseler/switchyard-adk-routing-assistant/actions/workflows/ci.yml)
[![Python 3.12–3.13](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

A minimal [Google ADK](https://adk.dev/) assistant that uses [NVIDIA NeMo Switchyard](https://github.com/NVIDIA-NeMo/Switchyard) to route simple requests to economical models and complex, tool-driven work to stronger models across configurable inference endpoints.

## Architecture

```text
ADK Web + SQLite session history
              |
              v
     employee_it_agent
        |           |
        |           `-- model calls --> NeMo Switchyard llm_classifier
        |                                |-- classifier endpoint
        |                                |-- SIMPLE ------> weak endpoint
        |                                `-- MEDIUM+ -----> strong endpoint
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

## Setup

Requirements: Python 3.12 or 3.13, [`uv`](https://docs.astral.sh/uv/), and
credentials for the inference endpoints you select.

### 1. Configure Switchyard

Edit [`switchyard.yaml`](switchyard.yaml) and configure its three model roles:

| Role | Purpose |
| --- | --- |
| `classifier` | Classify request complexity |
| `weak` | Handle `SIMPLE` requests |
| `strong` | Handle all other requests |

Each role selects its endpoint with the same core fields:

```yaml
weak:
  model: economical-model
  base_url: https://provider.example.com/v1
  api_key: ${PROVIDER_API_KEY}
  format: openai  # optional target-level override
```

### 2. Configure credentials

Copy the environment template:

```bash
cp .env.example .env
```

Every `${VARIABLE}` referenced by `switchyard.yaml` must have a non-empty value
in `.env`.

The checked-in configuration expects:

```dotenv
INFERENCE_HUB_API=your-nvidia-key
VERTEX_ACCESS_TOKEN=your-short-lived-google-token
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
```

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

## Demo

[`DEMO.md`](DEMO.md) contains the tested presenter workflow, example prompts,
expected routes, tool calls, and confirmation step.

The demo uses one fictional employee and local JSON-backed tools. Submitted tickets are
written to the ignored `.adk/employee_it.json`; run `make reset-tickets` to
restore the seed state.

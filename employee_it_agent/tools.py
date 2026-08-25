from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from google import genai
from google.genai import types


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "data" / "embeddings.json"
SEED_STATE_PATH = ROOT / "data" / "employee_it.json"
RUNTIME_STATE_PATH = ROOT / ".adk" / "employee_it.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_state() -> dict:
    path = RUNTIME_STATE_PATH if RUNTIME_STATE_PATH.exists() else SEED_STATE_PATH
    return _read_json(path)


def _write_state(state: dict) -> None:
    RUNTIME_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = RUNTIME_STATE_PATH.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(RUNTIME_STATE_PATH)


def _build_request(
    request_type: str,
    subject: str,
    description: str,
    business_impact: str,
    priority: str,
) -> dict:
    if request_type not in {"hardware_incident", "hardware_refresh"}:
        raise ValueError(f"Unsupported request type: {request_type}")
    if priority not in {"P1", "P2", "P3", "P4"}:
        raise ValueError(f"Unsupported priority: {priority}")

    state = _read_state()
    portal_request_type = (
        "Incident" if request_type == "hardware_incident" else "Service Request"
    )
    return {
        "requested_for": state["current_user"],
        "request_type": portal_request_type,
        "service": request_type,
        "category": "Hardware",
        "subject": subject,
        "description": description,
        "business_impact": business_impact,
        "priority": priority,
        "asset_tag": state["device"]["asset_tag"],
    }


def search_it_kb(query: str) -> dict:
    """Search the IT knowledge base and return the three most relevant sections.

    Use this for refresh eligibility, procedures, priorities, and support rules.
    It does not return employee-specific operational data.

    Args:
        query: The employee's policy or support question.
    """
    index = _read_json(INDEX_PATH)
    embedding_config = index["embedding"]
    client = genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=embedding_config["location"],
        http_options=types.HttpOptions(api_version="v1"),
    )
    response = client.models.embed_content(
        model=embedding_config["model"],
        contents=embedding_config["query_input"].format(query=query),
        config=types.EmbedContentConfig(
            output_dimensionality=embedding_config["dimensions"],
            auto_truncate=False,
        ),
    )
    if not response.embeddings or response.embeddings[0].values is None:
        raise RuntimeError("Vertex AI returned no query embedding")
    query_embedding = response.embeddings[0].values

    scored_chunks = [
        (
            sum(
                left * right
                for left, right in zip(
                    query_embedding, chunk["embedding"], strict=True
                )
            ),
            chunk,
        )
        for chunk in index["chunks"]
    ]
    ranked = sorted(scored_chunks, key=lambda item: item[0], reverse=True)[:3]
    return {
        "matches": [
            {
                "score": round(float(score), 6),
                "id": chunk["id"],
                "title": chunk["document_title"],
                "citation": f"{Path(chunk['source']).name} - {chunk['section']}",
                "source": chunk["source"],
                "section": chunk["section"],
                "text": chunk["text"],
            }
            for score, chunk in ranked
        ]
    }


def get_my_device() -> dict:
    """Return the current employee's assigned IT-managed device.

    Use this when an answer depends on the asset tag, device type, assignment
    date, lifecycle start date, model, operating system, condition, or issue.
    """
    state = _read_state()
    return {"device": state["device"]}


def get_my_open_tickets() -> dict:
    """Return the current employee's unresolved IT support tickets.

    Use this before drafting a request so the agent can avoid duplicates.
    """
    state = _read_state()
    open_tickets = [
        ticket
        for ticket in state["tickets"]
        if ticket["status"] not in {"Resolved", "Closed"}
    ]
    return {"tickets": open_tickets}


def draft_it_request(
    request_type: str,
    subject: str,
    description: str,
    business_impact: str,
    priority: str,
) -> dict:
    """Prepare a hardware IT request preview without submitting it.

    Call get_my_open_tickets first. This function has no external side effect.

    Args:
        request_type: Either hardware_incident or hardware_refresh.
        subject: A short, descriptive title.
        description: What is broken or being requested.
        business_impact: How the issue affects the employee's work.
        priority: The policy priority: P1, P2, P3, or P4.
    """
    return {
        "status": "success",
        "submitted": False,
        "draft": _build_request(
            request_type,
            subject,
            description,
            business_impact,
            priority,
        ),
    }


def submit_it_request(
    request_type: str,
    subject: str,
    description: str,
    business_impact: str,
    priority: str,
) -> dict:
    """Submit the reviewed hardware request to the local demo ticket store.

    Use only after draft_it_request showed the user the same request. ADK asks
    the user for confirmation before this function runs.

    Args:
        request_type: Either hardware_incident or hardware_refresh.
        subject: The reviewed request title.
        description: The reviewed problem or request description.
        business_impact: The reviewed impact on the employee's work.
        priority: The reviewed policy priority: P1, P2, P3, or P4.
    """
    request = _build_request(
        request_type,
        subject,
        description,
        business_impact,
        priority,
    )
    state = _read_state()
    duplicate = next(
        (
            ticket
            for ticket in state["tickets"]
            if ticket["status"] not in {"Resolved", "Closed"}
            and ticket.get("category") == "Hardware"
            and ticket.get("asset_tag") == request["asset_tag"]
        ),
        None,
    )
    if duplicate:
        return {
            "status": "duplicate",
            "submitted": False,
            "existing_ticket": duplicate,
        }

    ticket_numbers = [
        int(ticket["ticket_id"].rsplit("-", 1)[-1])
        for ticket in state["tickets"]
        if ticket["ticket_id"].rsplit("-", 1)[-1].isdigit()
    ]
    prefix = "INC" if request["request_type"] == "Incident" else "REQ"
    ticket = {
        "ticket_id": f"{prefix}-{max(ticket_numbers, default=1000) + 1}",
        "employee_id": state["current_user"]["employee_id"],
        **{key: value for key, value in request.items() if key != "requested_for"},
        "status": "Open",
        "created_at": date.today().isoformat(),
    }
    state["tickets"].append(ticket)
    _write_state(state)
    return {"status": "success", "submitted": True, "ticket": ticket}

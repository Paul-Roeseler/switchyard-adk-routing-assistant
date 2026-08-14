from __future__ import annotations

import json
import os
from pathlib import Path

from google import genai
from google.genai import types


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "data" / "embeddings.json"
STATE_PATH = ROOT / "data" / "employee_it.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
    state = _read_json(STATE_PATH)
    return {"device": state["device"]}


def get_my_open_tickets() -> dict:
    """Return the current employee's unresolved IT support tickets.

    Use this before drafting a request so the agent can avoid duplicates.
    """
    state = _read_json(STATE_PATH)
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
    if request_type not in {"hardware_incident", "hardware_refresh"}:
        raise ValueError(f"Unsupported request type: {request_type}")
    if priority not in {"P1", "P2", "P3", "P4"}:
        raise ValueError(f"Unsupported priority: {priority}")

    state = _read_json(STATE_PATH)
    portal_request_type = (
        "Incident" if request_type == "hardware_incident" else "Service Request"
    )
    return {
        "status": "success",
        "submitted": False,
        "draft": {
            "requested_for": state["current_user"],
            "request_type": portal_request_type,
            "service": request_type,
            "category": "Hardware",
            "subject": subject,
            "description": description,
            "business_impact": business_impact,
            "priority": priority,
            "asset_tag": state["device"]["asset_tag"],
        },
    }

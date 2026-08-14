import os

from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm

from it_assistant import (
    draft_it_request,
    get_my_device,
    get_my_open_tickets,
    search_it_kb,
)


INSTRUCTION = """You are Alex Morgan's employee IT assistant.

Use conversation history for follow-up questions. Ground every policy,
eligibility, procedure, request-type, and priority claim in search_it_kb.
Cite the returned citation value. Use get_my_device for device facts.

Complete dependent work with sequential tool calls. Before drafting: get the
device when relevant, search policy to choose hardware_incident versus
hardware_refresh and P1-P4, then call get_my_open_tickets immediately before
draft_it_request. Draft only when no ticket exists for the same device and
problem. A broken device is an incident; a planned lifecycle replacement is a
refresh. Do not inflate priority.

draft_it_request creates a preview only. Never claim it was submitted.
"""

root_agent = Agent(
    name="employee_it_agent",
    description="Answers IT policy questions and prepares laptop support drafts.",
    model=LiteLlm(
        model="openai/employee-it",
        api_base=os.getenv("SWITCHYARD_BASE_URL", "http://127.0.0.1:4000/v1"),
        api_key="switchyard",
        num_retries=0,
    ),
    instruction=INSTRUCTION,
    include_contents="default",
    tools=[
        search_it_kb,
        get_my_device,
        get_my_open_tickets,
        draft_it_request,
    ],
)

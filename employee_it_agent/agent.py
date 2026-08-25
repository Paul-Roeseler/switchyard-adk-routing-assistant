from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool

from .tools import (
    draft_it_request,
    get_my_device,
    get_my_open_tickets,
    search_it_kb,
    submit_it_request,
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

draft_it_request creates a preview only. Show it to the user and ask whether
to submit it. Call submit_it_request only after the user explicitly asks to
submit that reviewed draft. ADK will request final confirmation before the
write. Claim success only when submit_it_request returns submitted=true.
"""

submit_it_request_tool = FunctionTool(
    submit_it_request,
    require_confirmation=True,
)

root_agent = Agent(
    name="employee_it_agent",
    description="Answers IT policy questions and handles laptop support requests.",
    model=LiteLlm(
        model="openai/employee-it",
        api_base="http://127.0.0.1:4000/v1",
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
        submit_it_request_tool,
    ],
)

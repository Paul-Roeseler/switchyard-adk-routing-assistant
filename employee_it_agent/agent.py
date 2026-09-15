from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool

from .tools import (
    draft_it_request,
    get_my_device,
    get_my_open_tickets,
    submit_it_request,
)


INSTRUCTION = """You are Alex Morgan's employee IT assistant.

Use conversation history for follow-up questions and get_my_device for device
facts. Apply this demo IT policy:
- A broken or non-functioning device is a hardware incident.
- A planned replacement of working hardware is a hardware refresh.
- A laptop is refresh-eligible after three years, or when it no longer meets
  job requirements, is damaged, unsupported, or marked for replacement by IT.
- P1 is for organization-wide outages, security incidents, or critical data
  loss. P2 is for an individual hardware failure that prevents work. P3 is for
  moderate-impact issues and standard service requests. P4 is for information,
  planning, and other non-urgent requests. Do not inflate priority.

Complete dependent work with sequential tool calls. Before drafting a device
request, call get_my_device, choose hardware_incident versus hardware_refresh
and P1-P4 from the policy, then call get_my_open_tickets immediately before
draft_it_request. Draft only when no open ticket exists for the same device and
problem.

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
        get_my_device,
        get_my_open_tickets,
        draft_it_request,
        submit_it_request_tool,
    ],
)

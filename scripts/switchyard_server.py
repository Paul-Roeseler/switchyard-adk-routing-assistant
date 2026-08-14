from __future__ import annotations

import os
from typing import Any

import uvicorn
from fastapi import FastAPI
from switchyard import (
    BackendFormat,
    LlmTarget,
    ProfileSwitchyard,
    RouteTable,
    build_switchyard_app,
)
from switchyard.lib.backends.deterministic_routing_llm_backend import (
    DeterministicRoutingLLMBackend,
)
from switchyard.lib.processors.llm_classifier import (
    DEFAULT_CLASSIFIER_SYSTEM_PROMPT,
    LLMClassifierPresets,
    LLMClassifierRequestProcessor,
    RouteTier,
    SignalTierSelectorConfig,
    SignalTierSelectorRequestProcessor,
)
from switchyard.lib.processors.reasoning_effort_normalizer import (
    ReasoningEffortNormalizer,
)
from switchyard.lib.profiles.chain import ComponentChainProfile
from switchyard.lib.session_affinity import SessionAffinity
from switchyard.lib.stats_accumulator import StatsAccumulator


ROUTE_ID = "employee-it"
NVIDIA_BASE_URL = "https://inference-api.nvidia.com/v1"
GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

DEFAULT_SIMPLE_MODEL = "nvidia/meta/llama-3.1-8b-instruct"
DEFAULT_MEDIUM_MODEL = "nvidia/zai-org/glm-5.2"
DEFAULT_COMPLEX_MODEL = "gemini-3.6-flash"
DEFAULT_REASONING_MODEL = "gemini-3.1-pro-preview"

TIER_MAPPING = {
    RouteTier.SIMPLE: "simple",
    RouteTier.MEDIUM: "medium",
    RouteTier.COMPLEX: "complex",
    RouteTier.REASONING: "reasoning",
}

IT_CLASSIFIER_PROMPT = (
    DEFAULT_CLASSIFIER_SYSTEM_PROMPT
    + """

Apply these rules to the employee IT assistant in this request:

- SIMPLE: one direct policy question requiring at most one read-only
  search_it_kb call. A single lookup is not multi-step tool planning; set
  tool_planning_required=false unless the calls depend on one another.
- MEDIUM: combine policy with one employee or device lookup, or perform a
  routine comparison with light reasoning and no consequential action.
- COMPLEX: coordinate dependent calls across device, policy, and ticket data,
  choose request type or priority, prevent duplicates, or prepare a draft.
- REASONING: resolve genuinely ambiguous or conflicting policies, exceptions,
  or deep analysis where the complex model is likely insufficient.

Judge the operations actually needed for this user message. Do not increase
the tier merely because several tool definitions are present in the request.
"""
)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _setting(name: str, default: str) -> str:
    return os.getenv(name, "").strip() or default


def _target(
    tier: str,
    model: str,
    base_url: str,
    api_key: str,
    extra_body: dict[str, Any] | None = None,
) -> LlmTarget:
    return LlmTarget(
        id=tier,
        model=model,
        format=BackendFormat.OPENAI,
        base_url=base_url,
        api_key=api_key,
        timeout_secs=600.0,
        extra_body=extra_body,
    )


def create_app() -> FastAPI:
    """Build the four-tier Switchyard OpenAI-compatible proxy."""
    nvidia_key = _required_env("INFERENCE_HUB_API")
    google_key = _required_env("GOOGLE_API")

    simple_model = _setting("SWITCHYARD_SIMPLE_MODEL", DEFAULT_SIMPLE_MODEL)
    medium_model = _setting("SWITCHYARD_MEDIUM_MODEL", DEFAULT_MEDIUM_MODEL)
    complex_model = _setting("SWITCHYARD_COMPLEX_MODEL", DEFAULT_COMPLEX_MODEL)
    reasoning_model = _setting(
        "SWITCHYARD_REASONING_MODEL", DEFAULT_REASONING_MODEL
    )
    classifier_model = _setting("SWITCHYARD_CLASSIFIER_MODEL", medium_model)

    targets = {
        "simple": _target("simple", simple_model, NVIDIA_BASE_URL, nvidia_key),
        "medium": _target(
            "medium",
            medium_model,
            NVIDIA_BASE_URL,
            nvidia_key,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        ),
        "complex": _target("complex", complex_model, GOOGLE_BASE_URL, google_key),
        "reasoning": _target(
            "reasoning", reasoning_model, GOOGLE_BASE_URL, google_key
        ),
    }

    # Reuse Switchyard's packaged general prompt and RouteSignals schema. Only
    # the final tier mapping changes from two targets to four.
    general_profile = LLMClassifierPresets.general_2_tier(
        weak="simple",
        strong="reasoning",
    )
    affinity = SessionAffinity(enabled=True, max_sessions=10_000, warmup_turns=0)
    classifier_config = general_profile.make_classifier_config(
        model=classifier_model,
        api_key=nvidia_key,
        base_url=NVIDIA_BASE_URL,
        timeout_s=30.0,
        fail_open=False,
        recent_turn_window=4,
        system_prompt=IT_CLASSIFIER_PROMPT,
    )

    classifier = LLMClassifierRequestProcessor(
        classifier_config,
        signal_schema=general_profile.signal_schema,
        affinity=affinity,
    )
    selector = SignalTierSelectorRequestProcessor(
        SignalTierSelectorConfig(
            tier_mapping=TIER_MAPPING,
            default_tier="reasoning",
            min_confidence=0.6,
        ),
        affinity=affinity,
    )
    backend = DeterministicRoutingLLMBackend.from_tiers(
        tiers=targets,
        default_tier="reasoning",
    )

    stats = StatsAccumulator()
    profile = ComponentChainProfile(
        request_processors=[ReasoningEffortNormalizer(), classifier, selector],
        backend=backend,
        # Provider failures and context-window errors propagate in this demo.
        fallback_target_on_evict=None,
    ).with_runtime_components(stats_accumulator=stats, enable_stats=True)

    routes = RouteTable()
    routes.register(
        ROUTE_ID,
        ProfileSwitchyard(profile),
        metadata={"display_name": "Employee IT (four-tier)"},
        default=True,
    )
    return build_switchyard_app(routes)


def main() -> None:
    app = create_app()
    uvicorn.run(
        app,
        host=_setting("SWITCHYARD_HOST", "127.0.0.1"),
        port=int(_setting("SWITCHYARD_PORT", "4000")),
        workers=1,
    )


if __name__ == "__main__":
    main()

import os
from typing import Any

import uvicorn
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
    LLMClassifierPresets,
    LLMClassifierRequestProcessor,
    SignalTierSelectorConfig,
    SignalTierSelectorRequestProcessor,
)
from switchyard.lib.profiles.chain import ComponentChainProfile
from switchyard.lib.session_affinity import SessionAffinity


NVIDIA_BASE_URL = "https://inference-api.nvidia.com/v1"
GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

SIMPLE_MODEL = "nvidia/meta/llama-3.1-8b-instruct"
MEDIUM_MODEL = "nvidia/zai-org/glm-5.2"
COMPLEX_MODEL = "gemini-3.6-flash"
REASONING_MODEL = "gemini-3.1-pro-preview"


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


def create_app():
    """Build the four-tier Switchyard OpenAI-compatible proxy."""
    nvidia_key = os.environ["INFERENCE_HUB_API"]
    google_key = os.environ["GOOGLE_API"]

    targets = {
        "simple": _target("simple", SIMPLE_MODEL, NVIDIA_BASE_URL, nvidia_key),
        "medium": _target(
            "medium",
            MEDIUM_MODEL,
            NVIDIA_BASE_URL,
            nvidia_key,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        ),
        "complex": _target("complex", COMPLEX_MODEL, GOOGLE_BASE_URL, google_key),
        "reasoning": _target(
            "reasoning", REASONING_MODEL, GOOGLE_BASE_URL, google_key
        ),
    }

    # Use Switchyard's packaged general classifier and four policy-tier labels.
    general_profile = LLMClassifierPresets.general_2_tier(
        weak="simple",
        strong="reasoning",
    )
    affinity = SessionAffinity(enabled=True)
    classifier_config = general_profile.make_classifier_config(
        model=MEDIUM_MODEL,
        api_key=nvidia_key,
        base_url=NVIDIA_BASE_URL,
        timeout_s=30.0,
        fail_open=False,
        recent_turn_window=4,
    )

    classifier = LLMClassifierRequestProcessor(
        classifier_config,
        signal_schema=general_profile.signal_schema,
        affinity=affinity,
    )
    selector = SignalTierSelectorRequestProcessor(
        SignalTierSelectorConfig(
            default_tier="reasoning",
            min_confidence=0.6,
        ),
        affinity=affinity,
    )
    backend = DeterministicRoutingLLMBackend.from_tiers(
        tiers=targets,
        default_tier="reasoning",
    )

    profile = ComponentChainProfile(
        request_processors=[classifier, selector],
        backend=backend,
    ).with_runtime_components(enable_stats=True)

    routes = RouteTable()
    routes.register(
        "employee-it",
        ProfileSwitchyard(profile),
        default=True,
    )
    return build_switchyard_app(routes)


def main() -> None:
    uvicorn.run(
        create_app(),
        host="127.0.0.1",
        port=4000,
    )


if __name__ == "__main__":
    main()

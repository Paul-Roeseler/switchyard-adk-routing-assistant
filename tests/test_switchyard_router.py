from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from switchyard.lib.processors.llm_classifier import (
    CTX_DETERMINISTIC_ROUTE_SIGNALS,
    Complexity,
    ContextDependency,
    PrecisionRequirement,
    ReasonCode,
    ReasoningDepth,
    RiskLevel,
    RouteSignals,
    RouteTier,
    SignalTierSelectorConfig,
    SignalTierSelectorRequestProcessor,
    TaskType,
)
from switchyard.lib.backends.deterministic_routing_llm_backend import (
    CTX_DETERMINISTIC_ROUTING_TIER,
)
from switchyard.lib.proxy_context import ProxyContext
from switchyard_rust.core import ChatRequest, ChatRequestType

from switchyard_router import create_app


class SwitchyardRouterTests(unittest.TestCase):
    def test_each_policy_tier_selects_its_matching_target(self) -> None:
        for tier in RouteTier:
            with self.subTest(tier=tier.value):
                recommended_tier = (
                    RouteTier.REASONING
                    if tier is not RouteTier.REASONING
                    else RouteTier.SIMPLE
                )
                signals = self._signals(
                    complexity=Complexity(tier.value),
                    recommended_tier=recommended_tier,
                )
                ctx = ProxyContext(
                    metadata={CTX_DETERMINISTIC_ROUTE_SIGNALS: signals}
                )
                selector = SignalTierSelectorRequestProcessor(
                    SignalTierSelectorConfig(
                        default_tier="reasoning",
                        min_confidence=0.6,
                    )
                )

                asyncio.run(selector.process(ctx, self._request()))

                self.assertEqual(
                    ctx.metadata[CTX_DETERMINISTIC_ROUTING_TIER], tier.value
                )

    def test_low_confidence_defaults_to_reasoning(self) -> None:
        signals = self._signals(
            complexity=Complexity.SIMPLE,
            recommended_tier=RouteTier.SIMPLE,
            confidence=0.2,
        )
        ctx = ProxyContext(metadata={CTX_DETERMINISTIC_ROUTE_SIGNALS: signals})
        selector = SignalTierSelectorRequestProcessor(
            SignalTierSelectorConfig(
                default_tier="reasoning",
                min_confidence=0.6,
            )
        )

        asyncio.run(selector.process(ctx, self._request()))

        self.assertEqual(
            ctx.metadata[CTX_DETERMINISTIC_ROUTING_TIER], "reasoning"
        )

    @staticmethod
    def _request() -> ChatRequest:
        return ChatRequest(
            ChatRequestType.OPENAI_CHAT,
            {
                "model": "employee-it",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    @staticmethod
    def _signals(
        *,
        complexity: Complexity,
        recommended_tier: RouteTier,
        confidence: float = 1.0,
    ) -> RouteSignals:
        return RouteSignals(
            task_type=TaskType.CHAT,
            complexity=complexity,
            reasoning_depth=ReasoningDepth.NONE,
            tool_planning_required=False,
            precision_requirement=PrecisionRequirement.LOW,
            context_dependency=ContextDependency.LATEST_MESSAGE,
            structured_output_risk=RiskLevel.LOW,
            recommended_tier=recommended_tier,
            confidence=confidence,
            reason_code=ReasonCode.SIMPLE_QA,
            abstain=False,
        )

    def test_app_exposes_only_the_employee_it_route(self) -> None:
        with patch.dict(
            os.environ,
            {"INFERENCE_HUB_API": "test-nvidia", "GOOGLE_API": "test-google"},
            clear=False,
        ):
            with TestClient(create_app()) as client:
                self.assertEqual(client.get("/health").status_code, 200)
                response = client.get("/v1/models")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [model["id"] for model in response.json()["data"]],
            ["employee-it"],
        )

    def test_stats_endpoint_is_available(self) -> None:
        with patch.dict(
            os.environ,
            {"INFERENCE_HUB_API": "test-nvidia", "GOOGLE_API": "test-google"},
            clear=False,
        ):
            with TestClient(create_app()) as client:
                response = client.get("/v1/stats")

        self.assertEqual(response.status_code, 200)
        self.assertIn("tiers", response.json())


if __name__ == "__main__":
    unittest.main()

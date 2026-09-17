import json
from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "switchyard.toml"


class SwitchyardConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))

    def test_four_generation_targets(self) -> None:
        targets = self.config["targets"]

        self.assertEqual(
            targets["simple"]["id"],
            "Qwen/Qwen3-30B-A3B-Instruct-2507",
        )
        self.assertEqual(targets["medium"]["id"], "zai-org/GLM-5.3-Flash")
        self.assertEqual(
            targets["medium"]["extra_body"]["reasoning_effort"],
            "low",
        )
        self.assertEqual(targets["complex"]["id"], "google/gemini-3.8-flash")
        self.assertEqual(
            targets["reasoning"]["id"],
            "google/gemini-3.1-pro-preview-customtools",
        )

    def test_classifier_selects_all_four_targets(self) -> None:
        route = self.config["routes"]["employee_it"]

        self.assertEqual(route["classifier_target"], "classifier")
        self.assertEqual(
            route["targets"],
            ["reasoning", "complex", "medium", "simple"],
        )
        self.assertEqual(route["default_target"], "complex")
        self.assertTrue(route["session_affinity"])
        self.assertEqual(route["policy"]["type"], "target_selector")
        self.assertEqual(route["policy"]["selector"], "/target")

        response_schema = json.loads(route["response_schema"])
        self.assertEqual(response_schema["type"], "object")
        self.assertFalse(response_schema["additionalProperties"])
        self.assertEqual(response_schema["required"], ["target"])
        self.assertEqual(set(response_schema["properties"]), {"target"})
        self.assertEqual(response_schema["properties"]["target"]["type"], "string")
        self.assertEqual(
            response_schema["properties"]["target"]["enum"],
            ["simple", "medium", "complex", "reasoning"],
        )
        self.assertEqual(
            set(response_schema["properties"]["target"]["enum"]),
            set(route["targets"]),
        )

    def test_router_uses_nebius_and_vertex(self) -> None:
        clients = self.config["llm_clients"]
        targets = self.config["targets"]

        self.assertEqual(set(clients), {"nebius", "vertex"})
        self.assertEqual(
            clients["nebius"]["base_url"],
            "https://api.tokenfactory.nebius.com/v1/",
        )
        self.assertEqual(clients["nebius"]["api_key_env"], "NEBIUS_API_KEY")
        self.assertEqual(clients["vertex"]["api_key_env"], "VERTEX_ACCESS_TOKEN")
        self.assertEqual(
            targets["classifier"]["id"],
            "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
        )
        self.assertEqual(targets["classifier"]["llm_client"], "nebius")
        self.assertNotIn("extra_body", targets["classifier"])
        self.assertEqual(targets["simple"]["llm_client"], "nebius")
        self.assertEqual(targets["medium"]["llm_client"], "nebius")
        self.assertEqual(targets["complex"]["llm_client"], "vertex")
        self.assertEqual(targets["reasoning"]["llm_client"], "vertex")

    def test_classifier_prompt_covers_the_operational_demo_request(self) -> None:
        prompt = self.config["routes"]["employee_it"]["prompt"]

        self.assertIn("My laptop will not turn on", prompt)
        self.assertIn("morning. Can you help?\" -> complex", prompt)
        self.assertIn("Infer the operational work implied", prompt)


if __name__ == "__main__":
    unittest.main()

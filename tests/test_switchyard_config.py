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

        self.assertEqual(targets["simple"]["id"], "nvidia/qwen/qwen3.8-27b")
        self.assertEqual(targets["medium"]["id"], "zai-org/GLM-5.3-Flash")
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
        self.assertEqual(route["default_target"], "reasoning")
        self.assertTrue(route["session_affinity"])
        self.assertEqual(route["policy"]["selector"], "/decision/target")

    def test_router_uses_three_configured_providers(self) -> None:
        clients = self.config["llm_clients"]

        self.assertEqual(clients["nvidia"]["api_key_env"], "INFERENCE_HUB_API")
        self.assertEqual(clients["nebius"]["api_key_env"], "NEBIUS_API_KEY")
        self.assertEqual(clients["vertex"]["api_key_env"], "VERTEX_ACCESS_TOKEN")

    def test_classifier_prompt_covers_the_operational_demo_request(self) -> None:
        prompt = self.config["routes"]["employee_it"]["prompt"]

        self.assertIn("My laptop will not turn on", prompt)
        self.assertIn("morning. Can you help?\" -> complex", prompt)
        self.assertIn("Infer the operational work implied", prompt)


if __name__ == "__main__":
    unittest.main()

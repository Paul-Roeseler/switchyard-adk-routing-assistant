import os
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from switchyard import build_switchyard_app
from switchyard.cli.route_bundle import (
    load_route_bundle_table,
    parse_routing_profiles_file,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "switchyard.yaml"


class SwitchyardConfigTests(unittest.TestCase):
    def test_model_roles(self) -> None:
        route = parse_routing_profiles_file(CONFIG)["routes"]["employee-it"]

        self.assertEqual(route["classifier"]["model"], "nvidia/zai-org/glm-5.2")
        self.assertEqual(route["weak"]["model"], "gemini-3.6-flash")
        self.assertEqual(route["strong"]["model"], "nvidia/zai-org/glm-5.2")

    def test_stock_route_builds(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"GOOGLE_API": "test-google", "INFERENCE_HUB_API": "test-nvidia"},
            ),
            patch(
                "switchyard.cli.route_bundle._default_discovery_fn",
                return_value=[],
            ),
        ):
            routes = load_route_bundle_table(CONFIG)

        self.assertEqual(routes.default_model(), "employee-it")
        self.assertIn("employee-it", routes.registered_models())

        with TestClient(build_switchyard_app(routes)) as client:
            self.assertEqual(client.get("/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()

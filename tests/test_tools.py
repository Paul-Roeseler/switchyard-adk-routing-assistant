import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from employee_it_agent import tools
from employee_it_agent.agent import INSTRUCTION, root_agent, submit_it_request_tool


class TicketToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        runtime_path = Path(self.temporary_directory.name) / "employee_it.json"
        self.runtime_patch = patch.object(tools, "RUNTIME_STATE_PATH", runtime_path)
        self.runtime_patch.start()

    def tearDown(self) -> None:
        self.runtime_patch.stop()
        self.temporary_directory.cleanup()

    def test_submit_persists_ticket_and_open_ticket_lookup_finds_it(self) -> None:
        result = tools.submit_it_request(
            request_type="hardware_incident",
            subject="Laptop does not power on",
            description="Charging and docking checks completed; no power.",
            business_impact="Unable to work today.",
            priority="P2",
        )

        self.assertTrue(result["submitted"])
        self.assertEqual(result["ticket"]["ticket_id"], "INC-1843")
        self.assertTrue(tools.RUNTIME_STATE_PATH.exists())
        self.assertIn(
            "INC-1843",
            {
                ticket["ticket_id"]
                for ticket in tools.get_my_open_tickets()["tickets"]
            },
        )

    def test_submit_rejects_duplicate_hardware_ticket(self) -> None:
        arguments = {
            "request_type": "hardware_incident",
            "subject": "Laptop does not power on",
            "description": "No power after standard checks.",
            "business_impact": "Unable to work.",
            "priority": "P2",
        }

        first = tools.submit_it_request(**arguments)
        second = tools.submit_it_request(**arguments)

        self.assertTrue(first["submitted"])
        self.assertFalse(second["submitted"])
        self.assertEqual(second["status"], "duplicate")
        runtime_state = json.loads(tools.RUNTIME_STATE_PATH.read_text())
        hardware_tickets = [
            ticket
            for ticket in runtime_state["tickets"]
            if ticket["category"] == "Hardware"
        ]
        self.assertEqual(len(hardware_tickets), 1)

    def test_submission_tool_requires_adk_confirmation(self) -> None:
        requires_confirmation = asyncio.run(
            submit_it_request_tool.check_require_confirmation({}, None)
        )

        self.assertTrue(requires_confirmation)

    def test_agent_uses_only_operational_tools(self) -> None:
        tool_names = {
            tool.name if hasattr(tool, "name") else tool.__name__
            for tool in root_agent.tools
        }

        self.assertEqual(
            tool_names,
            {
                "get_my_device",
                "get_my_open_tickets",
                "draft_it_request",
                "submit_it_request",
            },
        )
        self.assertIn("A broken or non-functioning device", INSTRUCTION)


if __name__ == "__main__":
    unittest.main()

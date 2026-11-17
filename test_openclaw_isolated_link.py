"""
Verification Suite for OpenClaw Isolated Dedicated Link & Architecture Separation.
Tests:
1. Complete separation of ExamRankers platform and OpenClaw
2. Official source tracking (https://github.com/openclaw/openclaw.git)
3. Dedicated /openclaw/ portal rendering and status API
4. Render multi-service configuration in render.yaml
"""

import os
import sys
import json
import unittest
import urllib.parse
from io import BytesIO

# Ensure repo root is on sys.path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)

from app.openclaw_proxy import (
    render_openclaw_portal_html,
    is_openclaw_cli_available,
    is_gateway_online,
    handle_openclaw_route,
    OPENCLAW_REPO_URL,
    OPENCLAW_GATEWAY_PORT
)


class DummyHTTPHandler:
    def __init__(self, command="GET", path="/openclaw", headers=None, body=b""):
        self.command = command
        self.path = path
        self.headers = headers or {}
        if body and "Content-Length" not in self.headers:
            self.headers["Content-Length"] = str(len(body))
        self.rfile = BytesIO(body)
        self.status_code = None
        self.response_headers = {}
        self.wfile = BytesIO()

    def send_response(self, code):
        self.status_code = code

    def send_header(self, k, v):
        self.response_headers[k] = v

    def end_headers(self):
        pass


class TestOpenClawIsolatedLink(unittest.TestCase):

    def test_01_official_source_metadata(self):
        """Verifies official GitHub repository source reference."""
        self.assertEqual(OPENCLAW_REPO_URL, "https://github.com/openclaw/openclaw.git")
        self.assertEqual(OPENCLAW_GATEWAY_PORT, 18789)

    def test_02_portal_html_rendering(self):
        """Verifies dedicated /openclaw/ management portal HTML contains official link & clean UI."""
        html = render_openclaw_portal_html()
        self.assertIn("https://github.com/openclaw/openclaw.git", html)
        self.assertIn("OpenClaw Official Gateway", html)
        self.assertIn("/openclaw/", html)
        self.assertIn("18789", html)
        self.assertIn("Render", html)

    def test_03_status_api_endpoint(self):
        """Verifies /openclaw/api/status returns JSON with official source and port."""
        handler = DummyHTTPHandler(command="GET", path="/openclaw/api/status")
        handled = handle_openclaw_route(handler, "/openclaw/api/status")
        self.assertTrue(handled)
        self.assertEqual(handler.status_code, 200)

        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("source"), "https://github.com/openclaw/openclaw.git")
        self.assertEqual(data.get("port"), 18789)
        self.assertIn("cli_installed", data)

    def test_04_portal_get_route(self):
        """Verifies GET /openclaw and /openclaw/ route handler."""
        handler = DummyHTTPHandler(command="GET", path="/openclaw/")
        handled = handle_openclaw_route(handler, "/openclaw/")
        self.assertTrue(handled)
        self.assertEqual(handler.status_code, 200)
        body = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("OpenClaw Official Gateway", body)

    def test_05_render_yaml_separation(self):
        """Verifies render.yaml contains both separate services: platform and openclaw."""
        yaml_path = os.path.join(REPO_ROOT, "render.yaml")
        self.assertTrue(os.path.exists(yaml_path), "render.yaml must exist")
        with open(yaml_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("exam-rankers-bot", content)
        self.assertIn("openclaw-gateway", content)
        self.assertIn("ghcr.io/openclaw/openclaw:latest", content)
        self.assertIn("https://github.com/openclaw/openclaw.git", content)

    def test_06_complete_codebase_isolation(self):
        """Verifies that the bot, store, and admin modules do NOT import any old agents."""
        with open(os.path.join(REPO_ROOT, "app", "bot.py"), "r", encoding="utf-8") as f:
            bot_code = f.read()
        self.assertNotIn("openclaw_orchestrator", bot_code)
        self.assertNotIn("BaseSeniorAgent", bot_code)
        self.assertNotIn("ChiefExecutiveOfficer", bot_code)

        with open(os.path.join(REPO_ROOT, "app", "admin_panel.py"), "r", encoding="utf-8") as f:
            admin_code = f.read()
        self.assertNotIn("openclawControlBox", admin_code)
        self.assertNotIn("openclawDetailModal", admin_code)

    def test_07_agent_team_api_list(self):
        """Verifies /openclaw/api/agents returns default agent roster."""
        handler = DummyHTTPHandler(command="GET", path="/openclaw/api/agents")
        handled = handle_openclaw_route(handler, "/openclaw/api/agents")
        self.assertTrue(handled)
        self.assertEqual(handler.status_code, 200)
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data.get("success"))
        self.assertGreaterEqual(len(data.get("agents", [])), 5)
        agent_names = [a.get("name") for a in data.get("agents", [])]
        self.assertTrue(any("Objection Lead" in name for name in agent_names))

    def test_08_onboard_and_delete_agent_flow(self):
        """Verifies onboarding a new specialist agent and deleting it."""
        # 1. Onboard
        payload = {
            "name": "Custom Syllabus Agent",
            "role": "Curriculum Expert",
            "department": "Academics",
            "icon": "🎓",
            "model": "nvidia/nemotron-3.5-lightning:free",
            "instructions": "Verify MPSC syllabus changes."
        }
        handler = DummyHTTPHandler(
            command="POST",
            path="/openclaw/api/agents/onboard",
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload).encode("utf-8")
        )
        handled = handle_openclaw_route(handler, "/openclaw/api/agents/onboard")
        self.assertTrue(handled)
        self.assertEqual(handler.status_code, 200)
        res_data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(res_data.get("success"))
        agent_id = res_data["agent"]["id"]
        self.assertEqual(res_data["agent"]["name"], "Custom Syllabus Agent")

        # 2. Verify agent in list
        list_handler = DummyHTTPHandler(command="GET", path="/openclaw/api/agents")
        handle_openclaw_route(list_handler, "/openclaw/api/agents")
        list_data = json.loads(list_handler.wfile.getvalue().decode("utf-8"))
        found = any(a["id"] == agent_id for a in list_data.get("agents", []))
        self.assertTrue(found)

        # 3. Delete agent
        del_handler = DummyHTTPHandler(
            command="POST",
            path="/openclaw/api/agents/delete",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"agent_id": agent_id}).encode("utf-8")
        )
        handle_openclaw_route(del_handler, "/openclaw/api/agents/delete")
        self.assertEqual(del_handler.status_code, 200)
        del_res = json.loads(del_handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(del_res.get("success"))


if __name__ == "__main__":
    unittest.main()


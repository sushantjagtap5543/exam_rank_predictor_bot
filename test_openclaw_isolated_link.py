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
    def __init__(self, command="GET", path="/openclaw", headers=None):
        self.command = command
        self.path = path
        self.headers = headers or {}
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


if __name__ == "__main__":
    unittest.main()

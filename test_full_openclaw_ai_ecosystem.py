"""
Comprehensive Enterprise Test Suite for OpenClaw.ai Bot/Agents Ecosystem.
Verifies:
1. All 5 Specialist Agents + General Executive + Dynamic Custom Agents
2. Full Persona-Aware Task Execution (Objections, Quizzes, Notes, Cutoff SWOT, Marketing)
3. All 5 Built-in AgentSkills Execution
4. All 4 Scheduled Autonomous Crons Triggering
5. Interactive Live Widgets (Normalization Calculator Simulator)
6. Split-Pane Control UI HTML Rendering (ChatGPT-Style Assistant + Widgets)
7. Native Daemon TCP Loopback Server on 127.0.0.1:18789
8. 100% Architectural Isolation & Decoupling from ExamRankers Core Platform
"""

import os
import sys
import json
import time
import unittest
from io import BytesIO

# Ensure repo root is on sys.path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)

import httpx
from app.openclaw_proxy import (
    handle_openclaw_route,
    render_openclaw_dashboard_html,
    render_openclaw_portal_html,
    get_registered_agents,
    save_registered_agents,
    execute_openclaw_agent_task,
    execute_openclaw_skill,
    execute_openclaw_cron,
    calculate_normalization,
    start_gateway_background,
    is_gateway_online,
    is_openclaw_cli_available,
    DEFAULT_AGENTS_TEAM,
    DEFAULT_SKILLS,
    DEFAULT_CRON_JOBS,
    OPENCLAW_GATEWAY_PORT,
    OPENCLAW_AI_URL,
    OPENCLAW_REPO_URL
)


class MockHTTPHandler:
    """Mock handler simulating Python's BaseHTTPRequestHandler for unit tests."""
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


class TestFullOpenClawAiEcosystem(unittest.TestCase):

    def test_01_gateway_status_and_telemetry(self):
        """1. Verifies OpenClaw.ai system status, port, telemetry, and source."""
        handler = MockHTTPHandler(command="GET", path="/openclaw/api/status")
        handled = handle_openclaw_route(handler, "/openclaw/api/status")
        self.assertTrue(handled)
        self.assertEqual(handler.status_code, 200)

        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("online"))
        self.assertEqual(data.get("framework"), "openclaw.ai")
        self.assertEqual(data.get("port"), OPENCLAW_GATEWAY_PORT)
        self.assertGreaterEqual(data.get("total_agents", 0), 5)
        self.assertEqual(data.get("total_skills"), 5)
        self.assertEqual(data.get("total_crons"), 4)

    def test_02_all_preconfigured_specialist_agents(self):
        """2. Verifies that all 5 official specialist agents are loaded in roster."""
        handler = MockHTTPHandler(command="GET", path="/openclaw/api/agents")
        handle_openclaw_route(handler, "/openclaw/api/agents")
        self.assertEqual(handler.status_code, 200)

        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data.get("success"))
        agents = data.get("agents", [])
        agent_ids = [a["id"] for a in agents]

        expected_ids = [
            "agent_objection",
            "agent_content",
            "agent_quiz",
            "agent_analytics",
            "agent_marketing"
        ]
        for eid in expected_ids:
            self.assertIn(eid, agent_ids, f"Specialist agent '{eid}' must be registered.")

    def test_03_agent_execution_objection_lead(self):
        """3. Tests Objection Lead agent task execution: returns Balbharati & GR citations."""
        handler = MockHTTPHandler(
            command="POST",
            path="/openclaw/api/gateway/run",
            headers={"Content-Type": "application/json"},
            body=json.dumps({
                "prompt": "MPSC मराठी व्याकरण समास प्रश्नावर आक्षेप अर्ज तयार करा.",
                "agent_id": "agent_objection",
                "model": "nvidia/nemotron-3.5-lightning:free"
            }).encode("utf-8")
        )
        handled = handle_openclaw_route(handler, "/openclaw/api/gateway/run")
        self.assertTrue(handled)
        self.assertEqual(handler.status_code, 200)

        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data.get("success"))
        resp = data.get("response", "")
        self.assertIn("आक्षेप", resp)
        self.assertIn("बालभारती", resp)
        self.assertIn("कुमारभारती", resp)
        self.assertIn("शासन निर्णय", resp)

    def test_04_agent_execution_quiz_master(self):
        """4. Tests Quiz Master agent task execution: returns 4-option MCQs with memory tricks."""
        handler = MockHTTPHandler(
            command="POST",
            path="/openclaw/api/gateway/run",
            headers={"Content-Type": "application/json"},
            body=json.dumps({
                "prompt": "महाराष्ट्राच्या इतिहासावर दैनिक क्विझ पोल तयार करा.",
                "agent_id": "agent_quiz",
                "model": "nvidia/nemotron-3.5-lightning:free"
            }).encode("utf-8")
        )
        handled = handle_openclaw_route(handler, "/openclaw/api/gateway/run")
        self.assertTrue(handled)
        self.assertEqual(handler.status_code, 200)

        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data.get("success"))
        resp = data.get("response", "")
        self.assertIn("क्विझ", resp)
        self.assertIn("(A)", resp)
        self.assertIn("(B)", resp)
        self.assertIn("मेमरी ट्रिक", resp)

    def test_05_agent_execution_content_architect(self):
        """5. Tests Content Architect agent: returns high-weightage study notes & formulas."""
        handler = MockHTTPHandler(
            command="POST",
            path="/openclaw/api/gateway/run",
            headers={"Content-Type": "application/json"},
            body=json.dumps({
                "prompt": "MPSC राज्यसेवा २०२६ साठी सामान्य ज्ञान रिव्हिजन नोट्स द्या.",
                "agent_id": "agent_content",
                "model": "nvidia/nemotron-3.5-lightning:free"
            }).encode("utf-8")
        )
        handle_openclaw_route(handler, "/openclaw/api/gateway/run")
        self.assertEqual(handler.status_code, 200)

        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data.get("success"))
        resp = data.get("response", "")
        self.assertIn("रिव्हिजन", resp)
        self.assertIn("गोल्डन पॉईंट्स", resp)

    def test_06_agent_execution_rank_auditor(self):
        """6. Tests Rank & Cut-off Auditor agent: returns Raw Score, Normalization & SWOT analysis."""
        handler = MockHTTPHandler(
            command="POST",
            path="/openclaw/api/gateway/run",
            headers={"Content-Type": "application/json"},
            body=json.dumps({
                "prompt": "TCS नगरपरिषद Shift 2 मधील Raw Score 138 चे गुण व कट-ऑफ सांगा.",
                "agent_id": "agent_analytics",
                "model": "nvidia/nemotron-3.5-lightning:free"
            }).encode("utf-8")
        )
        handle_openclaw_route(handler, "/openclaw/api/gateway/run")
        self.assertEqual(handler.status_code, 200)

        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data.get("success"))
        resp = data.get("response", "")
        self.assertIn("नॉर्मलायझेशन", resp)
        self.assertIn("कट-ऑफ", resp)
        self.assertIn("SWOT", resp)

    def test_07_agent_execution_marketing_lead(self):
        """7. Tests Marketing Executive agent: returns viral promo post with discount and CTA."""
        handler = MockHTTPHandler(
            command="POST",
            path="/openclaw/api/gateway/run",
            headers={"Content-Type": "application/json"},
            body=json.dumps({
                "prompt": "MPSC GS मास्टर ई-बुकच्या ₹४९ ऑफरसाठी टेलिग्राम जाहिरात लिहा.",
                "agent_id": "agent_marketing",
                "model": "nvidia/nemotron-3.5-lightning:free"
            }).encode("utf-8")
        )
        handle_openclaw_route(handler, "/openclaw/api/gateway/run")
        self.assertEqual(handler.status_code, 200)

        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data.get("success"))
        resp = data.get("response", "")
        self.assertIn("ऑफर", resp)
        self.assertIn("₹४९", resp)

    def test_08_dynamic_agent_onboard_chat_delete_lifecycle(self):
        """8. Tests complete lifecycle: Onboard new specialist agent, dispatch task, delete."""
        # A. Onboard
        payload = {
            "name": "सिव्हिल इंजिनिअरिंग फॅकल्टी (Civil Faculty)",
            "role": "Technical Specialist",
            "department": "Engineering Advisory",
            "icon": "🏗️",
            "model": "qwen/qwen-2.5-coder-32b-instruct:free",
            "instructions": "PWD व WRD परीक्षेतील स्ट्रक्चरल अनालिसिस व सोम (SOM) विषयाचे विश्लेषण करा."
        }
        onboard_handler = MockHTTPHandler(
            command="POST",
            path="/openclaw/api/agents/onboard",
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload).encode("utf-8")
        )
        handle_openclaw_route(onboard_handler, "/openclaw/api/agents/onboard")
        self.assertEqual(onboard_handler.status_code, 200)
        res = json.loads(onboard_handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(res.get("success"))
        agent_id = res["agent"]["id"]

        # B. Dispatch task to new agent
        task_handler = MockHTTPHandler(
            command="POST",
            path="/openclaw/api/gateway/run",
            headers={"Content-Type": "application/json"},
            body=json.dumps({
                "prompt": "PWD कनिष्ठ अभियंता परीक्षेसाठी ५ मुख्य सूत्रे सांगा.",
                "agent_id": agent_id
            }).encode("utf-8")
        )
        handle_openclaw_route(task_handler, "/openclaw/api/gateway/run")
        self.assertEqual(task_handler.status_code, 200)
        task_res = json.loads(task_handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(task_res.get("success"))
        self.assertIn("कार्यपूर्ती अहवाल", task_res.get("response", ""))

        # C. Delete custom agent
        del_handler = MockHTTPHandler(
            command="POST",
            path="/openclaw/api/agents/delete",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"agent_id": agent_id}).encode("utf-8")
        )
        handle_openclaw_route(del_handler, "/openclaw/api/agents/delete")
        self.assertEqual(del_handler.status_code, 200)
        del_data = json.loads(del_handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(del_data.get("success"))

    def test_09_all_5_built_in_skills_execution(self):
        """9. Verifies execution of all 5 built-in OpenClaw AgentSkills."""
        skills = DEFAULT_SKILLS
        self.assertEqual(len(skills), 5)

        for s in skills:
            handler = MockHTTPHandler(
                command="POST",
                path="/openclaw/api/skills/run",
                headers={"Content-Type": "application/json"},
                body=json.dumps({"skill_id": s["id"]}).encode("utf-8")
            )
            handled = handle_openclaw_route(handler, "/openclaw/api/skills/run")
            self.assertTrue(handled)
            self.assertEqual(handler.status_code, 200)

            data = json.loads(handler.wfile.getvalue().decode("utf-8"))
            self.assertTrue(data.get("success"), f"Skill '{s['id']}' execution must succeed.")
            self.assertIn("output", data)
            self.assertTrue(len(data["output"]) > 10)

    def test_10_all_4_scheduled_crons_trigger(self):
        """10. Verifies triggering of all 4 scheduled autonomous automations."""
        crons = DEFAULT_CRON_JOBS
        self.assertEqual(len(crons), 4)

        for c in crons:
            handler = MockHTTPHandler(
                command="POST",
                path="/openclaw/api/cron/run",
                headers={"Content-Type": "application/json"},
                body=json.dumps({"cron_id": c["id"]}).encode("utf-8")
            )
            handled = handle_openclaw_route(handler, "/openclaw/api/cron/run")
            self.assertTrue(handled)
            self.assertEqual(handler.status_code, 200)

            data = json.loads(handler.wfile.getvalue().decode("utf-8"))
            self.assertTrue(data.get("success"), f"Cron '{c['id']}' trigger must succeed.")
            self.assertIn("यशस्वीरित्या", data.get("message", ""))

    def test_11_live_widget_normalization_calculator(self):
        """11. Tests the interactive normalization calculator live widget endpoint."""
        payload = {
            "raw_score": 145.0,
            "deduction": 5.25,
            "factor": 1.08
        }
        handler = MockHTTPHandler(
            command="POST",
            path="/openclaw/api/calculator/normalize",
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload).encode("utf-8")
        )
        handled = handle_openclaw_route(handler, "/openclaw/api/calculator/normalize")
        self.assertTrue(handled)
        self.assertEqual(handler.status_code, 200)

        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data.get("success"))
        # (145.0 - 5.25) * 1.08 = 139.75 * 1.08 = 150.93
        self.assertAlmostEqual(data.get("normalized_score"), 150.93, places=1)
        self.assertGreater(data.get("estimated_percentile"), 70.0)

    def test_12_full_control_ui_split_pane_rendering(self):
        """12. Verifies GET /openclaw/ renders the complete OpenClaw.ai Control UI."""
        handler = MockHTTPHandler(command="GET", path="/openclaw/")
        handled = handle_openclaw_route(handler, "/openclaw/")
        self.assertTrue(handled)
        self.assertEqual(handler.status_code, 200)

        body = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("OpenClaw.ai", body)
        self.assertIn("Control UI", body)
        self.assertIn("chat-pane", body)
        self.assertIn("widget-pane", body)
        self.assertIn("chatStream", body)
        self.assertIn("wtab-widgets", body)
        self.assertIn("normRaw", body)
        self.assertIn("Balbharati", body)
        self.assertIn("18789", body)

    def test_13_native_daemon_live_tcp_loopback(self):
        """13. Starts the Native Gateway Daemon and tests real TCP socket & HTTP probe."""
        res = start_gateway_background(OPENCLAW_GATEWAY_PORT)
        self.assertTrue(res.get("success"))
        self.assertTrue(is_gateway_online(1.0))
        self.assertTrue(is_openclaw_cli_available()[0])

        # Test real HTTP call to loopback port
        url = f"http://127.0.0.1:{OPENCLAW_GATEWAY_PORT}/api/status"
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(url)
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertTrue(data.get("online"))
                self.assertEqual(data.get("port"), OPENCLAW_GATEWAY_PORT)
        except Exception as e:
            self.fail(f"Could not connect to Native OpenClaw Daemon on port {OPENCLAW_GATEWAY_PORT}: {e}")

    def test_14_total_isolation_from_examrankers_core(self):
        """14. Verifies total architectural isolation between ExamRankers Core and OpenClaw."""
        with open(os.path.join(REPO_ROOT, "app", "bot.py"), "r", encoding="utf-8") as f:
            bot_code = f.read()
        self.assertNotIn("class NativeOpenClawGatewayHandler", bot_code)
        self.assertNotIn("DEFAULT_AGENTS_TEAM", bot_code)
        self.assertNotIn("DEFAULT_SKILLS", bot_code)

        with open(os.path.join(REPO_ROOT, "app", "admin_panel.py"), "r", encoding="utf-8") as f:
            admin_code = f.read()
        self.assertNotIn("render_openclaw_dashboard_html", admin_code)
        self.assertNotIn("execute_openclaw_agent_task", admin_code)

    def test_15_artifact_download_stream_and_api(self):
        """15. Verifies that generated artifacts can be listed via API and downloaded via HTTP."""
        # A. Verify artifacts API
        handler = MockHTTPHandler(command="GET", path="/openclaw/api/artifacts")
        handle_openclaw_route(handler, "/openclaw/api/artifacts")
        self.assertEqual(handler.status_code, 200)
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertTrue(data.get("success"))
        self.assertGreater(data.get("total", 0), 0)

        # B. Download first artifact
        first_art = data["artifacts"][0]
        dl_url = first_art["url"]
        dl_handler = MockHTTPHandler(command="GET", path=dl_url)
        handle_openclaw_route(dl_handler, dl_url)
        self.assertEqual(dl_handler.status_code, 200)
        content_bytes = dl_handler.wfile.getvalue()
        self.assertGreater(len(content_bytes), 20)
        self.assertIn("attachment", dl_handler.response_headers.get("Content-Disposition", ""))


if __name__ == "__main__":
    unittest.main()


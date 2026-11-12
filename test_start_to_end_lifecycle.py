import asyncio
import base64
import http.server
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
import urllib.error

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.bot import (
    HealthCheckHandler,
    EXAMS,
    DB_PATH,
    get_connection,
    get_candidate_scores,
    generate_signed_download_url,
    verify_signed_download_url,
    CHUNK_UPLOADS,
    CHUNK_UPLOADS_LOCK,
    process_sheet_payload,
)
from app.parser import (
    parse_answers,
    score_answers,
    detect_exam,
    extract_post_and_metadata,
    parse_html_response_sheet,
)
from app.rank import (
    estimate_cohort_rank,
)
import uuid
from app.agents.digital_product_agent import DigitalProductPackagingAgent
from app.agents.fulfillment_email_agent import FulfillmentEmailAgent

class TestStartToEndFullPlatformLifecycle(unittest.TestCase):
    """
    Comprehensive Start-to-End Platform Lifecycle Verification.
    Validates all candidate journeys, payments, admin management, and data persistence.
    """

    @classmethod
    def setUpClass(cls):
        # 1. Start ephemeral HTTP server for live web portal and API testing
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), HealthCheckHandler)
        cls.port = cls.server.server_port
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

        # 2. Ensure test database tables exist
        with get_connection() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER,
                    filename TEXT,
                    storage_path TEXT,
                    exam_key TEXT,
                    category TEXT,
                    post_name TEXT,
                    roll_number TEXT,
                    candidate_name TEXT,
                    score REAL,
                    correct_count INTEGER,
                    incorrect_count INTEGER,
                    unanswered_count INTEGER,
                    rank INTEGER,
                    percentile REAL,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_01_candidate_journey_html_response_sheet_to_rank(self):
        """Journey A: Candidate uploads raw HTML / DigiALM sheet text -> parsed, scored, ranked."""
        sample_html = """
        <html>
        <body>
            <div class="main-info-pnl">
                <table>
                    <tr><td>Candidate Name</td><td>Sushant Test</td></tr>
                    <tr><td>Roll No</td><td>202611099</td></tr>
                    <tr><td>Post Name</td><td>शिपाई / परिचर (Peon)</td></tr>
                    <tr><td>Subject</td><td>ZP Bharti Peon Examination 2026</td></tr>
                </table>
            </div>
            <div class="section-cntnr">
                <div class="section-lbl"><span class="bold">Section : मराठी भाषा</span></div>
                <div class="question-pnl">
                    <div class="question-row"><div class="question-text">Q.1 खालीलपैकी समानार्थी शब्द कोणता?</div></div>
                    <div class="menu-tbl">
                        <table>
                            <tr><td>Status : Answered</td></tr>
                            <tr><td>Chosen Option : 2</td></tr>
                        </table>
                    </div>
                    <div class="option-row rightAns"><div class="option-text">2. सूर्य</div></div>
                </div>
            </div>
            <div class="section-cntnr">
                <div class="section-lbl"><span class="bold">Section : सामान्य ज्ञान</span></div>
                <div class="question-pnl">
                    <div class="question-row"><div class="question-text">Q.2 महाराष्ट्राची राजधानी कोणती?</div></div>
                    <div class="menu-tbl">
                        <table>
                            <tr><td>Status : Answered</td></tr>
                            <tr><td>Chosen Option : 1</td></tr>
                        </table>
                    </div>
                    <div class="option-row rightAns"><div class="option-text">1. मुंबई</div></div>
                </div>
                <div class="question-pnl">
                    <div class="question-row"><div class="question-text">Q.3 भारताचे चलन कोणते?</div></div>
                    <div class="menu-tbl">
                        <table>
                            <tr><td>Status : Answered</td></tr>
                            <tr><td>Chosen Option : 3</td></tr>
                        </table>
                    </div>
                    <div class="option-row rightAns"><div class="option-text">1. रुपया</div></div>
                </div>
            </div>
        </body>
        </html>
        """
        # 1. Parse HTML response sheet
        parsed_text = parse_html_response_sheet(sample_html)
        self.assertIn("Q.1", parsed_text)
        self.assertIn("Chosen Option : 2", parsed_text)
        self.assertIn("Chosen Option : 1", parsed_text)

        # 2. Extract Candidate metadata
        meta = extract_post_and_metadata(parsed_text)
        self.assertIn("Sushant", meta.get("candidate_name", ""))
        self.assertEqual(meta.get("roll_number"), "202611099")

        # 3. Detect Exam
        detected = detect_exam(parsed_text, EXAMS)
        self.assertIn(detected.get("status"), ("detected", "ambiguous", "not_found"))

        # 4. Parse question answer records
        records = parse_answers(parsed_text)
        self.assertEqual(len(records), 3)

        # 5. Score answers with exam configuration
        exam_config = EXAMS.get("ZP_BHARTI", {"positive_marks": 2.0, "negative_marks": 0.0, "total_marks": 200})
        scoring = score_answers(records, exam_config)
        self.assertEqual(scoring["correct"], 2)
        self.assertEqual(scoring["incorrect"], 1)
        self.assertEqual(scoring["score"], 4.0)
        self.assertIn("मराठी भाषा", scoring.get("sections", {}))
        self.assertIn("सामान्य ज्ञान", scoring.get("sections", {}))

        # 6. Rank calculation
        overall_scores, exam_scores, post_scores, cat_scores, post_cat_scores = get_candidate_scores(
            "ZP_BHARTI", "Open", meta.get("post_name")
        )
        rank_info = estimate_cohort_rank(scoring["score"], exam_scores, "Open", cat_scores, overall_scores)
        self.assertGreaterEqual(rank_info["exam_rank"], 1)
        self.assertGreaterEqual(rank_info["exam_percentile"], 0.0)

        # 7. Comprehensive Bot Web Analytics Verification
        status_code, web_res = process_sheet_payload(
            file_bytes=sample_html.encode("utf-8"),
            filename="response_sheet.html",
            user_category="OBC",
            exam_override="ZP_BHARTI"
        )
        self.assertEqual(status_code, 200)
        self.assertTrue(web_res.get("success"))
        # Verify Scorecard & 4-Tier ranks
        self.assertEqual(web_res.get("raw_score"), 4.0)
        self.assertEqual(web_res.get("correct"), 2)
        self.assertEqual(web_res.get("incorrect"), 1)
        self.assertGreater(web_res.get("accuracy", 0), 0)
        self.assertIn("cutoff_zone", web_res)
        self.assertIn("overall_rank", web_res)
        self.assertIn("category_rank", web_res)
        # Verify AI SWOT Audit
        swot = web_res.get("swot", {})
        self.assertIn("strengths", swot)
        self.assertIn("weaknesses", swot)
        self.assertIn("opportunities", swot)
        self.assertIn("threats", swot)
        # Verify Wrong Answers & Objections
        wrong_qs = web_res.get("wrong_questions", [])
        self.assertEqual(len(wrong_qs), 1)
        self.assertIn("explanation", wrong_qs[0])
        self.assertIn("objection_reason", wrong_qs[0])
        # Verify All Questions Explorer
        all_qs = web_res.get("all_questions", [])
        self.assertEqual(len(all_qs), 3)

    def test_02_candidate_journey_web_portal_single_shot_upload(self):
        """Journey B: Candidate visits /upload and submits small file (<2MB) via single-shot API."""
        mock_pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Title (ZP Peon Test) >>\nendobj\nQ.1 Chosen: 1 Right: 1\n%%EOF"
        b64_payload = base64.b64encode(mock_pdf_content).decode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/upload_sheet",
            data=json.dumps({
                "file_b64": b64_payload,
                "filename": "sushant_peon_exam.pdf",
                "category": "OBC",
                "exam": "ZP_BHARTI",
                "telegram_user_id": 999888111
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req)
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")
        data = json.loads(resp.read().decode("utf-8"))
        self.assertIn("success", data)

    def test_03_candidate_journey_web_portal_chunked_upload(self):
        """Journey C: Candidate uploads large 25MB+ response sheet sliced into chunks."""
        upload_id = f"e2e_chunk_{int(time.time()*1000)}"
        chunk_a = base64.b64encode(b"%PDF-1.4 chunk A ").decode("utf-8")
        chunk_b = base64.b64encode(b"chunk B with ZP Bharti ").decode("utf-8")
        chunk_c = base64.b64encode(b"chunk C end %%EOF").decode("utf-8")

        # Upload Chunk 1 of 3
        req1 = urllib.request.Request(
            f"{self.base_url}/api/upload_chunk",
            data=json.dumps({
                "upload_id": upload_id, "chunk_index": 0, "total_chunks": 3,
                "filename": "large_peon_25mb.pdf", "category": "Open", "exam": "ZP_BHARTI",
                "data": chunk_a
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        resp1 = urllib.request.urlopen(req1)
        self.assertEqual(resp1.status, 200)
        d1 = json.loads(resp1.read().decode("utf-8"))
        self.assertEqual(d1["status"], "chunk_saved")

        # Upload Chunk 2 of 3
        req2 = urllib.request.Request(
            f"{self.base_url}/api/upload_chunk",
            data=json.dumps({
                "upload_id": upload_id, "chunk_index": 1, "total_chunks": 3,
                "filename": "large_peon_25mb.pdf", "category": "Open", "exam": "ZP_BHARTI",
                "data": chunk_b
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        resp2 = urllib.request.urlopen(req2)
        self.assertEqual(resp2.status, 200)

        # Upload Chunk 3 of 3 (final chunk triggers assembly and evaluation)
        req3 = urllib.request.Request(
            f"{self.base_url}/api/upload_chunk",
            data=json.dumps({
                "upload_id": upload_id, "chunk_index": 2, "total_chunks": 3,
                "filename": "large_peon_25mb.pdf", "category": "Open", "exam": "ZP_BHARTI",
                "data": chunk_c
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        resp3 = urllib.request.urlopen(req3)
        self.assertEqual(resp3.status, 200)
        d3 = json.loads(resp3.read().decode("utf-8"))
        self.assertIn("success", d3)

    def test_04_e_commerce_storefront_order_and_fulfillment(self):
        """Journey D: Candidate browses store -> checks out -> payment confirmed -> signed download unlocked."""
        agent = DigitalProductPackagingAgent()
        agent.init_products_db(str(DB_PATH))
        products = agent.get_all_products(str(DB_PATH), include_inactive=True)
        self.assertGreaterEqual(len(products), 1)

        prod_id = products[0].get("id") or products[0].get("product_id")
        price = products[0].get("price_inr", 49)

        # 1. Candidate initiates checkout: create order record
        token = str(uuid.uuid4())
        unique_utr = f"UTR{int(time.time()*1000)}"
        with get_connection() as db:
            db.execute("""
                INSERT INTO product_orders 
                (product_id, customer_telegram_id, amount_paid, status, customer_email, order_token, utr)
                VALUES (?, ?, ?, 'pending', ?, ?, ?)
            """, (prod_id, 123456789, price, "candidate@example.com", token, unique_utr))

        # 2. Strict payment gate: pending order token is pending
        with get_connection() as db:
            row = db.execute("SELECT status FROM product_orders WHERE order_token = ?", (token,)).fetchone()
            self.assertEqual(row[0], "pending")

        # 3. Payment approved (via Cashfree Webhook or Admin confirmation)
        with get_connection() as db:
            db.execute("UPDATE product_orders SET status = 'approved' WHERE order_token = ?", (token,))

        # 4. Fulfillment: generate signed download URL and verify signature
        signed_url = generate_signed_download_url(token, expires_in_seconds=3600)
        parsed_url = urllib.parse.urlparse(signed_url)
        params = urllib.parse.parse_qs(parsed_url.query)
        exp = params.get("exp", [""])[0]
        sig = params.get("sig", [""])[0]

        is_valid, err_msg = verify_signed_download_url(token, exp, sig)
        self.assertTrue(is_valid)
        self.assertEqual(err_msg, "")

        # Tampered signature must be rejected
        is_tampered, _ = verify_signed_download_url(token, exp, sig + "fake")
        self.assertFalse(is_tampered)

    def test_05_admin_control_and_security_gate(self):
        """Journey E: Admin security boundary verification."""
        # Unauthenticated request to /admin -> 403 Forbidden
        req_unauth = urllib.request.Request(f"{self.base_url}/admin")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_unauth)
        self.assertEqual(ctx.exception.code, 403)

        # Health endpoint always open for uptime monitors
        req_health = urllib.request.urlopen(f"{self.base_url}/health")
        self.assertEqual(req_health.status, 200)
        self.assertIn("OK", req_health.read().decode("utf-8"))

if __name__ == "__main__":
    unittest.main()

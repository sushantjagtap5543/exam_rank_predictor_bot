"""
test_security_attack_script.py
Comprehensive End-to-End Security Attack Validation Suite
Covers 9 Critical Attack Vectors with 0 Vulnerabilities Allowed.
"""

import os
import sys
import unittest
import sqlite3
import tempfile
import json
import time
import hmac
import hashlib
import threading
from pathlib import Path
import urllib.request
import urllib.error
from socketserver import ThreadingMixIn
import http.server

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent))

# Set test environment
os.environ["ADMIN_API_KEY"] = "super-secret-admin-key-test-999"
os.environ["DOWNLOAD_SIGNING_KEY"] = "signing-key-test-888"
os.environ["CASHFREE_SECRET_KEY"] = "cf-secret-test-777"
os.environ["CASHFREE_APP_ID"] = "cf-app-test-111"
os.environ["CASHFREE_ENV"] = "sandbox"

from app.bot import (
    is_admin_request_authenticated,
    validate_safe_url,
    generate_signed_download_url,
    verify_signed_download_url,
    HealthCheckHandler,
    on_chat_member_updated,
    init_db,
    ADMIN_IDS
)
from app.cashfree_client import CashfreeClient
from app.agents.digital_product_agent import DigitalProductPackagingAgent

class ThreadedHTTPServer(ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

class TestSecurityAttackSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set up a clean test database
        cls.tmp_dir = tempfile.TemporaryDirectory()
        cls.test_db = Path(cls.tmp_dir.name) / "test_attack.db"
        
        # Patch app.bot.DB_PATH for HTTP server handlers
        import app.bot
        cls.orig_db_path = app.bot.DB_PATH
        app.bot.DB_PATH = str(cls.test_db)

        # Initialize schema using standard init_db and init_products_db
        init_db()
        DigitalProductPackagingAgent().init_products_db(str(cls.test_db))

        # Insert standard product for attack testing
        with sqlite3.connect(cls.test_db) as db:
            db.execute("""
                INSERT OR REPLACE INTO digital_products (id, title, subject, price_inr, original_price_inr, pages, rating, reviews_count)
                VALUES ('prod_test_book', 'Test Guide for Security', 'Current Affairs', 29, 99, 50, 4.9, 100)
            """)
            db.commit()

        # Start live test HTTP server on random port
        cls.server = ThreadedHTTPServer(("127.0.0.1", 0), HealthCheckHandler)
        cls.port = cls.server.server_address[1]
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp_dir.cleanup()
        import app.bot
        app.bot.DB_PATH = cls.orig_db_path

    # VECTOR 1: Unauthenticated request to /api/admin/* and /admin returns 403 Forbidden
    def test_vector_1_admin_endpoints_require_valid_admin_key(self):
        # 1a. /admin without X-Admin-Key
        req = urllib.request.Request(f"{self.base_url}/admin")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 403)

        # 1b. /api/admin/visitors with invalid X-Admin-Key
        req_bad = urllib.request.Request(
            f"{self.base_url}/api/admin/visitors",
            headers={"X-Admin-Key": "attacker-forged-key"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_bad)
        self.assertEqual(ctx.exception.code, 403)

        # 1c. /api/admin/sync_products POST without X-Admin-Key
        req_post = urllib.request.Request(
            f"{self.base_url}/api/admin/sync_products",
            data=b"{}",
            headers={"Content-Type": "application/json"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_post)
        self.assertEqual(ctx.exception.code, 403)

        # 1d. Legitimate X-Admin-Key should succeed
        req_auth = urllib.request.Request(
            f"{self.base_url}/api/admin/visitors",
            headers={"X-Admin-Key": "super-secret-admin-key-test-999"}
        )
        resp = urllib.request.urlopen(req_auth)
        self.assertEqual(resp.status, 200)

    # VECTOR 2: Cashfree webhook with forged or missing HMAC-SHA256 signature returns 400
    def test_vector_2_cashfree_webhook_forged_signature_rejected(self):
        webhook_body = json.dumps({
            "type": "PAYMENT_SUCCESS_WEBHOOK",
            "data": {
                "order": {"order_id": "ORD_TEST_1", "order_amount": 29.0},
                "payment": {"payment_status": "SUCCESS"}
            }
        }).encode("utf-8")

        # 2a. Missing signature
        req_missing = urllib.request.Request(
            f"{self.base_url}/api/cashfree/webhook",
            data=webhook_body,
            headers={"Content-Type": "application/json"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_missing)
        self.assertEqual(ctx.exception.code, 400)

        # 2b. Forged signature
        req_forged = urllib.request.Request(
            f"{self.base_url}/api/cashfree/webhook",
            data=webhook_body,
            headers={
                "Content-Type": "application/json",
                "x-webhook-timestamp": str(int(time.time())),
                "x-webhook-signature": "bogus-signature-3984719283741928"
            }
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_forged)
        self.assertEqual(ctx.exception.code, 400)

    # VECTOR 3: Fake/tampered UTR submission returns pending, never auto-approved
    def test_vector_3_fake_utr_never_auto_approved(self):
        order_token = "ORD_ATTACK_UTR_3"
        with sqlite3.connect(self.test_db) as db:
            db.execute(
                "INSERT INTO product_orders (order_token, product_id, customer_email, amount_paid, status) VALUES (?, ?, ?, ?, 'pending')",
                (order_token, "prod_test_book", "user3@example.com", 29.0)
            )
            db.commit()

        fake_utr_payload = json.dumps({
            "order_token": order_token,
            "utr": "123456789012"
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/verify",
            data=fake_utr_payload,
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.read().decode("utf-8"))
        
        # Must be pending verification, NEVER auto-approved
        self.assertIn(data.get("status"), ("pending_verification", "pending_approval", "pending"))
        self.assertFalse(data.get("is_approved", False))

        with sqlite3.connect(self.test_db) as db:
            r = db.execute("SELECT status FROM product_orders WHERE order_token = ?", (order_token,)).fetchone()
            self.assertIn(r[0], ("pending_verification", "pending_approval", "pending"))

    # VECTOR 4: Tampered price in checkout request is ignored; price is enforced from digital_products
    def test_vector_4_tampered_checkout_price_ignored(self):
        tampered_body = json.dumps({
            "product_id": "prod_test_book",
            "email": "victim_or_hacker@example.com",
            "amount": 0.01  # Tampered client price!
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/checkout",
            data=tampered_body,
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.read().decode("utf-8"))
        
        # Server must enforce official catalog price ₹29
        self.assertEqual(data["amount"], 29)
        order_id = data["order_id"]

        with sqlite3.connect(self.test_db) as db:
            r = db.execute("SELECT amount_paid FROM product_orders WHERE order_token = ?", (order_id,)).fetchone()
            self.assertEqual(r[0], 29.0)

    # VECTOR 5: SSRF attempt to private/loopback/cloud metadata IPs is blocked
    def test_vector_5_ssrf_attacks_blocked(self):
        # 5a. AWS/GCP/Azure link-local cloud metadata
        safe, err = validate_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        self.assertIn("फक्त HTTPS", err)

        # 5b. Localhost
        safe, err = validate_safe_url("https://localhost/admin")
        self.assertFalse(safe)
        self.assertIn("अवैध डोमेन", err)

        # 5c. Private 10.x / 192.168.x / 127.0.0.1
        safe, err = validate_safe_url("https://127.0.0.1:8000/internal")
        self.assertFalse(safe)

        # 5d. Non-whitelisted external domain
        safe, err = validate_safe_url("https://evil-attacker-site.com/exploit")
        self.assertFalse(safe)
        self.assertIn("अवैध डोमेन", err)

    # VECTOR 6: Non-admin channel addition causes bot to leave unauthorized chat immediately
    def test_vector_6_non_admin_channel_addition_auto_leaves(self):
        class MockUser:
            id = 999999999  # Unauthorized non-admin user

        class MockChat:
            id = -100987654321
            title = "Unauthorized Channel"

        class MockChatMember:
            status = "administrator"

        class MockMyChatMember:
            new_chat_member = MockChatMember()
            from_user = MockUser()

        class MockBot:
            def __init__(self):
                self.left_chat_id = None

            async def leave_chat(self, chat_id):
                self.left_chat_id = chat_id

        class MockUpdate:
            my_chat_member = MockMyChatMember()
            effective_chat = MockChat()

        class MockContext:
            bot = MockBot()

        import asyncio
        update = MockUpdate()
        context = MockContext()
        asyncio.run(on_chat_member_updated(update, context))

        # Bot must have invoked leave_chat on the unauthorized chat
        self.assertEqual(context.bot.left_chat_id, -100987654321)

    # VECTOR 7: Order status query by email alone is rejected (token-only required)
    def test_vector_7_order_status_by_email_alone_prohibited(self):
        # Querying by email alone must return 400 Bad Request to prevent order enumeration
        req = urllib.request.Request(f"{self.base_url}/api/order_status?email=user3@example.com")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

        # Querying with empty token must also return 400
        req_empty = urllib.request.Request(f"{self.base_url}/api/order_status?token=")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_empty)
        self.assertEqual(ctx.exception.code, 400)

    # VECTOR 8: Request payload > 1 MB returns 413 Payload Too Large
    def test_vector_8_payload_too_large_rejected(self):
        oversized_payload = b"X" * (1024 * 1024 + 100)  # > 1 MB
        req = urllib.request.Request(
            f"{self.base_url}/api/checkout",
            data=oversized_payload,
            headers={"Content-Type": "application/json"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 413)

    # VECTOR 9: Expired or forged download token/signature returns 403 Forbidden
    def test_vector_9_expired_or_forged_download_links_blocked(self):
        # 9a. Forged signature
        valid, err = verify_signed_download_url("ORD_VALID_TOKEN", str(int(time.time()) + 3600), "bogus_signature")
        self.assertFalse(valid)
        self.assertIn("अवैध", err)

        # 9b. Expired signature
        exp_past = int(time.time()) - 100
        key = os.getenv("DOWNLOAD_SIGNING_KEY", "test-key").encode()
        data_to_sign = f"ORD_VALID_TOKEN:{exp_past}".encode()
        past_sig = hmac.new(key, data_to_sign, hashlib.sha256).hexdigest()

        valid_past, err_past = verify_signed_download_url("ORD_VALID_TOKEN", str(exp_past), past_sig)
        self.assertFalse(valid_past)
        self.assertIn("कालबाह्य", err_past)

        # 9c. Request to /download/ with invalid signature returns 403
        req = urllib.request.Request(f"{self.base_url}/download/ORD_VALID_TOKEN?exp={exp_past}&sig={past_sig}")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 403)


if __name__ == "__main__":
    unittest.main()

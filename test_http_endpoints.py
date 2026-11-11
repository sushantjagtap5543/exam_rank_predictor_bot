import os
import sys
import json
import sqlite3
import unittest
import urllib.request
import threading
import base64
from http.server import HTTPServer

sys.path.insert(0, os.path.abspath("."))
from app.bot import HealthCheckHandler, DB_PATH
from app.digital_store import packaging_agent

class TestHTTPEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 8769), HealthCheckHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = "http://127.0.0.1:8769"
        cls.admin_key = os.getenv("ADMIN_API_KEY", "admin_prod_examrankers_sec_997009")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_health(self):
        for ep in ("/health", "/healthz", "/ping"):
            req = urllib.request.urlopen(f"{self.base_url}{ep}")
            self.assertEqual(req.status, 200)
            self.assertEqual(req.read().decode("utf-8"), "OK")

    def test_admin_dashboard(self):
        # 1. Unauthenticated request without key must return 403 Forbidden
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{self.base_url}/admin")
        self.assertEqual(ctx.exception.code, 403)

        # 2. Authenticated request with key returns 200 OK
        req = urllib.request.urlopen(f"{self.base_url}/admin?key={self.admin_key}")
        self.assertEqual(req.status, 200)
        content = req.read().decode("utf-8")
        self.assertIn("Admin Studio", content)
        self.assertIn("थेट स्टोअर व्हिजिटर्स", content)
        self.assertIn("openAddModal", content)
        self.assertIn("purgeAllProducts", content)

    def test_storefront(self):
        req = urllib.request.urlopen(f"{self.base_url}/")
        self.assertEqual(req.status, 200)
        content = req.read().decode("utf-8")
        self.assertIn("ExamRankers", content)

    def test_manual_product_crud_apis(self):
        # 1. Create Product
        new_prod_payload = {
            "title": "मॅन्युअल चाचणी ई-बुक २०२६",
            "subtitle": "अतिसंभाव्य ५०० सराव प्रश्न",
            "subject": "Marathi",
            "price_inr": 25,
            "original_price_inr": 99,
            "pages": 55,
            "badge": "⭐ नवीन",
            "icon": "✍️",
            "download_file": "manual_test.pdf",
            "description": "मॅन्युअल ॲडमिन कंट्रोल चाचणी पुस्तक.",
            "is_active": 1
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/admin/create_product",
            data=json.dumps(new_prod_payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Admin-Key": self.admin_key}
        )
        resp = urllib.request.urlopen(req)
        self.assertEqual(resp.status, 200)
        res_data = json.loads(resp.read().decode("utf-8"))
        self.assertTrue(res_data.get("success"))
        created_p = res_data.get("product")
        prod_id = created_p["id"]
        self.assertEqual(created_p["title"], "मॅन्युअल चाचणी ई-बुक २०२६")

        # 2. Update Product
        up_req = urllib.request.Request(
            f"{self.base_url}/api/admin/update_product",
            data=json.dumps({"product_id": prod_id, "price_inr": 45, "title": "अद्ययावत मॅन्युअल ई-बुक"}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Admin-Key": self.admin_key}
        )
        up_resp = urllib.request.urlopen(up_req)
        self.assertEqual(up_resp.status, 200)
        up_data = json.loads(up_resp.read().decode("utf-8"))
        self.assertTrue(up_data.get("success"))

        # Verify DB updated
        p = packaging_agent.get_product_by_id(prod_id, DB_PATH)
        self.assertEqual(p["price_inr"], 45)
        self.assertEqual(p["title"], "अद्ययावत मॅन्युअल ई-बुक")

        # 3. Toggle Status (Active -> Hidden)
        tog_req = urllib.request.Request(
            f"{self.base_url}/api/admin/toggle_product_status",
            data=json.dumps({"product_id": prod_id}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Admin-Key": self.admin_key}
        )
        tog_resp = urllib.request.urlopen(tog_req)
        self.assertEqual(tog_resp.status, 200)
        p_after = packaging_agent.get_product_by_id(prod_id, DB_PATH)
        self.assertEqual(p_after["is_active"], 0)

        # 4. Delete Product
        del_req = urllib.request.Request(
            f"{self.base_url}/api/admin/delete_product",
            data=json.dumps({"product_id": prod_id}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Admin-Key": self.admin_key}
        )
        del_resp = urllib.request.urlopen(del_req)
        self.assertEqual(del_resp.status, 200)
        self.assertIsNone(packaging_agent.get_product_by_id(prod_id, DB_PATH))

    def test_upload_pdf_api(self):
        sample_pdf_bytes = b"%PDF-1.4 sample test bytes for admin manual upload"
        b64_str = base64.b64encode(sample_pdf_bytes).decode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/admin/upload_pdf",
            data=json.dumps({"filename": "test_admin_upload.pdf", "base64_data": b64_str}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Admin-Key": self.admin_key}
        )
        resp = urllib.request.urlopen(req)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.read().decode("utf-8"))
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("filename"), "test_admin_upload.pdf")

    def test_upload_fake_pdf_rejected(self):
        fake_pdf_bytes = b"This is just a text file renamed to .pdf"
        b64_str = base64.b64encode(fake_pdf_bytes).decode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/admin/upload_pdf",
            data=json.dumps({"filename": "fake_doc.pdf", "base64_data": b64_str}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Admin-Key": self.admin_key}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)
        err_json = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertFalse(err_json.get("success"))
        self.assertIn("अवैध PDF", err_json.get("message", ""))

    def test_order_action_api(self):
        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                INSERT OR REPLACE INTO product_orders (
                    order_token, product_id, customer_email, amount_paid, utr, status
                ) VALUES ('ORD_TEST_ACTION', 'prod_test', 'test@gmail.com', 29, '123456789012', 'pending')
            """)
            db.commit()

        req = urllib.request.Request(
            f"{self.base_url}/api/admin/order_action",
            data=json.dumps({"order_token": "ORD_TEST_ACTION", "action": "approve"}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Admin-Key": self.admin_key}
        )
        resp = urllib.request.urlopen(req)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.read().decode("utf-8"))
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("status"), "approved")

    def test_sample_image_and_preview_apis(self):
        # 1. Test /api/sample_preview returns JSON
        req_prev = urllib.request.urlopen(f"{self.base_url}/api/sample_preview?id=prod_file_0169460b0a")
        self.assertEqual(req_prev.status, 200)
        prev_data = json.loads(req_prev.read().decode("utf-8"))
        self.assertTrue(prev_data.get("success"))
        self.assertIn("image_url", prev_data)
        self.assertIn("total_pages", prev_data)

        # 2. Test /api/sample_image returns PNG binary image
        req_img = urllib.request.urlopen(f"{self.base_url}/api/sample_image?id=prod_file_0169460b0a")
        self.assertEqual(req_img.status, 200)
        self.assertEqual(req_img.headers.get("Content-Type"), "image/png")
        img_bytes = req_img.read()
        self.assertTrue(len(img_bytes) > 1000)
        # PNG signature check: \x89PNG\r\n\x1a\n
        self.assertTrue(img_bytes.startswith(b"\x89PNG\r\n\x1a\n"))

        # 3. Test fallback for nonexistent product ID
        req_prev_none = urllib.request.urlopen(f"{self.base_url}/api/sample_preview?id=prod_non_existent_999")
        self.assertEqual(req_prev_none.status, 200)
        data_none = json.loads(req_prev_none.read().decode("utf-8"))
        self.assertTrue(data_none.get("success"))

        req_img_none = urllib.request.urlopen(f"{self.base_url}/api/sample_image?id=prod_non_existent_999")
        self.assertEqual(req_img_none.status, 200)
        self.assertEqual(req_img_none.headers.get("Content-Type"), "image/png")
        self.assertTrue(req_img_none.read().startswith(b"\x89PNG\r\n\x1a\n"))

if __name__ == "__main__":
    unittest.main()

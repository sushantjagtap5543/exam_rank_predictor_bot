import os
import sys
import json
import sqlite3
import unittest
import urllib.request
import threading
from http.server import HTTPServer

sys.path.insert(0, os.path.abspath("."))
from app.bot import HealthCheckHandler, DB_PATH

class TestHTTPEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 8765), HealthCheckHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = "http://127.0.0.1:8765"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_health(self):
        req = urllib.request.urlopen(f"{self.base_url}/health")
        self.assertEqual(req.status, 200)
        self.assertEqual(req.read().decode("utf-8"), "OK")

    def test_admin_dashboard(self):
        req = urllib.request.urlopen(f"{self.base_url}/admin")
        self.assertEqual(req.status, 200)
        content = req.read().decode("utf-8")
        self.assertIn("ExamRankers™ Admin Command Center", content)
        self.assertIn("थेट स्टोअर व्हिजिटर्स", content)

    def test_storefront(self):
        req = urllib.request.urlopen(f"{self.base_url}/")
        self.assertEqual(req.status, 200)
        content = req.read().decode("utf-8")
        self.assertIn("ExamRankers", content)

    def test_admin_sync_products_api(self):
        req = urllib.request.Request(
            f"{self.base_url}/api/admin/sync_products",
            data=b"{}",
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.read().decode("utf-8"))
        self.assertIn("success", data)
        self.assertTrue(data["success"])

    def test_admin_update_price_api(self):
        req = urllib.request.Request(
            f"{self.base_url}/api/admin/update_price",
            data=json.dumps({"product_id": "prod_ca_monthly_top200", "price_inr": 25}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req)
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.read().decode("utf-8"))
        self.assertTrue(data.get("success"))

if __name__ == "__main__":
    unittest.main()

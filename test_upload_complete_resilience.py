import base64
import http.server
import json
import os
import sys
import threading
import time
import unittest
import urllib.request
import urllib.error

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.bot import HealthCheckHandler, CHUNK_UPLOADS, CHUNK_UPLOADS_LOCK, cleanup_stale_chunk_uploads

class TestUploadCompleteResilience(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start local test HTTP server on ephemeral port
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), HealthCheckHandler)
        cls.port = cls.server.server_port
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_01_upload_portal_html_render(self):
        """Verify GET /upload delivers complete portal with chunked upload & progress bar."""
        req = urllib.request.urlopen(f"{self.base_url}/upload")
        self.assertEqual(req.status, 200)
        html = req.read().decode("utf-8")
        self.assertIn("ExamRankers", html)
        self.assertIn("अधिकृत रिस्पॉन्स शीट वेब अपलोड पोर्टल", html)
        self.assertIn("/api/upload_chunk", html)
        self.assertIn("uploadProgressBar", html)
        self.assertIn("tryExtractUrlFromPdf", html)
        self.assertIn("readBlobAsBase64", html)
        self.assertIn("sectionTableContainer", html)

    def test_02_cors_preflight_options(self):
        """Verify OPTIONS /api/upload_chunk and /api/upload_sheet return 200 with permissive CORS."""
        for endpoint in ("/api/upload_chunk", "/api/upload_sheet"):
            req = urllib.request.Request(f"{self.base_url}{endpoint}", method="OPTIONS")
            resp = urllib.request.urlopen(req)
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")
            self.assertIn("POST", resp.headers.get("Access-Control-Allow-Methods"))

    def test_03_single_shot_small_file_empty_data(self):
        """Verify POST /api/upload_sheet with empty body returns 400."""
        req = urllib.request.Request(
            f"{self.base_url}/api/upload_sheet",
            data=json.dumps({}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_04_chunked_upload_multi_chunk_assembly(self):
        """Verify POST /api/upload_chunk accepts sequential chunks and assembles correctly."""
        upload_id = f"test_resilience_{int(time.time()*1000)}"
        mock_pdf_parts = [
            b"%PDF-1.4 header \n",
            b"Q.1 (1) Chosen: 1 \n",
            b"Q.2 (2) Chosen: 2 \n",
            b"%%EOF\n"
        ]
        total_chunks = len(mock_pdf_parts)

        # Upload first N-1 chunks
        for i in range(total_chunks - 1):
            chunk_b64 = base64.b64encode(mock_pdf_parts[i]).decode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/upload_chunk",
                data=json.dumps({
                    "upload_id": upload_id,
                    "chunk_index": i,
                    "total_chunks": total_chunks,
                    "filename": "resilience_test.pdf",
                    "category": "Open",
                    "data": chunk_b64
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            resp = urllib.request.urlopen(req)
            self.assertEqual(resp.status, 200)
            d = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(d.get("status"), "chunk_saved")
            self.assertEqual(d.get("chunk_index"), i)

        # Upload final chunk -> triggers assembly & scoring
        last_b64 = base64.b64encode(mock_pdf_parts[-1]).decode("utf-8")
        req_last = urllib.request.Request(
            f"{self.base_url}/api/upload_chunk",
            data=json.dumps({
                "upload_id": upload_id,
                "chunk_index": total_chunks - 1,
                "total_chunks": total_chunks,
                "filename": "resilience_test.pdf",
                "category": "Open",
                "data": last_b64
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        resp_last = urllib.request.urlopen(req_last)
        self.assertEqual(resp_last.status, 200)
        d_last = json.loads(resp_last.read().decode("utf-8"))
        self.assertIn("success", d_last)
        # Entry should be cleaned up from memory after completion
        with CHUNK_UPLOADS_LOCK:
            self.assertNotIn(upload_id, CHUNK_UPLOADS)

    def test_05_chunk_cleanup_stale_entries(self):
        """Verify cleanup_stale_chunk_uploads evicts incomplete uploads after timeout."""
        old_id = "test_stale_id_999"
        with CHUNK_UPLOADS_LOCK:
            CHUNK_UPLOADS[old_id] = {
                "chunks": {0: b"dummy"},
                "total_chunks": 5,
                "timestamp": time.time() - 700  # 700 seconds old (> 600s threshold)
            }
        cleanup_stale_chunk_uploads()
        with CHUNK_UPLOADS_LOCK:
            self.assertNotIn(old_id, CHUNK_UPLOADS)

    def test_06_invalid_chunk_payloads(self):
        """Verify invalid chunk payloads return 400."""
        # Missing upload_id
        req_bad = urllib.request.Request(
            f"{self.base_url}/api/upload_chunk",
            data=json.dumps({"chunk_index": 0, "total_chunks": 2, "data": "abc"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_bad)
        self.assertEqual(ctx.exception.code, 400)

if __name__ == "__main__":
    unittest.main()

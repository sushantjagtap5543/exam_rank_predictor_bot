import unittest
import os
import sys
import io
import fitz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.parser import (
    _extract_text_with_green_ticks,
    detect_exam,
    extract_post_and_metadata,
    parse_answers,
    score_answers,
)
from app.bot import EXAMS, process_sheet_payload

class TestGmcUploadVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Look for gmc.pdf in candidate locations
        cls.gmc_path = None
        candidates = [
            os.path.join(BASE_DIR, "admin_storage", "products", "gmc.pdf"),
            os.path.join(os.path.dirname(BASE_DIR), "gmc.pdf"),
            os.path.join(BASE_DIR, "gmc.pdf"),
        ]
        for c in candidates:
            if os.path.exists(c) and os.path.getsize(c) > 0:
                cls.gmc_path = c
                break

    def test_01_gmc_exam_detection_from_text(self):
        sample_text = (
            "SubQuestion No : 1\nQ.1\nQuestion\nAns\n1. A\n2. B [Correct Option]\n"
            "Chosen Option : 2\nward servant\nhttps://t.me/gmclatur\n"
        )
        detected = detect_exam(sample_text, EXAMS)
        self.assertEqual(detected.get("status"), "detected")
        self.assertEqual(detected.get("key"), "GMC_SARALSEWA")

    def test_02_gmc_post_name_extraction(self):
        sample_text = "ward servant\nhttps://t.me/gmclatur\nRoll No: 123456\n"
        meta = extract_post_and_metadata(sample_text)
        self.assertIn("कक्ष सेवक", meta.get("post_name", ""))

    def test_03_filename_fallback_gmc(self):
        pdf_doc = fitz.open()
        p = pdf_doc.new_page()
        p.insert_text((50, 50), "Q.1 Question text\nAns\n1. Option 1 [Correct Option]\nChosen Option : 1\n")
        pdf_bytes = pdf_doc.tobytes()
        pdf_doc.close()

        status_code, resp = process_sheet_payload(
            file_bytes=pdf_bytes,
            filename="gmc.pdf",
            exam_override="auto",
            user_category="Open"
        )
        self.assertEqual(status_code, 200)
        self.assertTrue(resp.get("success"))
        self.assertEqual(resp.get("exam_key"), "GMC_SARALSEWA")
        self.assertIn("GMC", resp.get("exam_title", ""))

    def test_04_green_tick_extraction_on_gmc_pages(self):
        if not self.gmc_path:
            self.skipTest("gmc.pdf not found in local workspace")

        doc = fitz.open(self.gmc_path)
        # Create a 5-page sub-doc from real gmc.pdf
        sub_doc = fitz.open()
        sub_doc.insert_pdf(doc, from_page=0, to_page=4)

        extracted_text = _extract_text_with_green_ticks(sub_doc)
        sub_doc.close()
        doc.close()

        self.assertIn("[Correct Option]", extracted_text)
        recs = parse_answers(extracted_text)
        self.assertGreater(len(recs), 0)

        cfg = EXAMS.get("GMC_SARALSEWA", {"positive_marks": 1.0, "negative_marks": 0.0})
        scored = score_answers(recs, cfg)
        self.assertGreater(scored.get("correct", 0), 0)
        self.assertGreater(scored.get("score", 0), 0)

if __name__ == "__main__":
    unittest.main()

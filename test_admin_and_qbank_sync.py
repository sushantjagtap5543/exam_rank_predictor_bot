import unittest
import json
import sqlite3
import os
from app.bot import init_db, sync_records_to_qbank, DB_PATH, get_connection
from app.admin_panel import render_admin_dashboard_html

class TestAdminAndQBankSync(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_sync_records_to_qbank(self):
        sample_records = [
            {
                "question_text": "महाराष्ट्राची उपराजधानी कोणती आहे?",
                "options": {
                    "1": "मुंबई",
                    "2": "नागपूर",
                    "3": "पुणे",
                    "4": "नाशिक"
                },
                "correct_option_number": 2,
                "correct_option_text": "नागपूर",
                "section": "General Knowledge",
                "explanation": "नागपूर ही महाराष्ट्राची अधिकृत हिवाळी व उपराजधानी आहे."
            },
            {
                "question_text": "खालीलपैकी 'प्रयोग' ओळखा: 'रामाने रावणास मारले.'",
                "options": {
                    "1": "कर्तरी प्रयोग",
                    "2": "कर्मणी प्रयोग",
                    "3": "भावे प्रयोग",
                    "4": "संकीर्ण प्रयोग"
                },
                "correct_option_number": 3,
                "correct_option_text": "भावे प्रयोग",
                "section": "मराठी व्याकरण",
                "explanation": "कर्ता व कर्म दोघांनाही प्रत्यय असल्याने क्रियापद तृतीयपुरुषी नपुंसकलिंगी एकावचनी राहते."
            }
        ]

        stored = sync_records_to_qbank(sample_records, exam_key="ZP_BHARTI", source="test_sync")
        self.assertGreaterEqual(stored, 0)

        # Verify items exist in qbank_questions table
        with get_connection() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT * FROM qbank_questions WHERE question_text LIKE '%उपराजधानी%'").fetchall()
            self.assertGreaterEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["section"], "General Knowledge")
            self.assertEqual(row["correct_option_num"], 2)

    def test_admin_dashboard_renders_new_controls(self):
        html = render_admin_dashboard_html(DB_PATH)
        # Check new KPI cards
        self.assertIn("केंद्रीय प्रश्नसंच", html)
        self.assertIn("एकूण रिस्पॉन्स शीट्स", html)
        self.assertIn("नोंदणीकृत सदस्य", html)
        self.assertIn("डेटाबेस व मेमरी", html)

        # Check new sections
        self.assertIn("केंद्रीय प्रश्नसंच व क्विझ व्यवस्थापन", html)
        self.assertIn("थेट परीक्षार्थी निकाल व अपलोड्स", html)

        # Check action functions
        self.assertIn("dispatchQuizNow", html)
        self.assertIn("optimizeSystemNow", html)
        self.assertIn("deleteUploadRecord", html)
        self.assertIn("/admin/export_qbank", html)

if __name__ == "__main__":
    unittest.main()

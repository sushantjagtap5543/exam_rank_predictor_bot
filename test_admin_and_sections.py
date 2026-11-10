import os
import sys
import json
import sqlite3
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath("."))

from app.admin_panel import render_admin_dashboard_html
from app.ai_analysis import generate_oneliner_question_bank_pdf, SECTION_DEFS
from app.digital_store import packaging_agent
from app.chalu_ghadamodi_builder import build_chalu_ghadamodi_pdf, structure_raw_data_to_chalu_ghadamodi
from app.agents.product_catalog_content import get_subject_specific_content
from app.parser import parse_answers, parse_general_mcqs
from app.quiz_generator import extract_quizzes_from_records, compute_question_hash, is_quiz_already_posted

class TestAdminAndSections(unittest.TestCase):
    def setUp(self):
        self.db_path = "bot.db"
        self.output_dir = Path("test_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def test_admin_dashboard_html_rendering(self):
        html = render_admin_dashboard_html(self.db_path)
        self.assertIn("Admin Studio", html)
        self.assertIn("थेट स्टोअर व्हिजिटर्स", html)
        self.assertIn("१२-अंकी UTR", html)
        self.assertIn("syncFolderPdfs", html)
        self.assertIn("updateProductPrice", html)
        self.assertIn("generateQBank", html)
        self.assertIn("generateChaluGhadamodi", html)
        self.assertIn("openBulkUploadModal", html)
        self.assertIn("startBulkUploadProcess", html)
        self.assertIn("scrollVisitors", html)
        self.assertIn("visitors-scroll-wrap", html)

    def test_section_defs_and_qbank_structure(self):
        self.assertTrue(len(SECTION_DEFS) >= 4)
        section_titles = [title for title, kws in SECTION_DEFS]
        self.assertTrue(any("मराठी" in t for t in section_titles))
        self.assertTrue(any("इंग्रजी" in t for t in section_titles))
        self.assertTrue(any("सामान्य ज्ञान" in t or "GS" in t for t in section_titles))
        self.assertTrue(any("अंकगणित" in t or "बुद्धिमत्ता" in t for t in section_titles))

        out_pdf = self.output_dir / "test_sectionwise_qbank.pdf"
        res_path = generate_oneliner_question_bank_pdf(self.db_path, str(out_pdf))
        self.assertTrue(os.path.exists(res_path))
        self.assertGreater(os.path.getsize(res_path), 5000)

    def test_chalu_ghadamodi_builder(self):
        raw_content = get_subject_specific_content("prod_ca_monthly_top200")
        data = structure_raw_data_to_chalu_ghadamodi(raw_content, month_name="चालू घडामोडी")
        self.assertIn("meta", data)
        self.assertIn("categories", data)
        self.assertGreater(len(data["categories"]), 0)

        out_pdf = self.output_dir / "test_chalu_ghadamodi.pdf"
        built_pdf = build_chalu_ghadamodi_pdf(data, str(out_pdf))
        self.assertTrue(os.path.exists(built_pdf))
        self.assertGreater(os.path.getsize(built_pdf), 1000)

    def test_product_pricing_range(self):
        added = packaging_agent.sync_folder_pdfs_to_products(self.db_path)
        self.assertIsInstance(added, int)
        
        products = packaging_agent.get_all_products(self.db_path)
        self.assertGreater(len(products), 0)
        for p in products:
            price = p.get("price_inr", 0)
            self.assertGreaterEqual(price, 10, f"Product {p.get('id')} price {price} is less than 10")
            self.assertLessEqual(price, 50, f"Product {p.get('id')} price {price} is greater than 50")

    def test_bulk_general_mcq_parsing(self):
        sample_qbank_text = """
1. भारताचे पहिले पंतप्रधान कोण होते?
A) महात्मा गांधी
B) पं. जवाहरलाल नेहरू
C) डॉ. बाबासाहेब आंबेडकर
D) सरदार पटेल
उत्तर: B

2. महाराष्ट्राची उपराजधानी कोणती आहे?
1) पुणे
2) नागपूर
3) नाशिक
4) छत्रपती संभाजीनगर
Ans: 2

Q. 3 खालीलपैकी कोणता मूलभूत हक्क नाही?
A) समतेचा हक्क
B) स्वातंत्र्याचा हक्क
C) संपत्तीचा हक्क
D) शोषणाविरुद्धचा हक्क
उत्तर: C
"""
        records = parse_answers(sample_qbank_text)
        self.assertGreaterEqual(len(records), 3)
        self.assertEqual(records[0]["question_text"], "भारताचे पहिले पंतप्रधान कोण होते?")
        self.assertEqual(records[0]["correct_option_number"], "2")
        self.assertEqual(records[1]["correct_option_number"], "2")
        self.assertEqual(records[2]["correct_option_number"], "3")

        quizzes = extract_quizzes_from_records(records, max_questions=10, filter_unposted=False, db_path=self.db_path)
        self.assertGreaterEqual(len(quizzes), 3)
        self.assertEqual(quizzes[0]["correct_option_index"], 1)

if __name__ == "__main__":
    unittest.main()

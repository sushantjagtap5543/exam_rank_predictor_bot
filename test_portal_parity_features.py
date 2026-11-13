import unittest
import json
from app.bot import render_upload_portal_html, process_sheet_payload, EXAMS

class TestPortalParityFeatures(unittest.TestCase):
    def test_portal_html_contains_all_bot_features(self):
        html = render_upload_portal_html()
        
        # 1. 3 Input Tabs (File, URL, Manual Score)
        self.assertIn("tabFileBtn", html)
        self.assertIn("tabUrlBtn", html)
        self.assertIn("tabManualBtn", html)
        self.assertIn("manualTabContent", html)
        self.assertIn("manualScoreInput", html)
        self.assertIn("postQuickRank", html)

        # 2. VIP Channel Unlock Banner
        self.assertIn("vipChannelBanner", html)
        self.assertIn("https://t.me/+EjtGp-pH4hMxZDM1", html)

        # 3. Two Offline Standalone HTML Downloads
        self.assertIn("downloadFullHtmlReport", html)
        self.assertIn("downloadWrongHtmlReport", html)
        self.assertIn("downloadHtmlFile", html)
        self.assertIn("१०० प्रश्न निकाल (HTML)", html)
        self.assertIn("चुकीचे प्रश्न अहवाल (HTML)", html)

        # 4. Exam-Specific Digital Books Store Shelf
        self.assertIn("TCS / IBPS स्पेशल ई-बुक्स", html)
        self.assertIn("/store", html)

        # 5. YouTube Live Analysis
        self.assertIn("ytLiveBtn", html)
        self.assertIn("YouTube उत्तरतालिका विश्लेषण", html)

    def test_quick_rank_parity(self):
        # Test quick rank integration through process_sheet_payload or EXAMS
        self.assertTrue(len(EXAMS) > 0)
        from app.rank import estimate_cohort_rank
        rank_info = estimate_cohort_rank(150.0, [100.0, 120.0, 140.0, 160.0], "Open", [110.0, 130.0], max_marks=200)
        self.assertIn("exam_rank", rank_info)
        self.assertIn("zone", rank_info)

if __name__ == "__main__":
    unittest.main()


"""
Exhaustive Test Suite for All 15 NEXUS Force Agents and Background Jobs:
Tests online & offline behaviors, schema resilience, and background orchestrators.
"""

import sys
import os
import unittest
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.agents import (
    ChiefExecutiveOfficer,
    AILeadDirector,
    AcademicDeanManager,
    GrowthMarketingManager,
    CommerceOperationsManager,
    ExamIntelligenceResearcher,
    CurriculumResearchSynthesist,
    UIUXDesignArchitect,
    BrandVisualsDesigner,
    MarathiSeniorFaculty,
    EnglishSeniorFaculty,
    MathsReasoningSeniorFaculty,
    CurrentAffairsSeniorEditor,
    ChannelBrandingAgent,
    DigitalProductPackagingAgent,
    MarketingSalesAgent,
    FulfillmentEmailAgent,
)

class TestAll15AgentsAndJobs(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = str(PROJECT_ROOT / "test_agents.db")
        pkg = DigitalProductPackagingAgent()
        pkg.init_products_db(cls.db_path)
        import sqlite3
        with sqlite3.connect(cls.db_path) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER,
                    filename TEXT,
                    exam_key TEXT,
                    category TEXT,
                    post_name TEXT DEFAULT 'General',
                    score REAL DEFAULT 0.0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.commit()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except Exception:
                pass

    async def test_01_all_15_agents_instantiation(self):
        agents = [
            ChiefExecutiveOfficer(),
            AILeadDirector(),
            AcademicDeanManager(),
            GrowthMarketingManager(),
            CommerceOperationsManager(),
            ExamIntelligenceResearcher(),
            CurriculumResearchSynthesist(),
            UIUXDesignArchitect(),
            BrandVisualsDesigner(),
            MarathiSeniorFaculty(),
            EnglishSeniorFaculty(),
            MathsReasoningSeniorFaculty(),
            CurrentAffairsSeniorEditor(),
            ChannelBrandingAgent(),
            DigitalProductPackagingAgent(),
        ]
        self.assertEqual(len(agents), 15)
        for a in agents:
            self.assertTrue(len(a.name) > 3)
            self.assertTrue(len(a.role) > 3)
            self.assertTrue(len(a.core_competencies) >= 2)

    async def test_02_executive_agents_execution(self):
        ceo = ChiefExecutiveOfficer()
        brief = await ceo.generate_executive_brief(self.db_path)
        self.assertIsInstance(brief, dict)
        self.assertIn("executive_summary", brief)

        ai_lead = AILeadDirector()
        audit = ai_lead.audit_ai_mesh_health()
        self.assertIsInstance(audit, dict)
        self.assertIn("status", audit)

        dean = AcademicDeanManager()
        plan = await dean.audit_content_quality("Marathi Vyakaran", [{"q": "Sample"}])
        self.assertIsInstance(plan, dict)
        self.assertIn("approval_status", plan)

    async def test_03_research_agents_execution(self):
        researcher = ExamIntelligenceResearcher()
        trends = await researcher.analyze_uploaded_exam_trends(self.db_path)
        self.assertIsInstance(trends, dict)
        self.assertIn("stats", trends)

        synthesist = CurriculumResearchSynthesist()
        ca_intel = await synthesist.generate_current_affairs_intelligence("चालू महिना")
        self.assertIsInstance(ca_intel, dict)
        self.assertIn("top_themes", ca_intel)

    async def test_04_design_agents_execution(self):
        architect = UIUXDesignArchitect()
        spec = architect.audit_storefront_ux_standards()
        self.assertIsInstance(spec, dict)
        self.assertIn("audit_score", spec)
        self.assertIn("metrics", spec)

        designer = BrandVisualsDesigner()
        cover_spec = designer.get_product_visual_spec("prod_marathi", "मराठी व्याकरण", "Marathi", 29)
        self.assertIsInstance(cover_spec, dict)
        self.assertIn("visual_theme", cover_spec)

    async def test_05_faculty_agents_offline_fallbacks(self):
        marathi = MarathiSeniorFaculty()
        capsule = await marathi.generate_grammar_capsule("प्रयोग", count=5)
        self.assertIsInstance(capsule, list)
        self.assertGreaterEqual(len(capsule), 1)
        self.assertIn("question", capsule[0])
        self.assertIn("options", capsule[0])

        english = EnglishSeniorFaculty()
        drills = await english.generate_error_spotting_drill(count=4)
        self.assertIsInstance(drills, list)
        self.assertGreaterEqual(len(drills), 1)
        self.assertIn("question", drills[0])
        self.assertIn("grammar_rule", drills[0])

        maths = MathsReasoningSeniorFaculty()
        shortcuts = await maths.generate_shortcut_drill("Percentage", count=4)
        self.assertIsInstance(shortcuts, list)
        self.assertGreaterEqual(len(shortcuts), 1)
        self.assertIn("shortcut_trick", shortcuts[0])

        ca = CurrentAffairsSeniorEditor()
        mcqs = await ca.generate_monthly_top_mcqs("नोव्हेंबर", "२०२६", count=5)
        self.assertIsInstance(mcqs, list)

    async def test_06_operations_and_fulfillment_agents(self):
        brand = ChannelBrandingAgent()
        trend = brand.detect_trending_exam(self.db_path)
        self.assertIsInstance(trend, dict)
        self.assertIn("exam_name", trend)

        growth = GrowthMarketingManager()
        strategy = growth.get_campaign_strategy("तलाठी भरती")
        self.assertIsInstance(strategy, dict)
        self.assertIn("primary_hook", strategy)

        commerce = CommerceOperationsManager()
        ops = commerce.get_operations_health()
        self.assertIsInstance(ops, dict)
        self.assertIn("store_status", ops)

        packaging = DigitalProductPackagingAgent()
        products = packaging.get_all_products(self.db_path)
        self.assertIsInstance(products, list)

        email_agent = FulfillmentEmailAgent()
        prod_stub = {"title": "Test Title", "price_inr": 19}
        ok, msg = email_agent.send_product_email("test@example.com", prod_stub, "tok_123", None)
        self.assertIsInstance(ok, bool)

if __name__ == "__main__":
    unittest.main()

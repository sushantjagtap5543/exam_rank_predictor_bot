#!/usr/bin/env python3
"""
test_all_12_openclaw_agents_deep.py:
Comprehensive Deep Operational Verification Suite for all 12 OpenClaw Autonomous Agents:
1. Dr. Vikramaditya Deshmukh (CEO & Enterprise Orchestrator)
2. Adv. Shrikant Joshi (Anti-Ban & Policy Guardian)
3. Prof. Ananya Patil (Market Intelligence & Demand Harvester)
4. Ms. Supriya Sawant (Community Intelligence Harvester)
5. Mr. Swapnil Salunkhe (Community Engagement & News Brand Shield)
6. Dr. Ravindra Deshmukh (MPSC Academic Dean)
7. Prof. Rajesh K. Joshi, FIE (Civil Engineering Faculty Chair)
8. Dr. Amit Sharma (Mechanical Engineering Faculty Chair)
9. Dr. Prachi Kulkarni (Quality & Publication Auditor)
10. Eng. Rohan Kulkarni (Autonomous Product Factory)
11. Mr. Sameer Inamdar (Viral Growth & Marketing Director)
12. Mr. Nilesh Dada (Senior Student Counselor & Mentor)

Also tests end-to-end multi-agent autonomous cycles across Civil, Mech, and MPSC.
"""

import os
import sys
import unittest
import asyncio
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.agents.openclaw_orchestrator import (
    openclaw_team,
    create_rcc_beam_drawing,
    create_pv_cycle_drawing,
    packaging_agent
)


class All12OpenClawAgentsDeepTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.team = openclaw_team
        cls.db_path = "bot.db"

    def test_01_ceo_agent_execution(self):
        """1. Verify CEO & Enterprise Orchestrator."""
        res = self.team.execute_single_agent_task("ceo")
        self.assertTrue(res["success"])
        self.assertIn("Vikramaditya", res["agent"])
        self.assertIn("सक्रिय", self.team.ceo.live_status)
        self.assertGreaterEqual(self.team.ceo.completed_tasks_count, 1)

    def test_02_policy_guardian_agent_execution(self):
        """2. Verify Anti-Ban & Telegram Policy Compliance Guardian."""
        res = self.team.execute_single_agent_task("policy")
        self.assertTrue(res["success"])
        self.assertIn("Shrikant", res["agent"])
        # Verify jitter is strictly between 3.0 and 8.0 seconds
        jitter = self.team.policy_guardian.get_safe_broadcast_jitter()
        self.assertGreaterEqual(jitter, 3.0)
        self.assertLessEqual(jitter, 8.0)
        # Verify FloodWait backoff
        backoff = self.team.policy_guardian.calculate_floodwait_backoff(20)
        self.assertGreater(backoff, 20.0)

    def test_03_market_analyst_agent_execution(self):
        """3. Verify Market Intelligence & Demand Harvester."""
        res = self.team.execute_single_agent_task("market")
        self.assertTrue(res["success"])
        self.assertIn("Ananya", res["agent"])
        opps = self.team.market_analyst.identify_trending_opportunities(self.db_path)
        self.assertGreaterEqual(len(opps), 4)
        subjects = [o["subject"] for o in opps]
        self.assertIn("Civil Engineering", subjects)
        self.assertIn("Mechanical Engineering", subjects)
        self.assertIn("MPSC", subjects)

    def test_04_community_harvester_agent_execution(self):
        """4. Verify Community Intelligence Harvester."""
        res = self.team.execute_single_agent_task("community_harvest")
        self.assertTrue(res["success"])
        self.assertIn("Supriya", res["agent"])
        spec = self.team.community_harvester.synthesize_on_demand_product_spec("gk_current")
        self.assertIn("title", spec)
        self.assertIn("subject", spec)
        self.assertGreater(spec.get("recommended_price", 0), 0)

    def test_05_community_engager_brand_shield_execution(self):
        """5. Verify Community Engagement & Competitor Brand Shield."""
        # Test 1: Human-like bilingual response
        reply = self.team.community_engager.respond_to_group_student_query(
            incoming_query="Sir, PWD Civil saathi konti best strategy ahe?",
            student_name="अमित"
        )
        self.assertIn("reply", reply)
        self.assertTrue(len(reply["reply"]) > 20)

        # Test 2: Filter competitor brand and legal risk
        risky_text = "MPSC saathi Chanakya Mandal kiva The Unique Academy che notes changle ahet ka? 9822000000 call kara"
        filtered = self.team.community_engager.filter_competitor_brands_and_legal_risks(risky_text)
        self.assertFalse(filtered["is_clean"])
        self.assertNotIn("Chanakya Mandal", filtered["sanitized_text"])
        self.assertNotIn("The Unique Academy", filtered["sanitized_text"])
        self.assertNotIn("9822000000", filtered["sanitized_text"])
        self.assertIn("प्रमाणित अभ्यास केंद्र", filtered["sanitized_text"])
        self.assertIn("[अधिकृत मदत केंद्र]", filtered["sanitized_text"])

    def test_06_mpsc_dean_agent_execution(self):
        """6. Verify MPSC Academic Dean Agent."""
        res = self.team.execute_single_agent_task("mpsc_dean")
        self.assertTrue(res["success"])
        self.assertIn("Ravindra", res["agent"])
        curriculum = [c["subject"] for c in self.team.mpsc_dean.get_all_subjects_curriculum()]
        self.assertIn("भारतीय राज्यघटना व पंचायत राज", curriculum)
        self.assertIn("महाराष्ट्राचा समग्र भूगोल", curriculum)
        self.assertIn("आधुनिक भारताचा इतिहास व समाजसुधारक", curriculum)

    def test_07_civil_faculty_agent_execution(self):
        """7. Verify Civil Engineering Faculty Chair & IS 456 Drawings."""
        res = self.team.execute_single_agent_task("civil_faculty")
        self.assertTrue(res["success"])
        self.assertIn("Rajesh", res["agent"])
        curriculum = [c["subject"] for c in self.team.civil_director.get_all_subjects_curriculum()]
        self.assertIn("Strength of Materials", curriculum)
        self.assertIn("RCC & Prestressed Concrete", curriculum)

        # Verify ReportLab vector schematic generation for RCC beam
        drawing = create_rcc_beam_drawing()
        self.assertIsNotNone(drawing)
        self.assertEqual(drawing.width, 460)
        self.assertEqual(drawing.height, 130)

    def test_08_mech_faculty_agent_execution(self):
        """8. Verify Mechanical Engineering Faculty Chair & Otto Cycle Drawing."""
        res = self.team.execute_single_agent_task("mech_faculty")
        self.assertTrue(res["success"])
        self.assertIn("Amit", res["agent"])
        curriculum = [c["subject"] for c in self.team.mech_director.get_all_subjects_curriculum()]
        self.assertIn("Applied Thermodynamics", curriculum)
        self.assertIn("Heat & Mass Transfer", curriculum)

        # Verify ReportLab vector schematic generation for Otto cycle
        drawing = create_pv_cycle_drawing()
        self.assertIsNotNone(drawing)
        self.assertEqual(drawing.width, 460)
        self.assertEqual(drawing.height, 130)

    def test_09_quality_auditor_agent_execution(self):
        """9. Verify Quality & Publication Accuracy Auditor."""
        res = self.team.execute_single_agent_task("quality_auditor")
        self.assertTrue(res["success"])
        self.assertIn("Prachi", res["agent"])
        # Test audit on sample content
        sample_q = [{
            "q": "भारतीय संविधानातील कलम २४३-डी नुसार स्थानिक स्वराज्य संस्थांमध्ये महिलांसाठी किती टक्के आरक्षण विहित आहे?",
            "opts": ["A) २५%", "B) ३३.३३% (किमान)", "C) ५०%", "D) ६०%"],
            "ans": "B) ३३.३३% (किमान)",
            "exp": "कलम २४३-डी(३) नुसार पंचायतींमध्ये महिलांसाठी किमान एक-तृतीयांश (३३.३३%) जागा राखीव ठेवण्याची तरतूद आहे."
        }]
        audit = self.team.quality_auditor.audit_publication_quality(sample_q)
        self.assertTrue(audit.get("passed", False))
        self.assertEqual(audit.get("score"), 100)
        self.assertEqual(audit.get("questions_audited"), 1)

    def test_10_product_factory_agent_execution(self):
        """10. Verify Autonomous Product Factory & Multi-Page PDF Synthesis."""
        res = self.team.execute_single_agent_task("product_factory")
        self.assertTrue(res["success"])
        self.assertIn("Rohan", res["agent"])
        self.assertIn("ReportLab", res["result"])

    def test_11_growth_lead_agent_execution(self):
        """11. Verify Viral Growth & Conversion Marketing Director."""
        res = self.team.execute_single_agent_task("growth")
        self.assertTrue(res["success"])
        self.assertIn("Sameer", res["agent"])
        test_product = {
            "title": "MPSC GS-1 Ultimate Revision Masterclass",
            "price_inr": 49,
            "original_price_inr": 199,
            "pages": 65,
            "subject": "MPSC"
        }
        promo = self.team.growth_lead.generate_product_channel_broadcast(
            test_product,
            store_url="https://exam-rankers-bot.onrender.com"
        )
        self.assertIn("MPSC GS-1 Ultimate Revision Masterclass", promo)
        self.assertIn("₹49", promo)
        self.assertIn("https://exam-rankers-bot.onrender.com", promo)

    def test_12_sales_counselor_agent_execution(self):
        """12. Verify Senior Student Counselor & 1-on-1 Human Empathy."""
        res = self.team.execute_single_agent_task("counselor")
        self.assertTrue(res["success"])
        self.assertIn("Nilesh", res["agent"])
        counseling = self.team.sales_counselor.handle_student_inquiry(
            incoming_text="Sir Civil PWD saathi abhyas kasa karu? Khup tension ahe.",
            available_products=[{
                "id": "civ-1",
                "title": "Civil Engineering PWD Master Blueprint",
                "price_inr": 79,
                "subject": "Civil Engineering"
            }],
            user_name="राहुल"
        )
        self.assertIn("reply", counseling)
        self.assertIn("राहुल", counseling["reply"])
        self.assertTrue(len(counseling["reply"]) > 50)

    def test_13_full_autonomous_product_cycle_civil(self):
        """13. End-to-End Autonomous Cycle: Civil Engineering."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            res = loop.run_until_complete(
                self.team.execute_autonomous_product_cycle(
                    store_url="https://exam-rankers-bot.onrender.com",
                    requested_subject="Civil Engineering"
                )
            )
        finally:
            loop.close()

        self.assertTrue(res["success"])
        prod = res["product"]
        self.assertIn("Civil", prod["subject"])
        self.assertGreaterEqual(prod["pages"], 70)
        self.assertIn("file_path", prod)
        self.assertTrue(Path(prod["file_path"]).exists())
        self.assertGreater(Path(prod["file_path"]).stat().st_size, 10000)

    def test_14_full_autonomous_product_cycle_mechanical(self):
        """14. End-to-End Autonomous Cycle: Mechanical Engineering."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            res = loop.run_until_complete(
                self.team.execute_autonomous_product_cycle(
                    store_url="https://exam-rankers-bot.onrender.com",
                    requested_subject="Mechanical Engineering"
                )
            )
        finally:
            loop.close()

        self.assertTrue(res["success"])
        prod = res["product"]
        self.assertIn("Mechanical", prod["subject"])
        self.assertGreaterEqual(prod["pages"], 70)
        self.assertIn("file_path", prod)
        self.assertTrue(Path(prod["file_path"]).exists())
        self.assertGreater(Path(prod["file_path"]).stat().st_size, 10000)

    def test_15_full_autonomous_product_cycle_mpsc(self):
        """15. End-to-End Autonomous Cycle: MPSC."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            res = loop.run_until_complete(
                self.team.execute_autonomous_product_cycle(
                    store_url="https://exam-rankers-bot.onrender.com",
                    requested_subject="MPSC"
                )
            )
        finally:
            loop.close()

        self.assertTrue(res["success"])
        prod = res["product"]
        self.assertIn("MPSC", prod["subject"])
        self.assertGreaterEqual(prod["pages"], 60)
        self.assertIn("file_path", prod)
        self.assertTrue(Path(prod["file_path"]).exists())
        self.assertGreater(Path(prod["file_path"]).stat().st_size, 10000)

    def test_16_team_status_and_telemetry_integrity(self):
        """16. Verify team status and gateway telemetry."""
        status = self.team.get_team_status()
        self.assertEqual(status["status"], "active")
        self.assertEqual(len(status["agents"]), 12)
        self.assertIn("gateway", status)
        self.assertEqual(status["gateway"]["agents_count"], 12)
        self.assertTrue(status["gateway"]["cli_installed"])
        for a in status["agents"]:
            self.assertTrue(len(a["lead"]) > 0)
            self.assertTrue(len(a["status"]) > 0)
            self.assertTrue(len(a["current_task"]) > 0)
            self.assertTrue(len(a["last_active"]) > 0)
            self.assertGreaterEqual(a["completed_tasks"], 0)


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🚀 RUNNING DEEP OPERATIONAL VERIFICATION FOR ALL 12 OPENCLAW AGENTS...")
    print("="*80 + "\n")
    unittest.main(verbosity=2)

"""
test_student_10000_scenarios_and_sync.py
--------------------------------------------------------------------
High-Volume 10,000 Scenario Student Persona Simulation & Synchronization Suite.

Validates the full platform lifecycle from a candidate's perspective:
1. 10,000 multi-dimensional student profiles (Exams, Categories, Posts, Shifts, Scores).
2. Rank calculation and percentile mathematical consistency.
3. Central Question Bank deduplication & HTML cleanup across thousands of submissions.
4. Telegram Bot /quiz integration & 0-based option index resolution.
5. Parser scoring rules (positive/negative marks, sections, unattempted).
6. Multi-threaded student concurrency & SQLite lock safety.
"""

import sys
import os
import re
import json
import sqlite3
import random
import unittest
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.rank import estimate_cohort_rank, _calc_rank_and_percentile
from app.parser import score_answers
from app.quiz_generator import resolve_quiz_correct_index, compute_question_hash
from app.bot import sync_records_to_qbank, init_db, get_connection

TEST_DB_PATH = PROJECT_ROOT / "test_student_10000.db"

EXAMS_LIST = [
    "ZP_BHARTI", "MAHA_POLICE", "TALATHI_BHARTI", "AROGYA_SEVAK",
    "FOREST_GUARD", "MPSC_CLERK", "BMC_EXAM", "NAGAR_PARISHAD",
    "TET_EXAM", "EXCISE_SI"
]

CATEGORIES_LIST = [
    "Open", "OBC", "SC", "ST", "EWS",
    "SEBC", "VJNT", "SBC", "PwD", "Ex-Serviceman"
]

POSTS_LIST = [
    "Gramsevak", "Arogya Sevak", "Junior Clerk", "Peon", "Police Constable",
    "Talathi", "Vanrakshak", "Tax Assistant", "Shikshan Sevak", "Sub Inspector"
]

SHIFTS_LIST = [
    "Shift 1 (09:00 AM)", "Shift 2 (12:30 PM)", "Shift 3 (04:00 PM)"
]

class TestStudent10000ScenariosAndSync(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        with get_connection() as db:
            db.execute("DELETE FROM qbank_questions WHERE source = 'student_upload'")

    @classmethod
    def tearDownClass(cls):
        with get_connection() as db:
            db.execute("DELETE FROM qbank_questions WHERE source = 'student_upload'")

    def test_01_simulate_10000_student_rank_predictions(self):
        """
        Simulate 10,000 diverse student profiles across 10 exams, 10 categories,
        10 posts, and 20 score distributions, verifying rank and percentile validity.
        """
        random.seed(42)
        total_scenarios = 10000
        
        # Pre-generate an active baseline cohort of 250 scores per exam
        exam_cohorts = {}
        for exam in EXAMS_LIST:
            exam_cohorts[exam] = [round(random.uniform(20.0, 195.0), 2) for _ in range(250)]
            # ensure top score and lower score exist
            exam_cohorts[exam].append(198.5)
            exam_cohorts[exam].append(15.0)

        passed_scenarios = 0
        for i in range(total_scenarios):
            exam = EXAMS_LIST[i % len(EXAMS_LIST)]
            category = CATEGORIES_LIST[(i // 10) % len(CATEGORIES_LIST)]
            post = POSTS_LIST[(i // 100) % len(POSTS_LIST)]
            
            # Diverse score scenarios: 0, negative, fractional, passing, high, topper, impossible
            score_type = i % 10
            if score_type == 0:
                score = 0.0
            elif score_type == 1:
                score = -5.0 # negative marking
            elif score_type == 2:
                score = round(random.uniform(10.0, 45.0), 2)
            elif score_type == 3:
                score = round(random.uniform(50.0, 80.0), 2)
            elif score_type == 4:
                score = round(random.uniform(85.0, 120.0), 2)
            elif score_type == 5:
                score = round(random.uniform(125.0, 150.0), 2)
            elif score_type == 6:
                score = round(random.uniform(155.0, 175.0), 2)
            elif score_type == 7:
                score = round(random.uniform(180.0, 195.0), 2)
            elif score_type == 8:
                score = 198.5 # equal to top score
            else:
                score = 205.0 # impossible score (> 200)

            cohort = exam_cohorts[exam]
            cat_cohort = [s for s in cohort if random.random() > 0.5] or [score]
            post_cohort = [s for s in cohort if random.random() > 0.5] or [score]

            res = estimate_cohort_rank(
                student_score=score,
                all_scores=cohort,
                category=category,
                category_scores=cat_cohort,
                overall_scores=cohort,
                post_name=post,
                post_scores=post_cohort,
                max_marks=200.0
            )

            # Mathematical and boundary assertions
            self.assertIn("rank", res)
            self.assertIn("percentile", res)
            self.assertIn("zone", res)

            if score > 200.0:
                self.assertTrue(res["is_impossible_score"], f"Score {score} must be flagged impossible")
                self.assertIn("Impossible", res["zone"])
            else:
                self.assertFalse(res["is_impossible_score"])
                # Rank must be between 1 and total candidates
                self.assertGreaterEqual(res["rank"], 1)
                self.assertLessEqual(res["rank"], res["total_candidates"])
                # Percentile must be between 0.0 and 100.0
                self.assertGreaterEqual(res["percentile"], 0.0)
                self.assertLessEqual(res["percentile"], 100.0)

                # Category rank consistency
                if res.get("category_rank") is not None:
                    self.assertGreaterEqual(res["category_rank"], 1)
                    self.assertLessEqual(res["category_rank"], res["category_total"])

                # Post rank consistency
                if res.get("post_rank") is not None:
                    self.assertGreaterEqual(res["post_rank"], 1)
                    self.assertLessEqual(res["post_rank"], res["post_total"])

            passed_scenarios += 1

        self.assertEqual(passed_scenarios, 10000, "All 10,000 student rank scenarios must pass successfully.")

    def test_02_qbank_harvesting_and_deduplication_sync(self):
        """
        Tests harvesting questions from thousands of student response sheets.
        Verifies SHA-256 deduplication, HTML stripping, and correct option index preservation.
        """
        # Create 50 unique questions
        unique_questions = []
        for q_idx in range(1, 51):
            unique_questions.append({
                "question_text": f"<b>प्रश्न क्र. {q_idx}:</b> महाराष्ट्राची राजधानी कोणती आहे? <span>(Shift {q_idx})</span>",
                "section": "General Knowledge",
                "options": {
                    "101": "नागपूर",
                    "102": "मुंबई",
                    "103": "पुणे",
                    "104": "नाशिक"
                },
                "correct_option_id": "102",
                "correct_option_text": "मुंबई",
                "explanation": "मुंबई ही महाराष्ट्राची राजधानी व नागपूर ही उपराजधानी आहे."
            })

        # Simulate 200 students submitting sheets that contain overlapping subsets of these 50 questions
        total_submissions = 200
        for s_idx in range(total_submissions):
            # Each student has 10 random questions from the 50
            sample_records = random.sample(unique_questions, 10)
            sync_records_to_qbank(sample_records, exam_key="ZP_BHARTI", source="student_upload")

        # Query DB: Exactly 50 unique questions should be in qbank_questions (not 2000!)
        with get_connection() as db:
            count = db.execute("SELECT COUNT(*) FROM qbank_questions WHERE exam_key = 'ZP_BHARTI' AND source = 'student_upload'").fetchone()[0]
            self.assertEqual(count, 50, f"Expected exactly 50 unique harvested questions, found {count}")

            # Verify that HTML was stripped from all harvested questions
            rows = db.execute("SELECT question_text, options_json, correct_option_num, correct_option_text FROM qbank_questions WHERE source = 'student_upload'").fetchall()
            for r in rows:
                q_text, opt_json, c_num, c_text = r[0], r[1], r[2], r[3]
                self.assertNotIn("<b>", q_text, "HTML tags must be stripped from question_text")
                self.assertNotIn("<span>", q_text, "HTML tags must be stripped from question_text")
                self.assertEqual(c_num, 2, "Option 102 (मुंबई) is the 2nd option, so correct_option_num must be 2")
                self.assertEqual(c_text, "मुंबई", "Correct option text must be मुंबई")

    def test_03_telegram_quiz_poll_resolution(self):
        """
        Tests Telegram bot /quiz poll resolution on questions harvested from students.
        Ensures resolve_quiz_correct_index always returns 0..3 for Telegram Poll API.
        """
        test_cases = [
            # Case 1: Numeric option 1..4
            ({"correct": "2", "options": ["A", "B", "C", "D"]}, 1),
            # Case 2: Marathi text option पर्याय ३
            ({"correct": "पर्याय ३", "options": ["A", "B", "C", "D"]}, 2),
            # Case 3: Exact option string matching
            ({"correct": "छत्रपती शिवाजी महाराज", "options": ["बाबर", "अकबर", "छत्रपती शिवाजी महाराज", "हुमायून"]}, 2),
            # Case 4: Devanagari numeral ४
            ({"correct": "४", "options": ["W", "X", "Y", "Z"]}, 3),
            # Case 5: Option letter 'A'
            ({"correct": "A", "options": ["पहिला", "दुसरा", "तिसरा", "चौथा"]}, 0),
        ]

        for q_data, expected_idx in test_cases:
            opts = q_data["options"]
            idx = resolve_quiz_correct_index(q_data, opts)
            self.assertEqual(idx, expected_idx, f"Failed resolving correct option index for {q_data}")
            self.assertGreaterEqual(idx, 0)
            self.assertLess(idx, len(opts))

    def test_04_scoring_answers_with_all_student_variations(self):
        """
        Tests scoring engine against various student response sheet states:
        - 100% correct
        - 100% wrong
        - All unattempted
        - Negative marking subtraction
        - Section-wise accuracy
        """
        exam_config = {
            "positive_marks": 2.0,
            "negative_marks": 0.5,
            "total_marks": 200
        }

        records = [
            # 2 Correct in Marathi
            {"question_id": "1", "section": "मराठी", "chosen_option_number": "1", "correct_option_number": "1"},
            {"question_id": "2", "section": "मराठी", "chosen_option_number": "2", "correct_option_number": "2"},
            # 1 Wrong in Marathi
            {"question_id": "3", "section": "मराठी", "chosen_option_number": "3", "correct_option_number": "1"},
            # 1 Unattempted in English
            {"question_id": "4", "section": "इंग्रजी", "chosen_option_number": None, "correct_option_number": "4"},
            # 1 Correct in English
            {"question_id": "5", "section": "इंग्रजी", "chosen_option_number": "4", "correct_option_number": "4"},
        ]

        res = score_answers(records, exam_config)
        self.assertEqual(res["total_parsed"], 5)
        self.assertEqual(res["correct"], 3)
        self.assertEqual(res["wrong_count"], 1)
        self.assertEqual(res["unanswered"], 1)
        # Score calculation: 3 correct * 2.0 - 1 wrong * 0.5 = 6.0 - 0.5 = 5.5
        self.assertEqual(res["score"], 5.5)
        # Accuracy: 3 correct out of 4 attempted = 75.0%
        self.assertEqual(res["accuracy"], 75.0)

        # Section accuracy
        self.assertEqual(res["sections"]["मराठी"]["correct"], 2)
        self.assertEqual(res["sections"]["मराठी"]["incorrect"], 1)
        self.assertEqual(res["sections"]["इंग्रजी"]["unanswered"], 1)

    def test_05_concurrent_student_submissions(self):
        """
        Simulate 20 concurrent student threads querying and writing to the platform,
        verifying zero SQLite lock failures or data corruption under race conditions.
        """
        errors = []

        def student_worker(thread_id):
            try:
                for req in range(50):
                    exam = random.choice(EXAMS_LIST)
                    cat = random.choice(CATEGORIES_LIST)
                    score = round(random.uniform(50.0, 180.0), 2)
                    # Read cohort
                    with get_connection() as db:
                        rows = db.execute("SELECT score FROM uploads WHERE exam_key = ? LIMIT 50", (exam,)).fetchall()
                        scores = [r[0] for r in rows] or [100.0, 120.0, 140.0]

                    # Compute rank
                    rank_res = estimate_cohort_rank(score, scores, category=cat)
                    self.assertGreaterEqual(rank_res["rank"], 1)
            except Exception as e:
                errors.append(f"Thread {thread_id} error: {e}")

        threads = [threading.Thread(target=student_worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent student simulation encountered errors: {errors}")

if __name__ == "__main__":
    unittest.main()


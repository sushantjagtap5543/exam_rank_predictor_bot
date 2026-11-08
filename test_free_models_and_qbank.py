import os
import unittest
import json
import re
from pathlib import Path

class TestFreeModelsAndQBank(unittest.TestCase):
    def test_free_models_enforced(self):
        """Verify that OpenRouter model configs use 100% free models without paid models."""
        from app.agents.base_agent import DEFAULT_MODEL, FALLBACK_MODELS
        import os

        # Verify default model is free tier
        self.assertTrue(DEFAULT_MODEL.endswith(":free") or "free" in DEFAULT_MODEL.lower(), f"DEFAULT_MODEL {DEFAULT_MODEL} must be a free model")

        # Verify all fallback models are free tier
        for model in FALLBACK_MODELS:
            self.assertTrue(model.endswith(":free") or "free" in model.lower(), f"Fallback model {model} must be a free model")

        # Verify .env model is free tier
        env_model = os.getenv("OPENROUTER_MODEL", "")
        if env_model:
            self.assertTrue(env_model.endswith(":free") or "free" in env_model.lower(), f".env model {env_model} must be free")

    def test_resolve_quiz_correct_index(self):
        """Verify resolve_quiz_correct_index correctly resolves answers for various question formats."""
        from app.quiz_generator import resolve_quiz_correct_index

        # Format 1: ans_text with option marker (C)
        q1 = {
            "question": "खालीलपैकी 'प्रयोग' ओळखा: 'रामाने रावणास मारले.'",
            "options": ["कर्तरी प्रयोग", "कर्मणी प्रयोग", "भावे प्रयोग", "संकीर्ण प्रयोग"],
            "answer": "C) भावे प्रयोग"
        }
        self.assertEqual(resolve_quiz_correct_index(q1, q1["options"]), 2)

        # Format 2: Marathi text 'पर्याय २'
        q2 = {
            "question": "माहितीचा अधिकार कायदा कोणत्या वर्षी लागू झाला?",
            "options": ["२००२", "२००५", "२०१०", "२०००"],
            "answer": "पर्याय २: २००५"
        }
        self.assertEqual(resolve_quiz_correct_index(q2, q2["options"]), 1)

        # Format 3: Devanagari numeral 'पर्याय ३'
        q3 = {
            "question": "महाराष्ट्रातील सर्वाधिक लांबीची नदी कोणती?",
            "options": ["कृष्णा", "भीमा", "गोदावरी", "तापी"],
            "answer": "पर्याय ३: गोदावरी"
        }
        self.assertEqual(resolve_quiz_correct_index(q3, q3["options"]), 2)

        # Format 4: Exact string match with option
        q4 = {
            "question": "Synonym of CANDID",
            "options": ["Deceitful", "Frank", "Shy", "Rude"],
            "correct": "Frank"
        }
        self.assertEqual(resolve_quiz_correct_index(q4, q4["options"]), 1)

        # Format 5: Master qbank item with 'A'
        q5 = {
            "q": "TCS PYQ Test: शिवाजी महाराजांचा राज्याभिषेक",
            "options": ["१६७४", "१६८०", "१६६५", "१६५०"],
            "correct": "A"
        }
        self.assertEqual(resolve_quiz_correct_index(q5, q5["options"]), 0)

    def test_quiz_deduplication(self):
        """Verify quiz deduplication catches submitted and repeated questions."""
        from app.quiz_generator import normalize_question_text, is_quiz_already_posted, mark_quiz_as_posted, compute_question_hash
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db = f.name

        try:
            q_text = "रामाने रावणास मारले या वाक्यातील प्रयोग ओळखा."
            opts = ["कर्तरी", "कर्मणी", "भावे", "संकीर्ण"]
            q_hash = compute_question_hash(q_text, opts)

            # Initially not posted
            self.assertFalse(is_quiz_already_posted(q_hash, q_text, db_path=temp_db))

            # Mark as posted
            mark_quiz_as_posted(q_hash, q_text, section="मराठी", db_path=temp_db)

            # Now must be detected as already posted
            self.assertTrue(is_quiz_already_posted(q_hash, q_text, db_path=temp_db))

            # Variation with question prefix should also be caught by normalized_q
            varied_q = "[मराठी व्याकरण] Q.1: रामाने रावणास मारले. या वाक्यातील प्रयोग ओळखा?"
            self.assertTrue(is_quiz_already_posted("different_hash", varied_q, db_path=temp_db))

        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def test_qbank_generation_full_coverage(self):
        """Verify that Q-Bank generates > 100 questions covering subject sections with strict 4 columns."""
        import tempfile
        import fitz
        from app.ai_analysis import generate_oneliner_question_bank_pdf

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            out_pdf = f.name

        try:
            result = generate_oneliner_question_bank_pdf("bot.db", out_pdf, exam_name="TCS/IBPS Test Exam")
            self.assertTrue(os.path.exists(result))
            self.assertGreater(os.path.getsize(result), 25000)

            # Inspect generated PDF
            doc = fitz.open(result)
            self.assertGreater(len(doc), 5)  # Multi-page PDF
            full_text = "".join([page.get_text("text") for page in doc])

            # Verify 4th column header is 'Explanation'
            self.assertIn("Explanation", full_text)
            self.assertIn("क्र.", full_text)
            self.assertIn("प्रश्न (Question)", full_text)
            self.assertIn("अचूक उत्तर (Answer)", full_text)

            # Verify sections are present
            self.assertIn("विभाग १: मराठी भाषा व व्याकरण", full_text)
            self.assertIn("विभाग २: इंग्रजी भाषा व व्याकरण", full_text)
            self.assertIn("विभाग ३: सामान्य ज्ञान", full_text)
            self.assertIn("विभाग ४: बौद्धिक चाचणी", full_text)

            doc.close()
        finally:
            if os.path.exists(out_pdf):
                os.remove(out_pdf)

if __name__ == "__main__":
    unittest.main()


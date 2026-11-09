import sys
import io
import asyncio
from pathlib import Path

# Fix Windows console UTF-8 output if needed using modern reconfigure
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.rank import estimate_cohort_rank
from app.parser import score_answers, parse_answers
from app.monetization import init_monetization_db, get_active_ad, build_ad_markup, get_paid_channel_link
from app.ai_analysis import explain_wrong_answers_and_objections
from app.bot import init_db

def test_rank():
    scores = [120.0, 140.0, 110.0, 150.0, 95.0]
    cat_scores = [120.0, 110.0, 95.0]
    res = estimate_cohort_rank(130.0, scores, "OBC", cat_scores)
    assert res["rank"] == 3
    assert res["total_candidates"] == 6
    assert res["category_rank"] == 1
    print("✅ Rank engine passed!")

def test_scoring_and_sections():
    dummy_records = [
        {"question_id": "1", "section": "Reasoning", "selected_option_id": "101", "correct_option_id": "101"},
        {"question_id": "2", "section": "Reasoning", "selected_option_id": "102", "correct_option_id": "103"},
        {"question_id": "3", "section": "Quant", "selected_option_id": None, "correct_option_id": "104"}
    ]
    config = {"positive_marks": 2.0, "negative_marks": 0.5}
    res = score_answers(dummy_records, config)
    assert res["correct"] == 1
    assert res["incorrect"] == 1
    assert res["unanswered"] == 1
    assert res["score"] == 1.5
    assert "Reasoning" in res["sections"]
    assert "Quant" in res["sections"]
    print("✅ Scoring and Subject-wise statistics passed!")

def test_monetization():
    init_db()
    link = get_paid_channel_link()
    assert "https://t.me/+EjtGp-pH4hMxZDM1" in link
    print("✅ Paid Channel link passed!")

def test_objection_analysis():
    async def _impl():
        wrong_records = [
            {
                "question_id": "100234",
                "section": "Reasoning",
                "chosen_option_number": "2",
                "correct_option_id": "4",
                "raw_excerpt": "Select the missing number in series: 2, 5, 10, 17, ?"
            }
        ]
        res, total_count, has_next, has_prev = await explain_wrong_answers_and_objections(wrong_records, "SSC CGL", max_questions=1)
        assert len(res) == 1
        assert "explanation" in res[0]
        assert "objection_recommended" in res[0]
        assert total_count == 1
        print("✅ AI Wrong Answer Explanation & Objection Advisory passed!")
    asyncio.run(_impl())

def test_daily_topic_and_questions():
    async def _impl():
        from app.ai_analysis import generate_topic_weightage_analysis, get_daily_latest_exam_questions
        analysis = await generate_topic_weightage_analysis("मराठी व्याकरण प्रयोग समास सामान्य ज्ञान भूगोल", "तलाठी भरती २०२४")
        assert "मराठी व्याकरण" in analysis
        assert "दैनिक शिफ्ट" in analysis
        print("✅ Paid Channel Daily Topic Weightage Analysis passed!")

        daily_q = get_daily_latest_exam_questions()
        assert len(daily_q["questions"]) >= 5
        assert "मराठी व्याकरण" in daily_q["questions"][0]["subject"]
        print("✅ Daily Latest Exam Questions engine passed!")
    asyncio.run(_impl())

def test_post_and_multi_tier_ranks():
    from app.parser import extract_post_and_metadata

    sample_sheet = """
    Roll Number: 23091823912
    Participant Name: Ramesh Pawar
    Test Date: 15/09/2023
    Post Name: ग्रामसेवक (Gramsevak)
    Subject: जिल्हा परिषद भरती २०२३
    """
    meta = extract_post_and_metadata(sample_sheet)
    assert "ग्रामसेवक" in meta["post_name"]
    assert meta["roll_number"] == "23091823912"

    overall_scores = [160.0, 150.0, 140.0, 130.0, 120.0, 110.0]
    exam_scores = [150.0, 140.0, 130.0, 120.0]
    post_scores = [140.0, 130.0, 120.0]
    cat_scores = [140.0, 120.0]
    post_cat_scores = [140.0, 120.0]

    ranks = estimate_cohort_rank(
        student_score=135.0,
        all_scores=exam_scores,
        category="OBC",
        category_scores=cat_scores,
        overall_scores=overall_scores,
        post_name="ग्रामसेवक (Gramsevak)",
        post_scores=post_scores,
        post_category_scores=post_cat_scores
    )

    assert ranks["overall_rank"] == 4
    assert ranks["exam_rank"] == 3
    assert ranks["post_rank"] == 2
    assert ranks["category_rank"] == 2
    assert ranks["post_category_rank"] == 2
    print("✅ 4-Tier Rank Engine (Overall, Exam, Post-wise, Category) passed!")

def test_html_and_exam_detection():
    from app.parser import parse_html_response_sheet, parse_answers, detect_exam
    import json

    with open("app/exams.json", "r", encoding="utf-8") as f:
        exams = json.load(f)

    # Test that 'STI' does not falsely match inside 'QUESTION' or 'INSTRUCTION'
    text_with_question = "Question 1: What is the capital? General Instruction for all candidates."
    res = detect_exam(text_with_question, exams)
    assert res.get("key") != "MPSC_COMBINED", "False positive: 'STI' matched inside QUESTION"

    # Test HTML parsing preserving correct answer indicators (.rightAns and tick images)
    sample_html = """
    <div class="question-pnl">
      <p>Q.1 What is the state flower of Maharashtra?</p>
      <table>
        <tr><td class="rightAns">1. Tamhan (जारूळ) <img src="images/tick.png"></td></tr>
        <tr><td>2. Rose (गुलाब)</td></tr>
      </table>
      <table>
        <tr><td>Question ID : 8801</td></tr>
        <tr><td>Option 1 ID : 9901</td></tr>
        <tr><td>Option 2 ID : 9902</td></tr>
        <tr><td>Status : Answered</td></tr>
        <tr><td>Chosen Option : 1</td></tr>
      </table>
    </div>
    """
    text = parse_html_response_sheet(sample_html)
    records = parse_answers(text)
    assert len(records) == 1
    assert records[0]["chosen_option_number"] == "1"
    assert records[0]["correct_option_number"] == "1"
    assert records[0]["selected_option_id"] == "9901"
    assert records[0]["correct_option_id"] == "9901"
    print("✅ HTML Response Sheet and Robust Exam Detection passed!")

def test_swot_and_qbank():
    from app.ai_analysis import generate_swot_analysis, format_swot_telegram_message, generate_oneliner_question_bank_pdf
    from app.parser import score_answers

    records = [
        {"question_id": "1", "section": "मराठी व्याकरण", "selected_option_id": "1", "correct_option_id": "1"},
        {"question_id": "2", "section": "मराठी व्याकरण", "selected_option_id": "2", "correct_option_id": "2"},
        {"question_id": "3", "section": "मराठी व्याकरण", "selected_option_id": "3", "correct_option_id": "3"},
        {"question_id": "4", "section": "English", "selected_option_id": "1", "correct_option_id": "2"},
        {"question_id": "5", "section": "English", "selected_option_id": "1", "correct_option_id": "3"},
        {"question_id": "6", "section": "GS", "selected_option_id": None, "correct_option_id": "4"},
        {"question_id": "7", "section": "GS", "selected_option_id": None, "correct_option_id": "4"},
        {"question_id": "8", "section": "GS", "selected_option_id": None, "correct_option_id": "4"},
    ]
    res = score_answers(records, {"positive_marks": 2.0, "negative_marks": 0.5})
    swot = generate_swot_analysis(records, res)
    assert len(swot["strengths"]) > 0
    assert len(swot["weaknesses"]) > 0
    assert len(swot["opportunities"]) > 0
    swot_msg = format_swot_telegram_message(swot)
    assert "SWOT विश्लेषण" in swot_msg
    print("✅ SWOT Performance Audit engine passed!")

    pdf_out = "reports/test_qbank_validation.pdf"
    gen_path = generate_oneliner_question_bank_pdf("bot.db", pdf_out, "तलाठी भरती २०२४")
    assert Path(gen_path).exists()
    assert Path(gen_path).stat().st_size > 1000
    print("✅ Admin One-Liner Question Bank PDF Generator passed!")

def test_quiz_dedup_and_passage():
    from app.quiz_generator import (
        compute_question_hash,
        is_quiz_already_posted,
        mark_quiz_as_posted,
        extract_quizzes_from_records,
        init_quiz_db
    )
    init_quiz_db("bot.db")
    test_q = "खालीलपैकी कर्मधारय समासाचे उदाहरण कोणते?"
    test_opts = ["नीलकमल", "बहिण-भाऊ", "यथाशक्ती", "नीलकंठ"]
    q_hash = compute_question_hash(test_q, test_opts)

    # Initially false or can mark
    mark_quiz_as_posted(q_hash, test_q, "मराठी व्याकरण", has_passage=True, db_path="bot.db")
    assert is_quiz_already_posted(q_hash, db_path="bot.db") is True

    # Test comprehension passage retention
    recs = [{
        "question_text": "उताऱ्यातील मुख्य विचार कोणता?",
        "options": {"1": "पर्याय १", "2": "पर्याय २", "3": "पर्याय ३", "4": "पर्याय ४"},
        "correct_option_number": "1",
        "section": "मराठी",
        "comprehension": "हा एक नमुना उतारा आहे ज्यावर आधारित प्रश्न विचारला गेला आहे."
    }]
    quizzes = extract_quizzes_from_records(recs, max_questions=1, filter_unposted=False, db_path="bot.db")
    assert len(quizzes) == 1
    assert "नमुना उतारा" in quizzes[0]["passage"]
    assert "[उताऱ्यावरील प्रश्न]" in quizzes[0]["question"]
    print("✅ Quiz Deduplication & Comprehension Passage support passed!")

if __name__ == "__main__":
    print("Running system validation tests...")
    test_rank()
    test_scoring_and_sections()
    test_post_and_multi_tier_ranks()
    test_html_and_exam_detection()
    test_monetization()
    test_swot_and_qbank()
    test_quiz_dedup_and_passage()
    asyncio.run(test_objection_analysis())
    asyncio.run(test_daily_topic_and_questions())
    print("🎉 ALL TESTS PASSED SUCCESSFULLY!")

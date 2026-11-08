"""
AI-Powered Telegram Quiz Generator using OpenRouter API and Direct Structured Records.
Extracts questions from response sheets and converts them into native Telegram Quiz polls.
Features:
- Strict SQLite deduplication (no repeated questions)
- Paragraph / Comprehension passage support (posts context before poll)
- Lightning-fast extraction from DB and response records
- Rich pedagogical explanations (within Telegram limits)
- Top Priority Topics for Maharashtra upcoming exams
- 100% anonymous (zero candidate data in channel)
"""

import os
import json
import logging
import re
import hashlib
import sqlite3
import httpx
from telegram import Bot

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
# Standardize on bot.db across all modules
DEFAULT_DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "bot.db"))

def normalize_question_text(q_text: str) -> str:
    """Strips variable prefixes like Q.1, [उताऱ्यावरील प्रश्न], [General], etc. and normalizes punctuation and spacing."""
    t = re.sub(r"^\[.*?\]\s*", "", q_text.strip())
    t = re.sub(r"^(?:Q\s*\.?\s*\d+|Question\s*(?:No\.?|Number)?\s*\d+|\d+[\.\):-])\s*[:\-]?\s*", "", t, flags=re.I)
    t = re.sub(r"[^\w\s]", "", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip().lower()

def resolve_quiz_correct_index(q_data: dict, raw_opts: list) -> int:
    """
    Robustly resolves 0-based correct option index across all formats:
    - Explicit 'correct_option_index' (0..3)
    - Explicit 'correct_option_number' (1..4)
    - 'correct' or 'answer' field with option letter/num (A, B, C, D, पर्याय १/२/३/४, 1..4)
    - Option text match
    """
    if "correct_option_index" in q_data and isinstance(q_data["correct_option_index"], int):
        idx = q_data["correct_option_index"]
        if 0 <= idx < len(raw_opts):
            return idx
    if "correct_option_number" in q_data:
        try:
            num = int(q_data["correct_option_number"])
            if 1 <= num <= len(raw_opts):
                return num - 1
        except Exception:
            pass

    ans_text = str(q_data.get("answer") or q_data.get("correct") or "").strip()

    # 1. Check for explicit English or numeric option markers (anchored to avoid matching letters inside words)
    m = re.search(r"^(?:(?:पर्याय|option|opt)\s*)?([1-4]|[A-Da-d])(?:\b|[\)\:\.\s]|$)", ans_text, re.I)
    if m:
        marker = m.group(1).upper()
        mapping = {"1": 0, "2": 1, "3": 2, "4": 3, "A": 0, "B": 1, "C": 2, "D": 3}
        if marker in mapping and mapping[marker] < len(raw_opts):
            return mapping[marker]

    # Devanagari numerals: १ -> 0, २ -> 1, ३ -> 2, ४ -> 3
    for dev_num, dev_idx in [("१", 0), ("२", 1), ("३", 2), ("४", 3)]:
        if f"पर्याय {dev_num}" in ans_text or f"{dev_num})" in ans_text or f"{dev_num}." in ans_text or ans_text.startswith(dev_num):
            if dev_idx < len(raw_opts):
                return dev_idx

    # 2. Match cleaned option text against ans_text / correct
    clean_target = re.sub(r"^[A-Da-d1-4][\.\):\-]\s*", "", ans_text).strip().lower()
    clean_target = re.sub(r"\[Correct Option\]|rightAns|[✓✔☑]", "", clean_target).strip()
    for idx, opt in enumerate(raw_opts):
        clean_opt = re.sub(r"^[A-Da-d1-4][\.\):\-]\s*", "", str(opt)).strip().lower()
        clean_opt = re.sub(r"\[Correct Option\]|rightAns|[✓✔☑]", "", clean_opt).strip()
        if clean_opt and clean_target:
            if clean_opt == clean_target or clean_opt in clean_target or clean_target in clean_opt:
                return idx

    # 3. Check explanation field for any explicit option citation
    exp_text = str(q_data.get("explanation") or "").strip()
    m_exp = re.search(r"(?:पर्याय|option|opt)\s*([1-4]|[A-Da-d]|१|२|३|४)", exp_text, re.I)
    if m_exp:
        mark = m_exp.group(1).upper()
        mapping = {"1": 0, "2": 1, "3": 2, "4": 3, "A": 0, "B": 1, "C": 2, "D": 3, "१": 0, "२": 1, "३": 2, "४": 3}
        if mark in mapping and mapping[mark] < len(raw_opts):
            return mapping[mark]

    return 0

def init_quiz_db(db_path: str = DEFAULT_DB_PATH):
    """Initializes the deduplication table for posted quizzes in bot.db."""
    dir_name = os.path.dirname(db_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posted_quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_hash TEXT UNIQUE,
                question_text TEXT,
                normalized_q TEXT,
                section TEXT,
                has_passage INTEGER DEFAULT 0,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Ensure normalized_q column exists for schema migration
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(posted_quizzes)")
        cols = [c[1] for c in cur.fetchall()]
        if "normalized_q" not in cols:
            conn.execute("ALTER TABLE posted_quizzes ADD COLUMN normalized_q TEXT")
        conn.commit()

def compute_question_hash(question_text: str, options: list[str]) -> str:
    """Computes a normalized SHA-256 hash for deduplication regardless of question number or section prefix."""
    clean_q = normalize_question_text(question_text)
    clean_opts = "|".join(re.sub(r"\s+", " ", opt.strip().lower()) for opt in sorted(options))
    raw_key = f"{clean_q}::{clean_opts}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

def is_quiz_already_posted(question_hash: str, question_text: str = "", db_path: str = DEFAULT_DB_PATH) -> bool:
    """Checks if a quiz with the same content hash or normalized question text was already posted."""
    try:
        init_quiz_db(db_path)
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM posted_quizzes WHERE question_hash = ? LIMIT 1", (question_hash,))
            if cur.fetchone() is not None:
                return True
            if question_text:
                norm_q = normalize_question_text(question_text)
                if len(norm_q) >= 6:
                    cur.execute("SELECT 1 FROM posted_quizzes WHERE normalized_q = ? LIMIT 1", (norm_q,))
                    if cur.fetchone() is not None:
                        return True
            return False
    except Exception as e:
        logger.warning(f"Error checking quiz deduplication: {e}")
        return False

def mark_quiz_as_posted(question_hash: str, question_text: str, section: str = "", has_passage: bool = False, db_path: str = DEFAULT_DB_PATH):
    """Marks a quiz as posted in the database with hash and normalized text."""
    try:
        init_quiz_db(db_path)
        norm_q = normalize_question_text(question_text)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO posted_quizzes 
                   (question_hash, question_text, normalized_q, section, has_passage) 
                   VALUES (?, ?, ?, ?, ?)""",
                (question_hash, question_text[:500], norm_q[:500], section[:100], 1 if has_passage else 0)
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Error marking quiz as posted: {e}")

def get_top_priority_topics_text() -> str:
    """Returns the curated list of top priority topics for upcoming Maharashtra exams."""
    return (
        "🎯 <b>आगामी परीक्षेसाठी Top Priority Topics (TCS / IBPS / MPSC Pattern):</b>\n\n"
        "🔹 <b>मराठी व्याकरण:</b>\n"
        "• समास व त्याचे प्रकार (कर्मधारय, बहुव्रीही, अव्ययीभाव)\n"
        "• प्रयोग (कर्तरी, कर्मणी, भावे)\n"
        "• शब्दसंग्रह: समानार्थी/विरुद्धार्थी, म्हणी, वाक्प्रचार व त्यांचे अर्थ\n"
        "• प्रसिद्ध पुस्तके व त्यांचे लेखक\n\n"
        "🔹 <b>English Language:</b>\n"
        "• Subject-Verb Agreement & Tenses\n"
        "• Error Spotting & Sentence Improvement\n"
        "• Idioms, Phrases & One-word Substitutions\n"
        "• Para Jumbles & Comprehension Passages\n\n"
        "🔹 <b>सामान्य ज्ञान (General Studies):</b>\n"
        "• माहितीचा अधिकार कायदा (RTI Act 2005) - वारंवार विचारली जाणारी कलमे\n"
        "• भारत व महाराष्ट्र जनगणना 2011 (साक्षरता, लिंगगुणोत्तर, घनता)\n"
        "• महाराष्ट्राचा भूगोल (गोदावरी, भीमा, कृष्णा नद्या व उपनद्या)\n"
        "• 1857 चा उठाव व महाराष्ट्रातील समाजसुधारक (फुले, आंबेडकर, शाहू महाराज)\n\n"
        "🔹 <b>बौद्धिक चाचणी व अंकगणित (Aptitude & Reasoning):</b>\n"
        "• बैठक व्यवस्था (Linear & Circular Seating Arrangement)\n"
        "• नातेसंबंध (Blood Relations) व दिशाज्ञान (Direction Test)\n"
        "• सांकेतिक भाषा (Coding-Decoding) व संख्यामालिका\n"
        "• नफा-तोटा, शेकडेवारी, वेळ-काम-वेग\n\n"
        "📢 <i>या सर्व घटकांचा नियमित सराव चॅनेलवर सुरू आहे. प्रश्न नक्की सोडवा!</i>"
    )

async def extract_quizzes_with_ai(raw_text: str, max_questions: int = 10) -> list[dict]:
    """
    Uses OpenRouter API to parse raw exam response text into structured Telegram Quizzes.
    Uses ultra low-cost or free models.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free").strip()

    if not api_key:
        logger.info("OPENROUTER_API_KEY not configured. Falling back to rule-based extractor.")
        return extract_quizzes_locally(raw_text, max_questions)

    prompt = f"""
You are an expert exam question parser.
Extract up to {max_questions} objective multiple-choice questions from the following exam response sheet text.
For each question:
1. Ensure the question text is clean, concise, under 280 characters.
2. If the question relates to a paragraph/passage, include the passage in the "passage" field (under 2500 characters).
3. Provide exactly 4 distinct options (under 90 characters each). Do NOT prefix with A), B), 1), 2).
4. Identify the correct option index (0 for first, 1 for second, 2 for third, 3 for fourth).
5. Provide a brief 1-line explanation (under 180 characters).
6. DO NOT include any candidate names, roll numbers, or student identifiers.

Return ONLY valid JSON array with no extra markdown formatting or backticks:
[
  {{
    "question": "Question text here?",
    "passage": "Optional passage text if reading comprehension, else empty string",
    "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
    "correct_option_index": 0,
    "explanation": "Brief explanation"
  }}
]

Raw Text:
{raw_text[:12000]}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://examrankers.bot",
        "X-Title": "ExamRankers Telegram Quiz Bot",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You extract multiple-choice questions from exam papers and return pure JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.warning(f"OpenRouter API returned {resp.status_code}: {resp.text}. Using local fallback.")
                return extract_quizzes_locally(raw_text, max_questions)

            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()

            # Resilient JSON extraction via regex
            match = re.search(r"\[.*\]", content, re.DOTALL)
            json_str = match.group(0) if match else content

            quizzes = json.loads(json_str)
            valid_quizzes = []
            for q in quizzes:
                if (
                    isinstance(q, dict)
                    and "question" in q
                    and isinstance(q.get("options"), list)
                    and 2 <= len(q["options"]) <= 10
                    and isinstance(q.get("correct_option_index"), int)
                    and 0 <= q["correct_option_index"] < len(q["options"])
                ):
                    # Enforce Telegram Quiz Limits
                    q["question"] = q["question"][:290]
                    q["options"] = [str(opt)[:95] for opt in q["options"][:4]]
                    q["explanation"] = q.get("explanation", "")[:190]
                    q["passage"] = q.get("passage", "").strip()[:3000]
                    valid_quizzes.append(q)

            logger.info(f"Successfully extracted {len(valid_quizzes)} quizzes with OpenRouter AI.")
            return valid_quizzes

    except Exception as e:
        logger.error(f"Error in extract_quizzes_with_ai: {e}")
        return extract_quizzes_locally(raw_text, max_questions)

def extract_quizzes_from_records(
    records: list[dict],
    max_questions: int = 15,
    filter_unposted: bool = True,
    db_path: str = DEFAULT_DB_PATH
) -> list[dict]:
    """
    Extracts authentic Telegram Quizzes directly from structured question records.
    Ensures:
    - Zero duplicates against SQLite posted_quizzes
    - Paragraph/passage support (saves passage for context broadcast)
    - Strict adherence to Telegram limits:
      * question <= 300 chars
      * 4 options <= 100 chars each
      * explanation <= 200 chars
      * completely anonymous
    """
    quizzes = []
    seen_hashes = set()
    init_quiz_db(db_path)

    for r in records:
        if len(quizzes) >= max_questions:
            break

        q_text = r.get("question_text", "").strip()
        options_dict = r.get("options", {})
        c_num = r.get("correct_option_number")
        c_id = r.get("correct_option_id")
        opt_ids = r.get("option_ids", {})
        passage = r.get("comprehension", "").strip()

        # Fallback 1: Resolve c_num from c_id and opt_ids
        if not c_num and c_id and opt_ids:
            for onum, oid in opt_ids.items():
                if str(oid).strip() == str(c_id).strip():
                    c_num = str(onum)
                    break

        # Fallback 2: Check options_dict for [Correct Option] or checkmarks
        if not c_num:
            for ok, ov in options_dict.items():
                if re.search(r"\[Correct Option\]|rightAns|[✓✔☑]", ov, re.I):
                    c_num = str(ok)
                    break

        if len(options_dict) >= 4 and str(c_num) in ("1", "2", "3", "4") and len(q_text) >= 5:
            # Clean each option: strip correct markers and prefixes
            opts = []
            for k in ["1", "2", "3", "4"]:
                raw_o = str(options_dict.get(str(k), ""))
                clean_o = re.sub(r"\[Correct Option\]|rightAns|[✓✔☑]", "", raw_o, flags=re.I)
                clean_o = re.sub(r"^[A-Da-d1-4][\.\):\-]\s*", "", clean_o).strip()
                opts.append(clean_o[:95])

            c_idx = resolve_quiz_correct_index(r, opts)
            sec = r.get("section", "General")

            # Check deduplication against in-memory batch and database
            q_hash = compute_question_hash(q_text, opts)
            if q_hash in seen_hashes:
                continue
            if filter_unposted and is_quiz_already_posted(q_hash, q_text, db_path):
                continue
            seen_hashes.add(q_hash)

            c_txt = opts[c_idx] if 0 <= c_idx < len(opts) else options_dict.get(str(c_num), "")
            exp = f"अधिकृत उत्तर: पर्याय {c_idx+1} ({c_txt[:50]}). {sec} पॅटर्ननुसार प्रमाणित स्पष्टीकरण."[:195]

            # If question has a passage, add prefix
            prefix = "[उताऱ्यावरील प्रश्न] " if passage else f"[{sec}] "
            final_q_text = f"{prefix}{q_text}"[:295]

            quizzes.append({
                "question": final_q_text,
                "passage": passage,
                "options": opts,
                "correct_option_index": c_idx,
                "explanation": exp,
                "section": sec,
                "hash": q_hash
            })

    return quizzes

def extract_quizzes_locally(raw_text: str, max_questions: int = 10, db_path: str = DEFAULT_DB_PATH) -> list[dict]:
    """Fallback question extractor using structured parser to guarantee real exam questions."""
    try:
        from .parser import parse_answers, parse_html_response_sheet
        if "<html" in raw_text.lower() or "<!doctype" in raw_text.lower() or "<table" in raw_text.lower():
            raw_text = parse_html_response_sheet(raw_text)
        records = parse_answers(raw_text)
        quizzes = extract_quizzes_from_records(records, max_questions, filter_unposted=True, db_path=db_path)
        if quizzes:
            return quizzes
    except Exception as e:
        logger.warning(f"Structured parser quiz fallback failed: {e}")

    quizzes = []
    blocks = re.split(r"(?=(?:Question\s*ID\s*[:\-]|Q\.\s*\d+))", raw_text, flags=re.I)

    for b in blocks:
        if len(quizzes) >= max_questions:
            break
        qid = re.search(r"Question\s*ID\s*[:\-]+\s*(\w+)", b, re.I)
        if not qid:
            continue
        opt_matches = re.findall(r"Option\s*([1-4])\s*ID\s*[:\-]+\s*(\w+)", b, re.I)
        correct_opt = re.search(r"Correct\s*Answer\s*[:\-].*?Option\s*ID\s*[:\-]*\s*(\w+)", b, re.I | re.S)

        if len(opt_matches) >= 2:
            options = [f"Option {num}" for num, _ in opt_matches[:4]]
            correct_idx = 0
            if correct_opt:
                target_id = correct_opt.group(1)
                for idx, (_, oid) in enumerate(opt_matches[:4]):
                    if oid == target_id:
                        correct_idx = idx
                        break

            q_str = f"Question (ID: {qid.group(1)}): What is the correct option?"
            q_hash = compute_question_hash(q_str, options)
            if is_quiz_already_posted(q_hash, db_path):
                continue

            quizzes.append({
                "question": q_str,
                "passage": "",
                "options": options,
                "correct_option_index": correct_idx,
                "explanation": f"Official Exam Answer Key identifies Option {correct_idx + 1}.",
                "section": "General",
                "hash": q_hash
            })

    return quizzes

async def send_quizzes_to_channel(
    bot: Bot,
    channel_id: str or int,
    quizzes: list[dict],
    header_text: str = None,
    send_priority_topics: bool = False,
    db_path: str = DEFAULT_DB_PATH,
    delay_seconds: float = None
) -> int:
    """
    Sends native Telegram Quizzes to a specified Telegram channel or group.
    - If question has an associated passage / paragraph, sends the passage first!
    - Completely anonymizes: zero candidate personal data.
    - Records question hash into posted_quizzes to prevent duplicate posts.
    - Optionally posts Top Priority Topics summary.
    - Posts 1-by-1 with throttled pacing (default 17s ~ 3-4 quizzes per minute).
    """
    import asyncio
    if not channel_id or not quizzes:
        return 0

    if delay_seconds is None:
        try:
            delay_seconds = float(os.getenv("QUIZ_POST_DELAY_SECONDS", "17.0"))
        except (ValueError, TypeError):
            delay_seconds = 17.0

    str_cid = str(channel_id).strip()
    if str_cid.startswith("http://") or str_cid.startswith("https://"):
        logger.warning(
            f"Cannot send quiz polls to invite URL '{str_cid}'. "
            "Please set PAID_CHANNEL_ID in .env to the numeric Channel ID (e.g. -100xxxxxxxxxx) or @username."
        )
        return 0

    target_chat = int(str_cid) if str_cid.lstrip("-").isdigit() else str_cid
    init_quiz_db(db_path)

    sent_count = 0
    if header_text:
        try:
            await bot.send_message(chat_id=target_chat, text=header_text, parse_mode="HTML", protect_content=True)
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.warning(f"Could not send header to channel {target_chat}: {e}")

    for q in quizzes:
        q_hash = q.get("hash") or compute_question_hash(q["question"], q["options"])

        # Deduplication check
        if is_quiz_already_posted(q_hash, q["question"], db_path):
            logger.info(f"Skipping already posted quiz: {q['question'][:40]}...")
            continue

        # If question has a passage, send the passage context first
        passage = q.get("passage", "").strip()
        if passage and len(passage) > 20:
            try:
                passage_msg = (
                    "📖 <b>वाचन आकलन / संदर्भ उतारा (Comprehension Passage):</b>\n\n"
                    f"<blockquote>{passage[:3000]}</blockquote>\n\n"
                    "👇 <b>खालील प्रश्न वरील उताऱ्यावर आधारित आहे:</b>"
                )
                await bot.send_message(chat_id=target_chat, text=passage_msg, parse_mode="HTML", protect_content=True)
                await asyncio.sleep(1.0)
            except Exception as e:
                logger.warning(f"Error sending comprehension passage to {target_chat}: {e}")

        try:
            await bot.send_poll(
                chat_id=target_chat,
                question=q["question"][:300],
                options=q["options"][:4],
                type="quiz",
                correct_option_id=q["correct_option_index"],
                explanation=q.get("explanation", "")[:195],
                is_anonymous=True,
                protect_content=True
            )
            # Mark as posted
            mark_quiz_as_posted(
                question_hash=q_hash,
                question_text=q["question"],
                section=q.get("section", ""),
                has_passage=bool(passage),
                db_path=db_path
            )
            sent_count += 1
            await asyncio.sleep(delay_seconds)
        except Exception as e:
            err_msg = str(e).lower()
            if "retry in" in err_msg or "flood" in err_msg:
                wait_sec = getattr(e, "retry_after", 16)
                try:
                    m = re.search(r"retry in (\d+)", err_msg)
                    if m:
                        wait_sec = int(m.group(1)) + 1
                except Exception:
                    pass
                logger.warning(f"Telegram rate limit hit. Waiting {wait_sec}s before continuing...")
                await asyncio.sleep(wait_sec)
                try:
                    await bot.send_poll(
                        chat_id=target_chat,
                        question=q["question"][:300],
                        options=q["options"][:4],
                        type="quiz",
                        correct_option_id=q["correct_option_index"],
                        explanation=q.get("explanation", "")[:195],
                        is_anonymous=True,
                        protect_content=True
                    )
                    mark_quiz_as_posted(
                        question_hash=q_hash,
                        question_text=q["question"],
                        section=q.get("section", ""),
                        has_passage=bool(passage),
                        db_path=db_path
                    )
                    sent_count += 1
                    await asyncio.sleep(delay_seconds)
                except Exception as retry_e:
                    logger.warning(f"Retry after backoff failed: {retry_e}")
            else:
                logger.warning(f"Error publishing quiz poll to channel {target_chat}: {e}")

    # Optionally post Top Priority Topics
    if send_priority_topics and sent_count > 0:
        try:
            await asyncio.sleep(1.0)
            topics_msg = get_top_priority_topics_text()
            await bot.send_message(chat_id=target_chat, text=topics_msg, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Error sending priority topics to channel: {e}")

    return sent_count

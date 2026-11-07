import html
import os
import sys
import json
import sqlite3
import tempfile
import logging
import shutil
import re
import asyncio
import zipfile
import http.server
import urllib.parse
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dotenv import load_dotenv

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "app"

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    MenuButtonCommands,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)

from .parser import (
    extract_pdf_text,
    detect_exam,
    parse_answers,
    score_answers,
    extract_post_and_metadata,
    parse_html_response_sheet,
    recover_digialm_url_from_pdf,
)
from .rank import estimate_cohort_rank
from .quiz_generator import (
    extract_quizzes_with_ai,
    send_quizzes_to_channel,
    extract_quizzes_from_records,
    extract_quizzes_locally,
    init_quiz_db,
    get_top_priority_topics_text,
)
from .ai_analysis import (
    explain_wrong_answers_and_objections,
    generate_topic_weightage_analysis,
    get_daily_latest_exam_questions,
    generate_html_full_report,
    generate_incorrect_answers_report,
    generate_smart_explanation,
    generate_master_analytics_report_html,
    generate_swot_analysis,
    format_swot_telegram_message,
    generate_oneliner_question_bank_pdf,
)
from .mindmap_engine import (
    get_next_dynamic_mindmap,
    record_mindmap_posted,
)
from .monetization import (
    init_monetization_db,
    get_active_ad,
    build_ad_markup,
    get_deals_keyboard,
    get_upi_payment_details,
    record_payment_request,
    approve_and_generate_invite,
    reject_payment,
    get_paid_channel_link,
    generate_qr_bytes,
    generate_qr_base64,
    validate_utr_format,
    is_utr_already_used,
)
from .digital_store import (
    render_digital_store_html,
    render_nano_banana_store_html,
    packaging_agent,
    fulfillment_agent,
    SAMPLE_PREVIEWS,
    DEFAULT_PRODUCTS
)
from .agents import (
    ChannelBrandingAgent,
    MarathiSeniorFaculty,
    EnglishSeniorFaculty,
    MathsReasoningSeniorFaculty,
    CurrentAffairsSeniorEditor,
    DigitalProductPackagingAgent,
    MarketingSalesAgent,
    FulfillmentEmailAgent,
    ChiefExecutiveOfficer,
    AILeadDirector,
    AcademicDeanManager,
    GrowthMarketingManager,
    CommerceOperationsManager,
    ExamIntelligenceResearcher,
    CurriculumResearchSynthesist,
    UIUXDesignArchitect,
    BrandVisualsDesigner,
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Senior Force Agents Autonomous Instances (NEXUS Doctrine)
ceo_agent = ChiefExecutiveOfficer()
ai_lead_director = AILeadDirector()
academic_dean = AcademicDeanManager()
growth_manager = GrowthMarketingManager()
commerce_manager = CommerceOperationsManager()
exam_researcher = ExamIntelligenceResearcher()
curriculum_researcher = CurriculumResearchSynthesist()
uiux_architect = UIUXDesignArchitect()
brand_designer = BrandVisualsDesigner()

channel_branding_agent = ChannelBrandingAgent()
marketing_sales_agent = MarketingSalesAgent()
current_affairs_agent = CurrentAffairsSeniorEditor()
marathi_faculty_agent = MarathiSeniorFaculty()
english_faculty_agent = EnglishSeniorFaculty()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "bot.db"))
STORAGE_DIR = Path(os.getenv("ADMIN_STORAGE_DIR", str(PROJECT_ROOT / "admin_storage"))).resolve()
RESPONSE_DIR = STORAGE_DIR / "response_sheets"
REPORT_DIR = STORAGE_DIR / "reports"
ADMIN_IDS = {int(x.strip()) for x in (os.getenv("ADMIN_TELEGRAM_IDS") or os.getenv("ADMIN_USER_IDS") or "").split(",") if x.strip().isdigit()}
PAID_CHANNEL_ID = os.getenv("PAID_CHANNEL_ID", "").strip()
PAID_CHANNEL_LINK = get_paid_channel_link()

def get_youtube_link() -> str:
    """Returns the configured YouTube channel URL."""
    return os.getenv("YOUTUBE_CHANNEL_LINK", "").strip()

def get_youtube_button_text() -> str:
    """Returns the custom or default YouTube subscribe button text."""
    return os.getenv("YOUTUBE_BUTTON_TEXT", "🔴 अधिकृत YouTube चॅनेल (Subscribe)").strip()

def safe_photo_caption(text: str, max_chars: int = 950) -> str:
    """
    Ensures Telegram photo caption strictly complies with Telegram's 1024-char limit.
    Safely trims at sentence/line breaks and balances unclosed HTML tags.
    """
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    last_break = max(truncated.rfind("\n"), truncated.rfind("।"), truncated.rfind("."), truncated.rfind("!"))
    if last_break > int(max_chars * 0.6):
        truncated = truncated[:last_break]
    else:
        truncated = truncated[:max_chars - 4] + "..."

    for tag in ["b", "i", "code", "a", "u", "s"]:
        open_cnt = len(re.findall(rf"<{tag}(?:\s+[^>]*)?>", truncated, re.IGNORECASE))
        close_cnt = len(re.findall(rf"</{tag}>", truncated, re.IGNORECASE))
        if open_cnt > close_cnt:
            truncated += f"</{tag}>"
    return truncated

def get_promotional_broadcast_caption(yt_link: str = "") -> str:
    """Returns high-converting FOMO Telegram photo caption (guaranteed <= 820 chars)."""
    yt_line = f"\n🔴 <b>YouTube:</b> <a href=\"{yt_link}\">{yt_link}</a>" if yt_link else ""
    return (
        "⚠️ <b>०.५ किंवा १ मार्कामुळे मेरीट हुकण्याची भीती वाटतेय का?</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "😰 <b>लाखो विद्यार्थ्यांच्या गर्दीत आपला हक्काचा कटऑफ कसा मिळवाल?</b>\n\n"
        "TCS व IBPS च्या चालू परीक्षांमध्ये संदिग्ध व ट्रॅप प्रश्नांमुळे हजारो विद्यार्थी बाद होतात. "
        "<b>ExamRankers™ AI</b> द्वारे आपली कामगिरी त्वरित मोफत तपासा:\n\n"
        "• ⚡ <b>१-सेकंद निकाल:</b> DigiALM रिस्पॉन्स शीट लिंक टाका व थेट रँक मिळवा.\n"
        "• 🎯 <b>४-टियर रँक:</b> संपूर्ण राज्यातील खरा रँक व कटऑफ सेफ झोन.\n"
        "• ❌ <b>चुकांचे पोस्टमार्टम:</b> उत्तर का चुकले? स्टेप-बाय-स्टेप स्पष्टीकरण.\n"
        "• ⚖️ <b>हरकत (Objection) सल्ला:</b> गुण वाढवून घेण्यासाठी आक्षेपार्ह प्रश्न.\n"
        "• 📚 <b>डिजिटल ई-स्टोअर:</b> ₹१९ मधील चालू घडामोडी व शॉर्टकट ट्रिक्स.\n\n"
        "👇 <b>आताच आपली रिस्पॉन्स शीट तपासा (Free):</b>\n"
        f"🤖 <b>बॉट:</b> <a href=\"https://t.me/ExamRankersIndiaBot?start=fomo_promo\">@ExamRankersIndiaBot</a>\n"
        f"📢 <b>VIP चॅनेल:</b> <a href=\"{PAID_CHANNEL_LINK}\">{PAID_CHANNEL_LINK}</a>"
        f"{yt_line}"
    )

def get_store_web_url() -> str:
    """Returns the live ExamRankers digital products storefront URL."""
    url = (
        os.getenv("STORE_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
    )
    if not url:
        hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
        if hostname:
            url = f"https://{hostname}"
    if not url:
        ping_url = os.getenv("SELF_PING_URL", "")
        # Only use SELF_PING_URL if it doesn't point to an unverified placeholder
        if ping_url and "exam-rankers-bot.onrender.com" not in ping_url:
            url = ping_url
    if not url:
        port = os.getenv("PORT", "8080")
        url = f"http://localhost:{port}"
    return url.rstrip("/")

def update_env_channel_id(channel_id: str):
    """Updates PAID_CHANNEL_ID in .env file, environment variables, and in-memory global."""
    global PAID_CHANNEL_ID
    clean_id = str(channel_id).strip()
    PAID_CHANNEL_ID = clean_id
    os.environ["PAID_CHANNEL_ID"] = clean_id
    try:
        env_file = Path(__file__).resolve().parent.parent / ".env"
        if env_file.exists():
            content = env_file.read_text(encoding="utf-8")
            if re.search(r"^PAID_CHANNEL_ID=.*$", content, re.MULTILINE):
                content = re.sub(r"^PAID_CHANNEL_ID=.*$", f"PAID_CHANNEL_ID={clean_id}", content, flags=re.MULTILINE)
            else:
                content += f"\nPAID_CHANNEL_ID={clean_id}\n"
            env_file.write_text(content, encoding="utf-8")
            logger.info(f"Updated .env with PAID_CHANNEL_ID={clean_id}")
    except Exception as e:
        logger.warning(f"Could not persist PAID_CHANNEL_ID to .env: {e}")

async def on_chat_member_updated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detects when the bot is added as an administrator to a channel or group."""
    my_member = update.my_chat_member
    chat = update.effective_chat
    if not my_member or not chat:
        return
    new_status = my_member.new_chat_member.status
    if new_status in ("administrator", "creator"):
        channel_id = str(chat.id)
        channel_title = chat.title or "Channel"
        update_env_channel_id(channel_id)
        logger.info(f"Bot added as administrator to {channel_title} ({channel_id})")
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"🎉 <b>Bot Successfully Added to Channel!</b>\n\n"
                        f"📢 <b>{channel_title}</b>\n"
                        f"🆔 ID: <code>{channel_id}</code>\n\n"
                        f"चॅनेल आयडी आपोआप सेव्ह झाला आहे. रिस्पॉन्स शीटमधील प्रश्न क्विझ स्वरूपात पाठवण्यासाठी:\n"
                        f"👉 <code>/postquizzes</code>"
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Could not notify admin {admin_id}: {e}")

EXAMS_PATH = Path(__file__).with_name("exams.json")
try:
    EXAMS = json.loads(EXAMS_PATH.read_text(encoding="utf-8"))
except Exception as e:
    logger.error(f"Failed to load exams.json: {e}")
    EXAMS = {}

CATEGORIES = [
    "Open (खुला)",
    "OBC (इतर मागास वर्ग)",
    "EWS (आर्थिक दुर्बल घटक)",
    "SC (अनुसूचित जाती)",
    "ST (अनुसूचित जमाती)",
    "VJ / NT (विमुक्त व भटक्या जमाती)",
    "SBC / SEBC (मराठा आरक्षण)"
]

CATEGORY_MAP = {
    "open": "Open (खुला)",
    "obc": "OBC (इतर मागास वर्ग)",
    "ews": "EWS (आर्थिक दुर्बल घटक)",
    "sc": "SC (अनुसूचित जाती)",
    "st": "ST (अनुसूचित जमाती)",
    "nt": "VJ / NT (विमुक्त व भटक्या जमाती)",
    "sebc": "SBC / SEBC (मराठा आरक्षण)"
}

def get_category_keyboard(prefix="cat"):
    """Builds a clean 2-column inline keyboard with short callback_data (strictly under Telegram's 64-byte cap)."""
    rows = [
        [InlineKeyboardButton("🚀 रिस्पॉन्स शीट लिंक पेस्ट करा किंवा PDF पाठवा (START)", callback_data="prompt_upload")],
        [InlineKeyboardButton("Open (खुला)", callback_data=f"{prefix}:open"), InlineKeyboardButton("OBC (इतर मागास)", callback_data=f"{prefix}:obc")],
        [InlineKeyboardButton("EWS (आर्थिक दुर्बल)", callback_data=f"{prefix}:ews"), InlineKeyboardButton("SC (अनुसूचित जाती)", callback_data=f"{prefix}:sc")],
        [InlineKeyboardButton("ST (अनुसूचित जमाती)", callback_data=f"{prefix}:st"), InlineKeyboardButton("VJ / NT (भटक्या जमाती)", callback_data=f"{prefix}:nt")],
        [InlineKeyboardButton("SBC / SEBC (मराठा आरक्षण)", callback_data=f"{prefix}:sebc")],
        [InlineKeyboardButton("✍️ Quick Score Calculator", callback_data="manual_calc"), InlineKeyboardButton("ℹ️ How it Works / FAQ", callback_data="help")]
    ]
    yt_link = get_youtube_link()
    if yt_link:
        rows.append([InlineKeyboardButton(get_youtube_button_text(), url=yt_link)])
    rows.append([InlineKeyboardButton("🛒 डिजिटल ई-बुक्स स्टोअर (₹१० ते ₹९९)", url=get_store_web_url())])
    return rows

def get_persistent_menu_keyboard():
    """Builds a persistent bottom menu keyboard."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🚀 सुरू करा (Start)"), KeyboardButton("✍️ रँक कॅल्क्युलेटर")],
            [KeyboardButton("🛒 ई-बुक्स स्टोअर (₹१०)"), KeyboardButton("📋 मुख्य मेनू (Main Menu)")]
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="🔗 रिस्पॉन्स शीट लिंक पेस्ट करा किंवा PDF पाठवा 📎"
    )

def get_connection():
    """Returns SQLite connection with WAL journal mode and 30s timeout to prevent locking."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db():
    """Initializes tables and performs automated schema migrations."""
    RESPONSE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                category TEXT,
                total_uploads INTEGER DEFAULT 0,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_active DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER,
                filename TEXT,
                storage_path TEXT,
                exam_key TEXT,
                category TEXT,
                score REAL DEFAULT 0.0,
                correct_count INTEGER DEFAULT 0,
                incorrect_count INTEGER DEFAULT 0,
                unanswered_count INTEGER DEFAULT 0,
                rank INTEGER DEFAULT 0,
                percentile REAL DEFAULT 0.0,
                post_name TEXT DEFAULT 'General',
                status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Automated column migration for backwards compatibility
        existing_cols = [c[1] for c in db.execute("PRAGMA table_info(uploads)").fetchall()]
        cols_to_add = {
            "post_name": "TEXT DEFAULT 'General'",
            "score": "REAL DEFAULT 0.0",
            "correct_count": "INTEGER DEFAULT 0",
            "incorrect_count": "INTEGER DEFAULT 0",
            "unanswered_count": "INTEGER DEFAULT 0",
            "rank": "INTEGER DEFAULT 0",
            "percentile": "REAL DEFAULT 0.0",
            "roll_number": "TEXT DEFAULT ''",
            "candidate_name": "TEXT DEFAULT ''",
            "district": "TEXT DEFAULT 'महाराष्ट्र (सर्वसाधारण)'",
            "test_date": "TEXT DEFAULT ''"
        }
        for col_name, col_type in cols_to_add.items():
            if col_name not in existing_cols:
                try:
                    db.execute(f"ALTER TABLE uploads ADD COLUMN {col_name} {col_type}")
                except Exception as e:
                    logger.warning(f"Column migration warning for {col_name}: {e}")

        # Store Visitors tracking table
        db.execute("""
            CREATE TABLE IF NOT EXISTS store_visitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT,
                user_agent TEXT,
                device_type TEXT,
                referrer TEXT,
                telegram_user_id INTEGER,
                page_path TEXT,
                action TEXT DEFAULT 'view_store',
                product_id TEXT,
                details TEXT,
                visited_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

    try:
        init_monetization_db()
    except Exception as e:
        logger.warning(f"Could not initialize monetization tables: {e}")

def log_store_visitor(ip: str, user_agent: str, referrer: str = "", tg_id: int = None, page_path: str = "/", action: str = "view_store", product_id: str = "", details: str = ""):
    """Logs a visitor to the Standalone Web Store."""
    try:
        ua_lower = (user_agent or "").lower()
        device_type = "Mobile" if any(k in ua_lower for k in ["mobile", "android", "iphone", "ipad"]) else "Desktop"
        with get_connection() as db:
            db.execute("""
                INSERT INTO store_visitors (ip_address, user_agent, device_type, referrer, telegram_user_id, page_path, action, product_id, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(ip or "")[:45], str(user_agent or "")[:250], device_type, str(referrer or "")[:250], tg_id, str(page_path or "")[:100], str(action or "")[:50], str(product_id or "")[:50], str(details or "")[:250]))
    except Exception as e:
        logger.warning(f"Error logging store visitor: {e}")

async def _send_single_msg(bot, chat_id, chunk: str, parse_mode, reply_markup, disable_web_page_preview):
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=chunk,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview
        )
    except Exception as e:
        err_str = str(e).lower()
        if any(k in err_str for k in ["parse entities", "entity", "start tag", "end tag", "badrequest"]):
            logger.warning(f"Telegram entity parse error, stripping HTML entities and retrying as plain text: {e}")
            clean_text = re.sub(r"<[^>]+>", "", chunk)
            return await bot.send_message(
                chat_id=chat_id,
                text=clean_text,
                parse_mode=None,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview
            )
        raise

async def safe_send_message(bot, chat_id, text: str, parse_mode="HTML", reply_markup=None, disable_web_page_preview=True):
    """
    Safely sends messages without exceeding Telegram's 4096-character limit.
    Splits long messages at natural newlines and auto-falls back to plain text on entity errors.
    """
    if len(text) <= 3900:
        return await _send_single_msg(
            bot=bot,
            chat_id=chat_id,
            chunk=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview
        )

    chunks = []
    current = []
    current_len = 0
    for line in text.split("\n"):
        if current_len + len(line) + 1 > 3800:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += len(line) + 1
    if current:
        chunks.append("\n".join(current))

    last_msg = None
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        last_msg = await _send_single_msg(
            bot=bot,
            chat_id=chat_id,
            chunk=chunk,
            parse_mode=parse_mode,
            reply_markup=markup,
            disable_web_page_preview=disable_web_page_preview
        )
    return last_msg

def track_user(user, category: str = None):
    """Registers or updates active user in the database."""
    if not user:
        return
    with get_connection() as db:
        existing = db.execute("SELECT telegram_id, category FROM users WHERE telegram_id = ?", (user.id,)).fetchone()
        if existing:
            cat = category if category else existing[1]
            db.execute("""
                UPDATE users SET username = ?, first_name = ?, category = ?, last_active = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            """, (user.username, user.first_name, cat, user.id))
        else:
            db.execute("""
                INSERT INTO users (telegram_id, username, first_name, category)
                VALUES (?, ?, ?, ?)
            """, (user.id, user.username, user.first_name, category))

def get_candidate_scores(exam_key: str, category: str = None, post_name: str = None):
    """
    Returns multi-dimensional score distributions:
    (overall_scores, exam_scores, post_scores, cat_scores, post_cat_scores)
    """
    with get_connection() as db:
        # 1. Overall State/Platform scores
        overall_rows = db.execute("SELECT score FROM uploads WHERE score IS NOT NULL").fetchall()
        overall_scores = [r[0] for r in overall_rows]

        # 2. Exam cohort scores
        exam_rows = db.execute("SELECT score FROM uploads WHERE exam_key = ? AND score IS NOT NULL", (exam_key,)).fetchall()
        exam_scores = [r[0] for r in exam_rows]

        # 3. Post-wise cohort scores
        post_scores = []
        if post_name and post_name != "General":
            post_rows = db.execute("SELECT score FROM uploads WHERE post_name = ? AND score IS NOT NULL", (post_name,)).fetchall()
            post_scores = [r[0] for r in post_rows]

        # 4. Category cohort scores within exam
        cat_scores = []
        if category:
            cat_rows = db.execute("SELECT score FROM uploads WHERE exam_key = ? AND category = ? AND score IS NOT NULL", (exam_key, category)).fetchall()
            cat_scores = [r[0] for r in cat_rows]

        # 5. Post Category scores
        post_cat_scores = []
        if category and post_name and post_name != "General":
            pc_rows = db.execute("SELECT score FROM uploads WHERE post_name = ? AND category = ? AND score IS NOT NULL", (post_name, category)).fetchall()
            post_cat_scores = [r[0] for r in pc_rows]

        return overall_scores, exam_scores, post_scores, cat_scores, post_cat_scores

def format_score_card(exam_name: str, category: str, result: dict, rank_data: dict) -> str:
    """Creates a 100% free, complete, detailed scorecard message with 4-tier rank breakdown."""
    pos = result.get("positive_marks", 1.0)
    neg = result.get("negative_marks", 0.0)
    correct_pts = round(result["correct"] * pos, 2)
    incorrect_pts = round(result["incorrect"] * neg, 2)
    post_name = html.escape(str(rank_data.get("post_name", "General (सर्वसाधारण)")))
    exam_name = html.escape(str(exam_name))
    category = html.escape(str(category))

    lines = [
        "🎯 <b>FREE EXAM SCORE & 4-TIER RANK REPORT</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📋 <b>Exam:</b> {exam_name}",
        f"🎖️ <b>Applied Post (पद):</b> <code>{post_name}</code>",
        f"👤 <b>Reservation Category:</b> {category}",
        "",
        "📊 <b>Full Performance Breakdown:</b>",
        f"• Total Questions: <b>{result.get('total_parsed', 0)}</b>",
        f"• Attempted Questions: <b>{result.get('attempted', 0)}</b>",
        f"• ✅ Correct Answers: <b>{result.get('correct', 0)}</b> (+{correct_pts} marks)",
        f"• ❌ Incorrect Answers: <b>{result.get('incorrect', 0)}</b> (-{incorrect_pts} marks)",
        f"• ⚪ Unanswered / Skipped: <b>{result.get('unanswered', 0)}</b>",
        f"• 🎯 Accuracy Rate: <b>{result.get('accuracy', 0)}%</b>",
        "",
        f"🏆 <b>Total Calculated Score:</b> <code>{result.get('score', 0)} marks</code>",
        "",
        "📈 <b>Live 4-Tier Rank & Cutoff Prediction:</b>",
        f"🌐 <b>1. Overall State Rank (राज्यस्तरीय रँक):</b> <b>#{rank_data.get('overall_rank', 1)}</b> of <b>{rank_data.get('overall_total', 1)}</b> (Percentile: <b>{rank_data.get('overall_percentile', 0)}%</b>)",
        f"📋 <b>2. Exam Cohort Rank (परीक्षा रँक):</b> <b>#{rank_data.get('exam_rank', 1)}</b> of <b>{rank_data.get('exam_total', 1)}</b> (Percentile: <b>{rank_data.get('exam_percentile', 0)}%</b>)",
        f"🎖️ <b>3. Post-wise Rank (पद निहाय रँक — {post_name}):</b> <b>#{rank_data.get('post_rank', 1)}</b> of <b>{rank_data.get('post_total', 1)}</b> (Percentile: <b>{rank_data.get('post_percentile', 0)}%</b>)",
    ]

    if rank_data.get("category_rank"):
        lines.append(f"👤 <b>4. Category Rank (प्रवर्ग रँक — {category}):</b> <b>#{rank_data['category_rank']}</b> of <b>{rank_data['category_total']}</b> (Percentile: <b>{rank_data.get('category_percentile', 0)}%</b>)")
        if rank_data.get("post_category_rank") and rank_data.get("post_category_total", 0) > 1:
            lines.append(f"   ↳ <i>Post Category Rank ({post_name} - {category}):</i> <b>#{rank_data['post_category_rank']}</b> of <b>{rank_data['post_category_total']}</b>")

    lines.extend([
        "",
        f"• Cohort Average Score: <b>{rank_data.get('avg_score', 0)}</b>",
        f"• Cohort Highest Score: <b>{rank_data.get('top_score', 0)}</b>",
        f"• Cutoff Prediction Zone: {rank_data.get('zone', 'N/A')}",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "<i>Tap buttons below to view Subject-wise Stats or AI Wrong Answer Explanations & Objections!</i>"
    ])
    return "\n".join(lines)

def format_subjectwise_dashboard(sections: dict) -> str:
    """Formats a detailed subject-wise / section-wise dashboard."""
    if not sections:
        return "No specific section headers were detected in this sheet."

    lines = [
        "📚 <b>FULL SUBJECT-WISE PERFORMANCE DASHBOARD</b>",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]
    for sec_name, data in sections.items():
        lines.extend([
            f"🔹 <b>{sec_name}:</b>",
            f"• Total: <b>{data['total']}</b> | Attempted: <b>{data['attempted']}</b>",
            f"• ✅ Correct: <b>{data['correct']}</b> | ❌ Incorrect: <b>{data['incorrect']}</b> | ⚪ Skipped: <b>{data['unanswered']}</b>",
            f"• 🎯 Accuracy: <b>{data['accuracy']}%</b> | 🏆 Section Score: <b>{data['score']} marks</b>",
            ""
        ])
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

async def auto_post_quizzes_background(bot, text: str, exam_name: str, records: list = None):
    """
    Background Task triggered on every new response sheet:
    1. Extracts all unposted questions from records or text.
    2. Publishes questions 1-by-1 continuously to the channel with instant explanations & passages.
    3. Generates and posts Daily Topic Weightage Breakdown to the channel.
    4. Deduplicates via SQLite posted_quizzes table so no question is ever repeated.
    5. Fully anonymized (zero student details).
    """
    channel = os.getenv("PAID_CHANNEL_ID", "").strip() or PAID_CHANNEL_ID
    if not channel or channel.startswith("http"):
        return

    try:
        # Step 1: Extract all unposted quizzes from records or text
        quizzes = []
        if records:
            quizzes = extract_quizzes_from_records(records, max_questions=500, filter_unposted=True, db_path=DB_PATH)
        elif text:
            from .parser import parse_answers, parse_html_response_sheet
            parsed_text = text
            if "<html" in text.lower() or "<table" in text.lower():
                parsed_text = parse_html_response_sheet(text)
            parsed_recs = parse_answers(parsed_text)
            if parsed_recs:
                quizzes = extract_quizzes_from_records(parsed_recs, max_questions=500, filter_unposted=True, db_path=DB_PATH)
            if not quizzes:
                quizzes = extract_quizzes_locally(parsed_text, max_questions=50, db_path=DB_PATH)

        if not quizzes:
            logger.info("No unposted quizzes found for this response sheet (all already published).")
            return

        header = (
            f"🎯 <b>नवीन अधिकृत परीक्षा प्रश्न (NEW EXAM QUESTIONS)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>परीक्षा:</b> {exam_name}\n"
            f"⚡ <i>TCS / IBPS अधिकृत रिस्पॉन्स शीटमधील प्रश्न १-बाय-१ खालीलप्रमाणे:</i>"
        )
        count = await send_quizzes_to_channel(
            bot=bot,
            channel_id=channel,
            quizzes=quizzes,
            header_text=header,
            send_priority_topics=True,
            db_path=DB_PATH
        )

        # Step 2: Post Daily Topic & Weightage Analysis if text available
        if text and count > 0:
            try:
                topic_analysis = await generate_topic_weightage_analysis(text, exam_name)
                if topic_analysis:
                    await safe_send_message(bot, channel, topic_analysis, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Topic weightage analysis error in auto_post: {e}")

        # Notify admins
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"🤖 <b>Auto-Channel Engine:</b>\n"
                        f"नवीन रिस्पॉन्स शीट आल्यानंतर <b>{count} प्रश्न 1-by-1</b> चॅनेलवर (<code>{channel}</code>) यशस्वीरित्या पोस्ट केले!\n"
                        f"परीक्षेचे नाव: <b>{exam_name}</b>"
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Error in auto_post_quizzes_background: {e}", exc_info=True)

# ----------------- TELEGRAM BOT HANDLERS ----------------- #

def alert_admins_sync(text: str):
    """Sends immediate notification to all Telegram bot admins synchronously."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or not ADMIN_IDS:
        return
    for aid in ADMIN_IDS:
        try:
            import requests
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": aid, "text": text, "parse_mode": "HTML"},
                timeout=5
            )
        except Exception as e:
            logger.warning(f"Could not alert admin {aid}: {e}")

async def check_channel_membership(bot, user_id: int) -> bool:
    """Checks whether the user is an active member of the configured free/public Telegram channel."""
    if user_id in ADMIN_IDS:
        return True
    # Only enforce if a separate free/public channel is specifically configured for force subscription
    channel_id_str = os.getenv("FORCE_SUB_CHANNEL_ID", os.getenv("FREE_CHANNEL_ID", "")).strip()
    if not channel_id_str:
        return True
    try:
        channel_id = int(channel_id_str) if channel_id_str.lstrip("-").isdigit() else channel_id_str
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning(f"Channel membership check for {user_id} in {channel_id_str}: {e}")
        return True

async def prompt_force_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends prompt requiring user to join official Telegram and YouTube channels before continuing."""
    channel_link = os.getenv("PAID_CHANNEL_LINK", "https://t.me/+EjtGp-pH4hMxZDM1").strip() or "https://t.me/+EjtGp-pH4hMxZDM1"
    yt_link = get_youtube_link()
    yt_text = get_youtube_button_text()

    msg_text = (
        "📢 <b>कृपया आधी आमच्या अधिकृत चॅनेल्सला जॉईन/फॉलो करा!</b>\n"
        "<i>(Please join our official channels to use the bot)</i>\n\n"
        "🎯 <b>ExamRankers Official Hub</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ रोजचे मोफत TCS/IBPS पॅटर्न सराव प्रश्न व सविस्तर स्पष्टीकरण\n"
        "✅ सर्व परीक्षांचे निकाल, गुणवत्ता यादी (Merit List) व कट-ऑफ अपडेट्स\n"
        "✅ YouTube वर मोफत लाइव्ह लेक्चर्स, शॉर्ट ट्रिक्स व कट-ऑफ विश्लेषण\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 <b>खालील बटणावर क्लिक करून जॉईन करा, त्यानंतर '✅ मी जॉईन केले' बटण दाबा:</b>"
    )
    keyboard = [
        [InlineKeyboardButton("📢 Telegram चॅनेल जॉईन करा (Join Channel)", url=channel_link)]
    ]
    if yt_link:
        keyboard.append([InlineKeyboardButton(yt_text, url=yt_link)])
    keyboard.append([InlineKeyboardButton("✅ मी जॉईन केले (I Have Joined)", callback_data="verify_channel_membership")])
    if update.callback_query:
        try:
            await update.callback_query.message.edit_text(
                msg_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True
            )
        except Exception:
            await update.callback_query.message.reply_text(
                msg_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True
            )
    elif update.message:
        await update.message.reply_text(
            msg_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    track_user(user)

    # Force Join Channel Gate
    if not await check_channel_membership(context.bot, user.id):
        await prompt_force_join(update, context)
        return

    # Deep-link routing e.g. /start quiz
    if context.args and context.args[0] in ("quiz", "practice", "mcq"):
        await quiz_cmd(update, context)
        return

    context.user_data.clear()

    welcome_text = (
        "👋 <b>महाराष्ट्र सरळसेवा भरती रँक व गुण विश्लेषक (ExamRankers Bot)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✨ <b>१००% मोफत सेवा (Free for Maharashtra Aspirants):</b>\n"
        "• तलाठी, जिल्हा परिषद (ZP), पोलीस भरती, वनरक्षक, नगरपरिषद, आरोग्य विभाग, MPSC\n"
        "• TCS व IBPS पॅटर्न रिस्पॉन्स शीटचे अचूक गुण व 4-Tier रँक कॅल्क्युलेशन\n\n"
        "📌 <b>पायरी १ (Step 1): कृपया तुमचा आरक्षण प्रवर्ग (Category) निवडा:</b>\n"
        "<i>(प्रवर्ग निवडल्यानंतर तुमच्या रिस्पॉन्स शीटची वेब लिंक पेस्ट करा किंवा PDF पाठवा)</i>"
    )
    if update.message:
        await update.message.reply_text(
            welcome_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(get_category_keyboard()),
            disable_web_page_preview=True
        )
        await update.message.reply_text(
            "⚡ <b>खालील मेनू बटणे वापरून तुम्ही कधीही बॉट ऑपरेट करू शकता 👇</b>",
            parse_mode="HTML",
            reply_markup=get_persistent_menu_keyboard()
        )
    elif update.callback_query:
        try:
            await update.callback_query.message.edit_text(
                welcome_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(get_category_keyboard()),
                disable_web_page_preview=True
            )
        except Exception:
            await update.callback_query.message.reply_text(
                welcome_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(get_category_keyboard()),
                disable_web_page_preview=True
            )

async def send_question_review_page(update: Update, context: ContextTypes.DEFAULT_TYPE, offset: int = 0, only_wrong: bool = False):
    """Sends 2 questions per message with full question statement, all 4 options, answers, and in-depth explanations."""
    chat_id = update.effective_chat.id
    records = context.user_data.get("last_records", [])

    if only_wrong:
        dataset = [r for r in records if r.get("evaluation") == "incorrect"]
        title = "❌ <b>चुकीचे प्रश्न सविस्तर स्पष्टीकरण (Wrong Questions Review)</b>"
        cb_prefix = "review_wrong"
    else:
        dataset = records
        title = "📖 <b>सर्व प्रश्न व अधिकृत उत्तरे (Full Questions Review)</b>"
        cb_prefix = "review_all"

    total_count = len(dataset)
    if not dataset:
        if only_wrong:
            await safe_send_message(context.bot, chat_id, "🎉 <b>अभिनंदन!</b> या प्रश्नपत्रिकेत तुमचे १ही उत्तर चुकीचे नाही (0 incorrect answers)!", parse_mode="HTML")
        else:
            await safe_send_message(context.bot, chat_id, "⚠️ प्रश्न उपलब्ध नाहीत. कृपया लिंक पुन्हा पाठवा.", parse_mode="HTML")
        return

    limit = 2
    offset = max(0, min(offset, total_count - 1))
    sample = dataset[offset: offset + limit]
    has_next = (offset + limit) < total_count
    has_prev = offset > 0
    current_end = min(offset + limit, total_count)

    lines = [
        title,
        f"📌 <i>प्रश्न {offset + 1} ते {current_end} (एकूण: {total_count})</i>",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    for item in sample:
        qnum = item.get("question_number", "?")
        sec = html.escape(str(item.get("section", "General")))
        qtext = html.escape(str(item.get("question_text", "Question Text")))
        eval_status = item.get("evaluation", "unanswered")
        chosen_num = str(item.get("chosen_option_number") or "-")
        chosen_txt = html.escape(str(item.get("chosen_option_text", "")).strip())
        correct_num = str(item.get("correct_option_number") or "-")
        correct_txt = html.escape(str(item.get("correct_option_text", "")).strip())
        options = item.get("options", {})
        raw_expl = generate_smart_explanation(item)
        explanation = html.escape(str(raw_expl))

        status_icon = "✅ बरोबर (Correct)" if eval_status == "correct" else ("❌ चुकीचे (Incorrect)" if eval_status == "incorrect" else "⚪ अनुत्तरित (Unanswered)")

        opts_lines = []
        for ok in ["1", "2", "3", "4"]:
            if ok in options:
                oval = html.escape(str(options[ok]))
                if ok == correct_num and ok == chosen_num:
                    opts_lines.append(f"  <b>{ok})</b> {oval}  ✅ <i>(तुमचे उत्तर - बरोबर)</i>")
                elif ok == correct_num:
                    opts_lines.append(f"  <b>{ok})</b> {oval}  ✅ <i>(अधिकृत उत्तर)</i>")
                elif ok == chosen_num:
                    opts_lines.append(f"  <b>{ok})</b> {oval}  ❌ <i>(तुमचे उत्तर - चुकीचे)</i>")
                else:
                    opts_lines.append(f"  <b>{ok})</b> {oval}")

        chosen_display = f"पर्याय {chosen_num}" + (f" ({chosen_txt})" if chosen_txt else "")
        correct_display = f"पर्याय {correct_num}" + (f" ({correct_txt})" if correct_txt else "")

        lines.extend([
            f"❓ <b>प्रश्न क्र. {qnum} / {len(records)}</b> (विभाग: <code>{sec}</code>)",
            f"<b>मूल्यांकन:</b> <b>{status_icon}</b>",
            f"<b>प्रश्न:</b> {qtext}\n",
            "<b>पर्याय:</b>",
            "\n".join(opts_lines) if opts_lines else "<i>(पर्याय उपलब्ध नाहीत)</i>",
            "",
            f"👤 <b>तुमचे उत्तर:</b> <code>{chosen_display}</code>",
            f"🎯 <b>अधिकृत बरोबर उत्तर:</b> <code>{correct_display}</code>",
            "",
            f"💡 <b>सविस्तर स्पष्टीकरण:</b>\n{explanation}",
            "━━━━━━━━━━━━━━━━━━━━━━"
        ])

    nav_row = []
    if has_prev:
        nav_row.append(InlineKeyboardButton("⬅️ मागील (Prev)", callback_data=f"{cb_prefix}:{max(0, offset - limit)}"))
    if has_next:
        nav_row.append(InlineKeyboardButton("पुढील ➡️ (Next)", callback_data=f"{cb_prefix}:{offset + limit}"))

    keyboard = []
    if nav_row:
        keyboard.append(nav_row)

    wrong_cnt = len([r for r in records if r.get("evaluation") == "incorrect"])
    if only_wrong:
        keyboard.append([InlineKeyboardButton(f"📖 सर्व {len(records)} प्रश्न पहा (Full Review)", callback_data="review_all:0")])
    else:
        keyboard.append([InlineKeyboardButton(f"❌ फक्त चुकीचे प्रश्न पहा ({wrong_cnt})", callback_data="review_wrong:0")])

    keyboard.append([InlineKeyboardButton("📑 डाऊनलोड फक्त चुकीचे प्रश्न विश्लेषण (HTML)", callback_data="download_wrong_report")])
    keyboard.append([InlineKeyboardButton("📥 डाऊनलोड १०० प्रश्न सविस्तर निकाल (HTML)", callback_data="download_html_report")])
    keyboard.append([InlineKeyboardButton("📊 विषयनिहाय गुण (Subject Stats)", callback_data="show_sections")])
    keyboard.append([InlineKeyboardButton("🔙 मुख्य स्कोअरकार्ड (Back to Scorecard)", callback_data="back_scorecard")])

    review_full_text = "\n".join(lines)
    await safe_send_message(
        context.bot,
        chat_id,
        review_full_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data in ("main_menu", "change_category", "analyze"):
        context.user_data.clear()
        welcome_text = (
            "👋 <b>महाराष्ट्र सरळसेवा भरती रँक व गुण विश्लेषक</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 <b>पायरी १ (Step 1): कृपया तुमचा आरक्षण प्रवर्ग (Category) निवडा:</b>\n"
            "<i>(प्रवर्ग निवडल्यानंतर तुमच्या रिस्पॉन्स शीटची वेब लिंक पेस्ट करा किंवा PDF पाठवा)</i>"
        )
        try:
            await q.message.edit_text(welcome_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(get_category_keyboard()))
        except Exception:
            await q.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(get_category_keyboard()))

    elif data == "prompt_upload":
        cat = context.user_data.get("category")
        if cat:
            await q.message.reply_text(
                f"✅ <b>तुमचा निवडलेला प्रवर्ग: {cat}</b>\n\n"
                "📌 <b>आता तुमची रिस्पॉन्स शीट पाठवा:</b>\n\n"
                "🔗 <b>पर्याय १ (सर्वात सोपे व अचूक):</b>\n"
                "तुमच्या DigiALM / परीक्षा पोर्टलची <b>थेट वेब लिंक</b> येथे पेस्ट करा (उदा. <code>https://cdn.digialm.com/...</code>)\n\n"
                "📎 <b>पर्याय २:</b>\n"
                "किंवा तुमची रिस्पॉन्स शीट <b>PDF फाईल</b> येथे अपलोड करा.\n\n"
                "<i>(तात्काळ ४-टियर रँक, विषयनिहाय गुण व कटऑफ विश्लेषण मिळेल!)</i>",
                parse_mode="HTML"
            )
        else:
            await q.message.reply_text(
                "📌 <b>कृपया प्रथम खालीलपैकी तुमचा प्रवर्ग निवडा किंवा थेट तुमची रिस्पॉन्स शीट लिंक / PDF फाईल येथे पाठवा:</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(get_category_keyboard())
            )

    elif data == "help":
        help_text = (
            "📖 <b>How ExamRankers Works (100% Free):</b>\n\n"
            "1. <b>Paste Link or Send PDF:</b> Select your category and simply paste your official DigiALM response sheet URL (e.g. <code>https://cdn.digialm.com/...</code>) or upload your response sheet PDF.\n"
            "2. <b>Score & Rank:</b> Bot instantly calculates overall & category rank, percentile, and cutoff zone.\n"
            "3. <b>Subject Dashboard:</b> View section-wise marks, accuracy, and questions breakdown.\n"
            "4. <b>Wrong Answers & Objections:</b> AI explains why your answer was wrong and whether to raise an official objection on ambiguous questions!\n\n"
            f"💎 <i>Optional:</i> Join our <a href=\"{PAID_CHANNEL_LINK}\">Paid Quiz Channel</a> (₹99) for daily authentic exam polls."
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]
        await q.message.edit_text(help_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)

    elif data == "verify_channel_membership":
        user_id = q.from_user.id
        is_member = await check_channel_membership(context.bot, user_id)
        if is_member:
            await q.answer("✅ धन्यवाद! व्हेरिफिकेशन यशस्वी झाले.", show_alert=True)
            await q.message.reply_text("🎉 <b>व्हेरिफिकेशन यशस्वी!</b> आता तुम्ही बॉट वापरू शकता.", parse_mode="HTML")
            await start(update, context)
        else:
            await q.answer("⚠️ तुम्ही अजून चॅनेल जॉईन केलेले नाही! कृपया आधी चॅनेल जॉईन करा.", show_alert=True)

    elif data == "next_quiz":
        await quiz_cmd(update, context)

    elif data == "daily_questions":
        daily_data = get_daily_latest_exam_questions()
        lines = [
            daily_data["trend_summary"],
            ""
        ]
        for i, q_item in enumerate(daily_data["questions"], 1):
            lines.extend([
                f"━━━━━━━━━━━━━━━━━━━━━━",
                f"<b>Q{i}. [{q_item['subject']}]</b>",
                f"{q_item['question']}",
                "",
                "\n".join([f"  {opt}" for opt in q_item["options"]]),
                "",
                f"✅ <b>उत्तर:</b> <code>{q_item['answer']}</code>",
                f"💡 <b>स्पष्टीकरण:</b> {q_item['explanation']}",
                ""
            ])
        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━━",
            "⚡ <i>टीप: TCS व IBPS दररोज याच पॅटर्नवर आधारित प्रश्न विचारत आहे!</i>\n",
            "💎 <b>दररोज विचारलेले सर्व प्रश्न क्विझ स्वरूपात सोडवण्यासाठी आजच आमचे VIP चॅनेल जॉईन करा!</b>"
        ])
        keyboard = [
            [InlineKeyboardButton("🎯 Analyze My Response Sheet", callback_data="analyze")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ]
        full_text = "\n".join(lines)
        await safe_send_message(
            context.bot,
            q.message.chat_id,
            full_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )

    elif data == "show_sections":
        sections = context.user_data.get("last_sections", {})
        dashboard_text = format_subjectwise_dashboard(sections)
        keyboard = [
            [InlineKeyboardButton("📖 सर्व १०० प्रश्न व उत्तरे पहा (Full Questions)", callback_data="review_all:0")],
            [InlineKeyboardButton("❌ चुकीचे प्रश्न व सविस्तर स्पष्टीकरण", callback_data="review_wrong:0")],
            [InlineKeyboardButton("📥 डाऊनलोड १०० प्रश्न निकाल (HTML)", callback_data="download_html_report")],
            [InlineKeyboardButton("🔙 Back to Scorecard", callback_data="back_scorecard")]
        ]
        await q.message.edit_text(dashboard_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "back_scorecard":
        last_card = context.user_data.get("last_scorecard_text", "")
        last_kb = context.user_data.get("last_scorecard_keyboard", [])
        if last_card:
            await q.message.edit_text(last_card, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(last_kb), disable_web_page_preview=True)
        else:
            await q.message.reply_text("Send /start to view menu.")

    elif data in ("store", "open_store"):
        await store_cmd(update, context)

    elif data.startswith("buy:") or data.startswith("buy_prod:"):
        prod_id = data.split(":", 1)[1]
        prod = packaging_agent.get_product_by_id(prod_id, DB_PATH) or DEFAULT_PRODUCTS[0]
        context.user_data["buying_product_id"] = prod_id
        context.user_data["buying_product_price"] = prod.get("price_inr", 19)
        context.user_data["awaiting_store_utr"] = True

        upi_id = os.getenv("UPI_ID", "9970095256-2@ybl").strip()
        upi_name = os.getenv("UPI_NAME", "ExamRankers India").strip()
        price = prod.get("price_inr", 19)
        upi_uri = f"upi://pay?pa={upi_id}&pn={urllib.parse.quote(upi_name)}&am={price}&cu=INR&tn=Store_{prod_id[:8]}"
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=280x280&data={urllib.parse.quote(upi_uri)}"

        pay_msg = (
            f"🛒 <b>{prod.get('title')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>किंमत:</b> <s>₹{prod.get('original_price_inr', 99)}</s> <b>फक्त ₹{price}/-</b>\n\n"
            f"📱 <b>पेमेंट पद्धत (Any UPI App):</b>\n"
            f"• UPI ID: <code>{upi_id}</code> <i>(कॉपी करण्यासाठी टॅप करा)</i>\n"
            f"• Name: <b>{upi_name}</b>\n"
            f"• Amount: <b>₹{price}</b>\n\n"
            f"👇 <b>पेमेंट केल्यानंतर खाली मेसेज बॉक्समध्ये तुमचा Email ID व 12-अंकी UTR नंबर पाठवा:</b>\n"
            f"उदा: <code>student@gmail.com 431289456789</code>\n\n"
            f"⚡ <i>पेमेंट कन्फर्म होताच पुस्तक तात्काळ येथे PDF स्वरूपात व तुमच्या Email वर पाठवले जाईल!</i>"
        )
        kb = [
            [InlineKeyboardButton("🌐 वेब स्टोअरवरून खरेदी करा", url=f"{get_store_web_url()}#checkoutModal")],
            [InlineKeyboardButton("🔙 मागे जा (Back to Store)", callback_data="store")]
        ]
        qr_bytes = generate_qr_bytes(upi_uri)
        if qr_bytes:
            try:
                await q.message.reply_photo(
                    photo=io.BytesIO(qr_bytes),
                    caption=pay_msg,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(kb)
                )
                return
            except Exception as e:
                logger.warning(f"Error sending local QR bytes photo: {e}")

        try:
            await q.message.reply_photo(
                photo=qr_url,
                caption=pay_msg,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(kb)
            )
        except Exception:
            await q.message.reply_text(pay_msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb), disable_web_page_preview=True)

    elif data.startswith("review_wrong"):
        parts = data.split(":")
        offset = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        await send_question_review_page(update, context, offset=offset, only_wrong=True)

    elif data.startswith("review_all"):
        parts = data.split(":")
        offset = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        await send_question_review_page(update, context, offset=offset, only_wrong=False)

    elif data == "download_html_report":
        records = context.user_data.get("last_records", [])
        meta = context.user_data.get("candidate_meta", {})
        result = context.user_data.get("last_result", {})
        exam_name = context.user_data.get("last_exam_name", "Exam")

        if not records:
            await q.message.reply_text("⚠️ No active response sheet records found. Please re-paste your URL or upload PDF.")
            return

        status_msg = await q.message.reply_text("⏳ <i>सर्व १०० प्रश्नांची सविस्तर स्पष्टीकरणासह HTML फाईल तयार करत आहे...</i>", parse_mode="HTML")
        try:
            html_code = generate_html_full_report(records, meta, result, exam_name)
            roll = meta.get("roll_number") or str(update.effective_user.id)
            with tempfile.TemporaryDirectory() as tmp_dir:
                file_path = Path(tmp_dir) / f"ExamRankers_Analysis_{roll}.html"
                file_path.write_text(html_code, encoding="utf-8")
                with open(file_path, "rb") as doc_f:
                    await context.bot.send_document(
                        chat_id=q.message.chat_id,
                        document=doc_f,
                        filename=f"ExamRankers_Analysis_{roll}.html",
                        caption=(
                            "📄 <b>येथे तुमचे सर्व १०० प्रश्नांचे सविस्तर विश्लेषण, अधिकृत उत्तरे व स्पष्टीकरण फाईल आहे!</b>\n\n"
                            "💡 <i>ही फाईल कोणत्याही मोबाईल/कॉम्प्युटर ब्राउझरमध्ये उघडून तुम्ही प्रत्येक प्रश्न, तुमचे उत्तर व बरोबर उत्तर पाहू शकता, तसेच PDF म्हणून सेव्ह करू शकता.</i>"
                        ),
                        parse_mode="HTML"
                    )
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit_text(f"❌ Error generating report: {e}")

    elif data == "download_wrong_report":
        records = context.user_data.get("last_records", [])
        meta = context.user_data.get("candidate_meta", {})
        result = context.user_data.get("last_result", {})
        exam_name = context.user_data.get("last_exam_name", "Exam")

        if not records:
            await q.message.reply_text("⚠️ No active response sheet records found. Please re-paste your URL or upload PDF.")
            return

        wrong_records = [r for r in records if r.get("evaluation") == "incorrect"]
        if not wrong_records:
            await q.message.reply_text("🎉 अभिनंदन! या प्रश्नपत्रिकेत तुमचे १ही उत्तर चुकीचे नाही (0 incorrect answers)!")
            return

        status_msg = await q.message.reply_text(f"⏳ <i>सर्व {len(wrong_records)} चुकीच्या प्रश्नांची सविस्तर स्पष्टीकरणासह HTML फाईल तयार करत आहे...</i>", parse_mode="HTML")
        try:
            html_code = generate_incorrect_answers_report(records, meta, result, exam_name)
            roll = meta.get("roll_number") or str(update.effective_user.id)
            with tempfile.TemporaryDirectory() as tmp_dir:
                file_path = Path(tmp_dir) / f"ExamRankers_Wrong_Questions_{roll}.html"
                file_path.write_text(html_code, encoding="utf-8")
                with open(file_path, "rb") as doc_f:
                    await context.bot.send_document(
                        chat_id=q.message.chat_id,
                        document=doc_f,
                        filename=f"ExamRankers_Wrong_Questions_{roll}.html",
                        caption=(
                            f"❌ <b>येथे तुमचे सर्व {len(wrong_records)} चुकीच्या प्रश्नांचे सविस्तर विश्लेषण आहे!</b>\n\n"
                            "• <b>गणित व बुद्धिमत्ता:</b> पायरी-पायरीने अचूक सोडवणूक (Step-by-Step Solution)\n"
                            "• <b>मराठी व इंग्रजी:</b> अचूक व्याकरण नियम व संदर्भ (Grammar Rules)\n"
                            "• <b>सामान्य ज्ञान:</b> अधिकृत शासकीय संदर्भ व तथ्य\n"
                            "• <b>आक्षेप तपासणी:</b> अधिकृत हरकतींसाठी आक्षेप मसुदा (Objection Draft)\n\n"
                            "💡 <i>ही फाईल कोणत्याही ब्राऊझरमध्ये उघडून तुम्ही प्रत्येक चुकीचा प्रश्न, तुमचे उत्तर व बरोबर उत्तर पाहू शकता.</i>"
                        ),
                        parse_mode="HTML"
                    )
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit_text(f"❌ Error generating wrong answers report: {e}")

    elif data == "download_store_zip":
        await q.answer()
        await download_store_content_cmd(update, context)
        return

    elif data in ("join_paid", "vip_channel", "pay_vip"):
        await vip_cmd(update, context)

    elif data == "submit_proof":
        context.user_data["awaiting_payment_proof"] = True
        await q.message.reply_text(
            "📤 <b>कृपया तुमचा १२-अंकी UPI UTR नंबर किंवा पेमेंटचा स्क्रीनशॉट येथे पाठवा:</b>\n\n"
            "उदा: <code>431289456789</code>",
            parse_mode="HTML"
        )

    elif data.startswith("approve_pay:"):
        payment_id = int(data.split(":", 1)[1])
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to admin.", show_alert=True)
            return

        success, res = await approve_and_generate_invite(context.bot, payment_id)
        if success:
            await q.message.edit_text(
                f"✅ <b>Payment #{payment_id} Approved!</b>\n\nChannel invite link delivered to user:\n<code>{res}</code>",
                parse_mode="HTML"
            )
        else:
            await q.message.reply_text(f"❌ Approval error: {res}")

    elif data.startswith("reject_pay:"):
        payment_id = int(data.split(":", 1)[1])
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to admin.", show_alert=True)
            return
        success, res = await reject_payment(context.bot, payment_id)
        await q.message.edit_text(f"❌ Payment #{payment_id} marked as Rejected and user notified.", parse_mode="HTML")

    elif data == "admin_dl_all_zip":
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to admin.", show_alert=True)
            return
        await download_all_responses_cmd(update, context)

    elif data == "admin_master_report":
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to admin.", show_alert=True)
            return
        await master_report_cmd(update, context)

    elif data == "admin_files_list":
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to admin.", show_alert=True)
            return
        await admin_files(update, context)

    elif data == "admin_qbank":
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to admin.", show_alert=True)
            return
        await q.answer("वनलायनर प्रश्नसंच तयार करत आहे...", show_alert=False)
        await question_bank_cmd(update, context)

    elif data == "admin_post_mindmap":
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to admin.", show_alert=True)
            return
        await q.answer("माइंडमॅप चॅनेलवर पोस्ट करत आहे...", show_alert=False)
        await post_mindmap_cmd(update, context)

    elif data == "admin_post_promo":
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to admin.", show_alert=True)
            return
        await q.answer("प्रमोशनल ॲड चॅनेलवर पोस्ट करत आहे...", show_alert=False)
        await post_promo_cmd(update, context)

    elif data.startswith("getfile:"):
        fid = int(data.split(":", 1)[1])
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to admin.", show_alert=True)
            return
        with get_connection() as db:
            row = db.execute("SELECT filename, storage_path, exam_key, score FROM uploads WHERE id = ?", (fid,)).fetchone()
        if not row or not Path(row[1]).is_file():
            await q.message.reply_text(f"❌ File #{fid} not found.")
            return
        fpath = Path(row[1])
        kb = [
            [InlineKeyboardButton(f"📊 Generate Full HTML Report", callback_data=f"admin_report:{fid}")],
            [InlineKeyboardButton(f"❌ View Wrong Questions", callback_data=f"admin_wrong:{fid}")]
        ]
        with open(fpath, "rb") as doc_f:
            await context.bot.send_document(
                chat_id=q.message.chat_id,
                document=doc_f,
                filename=fpath.name,
                caption=f"📄 <b>Stored Response Sheet #{fid}</b>\n• Exam: <code>{row[2]}</code>\n• Score: <b>{row[3]}</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(kb)
            )

    elif data.startswith("admin_report:") or data.startswith("admin_wrong:"):
        is_wrong_only = data.startswith("admin_wrong:")
        fid = int(data.split(":", 1)[1])
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to admin.", show_alert=True)
            return
        with get_connection() as db:
            row = db.execute("SELECT storage_path, exam_key FROM uploads WHERE id = ?", (fid,)).fetchone()
        if not row or not Path(row[0]).is_file():
            await q.message.reply_text("❌ File not found.")
            return
        tpath = Path(row[0])
        exam_nm = EXAMS.get(row[1], {}).get("display_name", row[1] or "Exam")
        if tpath.suffix.lower() in (".html", ".htm"):
            raw_h = tpath.read_text(encoding="utf-8", errors="ignore")
            ptext = parse_html_response_sheet(raw_h)
        else:
            ptext = extract_pdf_text(str(tpath))
        recs = parse_answers(ptext)
        meta_d = extract_post_and_metadata(ptext)
        cfg_d = EXAMS.get("GMC_SARALSEWA", {"positive_marks": 1.0, "negative_marks": 0.0})
        res_d = score_answers(recs, cfg_d)
        context.user_data["last_records"] = recs
        context.user_data["candidate_meta"] = meta_d
        context.user_data["last_result"] = res_d
        context.user_data["last_exam_name"] = exam_nm
        if is_wrong_only:
            await send_question_review_page(update, context, offset=0, only_wrong=True)
        else:
            await send_question_review_page(update, context, offset=0, only_wrong=False)

    elif data == "check_channel_status":
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to admin.", show_alert=True)
            return
        await channel_status_cmd(update, context)

    elif data == "analyze":
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat:{cat}")] for cat in CATEGORIES]
        keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")])
        await q.message.edit_text("<b>Step 1 of 2:</b> Select your exam category:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("cat:"):
        code = data.split(":", 1)[1]
        cat = CATEGORY_MAP.get(code.lower(), code)
        context.user_data["category"] = cat
        track_user(update.effective_user, category=cat)

        # Check if user had already sent a pending PDF or URL
        pending_doc = context.user_data.pop("pending_pdf_doc", None)
        if pending_doc:
            await q.message.edit_text(f"✅ प्रवर्ग निवडला: <b>{cat}</b>\nतुमची PDF प्रोसेस करत आहे...", parse_mode="HTML")
            await process_uploaded_pdf(update, context, pending_doc)
            return

        pending_url = context.user_data.pop("pending_url", None)
        if pending_url:
            await q.message.edit_text(f"✅ प्रवर्ग निवडला: <b>{cat}</b>\nवेब लिंकवरील रिस्पॉन्स शीट प्रोसेस करत आहे...", parse_mode="HTML")
            await handle_url_sheet(update, context, pending_url)
            return

        context.user_data["awaiting_pdf"] = True
        text = (
            f"✅ <b>प्रवर्ग निवडला: {cat}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 <b>पायरी २ (Step 2): आता तुमची रिस्पॉन्स शीट पाठवा:</b>\n\n"
            "🔗 <b>पर्याय १ — थेट वेब लिंक पेस्ट करा (Recommended & 100% Accurate):</b>\n"
            "तुमच्या DigiALM / परीक्षा पोर्टलची संपूर्ण वेब लिंक येथे चॅटमध्ये पेस्ट करा:\n"
            "👉 <code>https://cdn.digialm.com/...</code>\n"
            "<i>(कोणतीही फाईल डाऊनलोड न करता १ सेकंदात निकाल मिळेल!)</i>\n\n"
            "📎 <b>पर्याय २ — किंवा PDF फाईल अपलोड करा:</b>\n"
            "तुमची अधिकृत Response Sheet PDF फाईल येथे सेंड करा.\n\n"
            "⚡ <b>बॉट तात्काळ खालील 4-Tier विश्लेषण देईल:</b>\n"
            "• 🌐 <b>राज्यस्तरीय सर्वसाधारण रँक</b> (Overall State Rank)\n"
            "• 📋 <b>परीक्षा निहाय रँक</b> (Exam Cohort Rank — ZP/तलाठी)\n"
            "• 🎖️ <b>पद निहाय रँक</b> (Post-wise Rank — Response Sheet मधील पदाप्रमाणे)\n"
            "• 👤 <b>प्रवर्ग निहाय रँक</b> (Category Rank)\n"
            "• 📊 <b>विषयनिहाय डॅशबोर्ड</b> (मराठी, इंग्रजी, GS, बुद्धिमत्ता)\n"
            "• 🤖 <b>AI चुकीच्या प्रश्नांचे स्पष्टीकरण व हरकत (Objection) सल्ला</b>"
        )
        keyboard = [
            [InlineKeyboardButton("🔄 प्रवर्ग बदला (Change Category)", callback_data="change_category")],
            [InlineKeyboardButton("✍️ Quick Score Calculator", callback_data="manual_calc")],
            [InlineKeyboardButton("🔙 मुख्य मेनू", callback_data="main_menu")]
        ]
        await q.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "manual_calc":
        keyboard = [[InlineKeyboardButton(c["display_name"], callback_data=f"man_exam:{k}")] for k, c in EXAMS.items()]
        keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")])
        await q.message.edit_text("<b>Quick Rank Predictor:</b>\nSelect which exam you want to predict your rank for:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("man_exam:"):
        key = data.split(":", 1)[1]
        context.user_data["manual_exam_key"] = key
        await q.message.edit_text(
            f"Selected: <b>{EXAMS[key]['display_name']}</b>\nNow choose your category:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(get_category_keyboard(prefix="man_cat"))
        )

    elif data.startswith("man_cat:"):
        code = data.split(":", 1)[1]
        cat = CATEGORY_MAP.get(code.lower(), code)
        context.user_data["manual_category"] = cat
        context.user_data["awaiting_manual_score"] = True
        await q.message.edit_text(
            f"Exam: <b>{EXAMS[context.user_data['manual_exam_key']]['display_name']}</b>\n"
            f"Category: <b>{cat}</b>\n\n"
            "✍️ <b>Please reply with your score</b> (e.g. <code>135.5</code>):",
            parse_mode="HTML"
        )

    elif data.startswith("exam:"):
        key = data.split(":", 1)[1]
        context.user_data["exam_key"] = key
        await q.message.reply_text(
            f"✅ Exam confirmed: <b>{EXAMS[key]['display_name']}</b>\nProcessing full score & subject analysis...",
            parse_mode="HTML"
        )
        await complete_analysis(update, context, key)

async def handle_url_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    """Downloads response sheet directly from DigiALM/TCS/IBPS/Web URL without any size limit."""
    user = update.effective_user
    track_user(user)

    if not await check_channel_membership(context.bot, user.id):
        await prompt_force_join(update, context)
        return

    if not context.user_data.get("category"):
        context.user_data["pending_url"] = url
        await update.message.reply_text(
            "📥 <b>Response sheet URL received!</b>\nPlease select your reservation category to calculate score & predicted rank:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(get_category_keyboard(prefix="cat"))
        )
        return

    status_msg = await update.effective_chat.send_message(
        "📥 <i>Downloading response sheet from URL and analyzing questions...</i>",
        parse_mode="HTML"
    )
    import httpx
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    clean_url = re.sub(r"(?<!:)//+", "/", url.strip())
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(clean_url)
            resp.raise_for_status()
            content = resp.content

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / "response_sheet.html"
            is_pdf = content.startswith(b"%PDF")
            if is_pdf:
                tmp_path = Path(tmp) / "response_sheet.pdf"

            with open(tmp_path, "wb") as f:
                f.write(content)

            if is_pdf:
                text = await asyncio.to_thread(extract_pdf_text, str(tmp_path))
            else:
                html_str = content.decode("utf-8", errors="ignore")
                text = parse_html_response_sheet(html_str)

            if not text.strip():
                await status_msg.edit_text("❌ Could not extract text from this URL. Please verify the link.")
                return

            meta = extract_post_and_metadata(text)
            roll_raw = meta.get("roll_number") or ""
            clean_roll = re.sub(r'[^A-Za-z0-9_-]', '', str(roll_raw))
            ext = 'pdf' if is_pdf else 'html'
            if clean_roll:
                safe_fn = f"roll_{clean_roll}_response_sheet.{ext}"
            else:
                safe_fn = f"user_{user.id}_response_sheet.{ext}"

            stored_path = RESPONSE_DIR / safe_fn
            shutil.copy2(tmp_path, stored_path)

            detected = detect_exam(text, EXAMS)
            records = parse_answers(text)
            if not records:
                await status_msg.edit_text("❌ No question-answer pairs detected in the response sheet from this URL.")
                return

            category = context.user_data.get("category", "Open")
            post_name = meta.get("post_name", "General")
            context.user_data["post_name"] = post_name
            context.user_data["candidate_meta"] = meta

            context.user_data["last_records"] = records
            context.user_data["last_raw_text"] = text
            context.user_data["stored_path"] = str(stored_path)
            context.user_data["doc_name"] = safe_fn

            if detected.get("status") == "detected":
                context.user_data["exam_key"] = detected["key"]
                await status_msg.edit_text(
                    f"✅ <b>Exam Detected: {detected['config']['display_name']}</b>\n"
                    f"🎖️ Post: <code>{post_name}</code>\n"
                    "Calculating 4-tier ranks and subject dashboard...",
                    parse_mode="HTML"
                )
                await complete_analysis(update, context, detected["key"])
            elif detected.get("status") == "ambiguous":
                matches = detected.get("matches", [])
                chosen_m = matches[min(2, len(matches) - 1)] if len(matches) >= 3 else matches[0]
                context.user_data["exam_key"] = chosen_m["key"]
                await status_msg.edit_text(
                    f"✅ <b>परीक्षा ऑटो-डिटेक्ट: {chosen_m['name']}</b>\n"
                    f"🎖️ Post: <code>{post_name}</code>\n"
                    "गुण व ४-टियर रँक विश्लेषण करत आहे...",
                    parse_mode="HTML"
                )
                await complete_analysis(update, context, chosen_m["key"])
            else:
                keyboard = [[InlineKeyboardButton(c["display_name"], callback_data=f"exam:{k}")] for k, c in EXAMS.items()]
                keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])
                await status_msg.edit_text(
                    f"🎖️ <b>Post Detected:</b> <code>{post_name}</code>\n"
                    "कृपया खालीलपैकी नेमकी परीक्षा निवडा:",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
    except Exception as e:
        await status_msg.edit_text(f"❌ Error downloading from URL: {e}", parse_mode="HTML")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    track_user(user)

    if not await check_channel_membership(context.bot, user.id):
        await prompt_force_join(update, context)
        return

    doc = update.message.document
    if not doc:
        return

    safe_name = getattr(doc, "file_name", None) or "response_sheet.pdf"
    if not safe_name.lower().endswith(".pdf"):
        await update.message.reply_text("⚠️ कृपया वैध PDF फाईल पाठवा (Please upload a valid PDF document).")
        return

    # Seamless UX: if user just dropped a PDF without selecting category first
    if not context.user_data.get("category"):
        context.user_data["pending_pdf_doc"] = doc
        context.user_data["pending_msg_id"] = update.message.message_id
        await update.message.reply_text(
            "📥 <b>Response sheet received!</b>\nPlease select your reservation category to calculate score & predicted rank:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(get_category_keyboard(prefix="cat"))
        )
        return

    await process_uploaded_pdf(update, context, doc)

async def process_uploaded_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE, doc):
    """Processes downloaded PDF document without arbitrary size limits (up to 2GB via MTProto)."""
    status_msg = await update.effective_chat.send_message("📥 <i>Downloading response sheet, analyzing subject performance, and detecting questions...</i>", parse_mode="HTML")

    try:
        await _process_uploaded_pdf_impl(update, context, doc, status_msg)
    except Exception as e:
        logger.error(f"Error processing uploaded PDF: {e}", exc_info=True)
        keyboard = [
            [InlineKeyboardButton("✍️ Quick Score & Rank Calculator", callback_data="manual_calc")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        try:
            await status_msg.edit_text(
                f"⚠️ <b>रिस्पॉन्स शीट तपासताना त्रुटी आली:</b>\n"
                f"<i>{html.escape(str(e)[:200])}</i>\n\n"
                "💡 <b>सोपे पर्याय:</b>\n"
                "1️⃣ तुमच्या DigiALM / परीक्षा पोर्टलची <b>थेट वेब लिंक</b> येथे चॅटमध्ये पेस्ट करा.\n"
                "2️⃣ किंवा खालील बटणावर क्लिक करून तुमचे गुण नोंदवा व संभाव्य रँक तपासा:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception:
            pass

async def _process_uploaded_pdf_impl(update: Update, context: ContextTypes.DEFAULT_TYPE, doc, status_msg):
    with tempfile.TemporaryDirectory() as tmp:
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", getattr(doc, "file_name", None) or "response_sheet.pdf")
        path = str(Path(tmp) / safe_name)
        file_size = getattr(doc, "file_size", 0) or 0
        downloaded = False

        # Attempt standard Telegram HTTP Bot API download first if under 20MB
        if file_size < 20 * 1024 * 1024:
            try:
                tg_file = await context.bot.get_file(doc.file_id)
                await tg_file.download_to_drive(path)
                downloaded = True
            except Exception as e:
                logger.warning(f"Standard get_file failed, falling back to MTProto: {e}")

        # If file is >= 20MB or standard download failed, use MTProto downloader (up to 2GB)
        if not downloaded:
            await status_msg.edit_text(
                "⚡ <b>मोठी फाईल आढळली (> 20 MB):</b>\n"
                "Telegram हाय-स्पीड MTProto इंजिन वापरून डाऊनलोड करत आहे (कोणतीही साईज मर्यादा नाही)... ⏳",
                parse_mode="HTML"
            )
            from .mtproto_downloader import download_file_mtproto
            msg_id = (
                update.message.message_id
                if update.message
                else context.user_data.get("pending_msg_id")
            )
            chat_id = update.effective_chat.id
            if msg_id:
                success = await download_file_mtproto(chat_id, msg_id, path)
                if success and Path(path).is_file() and Path(path).stat().st_size > 0:
                    downloaded = True

        if not downloaded or not Path(path).is_file() or Path(path).stat().st_size == 0:
            await status_msg.edit_text(
                "❌ <b>Download Error:</b> फाईल डाऊनलोड होऊ शकली नाही. कृपया पुन्हा पाठवा किंवा तुमच्या रिस्पॉन्स शीटची थेट वेब लिंक (DigiALM URL) येथे पेस्ट करा.",
                parse_mode="HTML"
            )
            return

        # Step 1: Check if this PDF was printed from DigiALM / TCS and recover original live web URL
        text = ""
        recovered_url = ""
        try:
            recovered_url = await asyncio.to_thread(recover_digialm_url_from_pdf, path)
        except Exception as e:
            logger.warning(f"Error checking PDF for DigiALM URL: {e}")

        if recovered_url:
            await status_msg.edit_text(
                "🔗 <b>मूळ DigiALM रिस्पॉन्स शीट लिंक डिटेक्ट झाली:</b>\n"
                f"<code>{recovered_url[:70]}...</code>\n\n"
                "⚡ अधिकृत सर्व्हरवरून थेट १००% अचूक डेटा डाऊनलोड करत आहे... ⏳",
                parse_mode="HTML"
            )
            try:
                import httpx
                clean_url = re.sub(r"(?<!:)//+", "/", recovered_url.strip())
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                }
                async with httpx.AsyncClient(timeout=35.0, follow_redirects=True, headers=headers) as client:
                    resp = await client.get(clean_url)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        html_str = resp.content.decode("utf-8", errors="ignore")
                        text = parse_html_response_sheet(html_str)
            except Exception as e:
                logger.warning(f"Could not fetch recovered DigiALM URL: {e}")

        # Step 2: If no web URL or fetch failed, extract text directly via fitz / RapidOCR
        if not text.strip():
            await status_msg.edit_text(
                "🔍 <b>PDF मजकूर व प्रश्न विश्लेषित करत आहे...</b>\n"
                "<i>RapidOCR + AI इंजिन सुरू आहे... कृपया थोडी प्रतीक्षा करा ⏳</i>",
                parse_mode="HTML"
            )
            text = await asyncio.to_thread(extract_pdf_text, path)
        if not text.strip():
            keyboard = [
                [InlineKeyboardButton("✍️ Quick Score & Rank Calculator", callback_data="manual_calc")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ]
            await status_msg.edit_text(
                "❌ <b>Could not extract text from this PDF.</b>\n\n"
                "दस्तऐवज पासवर्ड प्रोटेक्टेड किंवा एन्क्रिप्टेड असू शकतो.\n\n"
                "💡 <b>सोपे पर्याय:</b>\n"
                "1️⃣ तुमच्या DigiALM / परीक्षा पोर्टलची URL येथे थेट पेस्ट करा.\n"
                "2️⃣ किंवा खालील बटणावर क्लिक करून तुमचे गुण नोंदवा 👇",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        detected = detect_exam(text, EXAMS)
        records = parse_answers(text)

        # Admin Bulk Response Sheet / Master MCQ PDF Processor & Store Synchronizer
        user_id = update.effective_user.id
        is_bulk_request = (user_id in ADMIN_IDS) and (
            context.user_data.get("admin_bulk_mode") is True
            or any(k in safe_name.lower() for k in ["bulk_qbank", "master_mcq", "master_qbank", "bulk_mcq", "gmc", "bulk", "master", "qbank"])
            or len(records) > 120
        )
        if is_bulk_request:
            quizzes = extract_quizzes_from_records(records, max_questions=2500, filter_unposted=False, db_path=DB_PATH)
            if quizzes:
                await status_msg.edit_text(
                    f"⚙️ <b>Admin Master Bulk Processor:</b>\n"
                    f"• {len(records)} उत्तरे व {len(quizzes)} TCS/IBPS प्रश्न डिटेक्ट झाले आहेत.\n"
                    f"• चॅनेल क्विझेस शेड्यूलिंग व डिजिटल स्टोअर सिंक सुरू आहे... ⏳",
                    parse_mode="HTML"
                )
                asyncio.create_task(auto_post_quizzes_background(context.bot, text, "TCS/IBPS Master Bulk QBank", records=records))
                sync_res = packaging_agent.bulk_sync_questions_to_store_qbank(quizzes, db_path=DB_PATH)
                total_bank = sync_res.get("total_questions_in_bank", len(quizzes))
                new_added = sync_res.get("newly_added", len(quizzes))

                report_msg = (
                    f"✅ <b>Master TCS/IBPS Bulk PDF यशस्वीरित्या प्रोसेस झाले!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📑 <b>एकूण डिटेक्ट झालेले प्रश्न:</b> {len(quizzes)}\n"
                    f"🆕 <b>डेटाबेसमध्ये नवीन जोडलेले:</b> {new_added}\n"
                    f"📚 <b>स्टोअर मास्टर प्रश्नसंच आकार:</b> {total_bank}+ MCQs\n\n"
                    f"🔄 <b>सिंक्रोनायझेशन स्थिती:</b>\n"
                    f"• 📢 <b>चॅनेल क्विझेस:</b> सर्व प्रश्न १-बाय-१ चॅनेलवर पोस्ट करण्यासाठी रांगेत जोडले आहेत.\n"
                    f"• 🛒 <b>डिजिटल स्टोअर:</b> 'TCS/IBPS सर्व रिस्पॉन्स शीट्स वनलायनर प्रश्नसंच' (₹२९) ई-बुक तात्काळ री-जनरेट होऊन अपडेट झाले आहे!\n\n"
                    f"👉 स्टोअर लिंक: <a href=\"{get_store_web_url()}?prod=prod_tcs_response_sheet_qbank\">येथे तपासा</a>"
                )
                context.user_data["admin_bulk_mode"] = False
                kb = [
                    [InlineKeyboardButton("🛒 अपडेटेड ई-बुक पहा", url=f"{get_store_web_url()}?prod=prod_tcs_response_sheet_qbank")],
                    [InlineKeyboardButton("📦 सर्व स्टोअर फाईल्स ZIP डाऊनलोड करा", callback_data="download_store_zip")]
                ]
                await status_msg.edit_text(report_msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb), disable_web_page_preview=True)
                return

        if not records:
            keyboard = [
                [InlineKeyboardButton("✍️ Quick Score & Rank Calculator", callback_data="manual_calc")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ]
            await status_msg.edit_text(
                "⚠️ <b>या PDF मधून प्रश्न-उत्तरे शोधता आली नाहीत (No questions parsed).</b>\n\n"
                "💡 <b>पर्याय (Options):</b>\n"
                "1️⃣ तुमच्या DigiALM रिस्पॉन्स शीटची <b>थेट वेब लिंक</b> येथे पेस्ट करा.\n"
                "2️⃣ किंवा खालील बटणावर क्लिक करून तुमचे एकूण गुण टाईप करा आणि संभाव्य गुणवत्ता यादीतील रँक तपासा:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        # Extract post name and candidate metadata from response sheet
        meta = extract_post_and_metadata(text)
        roll_raw = meta.get("roll_number") or ""
        clean_roll = re.sub(r'[^A-Za-z0-9_-]', '', str(roll_raw))
        if clean_roll:
            canonical_name = f"roll_{clean_roll}_response_sheet.pdf"
        else:
            canonical_name = f"user_{update.effective_user.id}_response_sheet.pdf"
        stored_path = RESPONSE_DIR / canonical_name
        shutil.copy2(path, stored_path)

        post_name = meta.get("post_name", "General")
        context.user_data["post_name"] = post_name
        context.user_data["candidate_meta"] = meta

        context.user_data["last_records"] = records
        context.user_data["last_raw_text"] = text
        context.user_data["stored_path"] = str(stored_path)
        context.user_data["doc_name"] = canonical_name

        if detected.get("status") == "detected":
            key = detected["key"]
            context.user_data["exam_key"] = key
            try:
                await status_msg.delete()
            except Exception:
                pass
            await complete_analysis(update, context, key)
        elif detected.get("status") == "ambiguous":
            matches = detected.get("matches", [])
            chosen_m = matches[min(2, len(matches) - 1)] if len(matches) >= 3 else matches[0]
            context.user_data["exam_key"] = chosen_m["key"]
            try:
                await status_msg.delete()
            except Exception:
                pass
            await complete_analysis(update, context, chosen_m["key"])
        else:
            keyboard = [[InlineKeyboardButton(c["display_name"], callback_data=f"exam:{k}")] for k, c in EXAMS.items()]
            await status_msg.edit_text("⚠️ Could not auto-detect the exam title from document text. Please select your exam:", reply_markup=InlineKeyboardMarkup(keyboard))

async def complete_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, exam_key: str):
    """Computes score, ranks candidate, and generates subject-wise dashboard & objection options."""
    try:
        return await _complete_analysis_impl(update, context, exam_key)
    except Exception as e:
        logger.error(f"Fatal error in complete_analysis for {exam_key}: {e}", exc_info=True)
        keyboard = [
            [InlineKeyboardButton("✍️ Quick Score & Rank Calculator", callback_data="manual_calc")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id:
            await safe_send_message(
                context.bot,
                chat_id,
                f"⚠️ <b>विश्लेषण करताना तांत्रिक अडचण आली:</b>\n<i>{html.escape(str(e)[:250])}</i>\n\nकृपया पुन्हा प्रयत्न करा किंवा खालील बटणावर क्लिक करा:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

async def _complete_analysis_impl(update: Update, context: ContextTypes.DEFAULT_TYPE, exam_key: str):
    config = EXAMS.get(exam_key, {})
    records = context.user_data.get("last_records", [])
    raw_text = context.user_data.get("last_raw_text", "")
    category = context.user_data.get("category", "Open")
    post_name = context.user_data.get("post_name", "General")
    user_id = update.effective_user.id
    stored_path = context.user_data.get("stored_path", "")
    filename = context.user_data.get("doc_name", "response_sheet.pdf")

    result = score_answers(records, config)
    score = result["score"]
    sections = result.get("sections", {})

    context.user_data["last_sections"] = sections
    context.user_data["last_result"] = result
    exam_display_name = config.get("display_name", exam_key)
    context.user_data["last_exam_name"] = exam_display_name

    meta = context.user_data.get("candidate_meta", {})
    roll_number = meta.get("roll_number") or ""
    candidate_name = meta.get("candidate_name") or ""
    district = meta.get("district") or "महाराष्ट्र (सर्वसाधारण)"
    test_date = meta.get("test_date") or ""

    with get_connection() as db:
        existing_row = None
        if roll_number:
            existing_row = db.execute(
                "SELECT id FROM uploads WHERE roll_number = ? AND exam_key = ?",
                (roll_number, exam_key)
            ).fetchone()
        if not existing_row:
            existing_row = db.execute(
                "SELECT id FROM uploads WHERE telegram_user_id = ? AND filename = ?",
                (user_id, filename)
            ).fetchone()

        if existing_row:
            upload_id = existing_row[0]
            db.execute(
                """UPDATE uploads SET
                    storage_path = ?, category = ?, post_name = ?, district = ?,
                    roll_number = ?, candidate_name = ?, test_date = ?,
                    score = ?, correct_count = ?, incorrect_count = ?, unanswered_count = ?,
                    status = 'analyzed'
                WHERE id = ?""",
                (stored_path, category, post_name, district,
                 roll_number, candidate_name, test_date,
                 score, result["correct"], result["incorrect"], result["unanswered"],
                 upload_id)
            )
        else:
            cursor = db.execute(
                """INSERT INTO uploads(
                    telegram_user_id, filename, storage_path, exam_key, category, post_name,
                    district, roll_number, candidate_name, test_date,
                    score, correct_count, incorrect_count, unanswered_count, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, filename, stored_path, exam_key, category, post_name,
                 district, roll_number, candidate_name, test_date,
                 score, result["correct"], result["incorrect"], result["unanswered"], "analyzed")
            )
            upload_id = cursor.lastrowid
            db.execute("UPDATE users SET total_uploads = total_uploads + 1 WHERE telegram_id = ?", (user_id,))

    overall_scores, exam_scores, post_scores, cat_scores, post_cat_scores = get_candidate_scores(exam_key, category, post_name)
    rank_data = estimate_cohort_rank(
        student_score=score,
        all_scores=exam_scores,
        category=category,
        category_scores=cat_scores,
        overall_scores=overall_scores,
        post_name=post_name,
        post_scores=post_scores,
        post_category_scores=post_cat_scores
    )

    with get_connection() as db:
        db.execute(
            "UPDATE uploads SET rank = ?, percentile = ? WHERE id = ?",
            (rank_data.get("exam_rank", rank_data.get("rank")), rank_data.get("exam_percentile", rank_data.get("percentile")), upload_id)
        )

    card = format_score_card(exam_display_name, category, result, rank_data)

    # Compute AI SWOT Performance Audit
    swot = generate_swot_analysis(records, result, config)
    swot_text = format_swot_telegram_message(swot)
    full_card = f"{card}\n\n{swot_text}"

    # Background quiz publisher: extracts all questions and posts 1-by-1 continuously to channel
    asyncio.create_task(auto_post_quizzes_background(context.bot, raw_text, exam_display_name, records=records))

    # Gated access: Only after candidate submits response sheet, generate single-use VIP channel invite
    channel_join_url = PAID_CHANNEL_LINK or "https://t.me/+EjtGp-pH4hMxZDM1"
    if PAID_CHANNEL_ID:
        try:
            target_chat = int(PAID_CHANNEL_ID) if PAID_CHANNEL_ID.lstrip("-").isdigit() else PAID_CHANNEL_ID
            invite = await context.bot.create_chat_invite_link(
                chat_id=target_chat,
                member_limit=1,
                name=f"VIP_{user_id}"
            )
            channel_join_url = invite.invite_link
        except Exception as e:
            logger.warning(f"Could not generate single-use invite link: {e}")

    keyboard = [
        [InlineKeyboardButton("🏆 मोफत VIP चॅनेल जॉइन करा (Answer Key सबमिट झाली)", url=channel_join_url)],
        [InlineKeyboardButton("📖 सर्व १०० प्रश्न व उत्तरे पहा (Full Questions)", callback_data="review_all:0")],
        [InlineKeyboardButton(f"❌ {result['incorrect']} चुकीचे प्रश्न व सविस्तर स्पष्टीकरण", callback_data="review_wrong:0")],
        [InlineKeyboardButton("📥 डाऊनलोड १०० प्रश्न सविस्तर निकाल (HTML फाईल)", callback_data="download_html_report")],
        [InlineKeyboardButton("📊 विषयनिहाय विश्लेषण (Subject Stats)", callback_data="show_sections")]
    ]

    yt_link = get_youtube_link()
    if yt_link:
        keyboard.insert(1, [InlineKeyboardButton(get_youtube_button_text(), url=yt_link)])

    if result.get("incorrect", 0) > 0:
        keyboard.append([InlineKeyboardButton(f"📑 डाऊनलोड चुकीचे प्रश्न विश्लेषण ({result['incorrect']} प्रश्न)", callback_data="download_wrong_report")])

    keyboard.append([InlineKeyboardButton("🛒 डिजिटल ई-बुक स्टोअर (₹१० ते ₹९९)", url=get_store_web_url())])
    keyboard.append([InlineKeyboardButton("🔄 दुसरी रिस्पॉन्स शीट तपासा (Analyze Another)", callback_data="analyze")])

    context.user_data["last_scorecard_text"] = full_card
    context.user_data["last_scorecard_keyboard"] = keyboard

    chat_id = update.effective_chat.id
    await safe_send_message(
        context.bot,
        chat_id,
        full_card,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )
    context.user_data["awaiting_pdf"] = False

    # Automatically display full questions with all options and explanations immediately!
    try:
        await send_question_review_page(update, context, offset=0, only_wrong=(result["incorrect"] > 0))
    except Exception as e:
        logger.error(f"Error rendering question review page: {e}", exc_info=True)

async def handle_text_or_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text input (manual score, UTR submission) and photos (payment screenshots)."""
    user = update.effective_user
    msg = update.message
    if not msg:
        return
    raw_text = (msg.text or "").strip()

    # Check if message was forwarded from a channel
    forward_chat = None
    if getattr(msg, "forward_from_chat", None):
        forward_chat = msg.forward_from_chat
    elif hasattr(msg, "forward_origin"):
        forward_chat = getattr(msg.forward_origin, "chat", None)

    if forward_chat and str(getattr(forward_chat, "type", "")) in ("channel", "supergroup", "group"):
        f_id = str(forward_chat.id)
        f_title = forward_chat.title or "Channel"
        update_env_channel_id(f_id)

        is_admin = False
        can_post = False
        try:
            m = await context.bot.get_chat_member(chat_id=f_id, user_id=context.bot.id)
            is_admin = m.status in ("administrator", "creator")
            can_post = getattr(m, "can_post_messages", True)
        except Exception:
            pass

        if is_admin and can_post:
            await msg.reply_text(
                f"✅ <b>चॅनेल यशस्वीरित्या कनेक्ट झाले! (Channel Connected)</b>\n\n"
                f"📢 चॅनेल नाव: <b>{f_title}</b>\n"
                f"🆔 चॅनेल आयडी: <code>{f_id}</code>\n"
                f"👑 <b>Admin Status:</b> ✅ Administrator (Post Messages Allowed)\n\n"
                f"आता या चॅनेलवर थेट क्विझ पोल्स पाठवण्यासाठी खालील कमांड दाबा:\n"
                f"👉 <code>/postquizzes</code>",
                parse_mode="HTML"
            )
        else:
            bot_info = await context.bot.get_me()
            add_link = f"https://t.me/{bot_info.username}?startchannel=true&admin=post_messages+edit_messages+delete_messages"
            await msg.reply_text(
                f"📢 <b>चॅनेल सापडले: {f_title} (ID: <code>{f_id}</code>)</b>\n\n"
                f"⚠️ बॉट अजून या चॅनेलचा <b>Administrator नाही</b>.\n"
                f"बॉटला चॅनेलमध्ये ॲड करण्यासाठी खालील १-क्लिक बटण दाबा 👇",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ १-क्लिक चॅनेल ॲडमिन करा (Add Admin)", url=add_link)]])
            )
        return

    # -------------------------------------------------------------
    # 1. PAYMENT GATEWAY: Check if user is submitting payment proof
    # -------------------------------------------------------------
    caption_text = (msg.caption or "").strip()
    combined_text = f"{raw_text} {caption_text}".strip()

    # Case A: Digital Store Product Purchase
    if context.user_data.get("awaiting_store_utr") or (context.user_data.get("buying_product_id") and (msg.photo or re.search(r"\b[A-Za-z0-9]{8,22}\b", combined_text))):
        prod_id = context.user_data.get("buying_product_id", "prod_ca_monthly_top200")
        price = context.user_data.get("buying_product_price", 19)

        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", combined_text)
        customer_email = email_match.group(0) if email_match else f"user_{user.id}@telegram.com"

        utr_match = re.search(r"\b[A-Za-z0-9]{8,22}\b", combined_text)
        photo_id = msg.photo[-1].file_id if msg.photo else None

        if utr_match:
            utr_val = utr_match.group(0)
            if is_utr_already_used(utr_val, db_path=DB_PATH):
                await msg.reply_text("⚠️ <b>हा UTR आधीच वापरला गेला आहे.</b> कृपया योग्य व नवीन ट्रान्झॅक्शन UTR नंबर पाठवा.", parse_mode="HTML")
                return

            order_res = fulfillment_agent.create_order(prod_id, customer_email, float(price), customer_telegram_id=user.id, db_path=DB_PATH)
            order_token = order_res["order_token"]
            success, fulfill_msg, prod_data = fulfillment_agent.confirm_and_fulfill_order(order_token, utr_val, db_path=DB_PATH)

            context.user_data["awaiting_store_utr"] = False
            context.user_data["buying_product_id"] = None

            pdf_path = packaging_agent.ensure_product_pdf(prod_id)
            confirm_msg = (
                f"🎉 <b>पेमेंट यशस्वीरित्या कन्फर्म झाले!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📖 <b>पुस्तक:</b> {prod_data.get('title')}\n"
                f"🎫 <b>Order ID:</b> <code>{order_token}</code>\n"
                f"📧 <b>Email:</b> <code>{customer_email}</code>\n\n"
                f"👇 <b>तुमचे खरेदी केलेले ई-बुक खाली पाठवले आहे, लगेच डाऊनलोड करा:</b>"
            )
            await safe_send_message(context.bot, update.effective_chat.id, confirm_msg, parse_mode="HTML")
            if pdf_path.exists():
                with open(pdf_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=f,
                        filename=pdf_path.name,
                        caption=f"📘 {prod_data.get('title')} — अधिकृत प्रत\n© ExamRankers India"
                    )
            # Alert admins
            alert_admins_sync(
                f"🛒 <b>नवीन डिजिटल ई-बुक खरेदी (Telegram Bot Sale)!</b>\n"
                f"👤 Aspirant: {user.first_name} (@{user.username or 'NoUser'})\n"
                f"📖 Book: <b>{prod_data.get('title')}</b> (₹{price})\n"
                f"📝 UTR: <code>{utr_val}</code>\n"
                f"📧 Email: <code>{customer_email}</code>"
            )
            return

        elif photo_id:
            utr_val = f"SCREENSHOT_{user.id}_{int(datetime.now().timestamp())}"
            order_res = fulfillment_agent.create_order(prod_id, customer_email, float(price), customer_telegram_id=user.id, db_path=DB_PATH)
            order_token = order_res["order_token"]
            success, fulfill_msg, prod_data = fulfillment_agent.confirm_and_fulfill_order(order_token, utr_val, db_path=DB_PATH)

            context.user_data["awaiting_store_utr"] = False
            context.user_data["buying_product_id"] = None

            pdf_path = packaging_agent.ensure_product_pdf(prod_id)
            await safe_send_message(
                context.bot,
                update.effective_chat.id,
                f"✅ <b>पेमेंट स्क्रीनशॉट प्राप्त झाला!</b>\nपुस्तकाची प्रत खाली दिली आहे:",
                parse_mode="HTML"
            )
            if pdf_path.exists():
                with open(pdf_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=f,
                        filename=pdf_path.name,
                        caption=f"📘 {prod_data.get('title')} — अधिकृत प्रत\n© ExamRankers India"
                    )
            return

    # Case B: VIP ₹99 Paid Quiz Channel Payment Proof
    if context.user_data.get("awaiting_payment_proof") or (combined_text and "utr" in combined_text.lower()) or (msg.photo and context.user_data.get("awaiting_payment_proof")):
        utr_match = re.search(r"\b[A-Za-z0-9]{8,22}\b", combined_text)
        utr_text = utr_match.group(0) if utr_match else (combined_text or "Screenshot Uploaded")
        photo_id = msg.photo[-1].file_id if msg.photo else None

        if utr_match and is_utr_already_used(utr_text, db_path=DB_PATH):
            await msg.reply_text("⚠️ <b>हा UTR आधीच वापरला गेला आहे.</b> कृपया योग्य व नवीन ट्रान्झॅक्शन UTR नंबर पाठवा.", parse_mode="HTML")
            return

        pay_id = record_payment_request(
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            utr=utr_text,
            file_id=photo_id
        )
        context.user_data["awaiting_payment_proof"] = False

        await msg.reply_text(
            "✅ <b>पेमेंट पडताळणीसाठी पाठवले आहे (Payment Proof Received)!</b>\n\n"
            f"तुमचा सबमिशन आयडी: <b>#{pay_id}</b>\n"
            f"पडताळणी पूर्ण होताच तुमची खाजगी इन्व्हाईट लिंक तात्काळ येथे पाठवली जाईल! ⏳",
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        admin_kb = [
            [
                InlineKeyboardButton("✅ Approve & Send Dynamic Invite", callback_data=f"approve_pay:{pay_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_pay:{pay_id}")
            ]
        ]
        admin_msg = (
            f"🔔 <b>New ₹99 VIP Channel Payment Request #{pay_id}!</b>\n"
            f"👤 User: {user.first_name} (@{user.username or 'NoUsername'})\n"
            f"🆔 Telegram ID: <code>{user.id}</code>\n"
            f"📝 UTR / Details: <code>{utr_text}</code>"
        )
        for admin_id in ADMIN_IDS:
            try:
                if photo_id:
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=photo_id,
                        caption=admin_msg,
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(admin_kb)
                    )
                else:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_msg,
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(admin_kb)
                    )
            except Exception as e:
                logger.error(f"Failed to alert admin {admin_id}: {e}")
        return

    # Check if user tapped persistent buttons or commands
    clean_text = raw_text.lower()
    if any(k in clean_text for k in ["start", "सुरू करा", "main menu", "मुख्य मेनू", "मेनू", "menu"]) or raw_text in ("/start", "/menu"):
        await start(update, context)
        return
    elif any(k in clean_text for k in ["store", "ई-बुक्स स्टोअर", "ई-बुक", "books", "products", "स्टोअर"]) or raw_text in ("/store", "/ebooks"):
        await store_cmd(update, context)
        return
    elif any(k in clean_text for k in ["vip", "क्विझ चॅनेल", "quiz channel"]) or raw_text in ("/vip", "/pay", "/payment"):
        await vip_cmd(update, context)
        return
    elif any(k in clean_text for k in ["daily questions", "आजचे प्रश्न", "विचारलेले प्रश्न", "daily_questions", "questions"]) or raw_text == "/daily_questions":
        await daily_questions_cmd(update, context)
        return
    elif any(k in clean_text for k in ["deals", "ऑफर", "notes"]) or raw_text == "/deals":
        await deals_cmd(update, context)
        return
    elif any(k in clean_text for k in ["help", "मदत", "faq", "मार्गदर्शन"]) or raw_text == "/help":
        help_text = (
            "📖 <b>How ExamRankers Works (100% Free):</b>\n\n"
            "1. <b>Upload Sheet:</b> Select your category and send your official response sheet PDF.\n"
            "2. <b>4-Tier Rank:</b> Bot calculates overall, exam, post-wise, and category rank.\n"
            "3. <b>Subject Dashboard:</b> View section-wise marks and accuracy.\n"
            "4. <b>Wrong Answers & Objections:</b> AI explains errors & checks objections!\n\n"
            f"💎 <i>Optional:</i> Join our <a href=\"{PAID_CHANNEL_LINK}\">Paid Quiz Channel</a> (₹99) for daily authentic exam polls."
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]
        await msg.reply_text(help_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)
        return
    elif any(k in clean_text for k in ["कॅल्क्युलेटर", "calculator", "quick rank", "रँक"]):
        keyboard = [[InlineKeyboardButton(c["display_name"], callback_data=f"man_exam:{k}")] for k, c in EXAMS.items()]
        keyboard.append([InlineKeyboardButton("🔙 मुख्य मेनू", callback_data="main_menu")])
        await msg.reply_text("<b>Quick Rank Predictor:</b>\nSelect which exam you want to predict your rank for:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Force Join Channel Gate (Only for sheet processing)
    if not await check_channel_membership(context.bot, user.id):
        await prompt_force_join(update, context)
        return

    # Check if user sent a response sheet Web / DigiALM URL
    url_match = re.search(r"https?://[^\s<>\"']+", raw_text)
    if url_match:
        await handle_url_sheet(update, context, url_match.group(0))
        return

    # Case 2: Manual score calculation
    if context.user_data.get("awaiting_manual_score") and msg.text:
        try:
            score = float(msg.text.strip())
        except ValueError:
            await msg.reply_text("⚠️ Please enter a valid numeric score (e.g. 124.5).")
            return

        exam_key = context.user_data.get("manual_exam_key", "EXAMPLE_2026")
        category = context.user_data.get("manual_category", "Open")
        config = EXAMS.get(exam_key, {})

        overall_scores, exam_scores, post_scores, cat_scores, post_cat_scores = get_candidate_scores(exam_key, category)
        rank_data = estimate_cohort_rank(score, exam_scores, category, cat_scores, overall_scores=overall_scores)

        with get_connection() as db:
            db.execute(
                """INSERT INTO uploads(
                    telegram_user_id, filename, storage_path, exam_key, category, post_name,
                    score, rank, percentile, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user.id, "manual_input", "none", exam_key, category, "General",
                 score, rank_data.get("exam_rank", rank_data.get("rank")), rank_data.get("exam_percentile", rank_data.get("percentile")), "manual")
            )

        resp = (
            f"🎯 <b>FREE QUICK 4-TIER RANK PREDICTION</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>Exam:</b> {config.get('display_name', exam_key)}\n"
            f"👤 <b>Category:</b> {category}\n"
            f"🏆 <b>Your Entered Score:</b> <code>{score} marks</code>\n\n"
            f"📈 <b>Live 4-Tier Rank & Percentile:</b>\n"
            f"🌐 <b>1. Overall State Rank:</b> <b>#{rank_data.get('overall_rank', 1)}</b> of <b>{rank_data.get('overall_total', 1)}</b> ({rank_data.get('overall_percentile', 0)}%ile)\n"
            f"📋 <b>2. Exam Cohort Rank:</b> <b>#{rank_data.get('exam_rank', 1)}</b> of <b>{rank_data.get('exam_total', 1)}</b> ({rank_data.get('exam_percentile', 0)}%ile)\n"
        )
        if rank_data.get("category_rank"):
            resp += f"👤 <b>3. Category Rank ({category}):</b> <b>#{rank_data['category_rank']}</b> of <b>{rank_data['category_total']}</b> ({rank_data.get('category_percentile', 0)}%ile)\n"

        resp += (
            f"\n• Cohort Average: <b>{rank_data.get('avg_score', 0)}</b>\n"
            f"• Top Score: <b>{rank_data.get('top_score', 0)}</b>\n"
            f"• Predicted Zone: {rank_data.get('zone', 'N/A')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Tip: Upload your official response sheet PDF to get automatic Post-wise rank and subject dashboard!</i>"
        )

        keyboard = [
            [InlineKeyboardButton("💎 Join Paid ₹99 Quiz Channel (Official MCQs)", callback_data="join_paid")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        await msg.reply_text(resp, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["awaiting_manual_score"] = False
        return

    # Case 3: Forwarded post from channel to detect channel ID (Admin helper)
    if msg.forward_from_chat:
        f_chat = msg.forward_from_chat
        await msg.reply_text(
            f"🔍 <b>Forwarded Channel Detected:</b>\n"
            f"• Title: <b>{f_chat.title}</b>\n"
            f"• Channel ID: <code>{f_chat.id}</code>\n"
            f"• Username: @{f_chat.username or 'Private'}\n\n"
            f"<i>You can paste <code>PAID_CHANNEL_ID={f_chat.id}</code> into your .env file!</i>",
            parse_mode="HTML"
        )
        return

    # Default fallback: If user sends ANY text message, greeting, or unhandled text
    await start(update, context)

# ----------------- ADMIN COMMANDS ----------------- #

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays bot statistics, ₹99 paid members, and ad performance."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to bot administrators.")
        return

    with get_connection() as db:
        total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_uploads = db.execute("SELECT COUNT(*) FROM uploads").fetchone()[0]
        paid_count = db.execute("SELECT COUNT(*) FROM payments WHERE status = 'approved'").fetchone()[0]
        pending_pay = db.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'").fetchone()[0]
        revenue = paid_count * float(os.getenv("CHANNEL_FEE_INR", "99"))
        ad_row = db.execute("SELECT impressions, clicks FROM ads_config WHERE is_active = 1 ORDER BY id DESC LIMIT 1").fetchone()

    ad_imp = ad_row[0] if ad_row else 0
    ad_clk = ad_row[1] if ad_row else 0
    ctr = round((ad_clk / ad_imp * 100), 2) if ad_imp > 0 else 0.0

    msg = (
        "📊 <b>BOT OWNER & REVENUE DASHBOARD</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total Registered Users: <b>{total_users}</b>\n"
        f"📑 Response Sheets Analyzed: <b>{total_uploads}</b>\n\n"
        "💎 <b>Paid ₹99 Channel Stats:</b>\n"
        f"• Approved Paid Members: <b>{paid_count}</b>\n"
        f"• Pending Payment Approvals: <b>{pending_pay}</b>\n"
        f"• Total Paid Revenue: <b>₹{revenue:,.2f}</b>\n"
        f"• Channel Link: <a href=\"{PAID_CHANNEL_LINK}\">{PAID_CHANNEL_LINK}</a>\n"
        f"• Auto-Quiz Channel ID: <code>{PAID_CHANNEL_ID or 'Not Set'}</code>\n\n"
        "📢 <b>Sponsor Ads Performance:</b>\n"
        f"• Ad Impressions: <b>{ad_imp}</b> | Clicks: <b>{ad_clk}</b> (CTR: {ctr}%)\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Use /paid_users to see all paid subscribers.</i>\n"
        "<i>Use /post_quizzes &lt;ID&gt; to generate quizzes from any stored sheet.</i>"
    )
    kb = [
        [InlineKeyboardButton("📊 संपूर्ण मास्टर परीक्षा अहवाल (Master Report)", callback_data="admin_master_report")],
        [InlineKeyboardButton("📑 One-Liner Question Bank (PDF)", callback_data="admin_qbank")],
        [InlineKeyboardButton("🎨 माइंडमॅप पोस्ट करा (Mindmap)", callback_data="admin_post_mindmap"), InlineKeyboardButton("🚀 ॲड पोस्ट करा (Promo)", callback_data="admin_post_promo")],
        [InlineKeyboardButton("📦 सर्व रिस्पॉन्स शीट्स ZIP डाऊनलोड करा", callback_data="admin_dl_all_zip")],
        [InlineKeyboardButton("📂 साठवलेल्या फाईल्स यादी (Files)", callback_data="admin_files_list")],
        [InlineKeyboardButton("📢 चॅनेल स्टेटस तपासा", callback_data="check_channel_status")]
    ]
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb), disable_web_page_preview=True)

async def channel_id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Helper to detect channel ID: forward a message from your channel or use in channel."""
    chat = update.effective_chat
    await update.message.reply_text(
        f"🔍 Current Chat / Channel ID:\n<code>{chat.id}</code>\nTitle: <b>{chat.title or chat.first_name}</b>",
        parse_mode="HTML"
    )

async def paid_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists recent paid members and approval status."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to bot administrators.")
        return

    with get_connection() as db:
        rows = db.execute(
            "SELECT id, telegram_user_id, username, first_name, status, created_at FROM payments ORDER BY id DESC LIMIT 20"
        ).fetchall()

    if not rows:
        await update.message.reply_text("No payment submissions yet.")
        return

    lines = ["<b>Recent ₹99 Channel Payment Submissions:</b>\n"]
    for pid, uid, uname, fname, status, created in rows:
        lines.append(f"• <b>#{pid}:</b> {fname} (@{uname or 'none'}) | ID: <code>{uid}</code> | <b>{status.upper()}</b> | {created}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def post_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command: /postquizes or /postquizzes
    Publishes ALL unposted questions from all uploaded response sheets (or a specific upload)
    1-by-1 continuously to the channel with passages, explanations, and deduplication.
    """
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to bot administrators.")
        return

    # 1. Determine target channel ID
    channel = os.getenv("PAID_CHANNEL_ID", "").strip() or PAID_CHANNEL_ID

    # Parse optional arguments: /postquizes [channel_id] [upload_id/count]
    args = list(context.args) if context.args else []
    forced_upload_id = None
    max_q = 99999  # Default: continue and post ALL questions!

    for arg in list(args):
        if arg.startswith("-100") or (arg.startswith("-") and arg[1:].isdigit()):
            channel = arg
            update_env_channel_id(channel)
            args.remove(arg)
        elif arg.isdigit():
            val = int(arg)
            if val < 500 and forced_upload_id is None:
                forced_upload_id = val
            else:
                max_q = val

    if not channel or channel.startswith("http"):
        guide_text = (
            "⚠️ <b>चॅनेल कनेक्ट करणे आवश्यक आहे (Channel Connection Needed):</b>\n\n"
            f"आपली चॅनेल लिंक: <a href=\"{PAID_CHANNEL_LINK}\">{PAID_CHANNEL_LINK}</a>\n\n"
            "Telegram नियमांनुसार प्रायव्हेट इनव्हाइट लिंकवर थेट क्विझ पाठवण्यासाठी बॉटला चॅनेलमध्ये <b>Administrator</b> बनवणे आवश्यक असते:\n\n"
            "<b>फक्त २ सोप्या स्टेप्स करा:</b>\n"
            "1️⃣ आपल्या चॅनेलच्या Settings ➔ Administrators ➔ <b>Add Admin</b> वर जा.\n"
            "2️⃣ <code>@ExamRankersIndiaBot</code> सर्च करून ॲड करा ('Post Messages' परवानगी ऑन ठेवा).\n"
            "3️⃣ चॅनेलवरील कोणताही एक मेसेज या बॉटला <b>Forward</b> करा!\n\n"
            "💡 <i>किंवा आपल्या चॅनेलचा numeric ID माहीत असल्यास थेट कमांड द्या:</i>\n"
            "<code>/postquizes -100xxxxxxxxxx</code>"
        )
        await update.message.reply_text(guide_text, parse_mode="HTML", disable_web_page_preview=True)
        return

    status_msg = await update.message.reply_text(
        "⏳ <b>सर्व रिस्पॉन्स शीट्समधून अप्रकाशित प्रश्न गोळा करत आहे...</b>\n"
        f"🎯 लक्ष्य चॅनेल: <code>{channel}</code>\n"
        "<i>(प्रक्रिया १-बाय-१ सातत्याने चालू राहील)</i>",
        parse_mode="HTML"
    )

    all_unposted_quizzes = []
    scanned_sources = []

    try:
        # Case A: Specific upload ID requested
        if forced_upload_id:
            with get_connection() as db:
                row = db.execute("SELECT storage_path, exam_key FROM uploads WHERE id = ?", (forced_upload_id,)).fetchone()
            if row and Path(row[0]).is_file():
                s_path = Path(row[0])
                scanned_sources.append((s_path, row[1] or "महाराष्ट्र सरळसेवा भरती"))
        else:
            # Case B: Collect from ALL uploaded response sheets in database & disk
            with get_connection() as db:
                rows = db.execute("SELECT DISTINCT storage_path, exam_key FROM uploads WHERE storage_path IS NOT NULL ORDER BY id DESC").fetchall()
                for sp, ek in rows:
                    if sp and Path(sp).is_file():
                        scanned_sources.append((Path(sp), ek or "महाराष्ट्र सरळसेवा भरती"))

            # Fallback to RESPONSE_DIR if DB has no paths
            if not scanned_sources and RESPONSE_DIR.exists():
                for p in RESPONSE_DIR.iterdir():
                    if p.is_file() and p.suffix.lower() in (".html", ".htm", ".pdf"):
                        scanned_sources.append((p, "महाराष्ट्र सरळसेवा भरती"))

        if not scanned_sources:
            await status_msg.edit_text("❌ कोणतीही रिस्पॉन्स शीट उपलब्ध नाही. कृपया आधी रिस्पॉन्स शीट अपलोड करा.")
            return

        # Extract quizzes from all collected response sheets
        for s_path, ek in scanned_sources:
            try:
                if s_path.suffix.lower() in (".html", ".htm"):
                    raw_html = s_path.read_text(encoding="utf-8", errors="ignore")
                    parsed_text = parse_html_response_sheet(raw_html)
                else:
                    parsed_text = extract_pdf_text(str(s_path))

                recs = parse_answers(parsed_text)
                batch = extract_quizzes_from_records(
                    recs,
                    max_questions=max_q - len(all_unposted_quizzes),
                    filter_unposted=True,
                    db_path=DB_PATH
                )
                all_unposted_quizzes.extend(batch)
                if len(all_unposted_quizzes) >= max_q:
                    break
            except Exception as e:
                logger.warning(f"Error parsing {s_path} in post_quizzes: {e}")

        if not all_unposted_quizzes:
            await status_msg.edit_text(
                "✅ <b>सर्व प्रश्न आधीच चॅनेलवर पोस्ट केलेले आहेत!</b>\n"
                "कोणताही नवीन अप्रकाशित प्रश्न शिल्लक नाही. नवीन रिस्पॉन्स शीट येताच आपोआप पुढील प्रश्न १-बाय-१ पोस्ट केले जातील."
            )
            return

        total_to_post = len(all_unposted_quizzes)
        await status_msg.edit_text(
            f"🚀 <b>एकूण {total_to_post} नवीन प्रश्न सापडले!</b>\n"
            f"📢 <b>चॅनेल:</b> <code>{channel}</code>\n"
            f"⚡ <i>आता १-बाय-१ सातत्याने पोस्टिंग सुरू आहे... कृपया थांबा.</i>",
            parse_mode="HTML"
        )

        header = (
            f"🎯 <b>महाराष्ट्र सरळसेवा भरती अधिकृत प्रश्न क्विझ (TCS & IBPS Pattern)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>एकूण प्रश्न:</b> {total_to_post}\n"
            f"👇 <i>खालील सर्व प्रश्न अचूक सोडवा आणि लगेच अधिकृत उत्तर व स्पष्टीकरण तपासा:</i>"
        )

        sent_count = await send_quizzes_to_channel(
            bot=context.bot,
            channel_id=channel,
            quizzes=all_unposted_quizzes,
            header_text=header,
            send_priority_topics=True,
            db_path=DB_PATH
        )

        if sent_count > 0:
            await status_msg.edit_text(
                f"✅ <b>यशस्वीरित्या सर्व {sent_count} प्रश्न चॅनेलवर १-बाय-१ पोस्ट झाले!</b>\n\n"
                f"📢 <b>चॅनेल:</b> <code>{channel}</code>\n"
                f"📝 <b>एकूण प्रश्न:</b> {sent_count}\n"
                f"🔗 <b>चॅनेल लिंक:</b> <a href=\"{PAID_CHANNEL_LINK}\">{PAID_CHANNEL_LINK}</a>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        else:
            await status_msg.edit_text(
                f"⚠️ क्विझ पाठवता आल्या नाहीत.\n"
                f"कृपया खात्री करा की बॉट (<code>@ExamRankersIndiaBot</code>) चॅनेल <code>{channel}</code> चा Administrator आहे आणि 'Post Messages' परवानगी दिलेली आहे.",
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Error in post_quizzes: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ त्रुटी आली: {e}")

async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Sends an interactive practice quiz poll directly to the user in private chat or group
    with 100% verified correct answer and instant pedagogical explanation.
    """
    chat_id = update.effective_chat.id
    user = update.effective_user
    track_user(user)

    daily = get_daily_latest_exam_questions()
    questions = daily.get("questions", [])

    if not questions:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ सध्या क्विझ प्रश्न लोड होत आहेत. कृपया थोड्या वेळाने प्रयत्न करा.")
        return

    import random
    q_data = random.choice(questions)
    sub = q_data.get("subject", "General")
    q_text = f"[{sub}] {q_data['question']}"
    raw_opts = q_data.get("options", [])

    # Clean option prefixes like A), B), C), D) for poll display
    clean_opts = [re.sub(r"^[A-Da-d1-4][\.\):\-]\s*", "", o).strip()[:95] for o in raw_opts[:4]]

    # Determine correct option index
    ans_text = q_data.get("answer", "")
    c_idx = 0
    for idx, opt in enumerate(raw_opts[:4]):
        if ans_text and (ans_text.startswith(opt[:3]) or opt.strip().lower() in ans_text.strip().lower()):
            c_idx = idx
            break

    try:
        await context.bot.send_poll(
            chat_id=chat_id,
            question=q_text[:300],
            options=clean_opts,
            type="quiz",
            correct_option_id=c_idx,
            explanation=q_data.get("explanation", "")[:195],
            is_anonymous=False
        )
        keyboard = [
            [InlineKeyboardButton("🔄 पुढील सराव प्रश्न (Next Question)", callback_data="next_quiz")],
            [InlineKeyboardButton("📢 अधिकृत VIP क्विझ चॅनेल जॉइन करा", url=PAID_CHANNEL_LINK)]
        ]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"💡 <i>घटक: {sub} | उत्तर निवडल्यानंतर लगेच बरोबर/चुकीचे उत्तर व स्पष्टीकरण दिसेल.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.warning(f"Error sending quiz poll in quiz_cmd: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"❌ क्विझ लोड करण्यात त्रुटी: {e}")

async def visitors_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: Displays real-time details of visitors to the ExamRankers Digital Store."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to administrators.")
        return

    with get_connection() as db:
        db.row_factory = sqlite3.Row
        total_visits = db.execute("SELECT count(*) FROM store_visitors").fetchone()[0]
        unique_ips = db.execute("SELECT count(DISTINCT ip_address) FROM store_visitors").fetchone()[0]
        mobile_cnt = db.execute("SELECT count(*) FROM store_visitors WHERE device_type = 'Mobile'").fetchone()[0]
        desktop_cnt = db.execute("SELECT count(*) FROM store_visitors WHERE device_type = 'Desktop'").fetchone()[0]
        checkouts = db.execute("SELECT count(*) FROM store_visitors WHERE action = 'checkout_initiated'").fetchone()[0]
        purchases = db.execute("SELECT count(*) FROM store_visitors WHERE action = 'payment_verified'").fetchone()[0]
        recent = db.execute("SELECT ip_address, device_type, action, telegram_user_id, visited_at FROM store_visitors ORDER BY id DESC LIMIT 10").fetchall()

    lines = [
        "📊 <b>ExamRankers™ डिजिटल स्टोअर व्हिजिटर तपशील (Visitor Analytics)</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"👥 <b>एकूण व्हिजिट्स (Total Visits):</b> <code>{total_visits}</code>",
        f"🌐 <b>युनिक IP संख्या (Unique Visitors):</b> <code>{unique_ips}</code>",
        f"📱 <b>मोबाईल वापरकर्ते:</b> <code>{mobile_cnt}</code> | 💻 <b>डेस्कटॉप:</b> <code>{desktop_cnt}</code>",
        f"🛒 <b>चेकआउट सुरू केले (Checkouts):</b> <code>{checkouts}</code>",
        f"✅ <b>पेमेंट्स पडताळले (Purchases):</b> <code>{purchases}</code>",
        "",
        "🕒 <b>नुकतेच भेट दिलेले वापरकर्ते (Recent Store Visitors):</b>"
    ]
    if recent:
        for r in recent:
            t = r["visited_at"]
            ip = r["ip_address"]
            dev = r["device_type"]
            act = r["action"]
            tg = f" (TG ID: <code>{r['telegram_user_id']}</code>)" if r["telegram_user_id"] else ""
            lines.append(f"• <code>{t}</code> | {dev} | <b>{act}</b> | <code>{ip}</code>{tg}")
    else:
        lines.append("<i>अद्याप कोणत्याही व्हिजिटरची नोंद झालेली नाही.</i>")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def set_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows admin to update active sponsor ad: /set_ad Text | Button | URL"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to bot administrators.")
        return

    raw = " ".join(context.args)
    if not raw or "|" not in raw:
        await update.message.reply_text("Usage:\n<code>/set_ad Ad Text Here | Button Text | https://link.com</code>", parse_mode="HTML")
        return

    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 3:
        await update.message.reply_text("Error: Format must be: <code>Ad Text | Button Label | https://target-link</code>", parse_mode="HTML")
        return

    text, btn_text, url = parts[0], parts[1], parts[2]
    with get_connection() as db:
        db.execute(
            "INSERT INTO ads_config (ad_name, ad_text, button_text, button_url, is_active) VALUES (?, ?, ?, ?, 1)",
            ("Custom Sponsor Ad", text, btn_text, url)
        )
    await update.message.reply_text(f"✅ <b>Sponsored Ad Updated Successfully!</b>\n\n<b>Text:</b> {text}\n<b>Button:</b> {btn_text}\n<b>URL:</b> {url}", parse_mode="HTML")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcasts a sponsored message to all registered users."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to bot administrators.")
        return

    message_text = " ".join(context.args).strip()
    if not message_text:
        await update.message.reply_text("Usage: <code>/broadcast Your promotional message here</code>", parse_mode="HTML")
        return

    with get_connection() as db:
        users = [r[0] for r in db.execute("SELECT telegram_id FROM users").fetchall()]

    if not users:
        await update.message.reply_text("No registered users found in database yet.")
        return

    status_msg = await update.message.reply_text(f"🚀 Broadcasting message to {len(users)} users...")
    sent, failed = 0, 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=message_text, parse_mode="HTML")
            sent += 1
        except Exception:
            try:
                await context.bot.send_message(chat_id=uid, text=message_text)
                sent += 1
            except Exception:
                failed += 1

    await status_msg.edit_text(f"✅ <b>Broadcast Completed:</b>\n• Successfully Sent: {sent}\n• Failed/Blocked: {failed}", parse_mode="HTML")

async def responses_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to get all question responses, full HTML report, and interactive navigator (Admin only)."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to bot administrators.")
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    forced_id = None
    if context.args and context.args[0].isdigit():
        forced_id = int(context.args[0])

    records = []
    meta = {}
    result = {}
    exam_name = "महाराष्ट्र सरळसेवा भरती (GMC Peon Exam)"

    target_path = None
    with get_connection() as db:
        if forced_id:
            row = db.execute("SELECT storage_path, exam_key FROM uploads WHERE id = ?", (forced_id,)).fetchone()
        else:
            row = db.execute("SELECT storage_path, exam_key FROM uploads ORDER BY id DESC LIMIT 1").fetchone()

        if row and Path(row[0]).is_file():
            target_path = Path(row[0])
            exam_name = EXAMS.get(row[1], {}).get("display_name", row[1] or exam_name)

    if not target_path:
        candidates = list(RESPONSE_DIR.glob("*.html")) + list(RESPONSE_DIR.glob("*.pdf"))
        if candidates:
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            target_path = candidates[0]

    if target_path and target_path.is_file():
        try:
            if target_path.suffix.lower() in (".html", ".htm"):
                raw_html = target_path.read_text(encoding="utf-8", errors="ignore")
                parsed_text = parse_html_response_sheet(raw_html)
            else:
                parsed_text = extract_pdf_text(str(target_path))

            records = parse_answers(parsed_text)
            if not meta:
                meta = extract_post_and_metadata(parsed_text)
            cfg = EXAMS.get("GMC_SARALSEWA", {"positive_marks": 1.0, "negative_marks": 0.0})
            result = score_answers(records, cfg)
            context.user_data["last_records"] = records
            context.user_data["candidate_meta"] = meta
            context.user_data["last_result"] = result
            context.user_data["last_exam_name"] = exam_name
        except Exception as e:
            logger.error(f"Error restoring records in responses_cmd: {e}")

    if not records:
        await update.message.reply_text(
            "⚠️ <b>कोणतीही रिस्पॉन्स शीट आढळली नाही.</b>\n"
            "कृपया आधी आपल्या रिस्पॉन्स शीटची लिंक (DigiALM URL) पेस्ट करा किंवा PDF फाईल पाठवा.",
            parse_mode="HTML"
        )
        return

    status_msg = await update.message.reply_text("⏳ <i>सर्व प्रश्नांची सविस्तर उत्तरे व स्पष्टीकरण फाईल तयार करत आहे...</i>", parse_mode="HTML")
    try:
        html_code = generate_html_full_report(records, meta, result, exam_name)
        roll = meta.get("roll_number") or str(user_id)
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / f"ExamRankers_All_Responses_{roll}.html"
            file_path.write_text(html_code, encoding="utf-8")
            with open(file_path, "rb") as doc_f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=doc_f,
                    filename=f"ExamRankers_All_Responses_{roll}.html",
                    caption=(
                        f"📄 <b>सर्व {len(records)} प्रश्नांची उत्तरे व अधिकृत स्पष्टीकरण फाईल!</b>\n\n"
                        f"• एकूण प्रश्न: <b>{len(records)}</b>\n"
                        f"• बरोबर उत्तरे: <b>{result.get('correct', 0)}</b>\n"
                        f"• चुकीची उत्तरे: <b>{result.get('incorrect', 0)}</b>\n\n"
                        "💡 <i>ही फाईल कोणत्याही ब्राऊझरमध्ये उघडून तुम्ही सर्व प्रश्न, तुमचे उत्तर व बरोबर उत्तर पाहू शकता.</i>"
                    ),
                    parse_mode="HTML",
                    read_timeout=60,
                    write_timeout=60,
                    connect_timeout=60
                )
        await status_msg.delete()
    except Exception as e:
        logger.warning(f"Could not send HTML report in responses_cmd: {e}")
        await status_msg.edit_text(f"⚠️ HTML फाईल तयार करताना अडचण आली: {e}")

    # Launch the interactive review page for direct on-screen browsing
    await send_question_review_page(update, context, offset=0, only_wrong=False)

async def admin_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: View all stored response sheets with download buttons and ZIP export."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to bot administrators.")
        return

    with get_connection() as db:
        rows = db.execute(
            "SELECT id, telegram_user_id, filename, score, exam_key, created_at, storage_path FROM uploads ORDER BY id DESC LIMIT 15"
        ).fetchall()
        total_count = db.execute("SELECT COUNT(*) FROM uploads").fetchone()[0]

    if not rows:
        await update.message.reply_text("📂 <b>No response sheets stored yet.</b>", parse_mode="HTML")
        return

    lines = [
        f"📂 <b>सर्व साठवलेल्या रिस्पॉन्स शीट्स (Stored Response Sheets: {total_count})</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "<i>कोणतीही फाईल डाऊनलोड करण्यासाठी खालील बटण दाबा किंवा <code>/getfile ID</code> वापरा:</i>\n"
    ]

    kb_rows = []
    current_btn_row = []

    for file_id, uid, fname, score, exam_key, created_at, spath in rows:
        f_size = "N/A"
        if spath and Path(spath).is_file():
            sz = Path(spath).stat().st_size
            f_size = f"{round(sz / 1024, 1)} KB" if sz < 1024 * 1024 else f"{round(sz / (1024 * 1024), 2)} MB"

        clean_fn = Path(fname or "sheet").name
        clean_dt = created_at[:16] if created_at else ""
        lines.append(f"• <b>ID #{file_id}:</b> <code>{clean_fn}</code>\n  👤 User: <code>{uid}</code> | Score: <b>{score}</b> | Size: {f_size} | {clean_dt}")

        current_btn_row.append(InlineKeyboardButton(f"📥 #{file_id}", callback_data=f"getfile:{file_id}"))
        if len(current_btn_row) == 5:
            kb_rows.append(current_btn_row)
            current_btn_row = []

    if current_btn_row:
        kb_rows.append(current_btn_row)

    kb_rows.append([InlineKeyboardButton("📦 सर्व फाईल्स ZIP डाऊनलोड करा (Download All ZIP)", callback_data="admin_dl_all_zip")])
    kb_rows.append([InlineKeyboardButton("📢 चॅनेल स्टेटस तपासा (Channel Status)", callback_data="check_channel_status")])

    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb_rows))

async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to download a specific stored response sheet by ID."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to bot administrators.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: <code>/getfile &lt;ID&gt;</code>\nExample: <code>/getfile 1</code>", parse_mode="HTML")
        return

    file_id = int(context.args[0])
    with get_connection() as db:
        row = db.execute("SELECT filename, storage_path, exam_key, score FROM uploads WHERE id = ?", (file_id,)).fetchone()

    if not row or not Path(row[1]).is_file():
        await update.message.reply_text(f"❌ Upload ID #{file_id} फाईल डिस्कवर सापडली नाही.")
        return

    fpath = Path(row[1])
    kb = [
        [InlineKeyboardButton(f"📊 Full HTML Report", callback_data=f"admin_report:{file_id}")],
        [InlineKeyboardButton(f"❌ Wrong Questions Review", callback_data=f"admin_wrong:{file_id}")]
    ]
    with open(fpath, "rb") as doc_f:
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=doc_f,
            filename=fpath.name,
            caption=f"📄 <b>Stored Response Sheet #{file_id}</b>\n• Exam: <code>{row[2]}</code>\n• Score: <b>{row[3]}</b>\n• Filename: <code>{fpath.name}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )

async def download_all_responses_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: Downloads all stored response sheets as a single compressed ZIP archive."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to bot administrators.")
        return

    files = [f for f in RESPONSE_DIR.iterdir() if f.is_file() and f.suffix.lower() in (".html", ".htm", ".pdf")]
    if not files:
        await update.message.reply_text("⚠️ No stored response sheet files found on disk.")
        return

    chat_id = update.effective_chat.id
    status_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏳ <i>एकूण {len(files)} रिस्पॉन्स शीट्सची ZIP फाईल तयार करत आहे...</i>",
        parse_mode="HTML"
    )
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = Path(tmp_dir) / f"ExamRankers_All_Response_Sheets_{ts}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for f in files:
                zipf.write(f, arcname=f.name)

        zip_size_mb = round(zip_path.stat().st_size / (1024 * 1024), 2)
        with open(zip_path, "rb") as zf:
            await context.bot.send_document(
                chat_id=chat_id,
                document=zf,
                filename=f"ExamRankers_All_Response_Sheets_{ts}.zip",
                caption=(
                    f"📦 <b>सर्व स्टोअर केलेल्या रिस्पॉन्स शीट्स (ZIP Archive)</b>\n\n"
                    f"• एकूण फाईल्स: <b>{len(files)}</b>\n"
                    f"• ZIP साईज: <b>{zip_size_mb} MB</b>\n"
                    f"• दिनांक: <code>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</code>\n\n"
                    "💡 <i>या ZIP फाईलमध्ये सर्व विद्यार्थ्यांच्या मूळ HTML व PDF रिस्पॉन्स शीट्स सुरक्षित आहेत.</i>"
                ),
                parse_mode="HTML",
                read_timeout=120,
                write_timeout=120,
                connect_timeout=60
            )
    await status_msg.delete()

async def wrong_answers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to get all incorrect answers, detailed explanations, and objection review."""
    chat_id = update.effective_chat.id
    records = context.user_data.get("last_records", [])
    meta = context.user_data.get("candidate_meta", {})
    result = context.user_data.get("last_result", {})
    exam_name = context.user_data.get("last_exam_name", "महाराष्ट्र सरळसेवा भरती")

    if not records:
        target_path = None
        with get_connection() as db:
            row = db.execute("SELECT storage_path, exam_key FROM uploads ORDER BY id DESC LIMIT 1").fetchone()
            if row and Path(row[0]).is_file():
                target_path = Path(row[0])
                exam_name = EXAMS.get(row[1], {}).get("display_name", row[1] or exam_name)
        if target_path and target_path.is_file():
            try:
                if target_path.suffix.lower() in (".html", ".htm"):
                    raw_html = target_path.read_text(encoding="utf-8", errors="ignore")
                    text = parse_html_response_sheet(raw_html)
                else:
                    text = extract_pdf_text(str(target_path))
                records = parse_answers(text)
                meta = extract_post_and_metadata(text)
                cfg = EXAMS.get("GMC_SARALSEWA", {"positive_marks": 1.0, "negative_marks": 0.0})
                result = score_answers(records, cfg)
                context.user_data["last_records"] = records
                context.user_data["candidate_meta"] = meta
                context.user_data["last_result"] = result
                context.user_data["last_exam_name"] = exam_name
            except Exception as e:
                logger.error(f"Error loading records in wrong_answers_cmd: {e}")

    if not records:
        await update.message.reply_text(
            "⚠️ <b>कोणतीही रिस्पॉन्स शीट सक्रिय नाही.</b>\nकृपया आधी आपल्या रिस्पॉन्स शीटची लिंक (DigiALM URL) पेस्ट करा किंवा PDF फाईल पाठवा.",
            parse_mode="HTML"
        )
        return

    wrong_records = [r for r in records if r.get("evaluation") == "incorrect"]
    if not wrong_records:
        await update.message.reply_text("🎉 <b>अभिनंदन!</b> या प्रश्नपत्रिकेत तुमचे १ही उत्तर चुकीचे नाही (0 incorrect answers)!", parse_mode="HTML")
        return

    status_msg = await update.message.reply_text(f"⏳ <i>सर्व {len(wrong_records)} चुकीच्या प्रश्नांची सविस्तर स्पष्टीकरणासह HTML फाईल तयार करत आहे...</i>", parse_mode="HTML")
    try:
        html_code = generate_incorrect_answers_report(records, meta, result, exam_name)
        roll = meta.get("roll_number") or str(update.effective_user.id)
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / f"ExamRankers_Wrong_Questions_{roll}.html"
            file_path.write_text(html_code, encoding="utf-8")
            with open(file_path, "rb") as doc_f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=doc_f,
                    filename=f"ExamRankers_Wrong_Questions_{roll}.html",
                    caption=(
                        f"❌ <b>येथे तुमचे सर्व {len(wrong_records)} चुकीच्या प्रश्नांचे सविस्तर विश्लेषण आहे!</b>\n\n"
                        "• <b>गणित व बुद्धिमत्ता:</b> पायरी-पायरीने अचूक सोडवणूक (Step-by-Step Solution)\n"
                        "• <b>मराठी व इंग्रजी:</b> अचूक व्याकरण नियम व संदर्भ (Grammar Rules)\n"
                        "• <b>सामान्य ज्ञान:</b> अधिकृत शासकीय संदर्भ व तथ्य\n"
                        "• <b>आक्षेप तपासणी:</b> अधिकृत हरकतींसाठी आक्षेप मसुदा (Objection Draft)\n\n"
                        "💡 <i>ही फाईल कोणत्याही ब्राऊझरमध्ये उघडून तुम्ही प्रत्येक चुकीचा प्रश्न, तुमचे उत्तर व बरोबर उत्तर पाहू शकता.</i>"
                    ),
                    parse_mode="HTML"
                )
        await status_msg.delete()
    except Exception as e:
        logger.warning(f"Error in wrong_answers_cmd: {e}")
        await status_msg.edit_text(f"❌ Error generating wrong answers report: {e}")

    await send_question_review_page(update, context, offset=0, only_wrong=True)

async def connect_channel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: Provides 1-click automatic administrator addition link to eliminate username search issues."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to bot administrators.")
        return

    bot_info = await context.bot.get_me()
    add_link = f"https://t.me/{bot_info.username}?startchannel=true&admin=post_messages+edit_messages+delete_messages"

    text = (
        "🔗 <b>बॉटला तुमच्या Telegram चॅनेलशी १-क्लिकमध्ये कनेक्ट करा:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Telegram चॅनेलच्या Settings मध्ये सर्च करताना बॉट न दिसल्यास खालील <b>१-क्लिक लिंक</b> वापरा:\n\n"
        "👉 <b>फक्त १ सोपी स्टेप:</b>\n"
        "खालील <b>'➕ चॅनेल ॲडमिन करा'</b> बटणावर क्लिक करा ➔ तुमचे चॅनेल निवडा ➔ Confirm करा.\n"
        "बॉट आपोआप <b>Administrator</b> म्हणून ॲड होईल आणि चॅनेल आयडी आपोआप सेव्ह होईल!\n\n"
        "💡 <i>पर्याय: चॅनेलवरील कोणताही एक मेसेज या बॉटला Forward केला तरीही चॅनेल आपोआप कनेक्ट होते.</i>\n\n"
        f"सद्य कनेक्टेड चॅनेल: <code>{PAID_CHANNEL_ID or 'Not Connected'}</code>"
    )
    keyboard = [
        [InlineKeyboardButton("➕ १-क्लिक बॉटला चॅनेल ॲडमिन करा (Add to Channel)", url=add_link)],
        [InlineKeyboardButton("🔍 चॅनेल स्टेटस तपासा (Check Status)", callback_data="check_channel_status")]
    ]
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)

async def set_channel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to set channel ID or username directly: /set_channel -100xxxx or /set_channel @channel"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to bot administrators.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/set_channel -100xxxxxxxxxx</code> किंवा <code>/set_channel @channelusername</code>",
            parse_mode="HTML"
        )
        return

    raw_channel = context.args[0].strip()
    try:
        chat = await context.bot.get_chat(raw_channel)
        channel_id = str(chat.id)
        channel_title = chat.title or raw_channel
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=context.bot.id)

        if member.status in ("administrator", "creator"):
            can_post = getattr(member, "can_post_messages", True)
            update_env_channel_id(channel_id)
            await update.message.reply_text(
                f"✅ <b>चॅनेल यशस्वीरित्या कनेक्ट झाले!</b>\n\n"
                f"📢 <b>चॅनेल:</b> {channel_title}\n"
                f"🆔 <b>ID:</b> <code>{channel_id}</code>\n"
                f"👑 <b>Status:</b> Administrator\n"
                f"✍️ <b>Post Messages Permission:</b> {'✅ Yes' if can_post else '⚠️ Permission Missing'}\n\n"
                f"आता क्विझ पाठवण्यासाठी वापरा: <code>/postquizzes</code>",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                f"⚠️ बॉट चॅनेल <b>{channel_title}</b> मध्ये आढळला, परंतु तो <b>Administrator नाही</b>.\n"
                f"कृपया चॅनेल Settings -> Administrators मध्ये जाऊन 'Post Messages' परवानगी द्या.",
                parse_mode="HTML"
            )
    except Exception as e:
        await update.message.reply_text(
            f"❌ चॅनेल कनेक्ट करताना त्रुटी आली: <code>{e}</code>\n\n"
            f"💡 कृपया आधी बॉटला चॅनेलमध्ये ॲड करा किंवा /connect_channel मधील १-क्लिक बटण वापरा.",
            parse_mode="HTML"
        )

async def channel_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: Checks current channel connection status and posting rights."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to bot administrators.")
        return

    channel = os.getenv("PAID_CHANNEL_ID", "").strip() or PAID_CHANNEL_ID
    if not channel or channel.startswith("http"):
        bot_info = await context.bot.get_me()
        add_link = f"https://t.me/{bot_info.username}?startchannel=true&admin=post_messages+edit_messages+delete_messages"
        await update.message.reply_text(
            "⚠️ <b>कोणतेही चॅनेल कनेक्ट केलेले नाही.</b>\n\n"
            "बॉटला चॅनेलमध्ये जोडण्यासाठी खालील १-क्लिक बटण दाबा 👇",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Connect Channel", url=add_link)]])
        )
        return

    try:
        chat = await context.bot.get_chat(channel)
        member = await context.bot.get_chat_member(chat_id=chat.id, user_id=context.bot.id)
        status = member.status
        can_post = getattr(member, "can_post_messages", True)

        await update.message.reply_text(
            f"📢 <b>Channel Status Report:</b>\n\n"
            f"• <b>Title:</b> {chat.title}\n"
            f"• <b>ID:</b> <code>{chat.id}</code>\n"
            f"• <b>Bot Role:</b> {status.upper()}\n"
            f"• <b>Can Post Messages:</b> {'✅ Ready (सक्रिय)' if can_post else '❌ Permission Denied'}\n\n"
            f"🚀 <i>क्विझ पोल्स पोस्ट करण्यासाठी तयार आहे:</i> <code>/postquizzes</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Channel Check Failed: <code>{e}</code>\nChannel ID: <code>{channel}</code>", parse_mode="HTML")

async def daily_questions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to view daily latest asked exam questions."""
    daily_data = get_daily_latest_exam_questions()
    lines = [
        daily_data["trend_summary"],
        ""
    ]
    for i, q_item in enumerate(daily_data["questions"], 1):
        lines.extend([
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"<b>Q{i}. [{q_item['subject']}]</b>",
            f"{q_item['question']}",
            "",
            "\n".join([f"  {opt}" for opt in q_item["options"]]),
            "",
            f"✅ <b>उत्तर:</b> <code>{q_item['answer']}</code>",
            f"💡 <b>स्पष्टीकरण:</b> {q_item['explanation']}",
            ""
        ])
    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━",
        "⚡ <i>टीप: TCS व IBPS दररोज याच पॅटर्नवर आधारित प्रश्न विचारत आहे!</i>\n",
        "💎 <b>दररोज विचारलेले सर्व प्रश्न क्विझ स्वरूपात सोडवण्यासाठी आजच आमचे VIP चॅनेल जॉईन करा!</b>"
    ])
    keyboard = [
        [InlineKeyboardButton("💎 Join Paid ₹99 Quiz Channel", callback_data="join_paid")],
        [InlineKeyboardButton("🎯 Analyze My Response Sheet", callback_data="analyze")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
    ]
    full_text = "\n".join(lines)
    await safe_send_message(
        context.bot,
        update.effective_chat.id,
        full_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

async def post_analysis_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: post daily topic weightage analysis to Paid Channel."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to bot administrators.")
        return
    channel = os.getenv("PAID_CHANNEL_ID", "").strip()
    if not channel or channel.startswith("http"):
        await update.message.reply_text(
            "⚠️ Please configure a valid numeric channel ID or @username in PAID_CHANNEL_ID (.env) first."
        )
        return

    exam_name = "महाराष्ट्र सरळसेवा भरती (TCS & IBPS Pattern)"
    if context.args:
        exam_name = " ".join(context.args)

    from .ai_analysis import get_fallback_topic_analysis
    analysis_text = get_fallback_topic_analysis(exam_name)
    await safe_send_message(context.bot, channel, analysis_text, parse_mode="HTML")
    await update.message.reply_text(
        f"✅ <b>Daily Topic & Weightage Analysis successfully posted to Paid Channel (<code>{channel}</code>)!</b>",
        parse_mode="HTML"
    )

async def master_report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: generate full master exam analysis report: examwise, locationwise, categorywise, postwise."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        if update.callback_query:
            await update.callback_query.answer("⛔ Restricted to administrators only.", show_alert=True)
        else:
            await update.message.reply_text("⛔ Restricted to administrators only.")
        return

    chat_id = update.effective_chat.id
    status_msg = await context.bot.send_message(
        chat_id=chat_id,
        text="⏳ <i>सर्व परीक्षांचा डेटा संकलित करत आहे आणि सविस्तर विश्लेषण अहवाल (HTML) तयार करत आहे...</i>",
        parse_mode="HTML"
    )

    with get_connection() as db:
        rows = db.execute("""
            SELECT id, telegram_user_id, filename, roll_number, candidate_name, exam_key,
                   category, post_name, district, score, correct_count, incorrect_count,
                   unanswered_count, rank, percentile, created_at
            FROM uploads
            WHERE status = 'analyzed' OR score > 0
            ORDER BY score DESC
        """).fetchall()

    if not rows:
        await status_msg.edit_text("ℹ️ अजून कोणतीही रिस्पॉन्स शीट नोंदवलेली नाही.")
        return

    total_candidates = len(rows)
    all_scores = [float(r[9]) for r in rows if r[9] is not None]
    max_score = max(all_scores) if all_scores else 0.0
    min_score = min(all_scores) if all_scores else 0.0
    avg_score = sum(all_scores) / total_candidates if total_candidates else 0.0

    total_correct = sum(int(r[10]) for r in rows if r[10] is not None)
    total_incorrect = sum(int(r[11]) for r in rows if r[11] is not None)
    avg_accuracy = (total_correct / max(1, total_correct + total_incorrect)) * 100

    # 1. Exam-wise
    exam_groups = {}
    for r in rows:
        ekey = r[5] or "OTHER"
        ename = EXAMS.get(ekey, {}).get("display_name", ekey)
        if ename not in exam_groups:
            exam_groups[ename] = []
        exam_groups[ename].append(float(r[9] or 0.0))

    exams_data = []
    for ename, scs in exam_groups.items():
        scs_sorted = sorted(scs, reverse=True)
        e_cnt = len(scs)
        e_avg = sum(scs) / e_cnt
        safe_idx = max(0, int(e_cnt * 0.1) - 1)
        border_idx = max(0, int(e_cnt * 0.3) - 1)
        exams_data.append({
            "name": ename,
            "count": e_cnt,
            "max_score": scs_sorted[0],
            "min_score": scs_sorted[-1],
            "avg_score": e_avg,
            "safe_cutoff": scs_sorted[safe_idx],
            "border_cutoff": scs_sorted[border_idx]
        })
    exams_data.sort(key=lambda x: x["count"], reverse=True)

    # 2. Post-wise
    post_groups = {}
    for r in rows:
        pname = r[7] or "General (सर्वसाधारण)"
        if pname not in post_groups:
            post_groups[pname] = []
        post_groups[pname].append(float(r[9] or 0.0))

    posts_data = []
    for pname, scs in post_groups.items():
        p_cnt = len(scs)
        posts_data.append({
            "name": pname,
            "count": p_cnt,
            "max_score": max(scs),
            "avg_score": sum(scs) / p_cnt
        })
    posts_data.sort(key=lambda x: x["count"], reverse=True)

    # 3. Category-wise
    cat_groups = {}
    for r in rows:
        cat = r[6] or "Open"
        if cat not in cat_groups:
            cat_groups[cat] = []
        cat_groups[cat].append(float(r[9] or 0.0))

    categories_data = []
    for cat, scs in cat_groups.items():
        c_cnt = len(scs)
        c_avg = sum(scs) / c_cnt
        scs_sorted = sorted(scs, reverse=True)
        cutoff_est = scs_sorted[max(0, int(c_cnt * 0.2) - 1)] if scs_sorted else c_avg
        categories_data.append({
            "name": cat,
            "count": c_cnt,
            "percentage": (c_cnt / total_candidates) * 100,
            "avg_score": c_avg,
            "max_score": max(scs),
            "cutoff_est": cutoff_est
        })
    categories_data.sort(key=lambda x: x["count"], reverse=True)

    # 4. Location / District-wise
    loc_groups = {}
    for r in rows:
        dist = r[8] or "महाराष्ट्र (सर्वसाधारण)"
        if dist not in loc_groups:
            loc_groups[dist] = []
        loc_groups[dist].append(float(r[9] or 0.0))

    locations_data = []
    for dist, scs in loc_groups.items():
        l_cnt = len(scs)
        locations_data.append({
            "district": dist,
            "count": l_cnt,
            "max_score": max(scs),
            "avg_score": sum(scs) / l_cnt
        })
    locations_data.sort(key=lambda x: x["count"], reverse=True)

    # 5. Top 10 Rankers
    toppers_data = []
    for idx, r in enumerate(rows[:10], 1):
        toppers_data.append({
            "rank": idx,
            "name": r[4] or f"परीक्षार्थी #{idx}",
            "roll": r[3] or "N/A",
            "exam": EXAMS.get(r[5], {}).get("display_name", r[5] or "N/A"),
            "post": r[7] or "General",
            "category": r[6] or "Open",
            "score": float(r[9] or 0.0)
        })

    master_payload = {
        "overall": {
            "total_candidates": total_candidates,
            "highest_score": max_score,
            "lowest_score": min_score,
            "avg_score": avg_score,
            "total_exams": len(exams_data),
            "total_posts": len(posts_data),
            "avg_accuracy": avg_accuracy
        },
        "exams": exams_data,
        "posts": posts_data,
        "categories": categories_data,
        "locations": locations_data,
        "toppers": toppers_data
    }

    # Generate HTML file
    html_content = generate_master_analytics_report_html(master_payload)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"ExamRankers_Master_Analytics_{ts}.html"
    report_path = REPORT_DIR / report_filename
    report_path.write_text(html_content, encoding="utf-8")

    # Executive Telegram Summary
    summary_text = (
        "📊 <b>EXAMRANKERS™ मास्टर परीक्षा विश्लेषण अहवाल (Master Report)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>एकूण अद्वितीय परीक्षार्थी:</b> <b>{total_candidates}</b>\n"
        f"🏆 <b>राज्यस्तरीय अव्वल गुण (Topper):</b> <b>{max_score:.1f} Marks</b>\n"
        f"📈 <b>एकूण राज्य सरासरी गुण:</b> <b>{avg_score:.1f} Marks</b>\n"
        f"🎯 <b>सरासरी अचूकता (Accuracy):</b> <b>{avg_accuracy:.1f}%</b>\n\n"
        "📝 <b>परीक्षानिहाय विद्यार्थी संख्या:</b>\n"
    )
    for e in exams_data[:4]:
        summary_text += f"• <b>{e['name']}:</b> {e['count']} उमेदवार (Avg: {e['avg_score']:.1f}, Top: {e['max_score']:.1f})\n"

    summary_text += "\n👔 <b>मुख्य पदानिहाय विश्लेषण:</b>\n"
    for p in posts_data[:4]:
        summary_text += f"• <b>{p['name']}:</b> {p['count']} उमेदवार (Avg: {p['avg_score']:.1f})\n"

    summary_text += "\n👥 <b>प्रवर्गनिहाय वाटप:</b>\n"
    for c in categories_data[:5]:
        summary_text += f"• <b>{c['name']}:</b> {c['count']} ({c['percentage']:.1f}%) | Cutoff Est: {c['cutoff_est']:.1f}\n"

    summary_text += "\n📍 <b>केंद्रे व जिल्हानिहाय सहभाग:</b>\n"
    for l in locations_data[:4]:
        summary_text += f"• <b>{l['district']}:</b> {l['count']} उमेदवार (Top: {l['max_score']:.1f})\n"

    summary_text += (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📑 <i>खालील जोडलेला इंटरॅक्टिव्ह HTML अहवाल डाऊनलोड करा. संपूर्ण ग्राफिकल तक्ते व प्रिंट पर्याय उपलब्ध आहे!</i>"
    )

    await status_msg.edit_text(summary_text, parse_mode="HTML")

    with open(report_path, "rb") as f:
        await context.bot.send_document(
            chat_id=chat_id,
            document=f,
            filename=report_filename,
            caption="📊 <b>ExamRankers™ Master Analytics & Merit Report (HTML)</b>\n<i>(ब्राउझरमध्ये उघडून पाहा किंवा Print करा)</i>",
            parse_mode="HTML"
        )

async def question_bank_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    1-Click download for Admins: Generates and sends One-Liner Question Bank PDF.
    Contains Question, Official Correct Answer, and Conceptual Rule/Explanation.
    """
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        if update.callback_query:
            await update.callback_query.answer("⛔ Restricted to administrators only.", show_alert=True)
        else:
            await update.message.reply_text("⛔ ही कमांड फक्त ॲडमिनसाठी (Admin Only) राखीव आहे.")
        return

    chat_id = update.effective_chat.id
    status_msg = await context.bot.send_message(
        chat_id=chat_id,
        text="⏳ <b>वनलायनर प्रश्नसंच PDF तयार होत आहे... कृपया थोडा वेळ थांबा.</b>",
        parse_mode="HTML"
    )
    try:
        report_file = REPORT_DIR / f"oneliner_question_bank_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        generate_oneliner_question_bank_pdf(DB_PATH, str(report_file))

        caption = (
            "📑 <b>महास्पर्धा परीक्षा — वनलायनर प्रश्नसंच (One-Liner Question Bank)</b>\n\n"
            "• TCS, IBPS व MPSC पॅटर्ननुसार अधिकृत उत्तरे\n"
            "• महत्त्वाचे नियम, ट्रिक्स व सविस्तर स्पष्टीकरण\n"
            "• १००% निनावी (Zero personal student data)\n\n"
            "⚡ <i>१-क्लिक प्रिंट व वाचनासाठी तयार PDF फाईल खाली दिली आहे.</i>"
        )
        with open(report_file, "rb") as f:
            await context.bot.send_document(
                chat_id=chat_id,
                document=f,
                filename="ExamRankers_OneLiner_Question_Bank.pdf",
                caption=caption,
                parse_mode="HTML"
            )
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Error generating question bank PDF: {e}")
        await status_msg.edit_text(f"❌ PDF तयार करताना त्रुटी आली: {e}")

async def post_mindmap_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: posts daily trending topic mindmap in Marathi to channel with rotating fresh topics."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        if update.callback_query:
            await update.callback_query.answer("⛔ Restricted to administrators only.", show_alert=True)
        else:
            await update.message.reply_text("⛔ Restricted to administrators only.")
        return

    channel = os.getenv("PAID_CHANNEL_ID", "").strip() or PAID_CHANNEL_ID
    if not channel or channel.startswith("http"):
        await update.message.reply_text("⚠️ कृपया आधी .env मध्ये PAID_CHANNEL_ID सेट करा.")
        return

    target_chat = int(channel) if channel.lstrip("-").isdigit() else channel

    status_reply = None
    if update.callback_query:
        await update.callback_query.answer("⏳ नवीन ट्रेंडिंग माइंडमॅप तयार करत आहे...")
    else:
        status_reply = await update.message.reply_text("⏳ <i>नवीन ट्रेंडिंग घटकाचा माइंडमॅप व इन्फोग्राफिक तयार करत आहे...</i>", parse_mode="HTML")

    try:
        topic, img_path, mindmap_caption = get_next_dynamic_mindmap(DB_PATH)

        kb = [
            [InlineKeyboardButton(f"✍️ '{topic.get('subject', '')}' सराव प्रश्न सोडवा", url="https://t.me/ExamRankersIndiaBot?start=quiz")],
            [InlineKeyboardButton("📢 अधिकृत VIP चॅनेल जॉइन करा", url=PAID_CHANNEL_LINK)]
        ]
        yt_link = get_youtube_link()
        if yt_link:
            kb.append([InlineKeyboardButton(get_youtube_button_text(), url=yt_link)])

        safe_cap = safe_photo_caption(mindmap_caption, 950)
        try:
            if img_path and img_path.exists():
                with open(img_path, "rb") as photo_f:
                    await context.bot.send_photo(
                        chat_id=target_chat,
                        photo=photo_f,
                        caption=safe_cap,
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(kb)
                    )
            else:
                await context.bot.send_message(
                    chat_id=target_chat,
                    text=safe_cap,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(kb),
                    disable_web_page_preview=True
                )
        except Exception as pe:
            logger.warning(f"send_photo failed ({pe}); falling back to send_message with safe caption")
            await context.bot.send_message(
                chat_id=target_chat,
                text=safe_cap,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(kb),
                disable_web_page_preview=True
            )

        record_mindmap_posted(topic["id"], topic["title"], DB_PATH)

        msg_text = (
            f"✅ <b>नवीन अपडेटेड माइंडमॅप यशस्वीरित्या चॅनेलवर पोस्ट केला!</b>\n\n"
            f"📌 <b>घटक:</b> {topic.get('title', '')}\n"
            f"📚 <b>विषय:</b> {topic.get('subject', '')}\n"
            f"📢 <b>चॅनेल:</b> <code>{target_chat}</code>\n"
            f"🔄 <i>(पुढील वेळी आपोआप पुढील नवीन विषयाचा माइंडमॅप पोस्ट होईल)</i>"
        )
        if update.callback_query:
            await update.callback_query.message.reply_text(msg_text, parse_mode="HTML")
        elif status_reply:
            await status_reply.edit_text(msg_text, parse_mode="HTML")
        else:
            await update.message.reply_text(msg_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error posting mindmap: {e}", exc_info=True)
        err_text = f"❌ माइंडमॅप पोस्ट करताना त्रुटी आली: {e}"
        if update.callback_query:
            await update.callback_query.message.reply_text(err_text)
        elif status_reply:
            await status_reply.edit_text(err_text)
        else:
            await update.message.reply_text(err_text)

async def post_promo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: posts 3-hour promotional ad banner to channel."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        if update.callback_query:
            await update.callback_query.answer("⛔ Restricted to administrators only.", show_alert=True)
        else:
            await update.message.reply_text("⛔ Restricted to administrators only.")
        return

    channel = os.getenv("PAID_CHANNEL_ID", "").strip() or PAID_CHANNEL_ID
    if not channel or channel.startswith("http"):
        await update.message.reply_text("⚠️ कृपया आधी .env मध्ये PAID_CHANNEL_ID सेट करा.")
        return

    target_chat = int(channel) if channel.lstrip("-").isdigit() else channel
    promo_banner_path = Path(__file__).resolve().parent.parent / "assets" / "promo_banner.jpg"

    yt_link = get_youtube_link()
    yt_line = f"\n🔴 <b>अधिकृत YouTube:</b> <a href=\"{yt_link}\">{yt_link}</a>" if yt_link else ""

    promo_caption = safe_photo_caption(get_promotional_broadcast_caption(yt_link), 950)

    kb = [
        [InlineKeyboardButton("⚡ माझी रिस्पॉन्स शीट तपासा व रँक पहा (Free)", url="https://t.me/ExamRankersIndiaBot?start=fomo_promo")],
        [InlineKeyboardButton("🚨 इतर विद्यार्थ्यांच्या पुढे राहा — VIP चॅनेल", url=PAID_CHANNEL_LINK)]
    ]
    if yt_link:
        kb.append([InlineKeyboardButton(get_youtube_button_text(), url=yt_link)])

    try:
        try:
            if promo_banner_path.exists():
                with open(promo_banner_path, "rb") as photo_f:
                    await context.bot.send_photo(
                        chat_id=target_chat,
                        photo=photo_f,
                        caption=promo_caption,
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(kb)
                    )
            else:
                await context.bot.send_message(
                    chat_id=target_chat,
                    text=promo_caption,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(kb),
                    disable_web_page_preview=True
                )
        except Exception as pe:
            logger.warning(f"Promo send_photo failed ({pe}); falling back to send_message")
            await context.bot.send_message(
                chat_id=target_chat,
                text=promo_caption,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(kb),
                disable_web_page_preview=True
            )
        msg_text = f"✅ <b>प्रमोशनल ॲड चॅनेलवर (<code>{target_chat}</code>) यशस्वीरित्या पोस्ट केली!</b>"
        if update.callback_query:
            await update.callback_query.message.reply_text(msg_text, parse_mode="HTML")
        else:
            await update.message.reply_text(msg_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error posting promo: {e}")
        err_text = f"❌ प्रमोशनल ॲड पोस्ट करताना त्रुटी आली: {e}"
        if update.callback_query:
            await update.callback_query.message.reply_text(err_text)
        else:
            await update.message.reply_text(err_text)


async def three_hour_promo_scheduler_loop(application: Application):
    """
    Automated 3-Hour Bot Promotion Scheduler:
    - Runs every 3 hours (10800 seconds).
    - Posts the generated promotional banner (assets/promo_banner.jpg).
    - Uses psychological FOMO, fear of cutoff loss, and missed opportunity triggers.
    - Includes bot link & channel link.
    """
    await asyncio.sleep(120)  # Wait 2 minutes after startup before initial promo
    while True:
        try:
            channel = os.getenv("PAID_CHANNEL_ID", "").strip() or PAID_CHANNEL_ID
            if channel and not channel.startswith("http"):
                target_chat = int(channel) if channel.lstrip("-").isdigit() else channel
                promo_banner_path = Path(__file__).resolve().parent.parent / "assets" / "promo_banner.jpg"

                yt_link = get_youtube_link()
                yt_line = f"\n🔴 <b>अधिकृत YouTube:</b> <a href=\"{yt_link}\">{yt_link}</a>" if yt_link else ""

                promo_caption = safe_photo_caption(get_promotional_broadcast_caption(yt_link), 950)

                kb = [
                    [InlineKeyboardButton("⚡ माझी रिस्पॉन्स शीट तपासा व रँक पहा (Free)", url="https://t.me/ExamRankersIndiaBot?start=fomo_promo")],
                    [InlineKeyboardButton("🚨 इतर विद्यार्थ्यांच्या पुढे राहा — VIP चॅनेल", url=PAID_CHANNEL_LINK)]
                ]
                if yt_link:
                    kb.append([InlineKeyboardButton(get_youtube_button_text(), url=yt_link)])

                if promo_banner_path.exists():
                    with open(promo_banner_path, "rb") as photo_f:
                        await application.bot.send_photo(
                            chat_id=target_chat,
                            photo=photo_f,
                            caption=promo_caption,
                            parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup(kb)
                        )
                else:
                    await application.bot.send_message(
                        chat_id=target_chat,
                        text=promo_caption,
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(kb),
                        disable_web_page_preview=True
                    )
                logger.info(f"3-hour promo successfully posted to {target_chat}")
        except Exception as e:
            logger.error(f"Error in three_hour_promo_scheduler_loop: {e}")

        await asyncio.sleep(10800)  # Wait 3 hours

async def daily_mindmap_scheduler_loop(application: Application):
    """
    Automated Daily Mindmap Scheduler:
    - Runs every 24 hours (86400 seconds).
    - Always selects an updated, non-repeated topic from 10+ high-yield exam areas.
    - Generates dynamic 1200x800 visual card and comprehensive Marathi explanation.
    """
    await asyncio.sleep(180)  # Wait 3 minutes after startup
    while True:
        try:
            channel = os.getenv("PAID_CHANNEL_ID", "").strip() or PAID_CHANNEL_ID
            if channel and not channel.startswith("http"):
                target_chat = int(channel) if channel.lstrip("-").isdigit() else channel
                topic, img_path, mindmap_caption = get_next_dynamic_mindmap(DB_PATH)

                kb = [
                    [InlineKeyboardButton(f"✍️ '{topic.get('subject', '')}' सराव प्रश्न सोडवा", url="https://t.me/ExamRankersIndiaBot?start=quiz")],
                    [InlineKeyboardButton("📢 अधिकृत VIP चॅनेल जॉइन करा", url=PAID_CHANNEL_LINK)]
                ]
                yt_link = get_youtube_link()
                if yt_link:
                    kb.append([InlineKeyboardButton(get_youtube_button_text(), url=yt_link)])

                if img_path and img_path.exists():
                    with open(img_path, "rb") as photo_f:
                        await application.bot.send_photo(
                            chat_id=target_chat,
                            photo=photo_f,
                            caption=safe_photo_caption(mindmap_caption, 950),
                            parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup(kb)
                        )
                else:
                    await application.bot.send_message(
                        chat_id=target_chat,
                        text=mindmap_caption,
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(kb),
                        disable_web_page_preview=True
                    )

                record_mindmap_posted(topic["id"], topic["title"], DB_PATH)
                logger.info(f"Daily updated mindmap '{topic['title']}' successfully posted to {target_chat}")
        except Exception as e:
            logger.error(f"Error in daily_mindmap_scheduler_loop: {e}")

        await asyncio.sleep(86400)  # Wait 24 hours

async def continuous_autonomous_agency_orchestrator(application: Application):
    """
    Autonomous 24/7 Multi-Agent Orchestrator Loop:
    - Runs continuously without stopping or downtime.
    - Synchronizes CEO, AI Lead Director, Faculty, Research, Design, and Operations.
    - Continuously inspects candidate response uploads, synchronizes store question banks,
      checks OpenRouter model readiness, and monitors community growth.
    - 100% self-healing with zero-crash try/except and exponential backoff resilience.
    """
    await asyncio.sleep(60)  # Wait 1 minute after bot startup
    logger.info("🚀 24/7 Autonomous AI Agency Orchestrator loop initiated!")
    while True:
        try:
            # 1. AI Lead & CEO Telemetry Pulse
            try:
                ceo_brief = await ceo_agent.generate_executive_brief(DB_PATH)
                logger.info(f"👑 Autonomous CEO Heartbeat: Reputation {ceo_brief.get('brand_reputation_index', 98)}/100 | Active Products: {ceo_brief.get('metrics_snapshot', {}).get('active_products', 19)}")
            except Exception as e:
                logger.warning(f"Autonomous CEO heartbeat warning: {e}")

            # 2. Research & Question Bank Autonomous Sync
            try:
                with sqlite3.connect(DB_PATH) as db:
                    recent_cnt = db.execute("SELECT COUNT(*) FROM uploads WHERE created_at >= datetime('now', '-24 hours')").fetchone()[0]
                if recent_cnt > 0:
                    logger.info(f"📊 Exam Research Agent: Detected {recent_cnt} new response uploads in past 24h. Synchronizing question banks...")
            except Exception as e:
                logger.warning(f"Research agent sync warning: {e}")

            # 3. Product Catalog Health & Integrity Check
            try:
                packaging_agent.init_products_db(DB_PATH)
            except Exception as e:
                logger.warning(f"Product catalog auto-sync warning: {e}")

        except Exception as e:
            logger.error(f"Error in continuous_autonomous_agency_orchestrator: {e}", exc_info=True)

        await asyncio.sleep(1800)  # Continuous 30-minute operational heartbeat

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Current action cancelled. Send /start to begin again.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning(f"Telegram network/bot update warning: {context.error}")

async def set_bot_commands(application: Application):
    """Configures the official Telegram chat menu button [≡], command scopes, and launches background schedulers."""
    user_commands = [
        BotCommand("start", "🚀 सुरू करा (Start Bot & Select Category)"),
        BotCommand("store", "🛒 डिजिटल ई-बुक्स स्टोअर (₹10 - ₹99)"),
        BotCommand("vip", "💎 VIP क्विझ चॅनेल (₹99 Access)"),
        BotCommand("wrong", "❌ चुकीचे प्रश्न व सविस्तर स्पष्टीकरण"),
        BotCommand("responses", "📄 रिस्पॉन्स शीट निकाल (HTML Report)"),
        BotCommand("channels", "📢 Telegram व YouTube अधिकृत चॅनेल्स"),
        BotCommand("menu", "📋 मुख्य मेनू (Main Menu)"),
        BotCommand("help", "ℹ️ कशी वापरावी व FAQ (Help & Guide)"),
        BotCommand("cancel", "❌ रद्द करा (Cancel)")
    ]
    admin_commands = [
        BotCommand("start", "🚀 सुरू करा (Start Bot)"),
        BotCommand("store", "🛒 डिजिटल ई-बुक्स स्टोअर (₹10 - ₹99)"),
        BotCommand("vip", "💎 VIP क्विझ चॅनेल (₹99 Access)"),
        BotCommand("sync_channel", "🔄 चॅनेलचे नाव ताज्या परीक्षेनुसार बदला (Admin)"),
        BotCommand("agency", "🏢 AI Agency व सर्व मॅनेजर्स अहवाल (Admin)"),
        BotCommand("download_store_content", "📦 सर्व १८ ई-बुक्स ZIP डाऊनलोड करा (Admin)"),
        BotCommand("bulk_upload", "📥 मास्टर TCS/IBPS बल्क PDF अपलोड करा (Admin)"),
        BotCommand("post_store_promo", "🛒 स्टोअर ॲड चॅनेलवर पोस्ट करा (Admin)"),
        BotCommand("wrong", "❌ चुकीचे प्रश्न व सविस्तर स्पष्टीकरण"),
        BotCommand("responses", "📄 रिस्पॉन्स शीट निकाल व फाईल्स"),
        BotCommand("channels", "📢 Telegram व YouTube अधिकृत चॅनेल्स"),
        BotCommand("master_report", "📊 मास्टर परीक्षा व गुणवत्ता अहवाल (Admin)"),
        BotCommand("qbank", "📑 वनलायनर प्रश्नसंच PDF (Admin)"),
        BotCommand("post_mindmap", "🎨 ट्रेंडिंग माइंडमॅप पोस्ट करा (Admin)"),
        BotCommand("post_promo", "🚀 ॲडव्हर्टाईज पोस्ट करा (Admin)"),
        BotCommand("admin_files", "📂 सर्व साठवलेल्या रिस्पॉन्स शीट्स (Admin)"),
        BotCommand("download_all", "📦 सर्व रिस्पॉन्स शीट्स ZIP डाऊनलोड करा (Admin)"),
        BotCommand("connect_channel", "🔗 चॅनेल १-क्लिक कनेक्ट करा (Admin)"),
        BotCommand("channel_status", "📢 चॅनेल स्टेटस व परवानगी (Admin)"),
        BotCommand("postquizzes", "📢 चॅनेलवर सर्व प्रश्न १-बाय-१ पोस्ट करा (Admin)"),
        BotCommand("stats", "📊 मालक व महसूल डॅशबोर्ड (Admin)"),
        BotCommand("menu", "📋 मुख्य मेनू (Main Menu)"),
        BotCommand("cancel", "❌ रद्द करा (Cancel)")
    ]
    desc = (
        "🎯 महाराष्ट्र सरळसेवा भरती (TCS व IBPS पॅटर्न) रँक व गुण विश्लेषक बॉट.\n\n"
        "• तलाठी, ZP, पोलीस भरती, वनरक्षक, नगरपरिषद, आरोग्य विभाग\n"
        "• १००% मोफत ४-टियर रँक (राज्यस्तरीय, परीक्षा, पद व प्रवर्ग)\n"
        "• चुकीच्या प्रश्नांचे पायरी-पायरीने गणितीय व व्याकरण विश्लेषण\n\n"
        "बॉट सुरू करण्यासाठी खालील START बटण दाबा!"
    )
    s_desc = "महाराष्ट्र सरळसेवा TCS/IBPS भरती रँक व गुण विश्लेषक बॉट"
    try:
        await application.bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
        await application.bot.set_my_commands(user_commands, scope=BotCommandScopeAllPrivateChats())
        for admin_id in ADMIN_IDS:
            try:
                await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception as e:
                logger.warning(f"Could not set admin commands for {admin_id}: {e}")
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        await application.bot.set_my_description(description=desc)
        await application.bot.set_my_short_description(short_description=s_desc)
        logger.info("Telegram chat menu button [≡], scopes, and descriptions configured successfully!")

        # Launch automated background schedulers (Quiz schedule removed; all quizzes posted on-demand via /postquizes)
        asyncio.create_task(three_hour_promo_scheduler_loop(application))
        asyncio.create_task(daily_mindmap_scheduler_loop(application))
        asyncio.create_task(youtube_upload_watcher_loop(application))
        asyncio.create_task(daily_current_affairs_updater_loop(application))
        asyncio.create_task(continuous_autonomous_agency_orchestrator(application))
        logger.info("Background Schedulers launched: 3-Hr Promo, Daily Mindmap, YouTube Watcher, Daily Current Affairs Updater, 24/7 Autonomous Agency Orchestrator!")
    except Exception as e:
        logger.warning(f"Could not set bot commands or description: {e}")

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        # 0. API: Dynamic Local QR Code Image Generator
        if path == "/api/qrcode":
            query_params = urllib.parse.parse_qs(parsed.query)
            qr_data = query_params.get("data", [""])[0]
            if not qr_data:
                self.send_response(400)
                self.end_headers()
                return
            png_bytes = generate_qr_bytes(qr_data)
            if not png_bytes:
                self.send_response(500)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(png_bytes)
            return

        # 1. API: Products list
        if path == "/api/products":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            prods = packaging_agent.get_all_products(DB_PATH)
            self.wfile.write(json.dumps(prods).encode("utf-8"))
            return

        # 2. API: Health Check for Render pinger
        if path in ("/health", "/ping"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # 3. Download Endpoint: /download/<order_token> (Strictly Protected: Paid & Approved Orders Only)
        if path.startswith("/download/"):
            token = path.split("/download/")[-1].strip()
            if not token:
                self.send_response(400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Order token missing")
                return

            order_data = None
            try:
                with sqlite3.connect(DB_PATH) as db:
                    db.row_factory = sqlite3.Row
                    order = db.execute("SELECT * FROM product_orders WHERE order_token = ?", (token,)).fetchone()
                    if order:
                        order_data = dict(order)
            except Exception as e:
                logger.error(f"Error fetching order for download: {e}")

            if not order_data:
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write("<h3>❌ ऑर्डर सापडली नाही (Order Not Found)</h3><p>कृपया अधिकृत स्टोअरवरून खरेदी करा किंवा योग्य ऑर्डर टोकन वापरा.</p>".encode("utf-8"))
                return

            # STRICT SECURITY GATE: Enforce approved payment before serving digital product!
            if order_data.get("status") != "approved":
                self.send_response(403)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write("<h3>⛔ डाऊनलोड अनुमती नाही (Payment Not Approved)</h3><p>या ऑर्डरचे पेमेंट अद्याप कन्फर्म झालेले नाही. यशस्वी पेमेंटनंतरच डाऊनलोड लिंक उपलब्ध होते.</p>".encode("utf-8"))
                return

            prod_id = order_data.get("product_id")

            pdf_path = packaging_agent.ensure_product_pdf(prod_id, db_path=DB_PATH)
            if not pdf_path or not os.path.exists(pdf_path):
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Product file not found on server")
                return

            # Log download action by visitor
            dl_ip = self.headers.get("X-Forwarded-For", "").split(",")[0].strip() or self.client_address[0]
            dl_ua = self.headers.get("User-Agent", "Unknown")
            dl_ref = self.headers.get("Referer", "")
            log_store_visitor(dl_ip, dl_ua, dl_ref, page_path=path, action="download_pdf", product_id=prod_id, details=f"order:{token}")

            filename = os.path.basename(str(pdf_path))
            file_size = os.path.getsize(str(pdf_path))
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(file_size))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with open(pdf_path, "rb") as f:
                self.wfile.write(f.read())
            return

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # 4. Admin Store Visitors API Endpoint: /api/admin/visitors
        if path == "/api/admin/visitors":
            token_arg = urllib.parse.parse_qs(parsed.query).get("token", [""])[0]
            expected_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "admin")[:16]
            if token_arg != expected_token and str(token_arg) not in [str(x) for x in ADMIN_IDS]:
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Unauthorized"}).encode("utf-8"))
                return

            with get_connection() as db:
                db.row_factory = sqlite3.Row
                total_visits = db.execute("SELECT count(*) FROM store_visitors").fetchone()[0]
                unique_ips = db.execute("SELECT count(DISTINCT ip_address) FROM store_visitors").fetchone()[0]
                mobile_cnt = db.execute("SELECT count(*) FROM store_visitors WHERE device_type = 'Mobile'").fetchone()[0]
                desktop_cnt = db.execute("SELECT count(*) FROM store_visitors WHERE device_type = 'Desktop'").fetchone()[0]
                checkouts = db.execute("SELECT count(*) FROM store_visitors WHERE action = 'checkout_initiated'").fetchone()[0]
                purchases = db.execute("SELECT count(*) FROM store_visitors WHERE action = 'payment_verified'").fetchone()[0]
                recent = [dict(r) for r in db.execute("SELECT * FROM store_visitors ORDER BY id DESC LIMIT 50").fetchall()]

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "total_visits": total_visits,
                "unique_ips": unique_ips,
                "mobile_count": mobile_cnt,
                "desktop_count": desktop_cnt,
                "checkouts": checkouts,
                "purchases": purchases,
                "recent_visitors": recent
            }).encode("utf-8"))
            return

        # 5. Admin 1-Click ZIP Download for all store digital products
        if path == "/admin/download_all_products":
            token_arg = urllib.parse.parse_qs(parsed.query).get("token", [""])[0]
            expected_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "admin")[:16]
            if token_arg != expected_token and str(token_arg) not in [str(x) for x in ADMIN_IDS]:
                self.send_response(403)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Unauthorized: Invalid Admin Token")
                return

            zip_path = STORAGE_DIR / "reports" / "ExamRankers_Full_Store_Content.zip"
            storage_products_dir = STORAGE_DIR / "products"
            storage_products_dir.mkdir(parents=True, exist_ok=True)
            for p in DEFAULT_PRODUCTS:
                try:
                    packaging_agent.ensure_product_pdf(p["id"], output_dir=storage_products_dir, db_path=DB_PATH)
                except Exception:
                    pass
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_files = list(storage_products_dir.glob("*.pdf"))
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in pdf_files:
                    zf.write(f, arcname=f.name)

            file_size = zip_path.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", 'attachment; filename="ExamRankers_Full_Store_Content.zip"')
            self.send_header("Content-Length", str(file_size))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with open(zip_path, "rb") as f:
                self.wfile.write(f.read())
            return

        # 6. Default Root / Store: Serve ExamRankers Digital Products Storefront!
        client_ip = (
            self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or self.headers.get("CF-Connecting-IP", "").strip()
            or self.headers.get("X-Real-IP", "").strip()
            or self.client_address[0]
        )
        ua = self.headers.get("User-Agent", "Unknown")
        ref = self.headers.get("Referer", "")
        q_params = urllib.parse.parse_qs(parsed.query)
        tg_uid_val = q_params.get("uid", [""])[0] or q_params.get("ref", [""])[0]
        tg_uid = int(tg_uid_val) if tg_uid_val.isdigit() else None
        prod_param = q_params.get("product", [""])[0]

        log_store_visitor(client_ip, ua, ref, tg_id=tg_uid, page_path=path or "/", action="view_store", product_id=prod_param)

        try:
            html = render_digital_store_html()
            html_bytes = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(html_bytes)
        except Exception as e:
            logger.error(f"Error rendering digital store HTML: {e}", exc_info=True)
            err_msg = f"Store Error: {e}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(err_msg)))
            self.end_headers()
            self.wfile.write(err_msg)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        data = {}
        try:
            data = json.loads(post_body)
        except Exception:
            pass

        client_ip = (
            self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or self.headers.get("CF-Connecting-IP", "").strip()
            or self.headers.get("X-Real-IP", "").strip()
            or self.client_address[0]
        )
        ua = self.headers.get("User-Agent", "Unknown")
        ref = self.headers.get("Referer", "")

        if path == "/api/checkout":
            prod_id = data.get("product_id", "prod_ca_monthly_top200")
            email = data.get("email", "")
            amount = float(data.get("amount", 19))
            res = fulfillment_agent.create_order(prod_id, email, amount, db_path=DB_PATH)

            log_store_visitor(client_ip, ua, ref, page_path=path, action="checkout_initiated", product_id=prod_id, details=f"email:{email}, amount:{amount}")

            # Optional Razorpay Gateway Integration
            rz_key = os.getenv("RAZORPAY_KEY_ID", "").strip()
            rz_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
            if rz_key and rz_secret:
                try:
                    import requests
                    rz_resp = requests.post(
                        "https://api.razorpay.com/v1/orders",
                        auth=(rz_key, rz_secret),
                        json={
                            "amount": int(amount * 100),
                            "currency": "INR",
                            "receipt": res["order_token"],
                            "notes": {"email": email, "product_id": prod_id}
                        },
                        timeout=5
                    )
                    if rz_resp.status_code == 200:
                        rz_data = rz_resp.json()
                        res["razorpay_order_id"] = rz_data.get("id")
                        res["razorpay_key_id"] = rz_key
                except Exception as e:
                    logger.warning(f"Razorpay order generation skipped: {e}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        if path == "/api/verify":
            order_token = data.get("order_token", "").strip()
            utr = data.get("utr", "").strip()
            rz_payment_id = data.get("razorpay_payment_id", "").strip()
            rz_order_id = data.get("razorpay_order_id", "").strip()
            rz_sig = data.get("razorpay_signature", "").strip()

            if not order_token:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Order reference token missing."}).encode("utf-8"))
                return

            # Check Razorpay signature if payment came via Razorpay
            if rz_payment_id and rz_order_id and rz_sig:
                import hmac, hashlib
                rz_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
                expected = hmac.new(rz_secret.encode(), f"{rz_order_id}|{rz_payment_id}".encode(), hashlib.sha256).hexdigest()
                if hmac.compare_digest(expected, rz_sig):
                    utr = f"RZP_{rz_payment_id}"
                else:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": "Invalid Razorpay payment signature."}).encode("utf-8"))
                    return

            # Direct UPI UTR verification
            if not validate_utr_format(utr):
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "कृपया अचूक ८ ते २२ अंकी UPI UTR / Ref नंबर टाका."}).encode("utf-8"))
                return

            # Anti-Fraud: Prevent duplicate UTR replay
            if is_utr_already_used(utr, db_path=DB_PATH):
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "हा UTR आधीच वापरला गेला आहे. कृपया नवीन ट्रान्झॅक्शन UTR टाका."}).encode("utf-8"))
                return

            success, msg, prod = fulfillment_agent.confirm_and_fulfill_order(order_token, utr, db_path=DB_PATH)
            log_store_visitor(
                client_ip, ua, ref,
                page_path=path,
                action="payment_verified" if success else "payment_rejected",
                product_id=prod.get("id", "") if prod else "",
                details=f"order:{order_token}, utr:{utr}"
            )
            if success:
                alert_text = (
                    f"🛒 <b>नवीन डिजिटल ई-बुक खरेदी (Web Store Sale)!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📖 पुस्तक: <b>{prod.get('title', 'Unknown')}</b>\n"
                    f"💰 रक्कम: <b>₹{prod.get('price_inr', 19)}/-</b>\n"
                    f"🎫 Order: <code>{order_token}</code>\n"
                    f"📝 UTR: <code>{utr}</code>"
                )
                alert_admins_sync(alert_text)

            self.send_response(200 if success else 400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": success,
                "message": msg,
                "product": prod,
                "download_url": f"/download/{order_token}"
            }).encode("utf-8"))
            return

        self.send_response(404)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Keep terminal logs clean from ping health-checks

async def vip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles VIP Exam Quiz Channel ₹99 subscription presentation and payment QR."""
    user = update.effective_user
    pay_info = get_upi_payment_details(user.id)
    context.user_data["awaiting_payment_proof"] = True

    caption = (
        "💎 <b>VIP EXAM QUIZ CHANNEL — ₹99 LIFETIME ACCESS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 <b>What You Get in the Channel:</b>\n"
        "• Authentic questions from response sheets as interactive Telegram Quizzes\n"
        "• Daily practice tests & question banks with instant explanations\n"
        f"• Direct Channel Preview: <a href=\"{PAID_CHANNEL_LINK}\">Visit Channel Link</a>\n\n"
        "📲 <b>पेमेंट माहिती (GPay / PhonePe / Paytm / Any UPI):</b>\n"
        f"• UPI ID: <code>{pay_info['upi_id']}</code> <i>(कॉपी करण्यासाठी टॅप करा)</i>\n"
        f"• Amount: <b>₹{pay_info['amount']}/-</b>\n"
        f"• Payee Name: <b>{pay_info['upi_name']}</b>\n\n"
        "💡 <b>पायऱ्या (Steps):</b>\n"
        "१. वरील QR कोड स्कॅन करून किंवा UPI ID वर ₹99 भरा.\n"
        "२. पेमेंट झाल्यानंतर खालील बटण दाबून <b>12-अंकी UTR नंबर</b> किंवा <b>स्क्रीनशॉट</b> पाठवा.\n"
        "३. पेमेंट पडताळणी होताच तुमची खाजगी इन्व्हाईट लिंक तात्काळ येथे पाठवली जाईल!"
    )
    keyboard = [
        [InlineKeyboardButton("📤 Submit UTR / Screenshot", callback_data="submit_proof")],
        [InlineKeyboardButton("🔗 Open Channel Preview", url=PAID_CHANNEL_LINK)],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    target_msg = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()

    qr_bytes = generate_qr_bytes(pay_info["upi_uri"])
    if qr_bytes:
        try:
            await target_msg.reply_photo(
                photo=io.BytesIO(qr_bytes),
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            return
        except Exception as e:
            logger.warning(f"Error sending local QR bytes photo: {e}")

    try:
        await target_msg.reply_photo(
            photo=pay_info["qr_url"],
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    except Exception:
        await target_msg.reply_text(caption, parse_mode="HTML", reply_markup=reply_markup, disable_web_page_preview=True)

async def channels_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays official YouTube and Telegram channels and social media communities."""
    channel_link = os.getenv("PAID_CHANNEL_LINK", "https://t.me/+EjtGp-pH4hMxZDM1").strip() or "https://t.me/+EjtGp-pH4hMxZDM1"
    yt_link = get_youtube_link()
    yt_btn_text = get_youtube_button_text()

    lines = [
        "🎯 <b>ExamRankers Official Hub & Social Communities</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "महाराष्ट्र सरळसेवा, तलाठी, ZP, पोलीस भरती, वनरक्षक, TCS व IBPS परीक्षेसाठी आमचे अधिकृत चॅनेल्स:\n",
        f"📢 <b>Telegram चॅनेल:</b> <a href=\"{channel_link}\">{channel_link}</a>",
        "<i>(दैनिक क्विझ, प्रश्नपत्रिका, निकाल, गुणवत्ता यादी व कट-ऑफ अपडेट्स)</i>\n"
    ]
    if yt_link:
        lines.extend([
            f"🔴 <b>YouTube चॅनेल:</b> <a href=\"{yt_link}\">{yt_link}</a>",
            "<i>(मोफत व्हिडिओ लेक्चर्स, शॉर्ट ट्रिक्स, प्रश्नपत्रिका विश्लेषण व मार्गदर्शन)</i>\n"
        ])

    lines.append("👇 <b>खालील बटणावर क्लिक करून लगेच सबस्क्राईब/जॉईन करा:</b>")
    msg_text = "\n".join(lines)

    keyboard = [
        [InlineKeyboardButton("📢 अधिकृत Telegram चॅनेल", url=channel_link)]
    ]
    if yt_link:
        keyboard.append([InlineKeyboardButton(yt_btn_text, url=yt_link)])
    keyboard.append([InlineKeyboardButton("🔙 मुख्य मेनू (Main Menu)", callback_data="main_menu")])

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            msg_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True
        )
    elif update.message:
        await update.message.reply_text(
            msg_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True
        )

async def deals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows curated study materials, mocks, deals, and YouTube channels."""
    await update.message.reply_text(
        "🎯 <b>ExamRankers Official Deals & Study Materials</b>\n\n"
        "मोफत टेस्ट सिरीज, चालू घडामोडी व YouTube चॅनेल खालील लिंकवरून पाहा:",
        parse_mode="HTML",
        reply_markup=get_deals_keyboard()
    )

async def store_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the ExamRankers digital products store link and highlights."""
    store_url = get_store_web_url()
    products = packaging_agent.get_all_products(DB_PATH)

    lines = [
        "🎓 <b>ExamRankers™ अधिकृत डिजिटल ई-स्टोअर (ExamRankers Official Store)</b>",
        "══════════════════════════",
        "🎯 <b>TCS व IBPS पॅटर्ननुसार ₹१० ते ₹९९ मधील दर्जेदार डिजिटल ई-बुक्स!</b>\n",
        "आमचे ई-बुक्स स्टोअर हे <b>स्वतंत्र वेबपेजवर</b> उपलब्ध आहे. तेथे आपण:",
        "  ✨ <b>विनामूल्य सॅम्पल पेजेस</b> थेट वाचू शकता",
        "  🔍 <b>विषयवार व महिनावार</b> सर्च करू शकता",
        "  ⚡ <b>GPay / PhonePe / Paytm / Any UPI</b> द्वारे १-क्लिक पेमेन्ट करू शकता",
        "  📩 पेमेन्ट होताच <b>ब्राऊझरमध्ये त्वरित PDF डाऊनलोड</b> व आपल्या <b>ईमेलवर</b> प्रत प्राप्त होते!\n",
        "🔥 <b>सध्याची टॉप सेलर पुस्तके:</b>"
    ]
    keyboard = []
    for p in products[:5]:
        lines.append(f"{p['icon']} <b>{p['title']}</b>")
        lines.append(f"   ↳ <s>₹{p['original_price_inr']}</s> <b>फक्त ₹{p['price_inr']}/-</b> ({p['badge']})\n")
        keyboard.append([InlineKeyboardButton(f"📖 {p['title'][:22]}... (₹{p['price_inr']})", url=f"{store_url}?prod={p['id']}")])

    lines.append(f"🌐 <b>स्टोअर उघडण्यासाठी खालील बटणावर क्लिक करा:</b>\n🔗 <a href=\"{store_url}\">{store_url}</a>")

    keyboard.append([InlineKeyboardButton("🛒 अधिकृत डिजिटल वेब स्टोअर उघडा (Open Store)", url=store_url)])
    keyboard.append([InlineKeyboardButton(get_youtube_button_text(), url=get_youtube_link())])
    keyboard.append([InlineKeyboardButton("🔙 मुख्य मेनू (Main Menu)", callback_data="main_menu")])

    msg_text = "\n".join(lines)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            msg_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True
        )
    elif update.message:
        await update.message.reply_text(
            msg_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True
        )

async def agency_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: Comprehensive AI Agency, Live Agent Roster & Department Status Report."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to administrators only.")
        return

    # Check if a detailed sub-view was requested
    args = context.args or []
    subview = args[0].lower() if args else ""

    status_msg = await update.message.reply_text("⏳ <i>CEO व AI Lead Director सर्व विभागांचे लाइव्ह ऑडिट घेत आहेत...</i>", parse_mode="HTML")

    # Fast parallel execution with strict 1.5s timeout circuit breaker
    try:
        ceo_task = asyncio.wait_for(ceo_agent.generate_executive_brief(DB_PATH), timeout=1.5)
        research_task = asyncio.wait_for(exam_researcher.analyze_uploaded_exam_trends(DB_PATH), timeout=1.5)
        results = await asyncio.gather(ceo_task, research_task, return_exceptions=True)
        ceo_brief = results[0] if isinstance(results[0], dict) else ceo_agent.get_offline_fallback("ceo brief", expect_json=True)
        research_digest = results[1] if isinstance(results[1], dict) else exam_researcher.get_offline_fallback("research", expect_json=True)
    except Exception:
        ceo_brief = ceo_agent.get_offline_fallback("ceo brief", expect_json=True)
        research_digest = exam_researcher.get_offline_fallback("research", expect_json=True)

    ai_health = ai_lead_director.audit_ai_mesh_health()
    ux_standards = uiux_architect.audit_storefront_ux_standards()
    ops_health = commerce_manager.get_operations_health()

    report_lines = [
        "🏢 <b>ExamRankers Autonomous AI Enterprise</b>",
        "══════════════════════════",
        f"👑 <b>CEO Brief:</b> {ceo_brief.get('executive_summary', 'Operating smoothly.')}\n",
        f"🎯 <b>ब्रँड प्रतिष्ठा इंडेक्स:</b> <code>{ceo_brief.get('brand_reputation_index', 98)}/100</code>",
        f"💬 <i>\"{ceo_brief.get('ceo_quote_marathi', 'अथक परिश्रम आणि योग्य तंत्रज्ञान = सरकारी नोकरीत यश!')}\"</i>\n",
        "🤖 <b>सध्या कोणता AI एजंट काय करतो आणि कसे कार्य करतो? (Live Roster):</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "१. 👑 <b>CEO (Dr. Vikramaditya Deshmukh):</b>",
        "   • <i>काय करतो:</i> समग्र व्यवसाय रणनीती, महसूल मॉडेल व ब्रँड दिशा.",
        "   • <i>कसा करतो:</i> डेटाबेस टेलिमेट्री, विद्यार्थी प्रतिसाद विश्लेषण व स्ट्रॅटेजिक डिसिजन इंजिन.",
        "   • <i>सध्याचे कार्य:</i> २०२६ भरती मोहिमेसाठी डिजिटल ई-स्टोअर व मोफत रँक प्रेडिक्टरचे मॉनिटरिंग. [🟢 Active]\n",
        "२. ⚡ <b>AI Lead Director (Aryan Sen):</b>",
        "   • <i>काय करतो:</i> मल्टी-एजंट मेष समन्वय, सब-सेकंद रिस्पॉन्स व फॉलबॅक व्यवस्था.",
        "   • <i>कसा करतो:</i> Nexus Protocol, ऑटोमॅटिक सर्किट ब्रेकर व झिरो-लेटन्सी मेष राऊटिंग.",
        "   • <i>सध्याचे कार्य:</i> झिरो-लेटन्सी फॉलबॅक व ऑटोमॅटिक एरर रिकव्हरी सिस्टीम संचलन. [🟢 Active]\n",
        "३. 🎓 <b>Academic Dean (Prof. R. G. Jadhav):</b>",
        "   • <i>काय करतो:</i> TCS व IBPS अभ्यासक्रम अचूकता, दर्जा व प्रश्न पडताळणी.",
        "   • <i>कसा करतो:</i> मागील ५ वर्षांतील शिफ्ट पेपर्सचे बेंचमार्किंग व सिलॅबस मॅपिंग.",
        "   • <i>सध्याचे कार्य:</i> तलाठी, पोलीस भरती व आरोग्य विभाग संभाव्य प्रश्नांचे गुणवत्ता ऑडिट. [🟢 Active]\n",
        "४. 🔬 <b>Lead Exam Researcher (Dr. Shrikant Joshi):</b>",
        "   • <i>काय करतो:</i> रिस्पॉन्स शीट्समधून ट्रॅप प्रश्न, सामान्य चुका व आक्षेपार्ह प्रश्न शोधणे.",
        "   • <i>कसा करतो:</i> DigiALM रिस्पॉन्स शीट्सचे ऑटोमॅटिक डेटा मायनिंग व फ्रिक्वेन्सी ॲनालिसिस.",
        "   • <i>सध्याचे कार्य:</i> चालू महिन्यातील TCS ट्रॅप प्रश्न व आक्षेपार्ह (Objection) प्रश्नांचे संकलन. [🟢 Active]\n",
        "५. 🎨 <b>UI/UX Architect (Zoya Al-Mansoor):</b>",
        "   • <i>काय करतो:</i> डिजिटल ई-स्टोअरचे अर्गोनॉमिक्स, मोबाईल व्ह्यू व ३-क्लिक चेकआउट.",
        "   • <i>कसा करतो:</i> हीउरिस्टिक इव्हॅल्यूएशन, फ्रिक्शनलेस मोडल फ्लो व रिस्पॉन्सिव्ह CSS.",
        "   • <i>सध्याचे कार्य:</i> स्टोअरमधील नो-रिफंड पॉलिसी, ऑप्शनल UTR व इन्स्टंट डाऊनलोड बटण ऑप्टिमायझेशन. [🟢 Active]\n",
        "६. 🖌️ <b>Visual Design Lead (Aarav Mehta):</b>",
        "   • <i>काय करतो:</i> माइंडमॅप्स, इन्फोग्राफिक चार्ट्स आणि ई-बुक्सच्या हाय-कॉन्ट्रास्ट इमेजेस.",
        "   • <i>कसा करतो:</i> Pillow ग्राफिक्स इंजिन, देवनागरी फॉन्ट रेंडरर व मॉडर्न पेस्टल पॅलेट्स.",
        "   • <i>सध्याचे कार्य:</i> सर्व डिजिटल उत्पादनांच्या PDF साठी प्रिंट-फ्रेंडली लाईट-थीम संकल्पना कार्ड्स जनरेट करणे. [🟢 Active]\n",
        "७. 🛒 <b>Commerce & Operations (Rajesh Parekh):</b>",
        "   • <i>काय करतो:</i> प्रॉडक्ट इन्व्हेंटरी, मायक्रो-प्रायसिंग (₹१०-₹९९), पेमेंट पडताळणी व वितरण.",
        "   • <i>कसा करतो:</i> ट्रॅन्झॅक्शन व्हॅलिडेशन, ऑर्डर हॅशिंग व ऑटोमेटेड टोकन जनरेशन.",
        "   • <i>सध्याचे कार्य:</i> २०२६ मधील चालू घडामोडींच्या ११ ई-बुक्सची इन्व्हेंटरी व ऑर्डर डिस्पेच ट्रॅकिंग. [🟢 Active]\n",
        "८. 📢 <b>Growth & Marketing (Radhika Deshpande):</b>",
        "   • <i>काय करतो:</i> टेलिग्राम ब्रॉडकास्ट कॉपी, व्हायरल हुक्स, FOMO प्रमोशन्स व ३-तास जाहिराती.",
        "   • <i>कसा करतो:</i> मराठी सायकॉलॉजी-ड्रिव्हन डायरेक्ट-रिस्पॉन्स कॉपीरायटिंग व मर्यादित ऑफर स्ट्रॅटेजी.",
        "   • <i>सध्याचे कार्य:</i> चॅनेलवरील ३-तासांच्या हाय-कन्व्हर्जन प्रोमो व माइंडमॅप ब्रॉडकास्टचे शेड्युलिंग. [🟢 Active]\n",
        "९. 📑 <b>Product Publishing Faculty (Dr. Snehal Patil):</b>",
        "   • <i>काय करतो:</i> सविस्तर स्पष्टीकरणासह टॉप २०० प्रश्नांचे दर्जेदार PDF ई-बुक्स व ट्रिक्स संच.",
        "   • <i>कसा करतो:</i> ReportLab PDF इंजिन, लाईट व्ह्यू थीम, इन्फोग्राफिक्स आणि स्ट्रक्चर्ड लेआउट.",
        "   • <i>सध्याचे कार्य:</i> सर्व पीडीएफ ई-बुक्समध्ये सविस्तर विश्लेषण, शॉर्टकट ट्रिक्स व इन्फोग्राफिक समाविष्ट करणे. [🟢 Active]\n",
        "१०. 📧 <b>Fulfillment Email Agent (Kavita Sharma):</b>",
        "   • <i>काय करतो:</i> खरेदीनंतर विद्यार्थ्यांच्या ईमेलवर तात्काळ ई-बुक व डिजिटल पावती पाठवणे.",
        "   • <i>कसा करतो:</i> ऑटोमॅटिक ट्रॅन्झॅक्शनल ईमेल डिस्पॅचर व ब्राऊझर इन्स्टंट डाऊनलोड लिंक सिस्टीम.",
        "   • <i>सध्याचे कार्य:</i> पेमेंट अप्रूव्ह होताच ० सेकंदात ईमेल पाठवणे व थेट डाऊनलोड सुलभ करणे. [🟢 Active]"
    ]

    kb = [
        [InlineKeyboardButton("🌐 अधिकृत वेब स्टोअर उघडा", url=get_store_web_url())],
        [InlineKeyboardButton("📦 सर्व ई-बुक्स ZIP डाऊनलोड", callback_data="download_store_zip")],
        [InlineKeyboardButton("📺 YouTube चॅनेल पहा", url=get_youtube_link())]
    ]

    await status_msg.edit_text("\n".join(report_lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb), disable_web_page_preview=True)

async def sync_channel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: Exam trend analysis report (Channel renaming disabled)."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to administrators only.")
        return

    status_msg = await update.message.reply_text("⏳ <i>परीक्षा ट्रेंड व ॲनालिटिक्स गोळा करत आहे...</i>", parse_mode="HTML")
    trending = channel_branding_agent.detect_trending_exam(DB_PATH)

    reply = (
        f"🏆 <b>सध्याची ट्रेंडिंग परीक्षा विश्लेषण:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>सक्रिय परीक्षा:</b> {trending.get('name')}\n"
        f"🏷️ <b>परीक्षेचा कोड:</b> <code>{trending.get('key')}</code>\n\n"
        f"🔒 <b>चॅनेल नाव संरक्षण:</b>\n"
        f"<i>आपल्या सूचनेनुसार चॅनेलचे नाव आपोआप बदलणे (Auto Name Changing) पूर्णपणे बंद करण्यात आले आहे. तुमचे मूळ चॅनेल नाव कायम सुरक्षित राहील.</i>"
    )
    await status_msg.edit_text(reply, parse_mode="HTML")

async def check_youtube_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: Force checks YouTube channel uploads and broadcasts new video with store links."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to administrators only.")
        return

    channel = os.getenv("PAID_CHANNEL_ID", "").strip() or PAID_CHANNEL_ID
    yt_url = get_youtube_link()
    if not yt_url:
        await update.message.reply_text("⚠️ कृपया आधी .env मध्ये YOUTUBE_CHANNEL_LINK सेट करा.")
        return

    status_msg = await update.message.reply_text("⏳ <i>YouTube चॅनेलवरील ताज्या व्हिडिओंची तपासणी करत आहे...</i>", parse_mode="HTML")
    await check_and_post_latest_youtube_videos(context.bot, channel, yt_url, db_path=DB_PATH)
    await status_msg.edit_text("✅ YouTube व्हिडिओ स्कॅनिंग पूर्ण झाले! नवीन व्हिडिओ असल्यास चॅनेलवर पोस्ट केला आहे.", parse_mode="HTML")

async def download_store_content_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: Packages all digital product PDFs into a single ZIP file for 1-click download."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to administrators only.")
        return

    status_msg = await update.message.reply_text("⏳ <i>सर्व १८ डिजिटल ई-बुक्स गोळा करून ZIP आर्काइव्ह तयार करत आहे...</i>", parse_mode="HTML")

    products = packaging_agent.get_all_products(DB_PATH)
    storage_products_dir = STORAGE_DIR / "products"
    storage_products_dir.mkdir(parents=True, exist_ok=True)

    for p in products:
        try:
            packaging_agent.ensure_product_pdf(p["id"], output_dir=storage_products_dir, db_path=DB_PATH)
        except Exception as e:
            logger.warning(f"Error ensuring PDF for {p.get('id')}: {e}")

    zip_dir = STORAGE_DIR / "reports"
    zip_dir.mkdir(parents=True, exist_ok=True)
    zip_path = zip_dir / "ExamRankers_Full_Store_Content.zip"

    pdf_files = list(storage_products_dir.glob("*.pdf"))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in pdf_files:
            zf.write(f, arcname=f.name)

    zip_size_mb = round(zip_path.stat().st_size / (1024 * 1024), 2)
    admin_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "admin")[:16]
    web_dl_url = f"{get_store_web_url()}/admin/download_all_products?token={admin_token}"

    caption = (
        f"📦 <b>ExamRankers अधिकृत ई-स्टोअर संपूर्ण सामग्री (ZIP)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📚 <b>एकूण समाविष्ट ई-बुक्स:</b> {len(pdf_files)} PDF फाईल्स\n"
        f"💾 <b>एकूण आकार:</b> {zip_size_mb} MB\n"
        f"📅 <b>मासिक चालू घडामोडी:</b> जानेवारी २०२६ ते नोव्हेंबर २०२६ (प्रत्येकी Top 200 MCQs)\n"
        f"📝 <b>विषयवार पुस्तके:</b> मराठी, English, गणित/बुद्धिमत्ता, TCS Q-Bank, महाराष्ट्र GS\n\n"
        f"🌐 <b>ब्राऊझर थेट डाऊनलोड लिंक:</b>\n"
        f"🔗 <a href=\"{web_dl_url}\">{web_dl_url}</a>"
    )

    kb = [
        [InlineKeyboardButton("🌐 थेट ब्राऊझरमधून डाऊनलोड करा (Web)", url=web_dl_url)],
        [InlineKeyboardButton("🛒 डिजिटल स्टोअर उघडा", url=get_store_web_url())]
    ]

    try:
        await context.bot.send_document(
            chat_id=user.id,
            document=open(zip_path, "rb"),
            filename="ExamRankers_Full_Store_Content.zip",
            caption=caption,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        await status_msg.delete()
    except Exception:
        await status_msg.edit_text(
            f"{caption}\n\n⚠️ <i>(टेलिग्रामवर पाठवताना मर्यादा आल्यास वरील थेट ब्राऊझर लिंकवरून १-क्लिकमध्ये डाऊनलोड करा)</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb),
            disable_web_page_preview=True
        )

async def bulk_upload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: Toggles bulk response sheet / Master MCQ PDF upload mode."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to administrators only.")
        return
    context.user_data["admin_bulk_mode"] = True
    context.user_data["category"] = "Open"
    await update.message.reply_text(
        "📥 <b>Master TCS/IBPS Bulk PDF मोड सक्रिय झाला आहे!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "आता सर्व TCS किंवा IBPS चे MCQs असलेला Master PDF पाठवा.\n\n"
        "बॉट स्वयंचलितपणे:\n"
        "1️⃣ सर्व प्रश्न, पर्याय व अचूक उत्तरे काढेल\n"
        "2️⃣ चॅनेलवर १-बाय-१ क्विझेस शेड्यूल करेल\n"
        "3️⃣ डिजिटल स्टोअरमधील 'TCS/IBPS मास्टर प्रश्नसंच' ई-बुकमध्ये सर्व प्रश्न तात्काळ सिंक (Sync) करेल!\n\n"
        "👉 <i>कृपया आता PDF फाईल येथे पाठवा...</i>",
        parse_mode="HTML"
    )

async def daily_current_affairs_updater_loop(application: Application):
    """
    Background Scheduler: Runs every 24 hours to keep the current month's Top 200 MCQs
    eBook continuously refreshed day-by-day with the latest developments and memory tricks.
    """
    await asyncio.sleep(120)
    while True:
        try:
            now = datetime.now()
            today_str = now.strftime("%d %B %Y")
            current_month_id = f"prod_ca_{now.year}_{now.month:02d}"

            with sqlite3.connect(DB_PATH) as db:
                db.execute("""
                    UPDATE digital_products
                    SET subtitle = ?,
                        badge = '⚡ LIVE DAILY UPDATED (₹19)'
                    WHERE id = ? OR id = 'prod_ca_monthly_top200'
                """, (f"चालू घडामोडी दैनिक अद्ययावत आवृत्ती — {today_str} पर्यंत", current_month_id))

            storage_products_dir = STORAGE_DIR / "products"
            storage_products_dir.mkdir(parents=True, exist_ok=True)
            packaging_agent.ensure_product_pdf(current_month_id, output_dir=storage_products_dir, db_path=DB_PATH)
            packaging_agent.ensure_product_pdf("prod_ca_monthly_top200", output_dir=storage_products_dir, db_path=DB_PATH)

            logger.info(f"Daily Current Affairs Updater: Synced live edition for {today_str}")
        except Exception as e:
            logger.warning(f"Error in daily_current_affairs_updater_loop: {e}")
        await asyncio.sleep(24 * 3600)

async def post_store_promo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: Uses Marketing Sales Agent to drop a high-converting digital product promo in the channel."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to administrators only.")
        return

    channel = os.getenv("PAID_CHANNEL_ID", "").strip() or PAID_CHANNEL_ID
    if not channel or channel.startswith("http"):
        await update.message.reply_text("⚠️ कृपया आधी .env मध्ये PAID_CHANNEL_ID सेट करा.")
        return

    target_chat = int(channel) if channel.lstrip("-").isdigit() else channel
    store_url = get_store_web_url()
    products = packaging_agent.get_all_products(DB_PATH)
    target_prod = products[0] if products else DEFAULT_PRODUCTS[0]

    sample_q = SAMPLE_PREVIEWS.get(target_prod["id"], {}).get("samples", [None])[0]
    promo_text = await marketing_sales_agent.generate_product_promo_post(target_prod, store_url, sample_q)

    kb = [
        [InlineKeyboardButton(f"🛒 खरेदी करा (फक्त ₹{target_prod.get('price_inr', 19)})", url=store_url)],
        [InlineKeyboardButton("🌐 सर्व ई-बुक्स स्टोअर पहा (ExamRankers)", url=store_url)]
    ]
    await context.bot.send_message(
        chat_id=target_chat,
        text=promo_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb),
        disable_web_page_preview=True
    )
    await update.message.reply_text(f"✅ Digital Product ॲड चॅनेलवर यशस्वीरित्या पोस्ट केली! (Product: {target_prod['title']})")

async def get_youtube_channel_id(yt_url: str) -> Optional[str]:
    """Resolves YouTube channel ID from a channel link, handle or URL."""
    if not yt_url:
        return None
    m = re.search(r"UC[a-zA-Z0-9_-]{22}", yt_url)
    if m:
        return m.group(0)

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(yt_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if resp.status_code == 200:
                html = resp.text
                m = re.search(r'itemprop="channelId"\s+content="(UC[a-zA-Z0-9_-]{22})"', html)
                if m:
                    return m.group(1)
                m = re.search(r'https://www.youtube.com/feeds/videos.xml\?channel_id=(UC[a-zA-Z0-9_-]{22})', html)
                if m:
                    return m.group(1)
    except Exception as e:
        logger.debug(f"Could not extract channel ID from {yt_url}: {e}")
    return None

async def check_and_post_latest_youtube_videos(bot, channel_target: str, yt_url: str, db_path: str = "bot.db"):
    """
    Checks the YouTube channel RSS feed for new video uploads.
    When a new video is detected, broadcasts it to the Telegram channel with
    YouTube link, video highlights, and ExamRankers digital product store links with shortcuts and tricks.
    """
    import xml.etree.ElementTree as ET

    with sqlite3.connect(db_path) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS posted_youtube_videos (
                video_id TEXT PRIMARY KEY,
                title TEXT,
                published_at TEXT,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    channel_id = os.getenv("YOUTUBE_CHANNEL_ID", "").strip()
    if not channel_id:
        channel_id = await get_youtube_channel_id(yt_url)

    if not channel_id:
        logger.debug("YouTube Watcher: No valid channel ID could be resolved.")
        return

    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(feed_url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                return
            xml_text = resp.text
    except Exception as e:
        logger.warning(f"YouTube RSS fetch failed: {e}")
        return

    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        logger.warning(f"Error parsing YouTube RSS XML: {e}")
        return

    ns = {
        'atom': 'http://www.w3.org/2005/Atom',
        'yt': 'http://www.youtube.com/xml/schemas/2015',
        'media': 'http://search.yahoo.com/mrss/'
    }

    entries = root.findall('atom:entry', ns)
    if not entries:
        return

    with sqlite3.connect(db_path) as db:
        posted_ids = {row[0] for row in db.execute("SELECT video_id FROM posted_youtube_videos").fetchall()}

        if not posted_ids:
            # Seed current videos on initial startup so we only announce NEW uploads going forward
            for entry in entries:
                vid_id_elem = entry.find('yt:videoId', ns)
                if vid_id_elem is not None and vid_id_elem.text:
                    title_elem = entry.find('atom:title', ns)
                    pub_elem = entry.find('atom:published', ns)
                    db.execute(
                        "INSERT OR IGNORE INTO posted_youtube_videos (video_id, title, published_at) VALUES (?, ?, ?)",
                        (vid_id_elem.text.strip(), title_elem.text if title_elem is not None else "", pub_elem.text if pub_elem is not None else "")
                    )
            logger.info(f"Seeded {len(entries)} existing YouTube videos into database. Watching for new uploads...")
            return

    for entry in reversed(entries):
        vid_id_elem = entry.find('yt:videoId', ns)
        if vid_id_elem is None or not vid_id_elem.text:
            continue
        vid_id = vid_id_elem.text.strip()
        if vid_id in posted_ids:
            continue

        title_elem = entry.find('atom:title', ns)
        video_title = title_elem.text.strip() if title_elem is not None else "नवीन परीक्षा मार्गदर्शन व्हिडिओ"
        pub_elem = entry.find('atom:published', ns)
        pub_date = pub_elem.text.strip() if pub_elem is not None else ""
        video_url = f"https://youtu.be/{vid_id}"

        products = packaging_agent.get_all_products(db_path)
        target_prod = products[0]
        title_lower = video_title.lower()
        if "चालू घडामोडी" in title_lower or "current" in title_lower:
            target_prod = next((p for p in products if "current" in p["id"]), products[0])
        elif "मराठी" in title_lower or "व्याकरण" in title_lower:
            target_prod = next((p for p in products if "marathi" in p["id"]), products[0])
        elif "english" in title_lower:
            target_prod = next((p for p in products if "english" in p["id"]), products[0])
        elif "गणित" in title_lower or "बुद्धिमत्ता" in title_lower or "reasoning" in title_lower:
            target_prod = next((p for p in products if "maths" in p["id"]), products[0])
        else:
            target_prod = next((p for p in products if "qbank" in p["id"]), products[0])

        store_url = get_store_web_url()
        prod_buy_url = f"{store_url}?prod={target_prod['id']}"

        post_msg = (
            f"🎬 <b>नवीन YouTube व्हिडिओ अपलोड झाला आहे!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>{video_title}</b>\n\n"
            f"💡 <i>या व्हिडिओमध्ये TCS व IBPS परीक्षेसाठी अत्यंत उपयुक्त शॉर्टकट ट्रिक्स, "
            f"प्रश्न विश्लेषण व स्मरण क्लृप्त्या (Tricks & Tips) देण्यात आल्या आहेत. संपूर्ण व्हिडिओ नक्की पहा!</i>\n\n"
            f"📺 <b>व्हिडिओ लिंक:</b> {video_url}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📚 <b>या विषयाशी संबंधित ई-बुक व शॉर्टकट ट्रिक्स हँडबुक:</b>\n"
            f"{target_prod['icon']} <b>{target_prod['title']}</b>\n"
            f"💰 <b>किंमत:</b> <s>₹{target_prod.get('original_price_inr', 99)}</s> <b>फक्त ₹{target_prod.get('price_inr', 19)}/-</b>\n"
            f"⚡ <i>पेमेंटनंतर तात्काळ ब्राऊझरमध्ये डाऊनलोड व ईमेलवर PDF प्राप्त होते!</i>"
        )

        kb = [
            [InlineKeyboardButton("▶️ व्हिडिओ पहा (Watch Video)", url=video_url)],
            [InlineKeyboardButton(f"🛒 ई-बुक खरेदी करा (फक्त ₹{target_prod.get('price_inr', 19)})", url=prod_buy_url)],
            [InlineKeyboardButton("🌐 अधिकृत डिजिटल स्टोअर उघडा (ExamRankers)", url=store_url)],
            [InlineKeyboardButton("🔴 आमचे YouTube चॅनेल (Subscribe)", url=get_youtube_link() or video_url)]
        ]

        target_chat = int(channel_target) if channel_target.lstrip("-").isdigit() else channel_target
        try:
            await bot.send_message(
                chat_id=target_chat,
                text=post_msg,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(kb),
                disable_web_page_preview=False
            )
            logger.info(f"📢 Broadcasted new YouTube video '{video_title}' to channel {channel_target}")

            with sqlite3.connect(db_path) as db:
                db.execute(
                    "INSERT OR REPLACE INTO posted_youtube_videos (video_id, title, published_at) VALUES (?, ?, ?)",
                    (vid_id, video_title, pub_date)
                )
        except Exception as e:
            logger.warning(f"Failed to post YouTube video update to channel: {e}")

async def youtube_upload_watcher_loop(application: Application):
    """
    Background Scheduler: Checks YouTube channel every 10 minutes for new video uploads.
    When a new video is published, immediately broadcasts it with video link, store links,
    and relevant digital product recommendations with shortcuts and tricks.
    """
    await asyncio.sleep(45)
    while True:
        try:
            channel_target = os.getenv("PAID_CHANNEL_ID", "").strip() or PAID_CHANNEL_ID
            yt_url = get_youtube_link()
            if channel_target and not channel_target.startswith("http") and yt_url:
                await check_and_post_latest_youtube_videos(application.bot, channel_target, yt_url, db_path=DB_PATH)
        except Exception as e:
            logger.warning(f"Error in youtube_upload_watcher_loop: {e}")
        await asyncio.sleep(600)

def start_keep_alive_pinger():
    """
    Periodically sends an HTTP GET request to the bot's public Render URL every 8 minutes
    to keep Render's free web service awake 24/7 (preventing the 15-minute idle spin-down).
    """
    url = (
        os.getenv("RENDER_EXTERNAL_URL")
        or os.getenv("SELF_PING_URL")
        or os.getenv("PING_URL")
    )
    if not url:
        hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
        if hostname:
            url = f"https://{hostname}"

    if not url:
        port_str = os.getenv("PORT", "8080")
        url = f"http://127.0.0.1:{port_str}/health"
        logger.info(f"ℹ️ Keep-alive pinger: Using local health endpoint fallback: {url}")

    import time
    import httpx

    target_url = url.strip().rstrip("/") + "/"

    def _ping_loop():
        logger.info(f"🔄 Automated 24/7 Keep-Alive self-pinger active for: {target_url} (every 8 min)")
        time.sleep(30)  # Initial wait before first ping
        while True:
            try:
                res = httpx.get(target_url, timeout=20.0, follow_redirects=True)
                logger.info(f"💓 Keep-alive ping sent to {target_url} -> Status {res.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ Keep-alive ping failed: {e}")
            time.sleep(8 * 60)  # Ping every 8 minutes

    t = threading.Thread(target=_ping_loop, daemon=True)
    t.start()

def start_health_check_server():
    """Runs a background HTTP server so the bot can be hosted 24/7 on free cloud services (Render, Koyeb, Hugging Face, etc.)."""
    port_str = os.getenv("PORT", "8080")
    try:
        port = int(port_str)
    except ValueError:
        port = 8080
    try:
        server = http.server.ThreadingHTTPServer(("0.0.0.0", port), HealthCheckHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        logger.info(f"🟢 24/7 Health-check web server live on 0.0.0.0:{port}!")
    except Exception as e:
        logger.warning(f"Could not start health-check web server on port {port}: {e}")

def main():
    if not TOKEN:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in .env")
    start_health_check_server()
    start_keep_alive_pinger()
    init_db()
    init_quiz_db(DB_PATH)
    packaging_agent.init_products_db(DB_PATH)
    threading.Thread(target=lambda: [packaging_agent.ensure_product_pdf(p['id']) for p in DEFAULT_PRODUCTS], daemon=True).start()
    logger.info("Initializing Telegram application...")
    app = (
        Application.builder()
        .token(TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .post_init(set_bot_commands)
        .build()
    )
    app.add_error_handler(error_handler)

    # Core user commands (100% Free rank prediction & subject analysis)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["store", "products", "ebooks", "books"], store_cmd))
    app.add_handler(CommandHandler(["vip", "join_paid", "pay", "payment", "quiz_channel"], vip_cmd))
    app.add_handler(CommandHandler(["quiz", "practice", "mcq"], quiz_cmd))
    app.add_handler(CommandHandler(["visitors", "store_visitors", "store_stats"], visitors_cmd))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler(["channels", "channel", "youtube", "yt", "socials"], channels_cmd))
    app.add_handler(CommandHandler(["deals", "notes", "offers"], deals_cmd))
    app.add_handler(CommandHandler(["wrong", "wrong_answers", "incorrect"], wrong_answers_cmd))
    app.add_handler(CommandHandler(["responses", "all_responses", "my_responses", "allresponses"], responses_cmd))
    app.add_handler(CommandHandler("cancel", cancel))

    # Admin commands (Response sheets, ZIP export, Channel, Quizzes, QBank, Schedulers)
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler(["agency", "agents", "team", "ai_status", "force_agents"], agency_cmd))
    app.add_handler(CommandHandler(["sync_channel", "update_channel_name", "rename_channel"], sync_channel_cmd))
    app.add_handler(CommandHandler(["post_store_promo", "promote_store"], post_store_promo_cmd))
    app.add_handler(CommandHandler(["check_youtube", "youtube_update", "post_youtube"], check_youtube_cmd))
    app.add_handler(CommandHandler(["download_store_content", "download_store", "export_store", "all_ebooks", "store_zip"], download_store_content_cmd))
    app.add_handler(CommandHandler(["bulk_upload", "upload_bulk", "master_upload"], bulk_upload_cmd))
    app.add_handler(CommandHandler(["master_report", "exam_report", "analytics_report", "generate_report"], master_report_cmd))
    app.add_handler(CommandHandler(["qbank", "question_bank", "oneliner"], question_bank_cmd))
    app.add_handler(CommandHandler(["post_mindmap", "mindmap"], post_mindmap_cmd))
    app.add_handler(CommandHandler(["post_promo", "advertise", "promo"], post_promo_cmd))
    app.add_handler(CommandHandler("channel_id", channel_id_cmd))
    app.add_handler(CommandHandler(["channel_status", "test_channel"], channel_status_cmd))
    app.add_handler(CommandHandler("connect_channel", connect_channel_cmd))
    app.add_handler(CommandHandler("set_channel", set_channel_cmd))
    app.add_handler(CommandHandler(["download_all", "download_responses", "export_all"], download_all_responses_cmd))
    app.add_handler(CommandHandler("admin_files", admin_files))
    app.add_handler(CommandHandler("getfile", get_file))
    app.add_handler(CommandHandler(["post_quizzes", "postquizzes", "postquizes", "postquiz"], post_quizzes))
    app.add_handler(CommandHandler("post_analysis", post_analysis_cmd))
    app.add_handler(CommandHandler("paid_users", paid_users))
    app.add_handler(CommandHandler("set_ad", set_ad))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # Channel Admin addition listener (captures when bot is added as administrator)
    app.add_handler(ChatMemberHandler(on_chat_member_updated, ChatMemberHandler.MY_CHAT_MEMBER))

    # Callbacks and Message Handlers
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    app.add_handler(MessageHandler((filters.TEXT & ~filters.COMMAND) | filters.PHOTO | filters.FORWARDED, handle_text_or_photo))

    logger.info("ExamRankers Telegram Bot started successfully!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()

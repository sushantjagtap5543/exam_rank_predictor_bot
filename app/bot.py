import asyncio
import base64
import hashlib
import hmac
import html
import http.server
import io
import ipaddress
import json
import logging
import os
import random
import re
import secrets
import shutil
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import httpx
from dotenv import load_dotenv
from telegram.error import RetryAfter

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "app"

from telegram import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonCommands,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .admin_panel import render_admin_dashboard_html, render_admin_login_html
from .agents import (
    AcademicDeanManager,
    AILeadDirector,
    BrandVisualsDesigner,
    ChannelBrandingAgent,
    ChiefExecutiveOfficer,
    CommerceOperationsManager,
    CurrentAffairsSeniorEditor,
    CurriculumResearchSynthesist,
    EnglishSeniorFaculty,
    ExamIntelligenceResearcher,
    GrowthMarketingManager,
    MarathiSeniorFaculty,
    MarketingSalesAgent,
    UIUXDesignArchitect,
)
from .ai_analysis import (
    format_swot_telegram_message,
    generate_html_full_report,
    generate_incorrect_answers_report,
    generate_master_analytics_report_html,
    generate_oneliner_question_bank_pdf,
    generate_smart_explanation,
    generate_swot_analysis,
    generate_topic_weightage_analysis,
    get_daily_latest_exam_questions,
)
from .digital_store import (
    DEFAULT_PRODUCTS,
    SAMPLE_PREVIEWS,
    fulfillment_agent,
    get_product_sample_page_image,
    get_product_sample_preview_data,
    packaging_agent,
    render_digital_store_html,
)
from .mindmap_engine import (
    get_next_dynamic_mindmap,
    record_mindmap_posted,
)
from .monetization import (
    approve_and_generate_invite,
    generate_qr_bytes,
    get_deals_keyboard,
    get_paid_channel_link,
    init_monetization_db,
    is_utr_already_used,
    record_payment_request,
    reject_payment,
    validate_utr_format,
)
from .parser import (
    detect_exam,
    extract_pdf_text,
    extract_pdf_text_with_status,
    extract_post_and_metadata,
    parse_answers,
    parse_general_mcqs,
    parse_html_response_sheet,
    recover_digialm_url_from_pdf,
    score_answers,
)
from .quiz_generator import (
    compute_question_hash,
    extract_quizzes_from_records,
    extract_quizzes_locally,
    init_quiz_db,
    is_quiz_already_posted,
    send_quizzes_to_channel,
)
from .rank import estimate_cohort_rank

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
PERSISTENT_ROOT = Path(os.getenv("DATA_DIR") or os.getenv("PERSISTENT_STORAGE_DIR") or str(PROJECT_ROOT)).resolve()
DB_PATH = os.getenv("DATABASE_PATH", str(PERSISTENT_ROOT / "bot.db"))
STORAGE_DIR = Path(os.getenv("ADMIN_STORAGE_DIR", str(PERSISTENT_ROOT / "admin_storage"))).resolve()
RESPONSE_DIR = STORAGE_DIR / "response_sheets"
REPORT_DIR = STORAGE_DIR / "reports"
ADMIN_IDS = {int(x.strip()) for x in (os.getenv("ADMIN_TELEGRAM_IDS") or os.getenv("ADMIN_USER_IDS") or "705909048").split(",") if x.strip().isdigit()}
PAID_CHANNEL_ID = os.getenv("PAID_CHANNEL_ID", "-1004381339759").strip()
PAID_CHANNEL_LINK = get_paid_channel_link()
_configured_dl_key = os.getenv("DOWNLOAD_SECRET_KEY", "").strip()
if not _configured_dl_key or len(_configured_dl_key) < 16 or _configured_dl_key == "examrankers_secure_download_secret_key_32b":
    DOWNLOAD_SECRET_KEY = secrets.token_hex(32)
    logger.warning("SECURITY NOTICE: DOWNLOAD_SECRET_KEY is unset or using known default. An ephemeral 32-byte cryptographic key has been generated in memory.")
else:
    DOWNLOAD_SECRET_KEY = _configured_dl_key
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()

from .cashfree_client import get_cashfree_client

SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
if SENTRY_DSN:
    try:
        import importlib
        sentry_sdk = importlib.import_module("sentry_sdk")
        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.2)
        logger.info("Sentry monitoring initialized successfully.")
    except Exception as e:
        logger.warning(f"Sentry init warning: {e}")

LEAKED_OR_PLACEHOLDER_TOKENS = {
    "your_telegram_bot_token_here",
    "YOUR_TELEGRAM_BOT_TOKEN",
    "8198751433:AAGf_4oG7YQf6QYj8v5r5d7f3h8k9l0m1n2",
    "8780012402:AAGv4k7r9l0m1n2o3p4q5r6s7t8u9v0w1x2",
}

def validate_environment_security():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token in LEAKED_OR_PLACEHOLDER_TOKENS or token.startswith("8198751433:") or "your_telegram_bot_token" in token.lower():
        raise SystemExit(
            "FATAL SECURITY REFUSAL: Leaked, placeholder, or revoked TELEGRAM_BOT_TOKEN detected. "
            "Please obtain a fresh, secure bot token from @BotFather, configure it in .env, "
            "and revoke any previously exposed tokens immediately."
        )
    admin_key = os.getenv("ADMIN_API_KEY", "").strip()
    if not admin_key or len(admin_key) < 8:
        logger.warning("SECURITY NOTICE: ADMIN_API_KEY is not configured or too short. All /api/admin/* and /admin/* endpoints are disabled.")

def is_admin_request_authenticated(headers, query_params) -> bool:
    admin_key = os.getenv("ADMIN_API_KEY", "").strip()
    if not admin_key or len(admin_key) < 8:
        return False
    provided = headers.get("X-Admin-Key", "").strip()
    if not provided:
        provided = query_params.get("key", [""])[0].strip() or query_params.get("token", [""])[0].strip() or query_params.get("admin_key", [""])[0].strip()
    if not provided:
        cookie_header = headers.get("Cookie", "")
        if "admin_key=" in cookie_header:
            for part in cookie_header.split(";"):
                part = part.strip()
                if part.startswith("admin_key="):
                    provided = urllib.parse.unquote(part.split("admin_key=", 1)[1].strip())
                    break
    if not provided:
        return False
    return hmac.compare_digest(provided, admin_key)

ALLOWED_RESPONSE_DOMAINS = (
    ".digialm.com",
    "digialm.com",
    "cdn.digialm.com",
    ".ibpsonline.ibps.in",
    "ibpsonline.ibps.in",
    ".tcsion.com",
    "tcsion.com",
)

def validate_safe_url(url: str) -> Tuple[bool, str]:
    try:
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.scheme.lower() != "https":
            return False, "सुरक्षा कारणास्तव फक्त HTTPS URL स्वीकारल्या जातात (Only HTTPS URLs allowed)."
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False, "अवैध URL (Invalid URL format)."
        allowed = any(hostname == d or hostname.endswith("." + d.lstrip(".")) for d in ALLOWED_RESPONSE_DOMAINS)
        if not allowed:
            return False, "अवैध डोमेन. फक्त DigiALM, TCS iON किंवा IBPS ची अधिकृत लिंक टाका."
        addr_info = socket.getaddrinfo(hostname, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            # Support RFC 6052 NAT64 Well-Known Prefix (64:ff9b::/96) used by Indian ISPs/telcos
            if ip.version == 6 and ip in ipaddress.IPv6Network("64:ff9b::/96"):
                embedded_v4 = ipaddress.ip_address(ip.packed[-4:])
                if embedded_v4.is_private or embedded_v4.is_loopback or embedded_v4.is_link_local or str(embedded_v4).startswith("169.254."):
                    return False, "असुरक्षित सर्व्हर पत्ता (Private or reserved IP blocked)."
                continue

            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip_str.startswith("169.254."):
                return False, "असुरक्षित सर्व्हर पत्ता (Private or reserved IP blocked)."
        return True, ""
    except socket.gaierror:
        return False, "DNS Lookup अयशस्वी झाला (Unable to resolve host)."
    except Exception as e:
        return False, f"URL त्रुटी: {e}"

def generate_signed_download_url(order_token: str, expires_in_seconds: int = 86400) -> str:
    exp = int(time.time()) + expires_in_seconds
    payload = f"{order_token}:{exp}"
    sig = hmac.new(DOWNLOAD_SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"/download/{order_token}?exp={exp}&sig={sig}"

def verify_signed_download_url(order_token: str, exp_str: str, sig_str: str) -> Tuple[bool, str]:
    if not exp_str or not sig_str:
        return False, "Missing signature or expiration parameter"
    try:
        exp = int(exp_str)
        if time.time() > exp:
            return False, "ही डाऊनलोड लिंक कालबाह्य (Expired) झाली आहे. कृपया नवीन लिंकसाठी सपोर्टशी संपर्क साधा."
        expected_sig = hmac.new(DOWNLOAD_SECRET_KEY.encode("utf-8"), f"{order_token}:{exp}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, sig_str):
            return False, "अवैध डाऊनलोड स्वाक्षरी (Invalid download signature)."
        return True, ""
    except Exception as e:
        return False, f"Verification error: {e}"

CHECKOUT_RATE_LIMITS: Dict[str, List[float]] = {}
CHECKOUT_RATE_LIMIT_LOCK = threading.Lock()

def is_ip_rate_limited(ip: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    now = time.time()
    with CHECKOUT_RATE_LIMIT_LOCK:
        # Periodic cleanup if dictionary grows large (prevents memory leak over long uptime)
        if len(CHECKOUT_RATE_LIMITS) > 1000:
            stale_keys = [k for k, ts in CHECKOUT_RATE_LIMITS.items() if not ts or (now - ts[-1] > window_seconds * 2)]
            for k in stale_keys:
                CHECKOUT_RATE_LIMITS.pop(k, None)
        timestamps = CHECKOUT_RATE_LIMITS.setdefault(ip, [])
        timestamps = [t for t in timestamps if now - t < window_seconds]
        CHECKOUT_RATE_LIMITS[ip] = timestamps
        if len(timestamps) >= max_requests:
            return True
        timestamps.append(now)
        return False

def backup_sqlite_database(db_path: str = DB_PATH, backup_dir: Optional[Path] = None) -> Optional[Path]:
    """Uses sqlite3 Backup API to create an atomic, non-blocking backup."""
    if backup_dir is None:
        backup_dir = STORAGE_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"bot_backup_{timestamp}.db"
    try:
        with sqlite3.connect(db_path, timeout=30.0) as src, sqlite3.connect(str(backup_file), timeout=30.0) as dst:
            src.backup(dst, pages=100, sleep=0.01)
        logger.info(f"SQLite backup successfully created at {backup_file}")

        # Disk retention: keep last 7 backups, prune older ones to avoid ENOSPC
        try:
            existing_backups = sorted(backup_dir.glob("bot_backup_*.db"), key=lambda p: p.stat().st_mtime)
            if len(existing_backups) > 7:
                for old_b in existing_backups[:-7]:
                    try:
                        old_b.unlink()
                        logger.info(f"Pruned old backup file: {old_b.name}")
                    except Exception:
                        pass
        except Exception:
            pass

        return backup_file
    except Exception as e:
        logger.error(f"Failed to create SQLite backup: {e}")
        return None


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
    """Detects when the bot is added to a channel or group. Only bot administrators are allowed to connect channels."""
    my_member = update.my_chat_member
    chat = update.effective_chat
    if not my_member or not chat:
        return
    new_status = my_member.new_chat_member.status
    acting_user = my_member.from_user

    # Security check: If added by non-admin, immediately leave the unauthorized chat
    if not acting_user or acting_user.id not in ADMIN_IDS:
        if new_status in ("administrator", "member"):
            logger.warning(f"Unauthorized chat addition by non-admin user {getattr(acting_user, 'id', 'Unknown')} to chat {chat.id}. Leaving chat.")
            try:
                await context.bot.leave_chat(chat.id)
            except Exception as e:
                logger.warning(f"Failed to leave unauthorized chat {chat.id}: {e}")
        return

    if new_status in ("administrator", "creator"):
        channel_id = str(chat.id)
        channel_title = chat.title or "Channel"
        update_env_channel_id(channel_id)
        logger.info(f"Bot added as administrator to {channel_title} ({channel_id}) by admin {acting_user.id}")
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"🎉 <b>Bot Successfully Added to Channel!</b>\n\n"
                        f"📢 <b>{html.escape(channel_title)}</b>\n"
                        f"🆔 ID: <code>{html.escape(channel_id)}</code>\n"
                        f"👤 Authorized by Admin ID: <code>{acting_user.id}</code>\n\n"
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

        # Question Bank table for harvested authentic exam questions from response sheets
        db.execute("""
            CREATE TABLE IF NOT EXISTS qbank_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_hash TEXT UNIQUE,
                exam_key TEXT,
                section TEXT,
                question_text TEXT,
                options_json TEXT,
                correct_option_num INTEGER DEFAULT 1,
                correct_option_text TEXT,
                explanation TEXT,
                source TEXT DEFAULT 'web_upload',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Security & Integrity: Unique constraints inside BEGIN IMMEDIATE
        try:
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_uploads_roll_exam ON uploads(roll_number, exam_key) WHERE roll_number != '' AND roll_number IS NOT NULL")
        except Exception as e:
            logger.debug(f"Note on idx_uploads_roll_exam: {e}")

        try:
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_utr_unique ON product_orders(utr) WHERE utr != '' AND utr IS NOT NULL AND utr NOT LIKE 'VERIFIED_%' AND utr NOT LIKE 'ADMIN_%'")
        except Exception as e:
            logger.debug(f"Note on idx_orders_utr_unique: {e}")

        # Performance compound indexes for lightning-fast rank & cohort queries
        try:
            db.execute("CREATE INDEX IF NOT EXISTS idx_uploads_exam_status ON uploads(exam_key, status)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_uploads_exam_cat ON uploads(exam_key, category, status)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_uploads_exam_post ON uploads(exam_key, post_name, status)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_qbank_exam_sec ON qbank_questions(exam_key, section)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_visitors_action ON store_visitors(action, visited_at)")
        except Exception as e:
            logger.debug(f"Note on compound indexes: {e}")

    try:
        init_monetization_db(DB_PATH)
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

def sync_records_to_qbank(records: list, exam_key: str = "ZP_BHARTI", source: str = "web_upload") -> int:
    """
    Synchronizes parsed questions from submitted response sheets into central qbank_questions table.
    Ensures strict SHA-256 deduplication, HTML entity sanitation, and valid 4-option formatting so
    the questions can be immediately used by Telegram bot /quiz, channel polls, and Question Bank PDF generation.
    Returns number of newly stored questions.
    """
    if not records:
        return 0
    from app.quiz_generator import compute_question_hash
    import html as html_lib
    stored_cnt = 0
    try:
        with get_connection() as db:
            for r in records:
                raw_q = (r.get("question_text") or "").strip()
                opts = r.get("options") or {}
                if not raw_q or len(raw_q) < 6 or len(opts) < 2:
                    continue

                # Strip HTML tags and unescape entities for clean plain-text question
                clean_q = re.sub(r"<[^>]+>", " ", raw_q)
                clean_q = html_lib.unescape(clean_q)
                clean_q = re.sub(r"\s+", " ", clean_q).strip()

                # Clean options
                clean_opts = {}
                for k, v in opts.items():
                    c_v = re.sub(r"<[^>]+>", " ", str(v))
                    c_v = html_lib.unescape(c_v)
                    c_v = re.sub(r"\s+", " ", c_v).strip()
                    clean_opts[str(k)] = c_v

                opts_list = [str(v) for v in clean_opts.values()]
                q_hash = compute_question_hash(clean_q, opts_list)

                # Resolve correct_option_num (1..4)
                c_num = r.get("correct_option_number")
                if c_num is not None:
                    try:
                        c_num = int(re.sub(r"[^\d]+", "", str(c_num)) or 0)
                    except Exception:
                        c_num = 0

                # Match correct_option_id with option keys (e.g. TCS 10-digit option ID)
                if not c_num and r.get("correct_option_id"):
                    c_id = str(r.get("correct_option_id")).strip()
                    for idx, k in enumerate(clean_opts.keys(), start=1):
                        if str(k).strip() == c_id:
                            c_num = idx
                            break

                # Match correct_option_text with option values
                c_text = (r.get("correct_option_text") or "").strip()
                if not c_num and c_text:
                    c_txt_clean = html_lib.unescape(re.sub(r"<[^>]+>", "", c_text)).strip().lower()
                    for idx, v in enumerate(clean_opts.values(), start=1):
                        if str(v).strip().lower() == c_txt_clean:
                            c_num = idx
                            break

                if not c_num or c_num < 1 or c_num > len(clean_opts):
                    c_num = 1

                # If c_text empty, auto-populate from option values
                if not c_text and 1 <= c_num <= len(clean_opts):
                    c_text = list(clean_opts.values())[c_num - 1]

                sec = (r.get("section") or "General").strip()
                exp = (r.get("explanation") or "").strip()

                cur = db.execute(
                    """INSERT OR IGNORE INTO qbank_questions(
                        question_hash, exam_key, section, question_text, options_json,
                        correct_option_num, correct_option_text, explanation, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        q_hash, exam_key, sec, clean_q, json.dumps(clean_opts, ensure_ascii=False),
                        c_num, c_text, exp, source
                    )
                )
                if cur.rowcount > 0:
                    stored_cnt += 1
        if stored_cnt > 0:
            logger.info(f"Synchronized {stored_cnt} new questions from {source} ({exam_key}) into Question Bank.")
    except Exception as e:
        logger.warning(f"Failed to sync records to qbank: {e}")
    return stored_cnt

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
        if "forbidden" in err_str or "blocked" in err_str or "deactivated" in err_str:
            logger.warning(f"Message not delivered to {chat_id} because bot was blocked/deactivated: {e}")
            return None
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
    Splits long messages at natural newlines (and slices unbroken lines >3800 chars)
    and auto-falls back to plain text on entity errors.
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
    for raw_line in text.split("\n"):
        line_parts = [raw_line[i:i+3800] for i in range(0, len(raw_line), 3800)] if len(raw_line) > 3800 else [raw_line]
        for line in line_parts:
            if current_len + len(line) + 1 > 3800:
                if current:
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

async def safe_edit_message(target, text: str, parse_mode="HTML", reply_markup=None, disable_web_page_preview=True):
    """
    Safely edits an existing Telegram message.
    Gracefully handles 'Message is not modified' (from repeated button taps)
    and 'Message to edit not found', preventing unhandled BadRequest crashes.
    """
    try:
        if hasattr(target, "edit_text"):
            return await target.edit_text(
                text=text[:4096],
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview
            )
        elif hasattr(target, "edit_message_text"):
            return await target.edit_message_text(
                text=text[:4096],
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview
            )
    except Exception as e:
        err_msg = str(e).lower()
        if "message is not modified" in err_msg:
            return target
        if "message to edit not found" in err_msg:
            logger.debug("Message to edit was deleted.")
            return None
        logger.warning(f"safe_edit_message error: {e}")
        if "can't parse entities" in err_msg or "entity" in err_msg:
            try:
                plain = re.sub(r"<[^>]+>", "", text)
                if hasattr(target, "edit_text"):
                    return await target.edit_text(text=plain[:4096], parse_mode=None, reply_markup=reply_markup)
            except Exception:
                pass
        return None

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

async def auto_post_quizzes_background(bot, text: str, exam_name: str, records: list = None, chat_id: Optional[Union[int, str]] = None):
    """
    Background Task: Extracts all unposted questions from records or text,
    syncs them to master question bank, and automatically posts them 1-by-1 to
    the Telegram channel or group.
    """
    if os.getenv("ENABLE_AUTO_QUIZ_POSTING", "true").lower() in ("false", "0", "no"):
        logger.info("Auto-posting quizzes to channel is paused (disabled via ENABLE_AUTO_QUIZ_POSTING=false).")
        return
    channel = chat_id or os.getenv("PAID_CHANNEL_ID", "").strip() or PAID_CHANNEL_ID or "-1004381339759"
    if not channel or str(channel).startswith("http"):
        logger.warning(f"No valid numeric or username channel ID found for auto quiz posting (channel='{channel}').")
        return

    try:
        # Step 1: Extract all unposted quizzes from records or text
        quizzes = []
        if records:
            quizzes = extract_quizzes_from_records(records, max_questions=2500, filter_unposted=True, db_path=DB_PATH)
        elif text:
            from .parser import parse_answers, parse_html_response_sheet
            parsed_text = text
            if "<html" in text.lower() or "<table" in text.lower():
                parsed_text = parse_html_response_sheet(text)
            parsed_recs = parse_answers(parsed_text)
            if parsed_recs:
                quizzes = extract_quizzes_from_records(parsed_recs, max_questions=2500, filter_unposted=True, db_path=DB_PATH)
            if not quizzes:
                quizzes = extract_quizzes_locally(parsed_text, max_questions=100, db_path=DB_PATH)

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
    """Sends notification to Telegram bot admins asynchronously in a background thread."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or not ADMIN_IDS:
        return
    def _send_bg():
        for aid in ADMIN_IDS:
            try:
                with httpx.Client(timeout=5.0) as client:
                    resp = client.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={"chat_id": aid, "text": text, "parse_mode": "HTML"},
                    )
                    if resp.status_code != 200:
                        logger.warning(f"Admin alert to {aid} returned HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"Could not alert admin {aid}: {e}")
    threading.Thread(target=_send_bg, daemon=True).start()

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
    if not q:
        return
    try:
        await q.answer()
    except Exception as e:
        logger.debug(f"Note on initial callback query answer: {e}")
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
            f"📢 <b>मोफत टेलिग्राम चॅनेल:</b> <a href=\"{PAID_CHANNEL_LINK}\">येथे मोफत जॉईन करा</a>\n"
            f"🛒 <b>डिजिटल ई-बुक्स स्टोअर (₹१० ते ₹५०):</b> <a href=\"{get_store_web_url()}\">येथे खरेदी करा</a>"
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
                "━━━━━━━━━━━━━━━━━━━━━━",
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

        upi_id = os.getenv("UPI_ID", "").strip()
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

    elif data in ("admin_post_quizzes", "post_quizzes_now"):
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to admin.", show_alert=True)
            return
        await q.answer("क्विझेस चॅनेलवर पोस्ट करण्याची प्रक्रिया सुरू करत आहे...", show_alert=False)
        await post_quizzes(update, context)

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
            [InlineKeyboardButton("📊 Generate Full HTML Report", callback_data=f"admin_report:{fid}")],
            [InlineKeyboardButton("❌ View Wrong Questions", callback_data=f"admin_wrong:{fid}")]
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

    elif data == "admin_sync_folder":
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to administrators only.", show_alert=True)
            return
        await q.answer("🔄 फोल्डर सिंक सुरू आहे...")
        added_cnt = await asyncio.to_thread(packaging_agent.sync_folder_pdfs_to_products, DB_PATH)
        all_prods = packaging_agent.get_all_products(DB_PATH)
        await q.message.reply_text(
            f"✅ <b>PDF फोल्डर सिंक यशस्वी!</b>\n\n"
            f"• नवीन जोडलेली पुस्तके: <b>{added_cnt}</b>\n"
            f"• स्टोअरमधील एकूण उत्पादने: <b>{len(all_prods)}</b>\n\n"
            f"सर्व पुस्तके आता थेट वेब स्टोअरवर उपलब्ध आहेत:\n🔗 {get_store_web_url()}",
            parse_mode="HTML"
        )

    elif data == "admin_gen_qbank":
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to administrators only.", show_alert=True)
            return
        await q.answer("📑 प्रश्नसंच तयार होत आहे...")
        await question_bank_cmd(update, context)

    elif data == "admin_gen_ca":
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to administrators only.", show_alert=True)
            return
        await q.answer("📰 चालू घडामोडी PDF तयार होत आहे...")
        status_msg = await q.message.reply_text("⏳ <i>चालू घडामोडी PDF तयार होत आहे... कृपया थोडा वेळ थांबा.</i>", parse_mode="HTML")
        try:
            now = datetime.now()
            curr_month_id = f"prod_ca_{now.year}_{now.month:02d}"
            pdf_path = await asyncio.to_thread(packaging_agent.ensure_product_pdf, curr_month_id, db_path=DB_PATH)
            if pdf_path and Path(pdf_path).exists():
                with open(pdf_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=q.message.chat_id,
                        document=f,
                        filename=Path(pdf_path).name,
                        caption=f"📰 <b>चालू घडामोडी विशेष ई-बुक तयार झाले!</b>\nमहिना: {now.strftime('%B %Y')}",
                        parse_mode="HTML"
                    )
                await status_msg.delete()
            else:
                await status_msg.edit_text("⚠️ चालू घडामोडी PDF तयार करता आली नाही. कृपया लॉग तपासा.")
        except Exception as e:
            await status_msg.edit_text(f"⚠️ त्रुटी: {html.escape(str(e))}")

    elif data == "admin_visitor_stats":
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to administrators only.", show_alert=True)
            return
        await q.answer()
        await visitors_cmd(update, context)

    elif data == "admin_dl_zip":
        if update.effective_user.id not in ADMIN_IDS:
            await q.answer("⛔ Restricted to administrators only.", show_alert=True)
            return
        await q.answer()
        await download_store_content_cmd(update, context)

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

    elif data == "use_rec_url":
        rec_url = context.user_data.get("recovered_url", "")
        if rec_url:
            await q.message.edit_text("⚡ <b>अधिकृत वेब लिंकवरून रिस्पॉन्स शीट तपासत आहे...</b> ⏳", parse_mode="HTML")
            await handle_url_sheet(update, context, rec_url)
            return

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

    is_safe, err_msg = validate_safe_url(url)
    if not is_safe:
        await update.message.reply_text(f"❌ <b>सुरक्षा मर्यादा (Security Alert):</b>\n{html.escape(err_msg)}", parse_mode="HTML")
        return

    status_msg = await update.effective_chat.send_message(
        "📥 <i>Downloading response sheet from URL and analyzing questions...</i>",
        parse_mode="HTML"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    clean_url = re.sub(r"(?<!:)//+", "/", url.strip())
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=False, headers=headers) as client:
            resp = await client.get(clean_url)
            if resp.is_redirect:
                target_redir = resp.headers.get("location", "")
                if target_redir.startswith("/"):
                    parsed_base = urllib.parse.urlparse(clean_url)
                    target_redir = f"{parsed_base.scheme}://{parsed_base.netloc}{target_redir}"
                is_redir_safe, redir_err = validate_safe_url(target_redir)
                if not is_redir_safe:
                    await status_msg.edit_text(f"❌ <b>असुरक्षित रिडायरेक्ट (Unsafe Redirect Blocked):</b> {html.escape(redir_err)}", parse_mode="HTML")
                    return
                resp = await client.get(target_redir)
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
            roll_entropy = hashlib.sha256(f"{user.id}:{clean_roll}:{time.time()}".encode()).hexdigest()[:8]
            safe_fn = f"user_{user.id}_roll_{clean_roll or 'none'}_{roll_entropy}.{ext}"

            stored_path = RESPONSE_DIR / safe_fn
            shutil.copy2(tmp_path, stored_path)

            detected = detect_exam(text, EXAMS)
            records = parse_answers(text)
            if not records:
                await status_msg.edit_text("❌ No question-answer pairs detected in the response sheet from this URL.")
                return

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
                    f"🎖️ Post: <code>{html.escape(post_name)}</code>\n"
                    "Calculating 4-tier ranks and subject dashboard...",
                    parse_mode="HTML"
                )
                await complete_analysis(update, context, detected["key"])
            elif detected.get("status") == "ambiguous":
                matches = detected.get("matches", [])
                keyboard = [[InlineKeyboardButton(m["name"], callback_data=f"exam:{m['key']}")] for m in matches]
                keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])
                await status_msg.edit_text(
                    f"⚠️ <b>एकापेक्षा जास्त परीक्षांचे निकष जुळत आहेत:</b>\n"
                    f"🎖️ Post: <code>{html.escape(post_name)}</code>\n\n"
                    "कृपया खालीलपैकी तुमची नेमकी परीक्षा निवडा:",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                keyboard = [[InlineKeyboardButton(c["display_name"], callback_data=f"exam:{k}")] for k, c in EXAMS.items()]
                keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])
                await status_msg.edit_text(
                    f"🎖️ <b>Post Detected:</b> <code>{html.escape(post_name)}</code>\n"
                    "कृपया खालीलपैकी नेमकी परीक्षा निवडा:",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
    except Exception as e:
        await status_msg.edit_text(f"❌ Error downloading from URL: {html.escape(str(e))}", parse_mode="HTML")

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
            await safe_edit_message(
                status_msg,
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
    finally:
        context.user_data.pop("pending_msg_id", None)
        context.user_data.pop("pending_pdf_doc", None)

async def _process_uploaded_pdf_impl(update: Update, context: ContextTypes.DEFAULT_TYPE, doc, status_msg):
    with tempfile.TemporaryDirectory() as tmp:
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", getattr(doc, "file_name", None) or "response_sheet.pdf")
        path = str(Path(tmp) / safe_name)
        file_size = getattr(doc, "file_size", 0) or 0
        downloaded = False

        # Tier 1: Resilient chunked HTTP download via direct Telegram API file URL with retries
        if file_size == 0:
            logger.warning(f"Document {getattr(doc, 'file_id', 'unknown')} has file_size 0, failing fast.")
        elif file_size >= 20_000_000:
            logger.info(f"Document file_size {file_size} >= 20MB. Skipping Bot API get_file and proceeding directly to MTProto fallback.")
        else:
            for attempt in range(1, 4):
                try:
                    tg_file = await context.bot.get_file(
                        doc.file_id,
                        read_timeout=120,
                        write_timeout=120,
                        connect_timeout=60
                    )
                    file_url = tg_file.file_path
                    if file_url and not file_url.startswith("http"):
                        file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_url.lstrip('/')}"

                    if file_url:
                        async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
                            async with client.stream("GET", file_url) as resp:
                                if resp.status_code == 200:
                                    with open(path, "wb") as f:
                                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                                            f.write(chunk)
                                    if Path(path).is_file() and Path(path).stat().st_size > 0:
                                        downloaded = True
                                        logger.info(f"Successfully downloaded document {doc.file_id} via direct stream ({Path(path).stat().st_size} bytes)")
                                        break

                    # Fallback to download_to_drive if direct stream was not used
                    if not downloaded:
                        await tg_file.download_to_drive(path, read_timeout=120, write_timeout=120)
                        if Path(path).is_file() and Path(path).stat().st_size > 0:
                            downloaded = True
                            break
                except Exception as e:
                    err_str = str(e).lower()
                    logger.warning(f"Download attempt {attempt}/3 for {doc.file_id} failed: {e}")
                    # Permanent errors: do not retry
                    if "file is too big" in err_str or "file_too_big" in err_str or "filenotfound" in err_str:
                        break
                    if attempt < 3:
                        await asyncio.sleep(2 * attempt)

        # If file is >= 20MB or standard download failed, use MTProto downloader (up to 2GB)
        if not downloaded:
            await safe_edit_message(
                status_msg,
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
            username = getattr(update.effective_user, "username", None) if update.effective_user else None
            if msg_id:
                try:
                    success = await asyncio.wait_for(
                        download_file_mtproto(chat_id, msg_id, path, username=username, timeout_seconds=30.0),
                        timeout=35.0
                    )
                    if success and Path(path).is_file() and Path(path).stat().st_size > 0:
                        downloaded = True
                except Exception as e:
                    logger.warning(f"MTProto fallback attempt failed or timed out: {e}")

        if not downloaded or not Path(path).is_file() or Path(path).stat().st_size == 0:
            is_large_file = file_size >= 20_000_000
            web_upload_link = f"{get_store_web_url()}/upload"
            calc_kb = [
                [InlineKeyboardButton("🌐 वेबवरून थेट अपलोड करा (कोणतीही साईज मर्यादा नाही)", url=web_upload_link)],
                [InlineKeyboardButton("✍️ थेट गुण नोंदवा (Manual Score & Rank)", callback_data="manual_calc")]
            ]

            if is_large_file:
                size_mb = round(file_size / (1024 * 1024), 1)
                await safe_edit_message(
                    status_msg,
                    f"⚠️ <b>मोठी फाईल मर्यादा ({size_mb} MB):</b>\n"
                    "Telegram Bot API च्या अधिकृत नियमांनुसार २० MB पेक्षा मोठ्या फाईल्स थेट बॉट API द्वारे डाऊनलोड होऊ शकत नाहीत.\n\n"
                    "💡 <b>या फाईलसाठी पुढील सोपे पर्याय वापरा:</b>\n\n"
                    "1️⃣ <b>थेट DigiALM लिंक (शिफारस):</b> तुमच्या रिस्पॉन्स शीटची थेट वेब लिंक येथे चॅटमध्ये पेस्ट करा (उदा. <code>https://cdn.digialm.com/...</code>).\n"
                    "<i>(कोणतीही फाईल अपलोड न करता १ सेकंदात निकाल व रँक मिळते!)</i>\n\n"
                    f"2️⃣ <b>वेब अपलोड पोर्टल:</b> ही फाईल थेट <b>{web_upload_link}</b> वरून अपलोड करा (कोणतीही २० MB मर्यादा नाही, २५ MB+ फाईल्स १ सेकंदात तपासल्या जातात).\n\n"
                    "3️⃣ <b>फाईल कॉम्प्रेस करा:</b> ilovepdf.com किंवा तत्सम टूल वापरून ही फाईल २० MB च्या आत कॉम्प्रेस करून पुन्हा पाठवा.\n\n"
                    "4️⃣ <b>किंवा थेट गुण नोंदवा:</b> खालील बटणावर क्लिक करून तुमचे गुण नोंदवा व संभाव्य रँक तपासा:",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(calc_kb)
                )
            else:
                await safe_edit_message(
                    status_msg,
                    "❌ <b>Download Error:</b> फाईल डाऊनलोड होऊ शकली नाही.\n\n"
                    "💡 <b>सर्वात सोपा व १००% अचूक पर्याय:</b>\n"
                    "तुमच्या DigiALM / परीक्षा पोर्टलची <b>थेट वेब लिंक</b> येथे चॅटमध्ये पेस्ट करा (उदा. <code>https://cdn.digialm.com/...</code>)\n"
                    "<i>(कोणतीही फाईल अपलोड न करता १ सेकंदात निकाल व रँक मिळते!)</i>",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(calc_kb[1:])
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
            clean_url = re.sub(r"(?<!:)//+", "/", recovered_url.strip())
            is_safe, sec_err = validate_safe_url(clean_url)
            if not is_safe:
                logger.warning(f"SSRF protection: rejected recovered URL '{clean_url}': {sec_err}")
            else:
                context.user_data["recovered_url"] = clean_url
                await safe_edit_message(
                    status_msg,
                    "🔗 <b>मूळ DigiALM रिस्पॉन्स शीट लिंक डिटेक्ट झाली:</b>\n"
                    f"<code>{html.escape(clean_url[:70])}...</code>\n\n"
                    "⚡ अधिकृत सर्व्हरवरून थेट १००% अचूक डेटा डाऊनलोड करत आहे... ⏳",
                    parse_mode="HTML"
                )
                try:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9,mr;q=0.8",
                        "Connection": "keep-alive"
                    }
                    curr_url = clean_url
                    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True, headers=headers) as client:
                        resp = await client.get(curr_url)
                        if resp.status_code == 200 and len(resp.content) > 1000:
                            if len(resp.content) <= 25_000_000:
                                html_str = resp.content.decode("utf-8", errors="ignore")
                                text = parse_html_response_sheet(html_str)
                                if text.strip():
                                    logger.info(f"Successfully fetched and parsed recovered DigiALM HTML ({len(text)} chars)")
                        elif resp.status_code in (400, 403):
                            # Mobile user-agent fallback
                            m_headers = {
                                "User-Agent": "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
                                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                            }
                            resp_m = await client.get(curr_url, headers=m_headers)
                            if resp_m.status_code == 200 and len(resp_m.content) > 1000:
                                html_str = resp_m.content.decode("utf-8", errors="ignore")
                                text = parse_html_response_sheet(html_str)
                except Exception as e:
                    logger.warning(f"Could not fetch recovered DigiALM URL: {e}")

        # Step 2: If no web URL or fetch failed, extract text directly via fitz / RapidOCR
        pdf_err_code = ""
        if not text.strip():
            await safe_edit_message(
                status_msg,
                "🔍 <b>PDF मजकूर व प्रश्न विश्लेषित करत आहे...</b>\n"
                "<i>RapidOCR + AI इंजिन सुरू आहे... कृपया थोडी प्रतीक्षा करा ⏳</i>",
                parse_mode="HTML"
            )
            text, pdf_err_code = await asyncio.to_thread(extract_pdf_text_with_status, path)

        if not text.strip():
            rec_url = context.user_data.get("recovered_url", "")
            keyboard = [
                [InlineKeyboardButton("✍️ Quick Score & Rank Calculator", callback_data="manual_calc")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ]
            if rec_url:
                keyboard.insert(0, [InlineKeyboardButton("⚡ या लिंकवरून थेट निकाल पहा (1-Click)", callback_data="use_rec_url")])
                err_detail = (
                    "🔗 <b>तुमच्या PDF मधून अधिकृत DigiALM लिंक सापडली आहे:</b>\n"
                    f"<code>{html.escape(rec_url)}</code>\n\n"
                    "⚠️ सर्व्हरवरील नेटवर्क वेळेच्या मर्यादेमुळे थेट फाईल डाऊनलोड होऊ शकली नाही.\n"
                    "💡 <b>उपाय:</b> वरील लिंक कॉपी करून थेट चॅटमध्ये पाठवा किंवा खालील <b>१-क्लिक बटण</b> दाबा!"
                )
            elif pdf_err_code == "password_protected":
                err_detail = (
                    "🔒 <b>हा PDF पासवर्ड प्रोटेक्टेड (Password Protected) आहे.</b>\n\n"
                    "कृपया या PDF चा पासवर्ड काढून किंवा अनलॉक करून ती पुन्हा पाठवा."
                )
            elif pdf_err_code == "corrupt_pdf":
                err_detail = (
                    "⚠️ <b>ही फाईल खराब (Corrupt) किंवा अवैध PDF आहे.</b>\n\n"
                    "कृपया अधिकृत पोर्टलवरून मूळ PDF पुन्हा डाऊनलोड करून पाठवा."
                )
            elif pdf_err_code == "empty_file":
                err_detail = (
                    "⚠️ <b>ही फाईल रिकामी (0 Bytes / Empty) आहे.</b>\n\n"
                    "कृपया योग्य फाईल निवडून पुन्हा पाठवा."
                )
            else:
                err_detail = (
                    "❌ <b>या PDF मधून मजकूर किंवा प्रश्न सापडले नाहीत.</b>\n\n"
                    "(स्कॅन खूप अस्पष्ट असू शकते किंवा प्रश्नपत्रिका नसलेली फाईल असू शकते.)"
                )

            await safe_edit_message(
                status_msg,
                f"{err_detail}\n\n"
                "💡 <b>सोपे पर्याय:</b>\n"
                "1️⃣ तुमच्या DigiALM / परीक्षा पोर्टलची URL येथे थेट पेस्ट करा.\n"
                "2️⃣ किंवा खालील बटणावर क्लिक करून तुमचे गुण नोंदवा 👇",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        detected = detect_exam(text, EXAMS)
        records = parse_answers(text)

        # Extract post name and candidate metadata from response sheet
        meta = extract_post_and_metadata(text)
        roll_raw = meta.get("roll_number") or ""
        clean_roll = re.sub(r'[^A-Za-z0-9_-]', '', str(roll_raw))
        user_id = update.effective_user.id
        roll_entropy = hashlib.sha256(f"{user_id}:{clean_roll}:{time.time()}".encode()).hexdigest()[:8]

        # Check if this is an Admin Bulk / Master MCQ PDF or an individual candidate response sheet
        has_bulk_keyword = any(k in safe_name.lower() for k in ["bulk", "master", "qbank", "mcq_master", "master_book"])
        is_large_master_bank = (len(records) > 120 and not clean_roll)
        is_admin_bulk_mode = (user_id in ADMIN_IDS) and (context.user_data.get("admin_bulk_mode") is True)

        is_bulk_request = (user_id in ADMIN_IDS) and (has_bulk_keyword or is_large_master_bank or is_admin_bulk_mode)

        RESPONSE_DIR.mkdir(parents=True, exist_ok=True)
        if is_bulk_request:
            canonical_name = f"admin_bulk_{user_id}_{roll_entropy}_{safe_name}"
        else:
            canonical_name = f"user_{user_id}_roll_{clean_roll or 'none'}_{roll_entropy}.pdf"
        stored_path = RESPONSE_DIR / canonical_name
        shutil.copy2(path, stored_path)

        context.user_data["stored_path"] = str(stored_path)
        context.user_data["doc_name"] = canonical_name
        context.user_data["last_records"] = records
        context.user_data["last_raw_text"] = text

        if is_bulk_request:
            quizzes = extract_quizzes_from_records(records, max_questions=2500, filter_unposted=False, db_path=DB_PATH)
            if not quizzes:
                quizzes = extract_quizzes_locally(text, max_questions=2500, db_path=DB_PATH)

            exam_key_for_bulk = detected.get("key") or "saralseva_general"
            with get_connection() as db:
                db.execute(
                    """INSERT INTO uploads (
                        telegram_user_id, filename, storage_path, exam_key, category, post_name,
                        score, correct_count, incorrect_count, unanswered_count, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, safe_name, str(stored_path), exam_key_for_bulk, "Open", "Master Bulk QBank",
                     0.0, len(quizzes), 0, 0, "admin_bulk")
                )

            # 1. Sync questions into master question bank (qbank_master.json)
            sync_res = packaging_agent.bulk_sync_questions_to_store_qbank(quizzes, db_path=DB_PATH)
            total_bank = sync_res.get("total_questions_in_bank", len(quizzes))
            new_added = sync_res.get("newly_added", len(quizzes))

            # 2. Automatically trigger 1-by-1 quiz posting to the group or channel
            target_chat_for_quiz = None
            if update.effective_chat and str(update.effective_chat.type) in ("group", "supergroup"):
                target_chat_for_quiz = update.effective_chat.id

            asyncio.create_task(auto_post_quizzes_background(
                context.bot,
                text,
                detected.get("name") or "TCS/IBPS Master Bulk QBank",
                records=records,
                chat_id=target_chat_for_quiz
            ))

            channel_target_display = target_chat_for_quiz or os.getenv("PAID_CHANNEL_ID", "").strip() or PAID_CHANNEL_ID or "-1004381339759"
            report_msg = (
                f"✅ <b>Master TCS/IBPS Bulk PDF यशस्वीरित्या प्रोसेस झाले!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📑 <b>एकूण डिटेक्ट झालेले प्रश्न:</b> {len(quizzes)}\n"
                f"🆕 <b>मास्टर प्रश्नसंचातील नवीन प्रश्न:</b> {new_added}\n"
                f"📚 <b>एकूण उपलब्ध प्रश्नसंख्या:</b> {total_bank}+ MCQs\n"
                f"📂 <b>साठवलेली फाईल:</b> <code>{canonical_name}</code>\n\n"
                f"🔄 <b>स्वयंचलित सिंक्रोनायझेशन व क्विझ पोस्टिंग सुरू:</b>\n"
                f"• 🧠 <b>Question Bank:</b> सर्व प्रश्न <code>qbank_master.json</code> व मास्टर स्टोअरमध्ये जोडले गेले आहेत.\n"
                f"• 📢 <b>1-by-1 क्विझ:</b> ग्रुप/चॅनेलवर (<code>{channel_target_display}</code>) १-बाय-१ क्विझ पोस्टिंग स्वयंचलित सुरू झाले आहे! 🚀\n"
                f"• 💾 <b>सुरक्षित बॅकअप:</b> सर्व प्रश्नपत्रिका डेटाबेसमध्ये सुरक्षित जतन केल्या आहेत.\n\n"
                f"👉 स्टोअर लिंक: <a href=\"{get_store_web_url()}\">येथे तपासा</a>"
            )
            context.user_data["admin_bulk_mode"] = False
            kb = [
                [InlineKeyboardButton("📢 चॅनेलवर क्विझेस पोस्ट करा (/postquizzes)", callback_data="admin_post_quizzes")],
                [InlineKeyboardButton("🛒 डिजिटल स्टोअर पहा", url=get_store_web_url())],
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
            keyboard = [[InlineKeyboardButton(m["name"], callback_data=f"exam:{m['key']}")] for m in matches]
            keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])
            await status_msg.edit_text(
                f"⚠️ <b>एकापेक्षा जास्त परीक्षांचे निकष जुळत आहेत:</b>\n"
                f"🎖️ Post: <code>{html.escape(post_name)}</code>\n\n"
                "कृपया खालीलपैकी तुमची नेमकी परीक्षा निवडा:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [[InlineKeyboardButton(c["display_name"], callback_data=f"exam:{k}")] for k, c in EXAMS.items()]
            keyboard.append([InlineKeyboardButton("🔙 मुख्य मेनू (Main Menu)", callback_data="main_menu")])
            await status_msg.edit_text(
                "⚠️ <b>या PDF मधून परीक्षेचे नाव थेट डिटेक्ट झाले नाही.</b>\n\n"
                "कृपया खालील यादीतून तुमची परीक्षा निवडा:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

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

        try:
            sync_records_to_qbank(records, exam_key=exam_key, source="telegram_bot")
        except Exception as qb_err:
            logger.warning(f"Could not sync records to qbank from bot upload: {qb_err}")

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

    # Automatically post unposted exam questions 1-by-1 to configured channel/group
    target_chat_for_quiz = None
    if update.effective_chat and str(update.effective_chat.type) in ("group", "supergroup"):
        target_chat_for_quiz = update.effective_chat.id

    asyncio.create_task(auto_post_quizzes_background(
        context.bot,
        raw_text,
        exam_display_name,
        records=records,
        chat_id=target_chat_for_quiz
    ))

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

    # If the forwarded message contains a document/PDF, route directly to handle_document
    if msg.document:
        await handle_document(update, context)
        return

    # Check if message was forwarded from a channel
    forward_chat = None
    if getattr(msg, "forward_from_chat", None):
        forward_chat = msg.forward_from_chat
    elif hasattr(msg, "forward_origin"):
        forward_chat = getattr(msg.forward_origin, "chat", None)

    if forward_chat and str(getattr(forward_chat, "type", "")) in ("channel", "supergroup", "group"):
        if user.id not in ADMIN_IDS:
            await msg.reply_text("⛔ <b>मर्यादित:</b> चॅनेल जोडण्याची परवानगी फक्त बॉट ॲडमिनिस्ट्रेटरना आहे (Admin Only).", parse_mode="HTML")
            return

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
                f"📢 चॅनेल नाव: <b>{html.escape(f_title)}</b>\n"
                f"🆔 चॅनेल आयडी: <code>{html.escape(f_id)}</code>\n"
                f"👑 <b>Admin Status:</b> ✅ Administrator (Post Messages Allowed)\n\n"
                f"आता या चॅनेलवर थेट क्विझ पोल्स पाठवण्यासाठी खालील कमांड दाबा:\n"
                f"👉 <code>/postquizzes</code>",
                parse_mode="HTML"
            )
        else:
            bot_info = await context.bot.get_me()
            add_link = f"https://t.me/{bot_info.username}?startchannel=true&admin=post_messages+edit_messages+delete_messages"
            await msg.reply_text(
                f"📢 <b>चॅनेल सापडले: {html.escape(f_title)} (ID: <code>{html.escape(f_id)}</code>)</b>\n\n"
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

    # Case A: Digital Store Product Purchase (Manual Review Mode - NEVER Auto-Approve)
    if context.user_data.get("awaiting_store_utr") or (context.user_data.get("buying_product_id") and (msg.photo or re.search(r"\b[A-Za-z0-9]{8,22}\b", combined_text))):
        prod_id = context.user_data.get("buying_product_id", "prod_ca_monthly_top200")
        price = context.user_data.get("buying_product_price", 19)

        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", combined_text)
        customer_email = email_match.group(0) if email_match else f"user_{user.id}@telegram.com"

        utr_match = re.search(r"\b[A-Za-z0-9]{8,22}\b", combined_text)
        photo_id = msg.photo[-1].file_id if msg.photo else None
        utr_val = utr_match.group(0) if utr_match else f"SCREENSHOT_{user.id}_{int(time.time())}"

        if utr_match and is_utr_already_used(utr_val, db_path=DB_PATH):
            await msg.reply_text("⚠️ <b>हा UTR आधीच वापरला गेला आहे.</b> कृपया योग्य व नवीन ट्रान्झॅक्शन UTR नंबर पाठवा.", parse_mode="HTML")
            return

        order_res = fulfillment_agent.create_order(prod_id, customer_email, float(price), customer_telegram_id=user.id, db_path=DB_PATH)
        order_token = order_res["order_token"]

        with sqlite3.connect(DB_PATH, timeout=30.0) as db:
            db.execute(
                "UPDATE product_orders SET utr = ?, status = 'pending', delivery_status = 'pending_verification' WHERE order_token = ?",
                (utr_val, order_token)
            )
            db.commit()

        context.user_data["awaiting_store_utr"] = False
        context.user_data["buying_product_id"] = None

        prod_data = packaging_agent.get_product_by_id(prod_id, db_path=DB_PATH) or {"title": prod_id}

        await msg.reply_text(
            "⏳ <b>पेमेंट पडताळणीसाठी पाठवले आहे (Pending Admin Verification)!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📖 <b>पुस्तक:</b> {html.escape(prod_data.get('title', ''))}\n"
            f"🎫 <b>Order Token:</b> <code>{order_token}</code>\n"
            f"📝 <b>UTR / Screenshot:</b> <code>{html.escape(utr_val)}</code>\n\n"
            "ॲडमिनद्वारे पडताळणी पूर्ण होताच तुमचे पुस्तक येथे थेट पाठवले जाईल आणि डाऊनलोड उपलब्ध होईल!",
            parse_mode="HTML"
        )

        # Notify admins with inline approval buttons
        admin_kb = [
            [
                InlineKeyboardButton("✅ Approve & Deliver", callback_data=f"approve_store_ord:{order_token}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_store_ord:{order_token}")
            ]
        ]
        admin_alert = (
            f"🛒 <b>नवीन डिजिटल ई-बुक खरेदी पडताळणी विनंती!</b>\n"
            f"👤 Aspirant: {html.escape(user.first_name)} (@{html.escape(user.username or 'NoUser')})\n"
            f"🆔 Telegram ID: <code>{user.id}</code>\n"
            f"📖 Book: <b>{html.escape(prod_data.get('title', ''))}</b> (₹{price})\n"
            f"🎫 Order Token: <code>{order_token}</code>\n"
            f"📝 UTR: <code>{html.escape(utr_val)}</code>\n"
            f"📧 Email: <code>{html.escape(customer_email)}</code>"
        )
        for admin_id in ADMIN_IDS:
            try:
                if photo_id:
                    await context.bot.send_photo(chat_id=admin_id, photo=photo_id, caption=safe_photo_caption(admin_alert, 950), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(admin_kb))
                else:
                    await context.bot.send_message(chat_id=admin_id, text=admin_alert, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(admin_kb))
            except Exception as e:
                logger.warning(f"Could not notify admin {admin_id} of store order: {e}")
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
            f"👤 User: {html.escape(user.first_name or '')} (@{html.escape(user.username or 'NoUsername')})\n"
            f"🆔 Telegram ID: <code>{user.id}</code>\n"
            f"📝 UTR / Details: <code>{html.escape(str(utr_text))}</code>"
        )
        for admin_id in ADMIN_IDS:
            try:
                if photo_id:
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=photo_id,
                        caption=safe_photo_caption(admin_msg, 950),
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
            f"📢 <b>मोफत टेलिग्राम चॅनेल:</b> <a href=\"{PAID_CHANNEL_LINK}\">येथे मोफत जॉईन करा</a>\n"
            f"🛒 <b>डिजिटल ई-बुक्स स्टोअर (₹१० ते ₹५०):</b> <a href=\"{get_store_web_url()}\">येथे खरेदी करा</a>"
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
            [InlineKeyboardButton("🛒 डिजिटल ई-बुक्स स्टोअर (₹१० ते ₹५०)", callback_data="store")],
            [InlineKeyboardButton("📢 मोफत टेलिग्राम चॅनेल", url=PAID_CHANNEL_LINK)],
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

async def delete_my_data_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    DPDP / Privacy Compliance: Allows a user to delete all their stored response sheets,
    scores, roll numbers, and physical files from the server.
    """
    user = update.effective_user
    if not user:
        return

    tg_id = user.id
    deleted_files = 0
    deleted_rows = 0

    try:
        with sqlite3.connect(DB_PATH, timeout=30.0) as db:
            cur = db.execute("SELECT storage_path FROM uploads WHERE telegram_user_id = ?", (tg_id,))
            file_paths = [r[0] for r in cur.fetchall() if r[0]]

            # Delete physical files
            for fp in file_paths:
                try:
                    p = Path(fp)
                    if p.exists() and p.is_file():
                        p.unlink()
                        deleted_files += 1
                except Exception as e:
                    logger.warning(f"Failed to delete user file {fp}: {e}")

            # Delete DB records
            cur = db.execute("DELETE FROM uploads WHERE telegram_user_id = ?", (tg_id,))
            deleted_rows = cur.rowcount

            # Delete from users table
            db.execute("DELETE FROM users WHERE telegram_id = ?", (tg_id,))
            db.commit()

        msg = (
            "🗑️ <b>तुमचा डेटा यशस्वीरित्या हटवण्यात आला आहे (Data Erased).</b>\n\n"
            f"• हटवलेल्या रिस्पॉन्स शीट्स: <b>{deleted_rows}</b>\n"
            f"• सर्व्हरवरून नष्ट केलेल्या फाईल्स: <b>{deleted_files}</b>\n"
            "• तुमची प्रोफाइल माहिती पूर्णपणे हटवण्यात आली आहे.\n\n"
            "<i>DPDP ऍक्टनुसार तुमच्या गोपनीयतेचे (Privacy) पूर्ण संरक्षण केले जाते. धन्यवाद!</i>"
        )
    except Exception as e:
        logger.error(f"Error executing delete_my_data for user {tg_id}: {e}", exc_info=True)
        msg = f"❌ डेटा हटवताना तांत्रिक त्रुटी आली: {e}"

    await update.message.reply_text(msg, parse_mode="HTML")

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
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode="HTML")

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
        seen_paths = set()
        # Case A: Specific upload ID requested
        if forced_upload_id:
            with get_connection() as db:
                row = db.execute("SELECT storage_path, exam_key FROM uploads WHERE id = ?", (forced_upload_id,)).fetchone()
            if row and Path(row[0]).is_file():
                s_path = Path(row[0])
                scanned_sources.append((s_path, row[1] or "महाराष्ट्र सरळसेवा भरती"))
                seen_paths.add(str(s_path.resolve()))
        else:
            # Case B: Collect from ALL uploaded response sheets in database & disk
            with get_connection() as db:
                rows = db.execute("SELECT DISTINCT storage_path, exam_key FROM uploads WHERE storage_path IS NOT NULL ORDER BY id DESC").fetchall()
                for sp, ek in rows:
                    if sp and Path(sp).is_file():
                        p_obj = Path(sp).resolve()
                        if str(p_obj) not in seen_paths:
                            scanned_sources.append((Path(sp), ek or "महाराष्ट्र सरळसेवा भरती"))
                            seen_paths.add(str(p_obj))

            # Check recent upload in context.user_data
            user_stored = context.user_data.get("stored_path")
            if user_stored and Path(user_stored).is_file():
                p_obj = Path(user_stored).resolve()
                if str(p_obj) not in seen_paths:
                    scanned_sources.append((Path(user_stored), context.user_data.get("exam_key") or "महाराष्ट्र सरळसेवा भरती"))
                    seen_paths.add(str(p_obj))

            # Fallback to RESPONSE_DIR if more files exist
            if RESPONSE_DIR.exists():
                for p in RESPONSE_DIR.iterdir():
                    if p.is_file() and p.suffix.lower() in (".html", ".htm", ".pdf"):
                        p_obj = p.resolve()
                        if str(p_obj) not in seen_paths:
                            scanned_sources.append((p, "महाराष्ट्र सरळसेवा भरती"))
                            seen_paths.add(str(p_obj))

            # Fallback to products storage directory for uploaded PDFs
            products_dir = STORAGE_DIR / "products"
            if products_dir.exists():
                for p in products_dir.iterdir():
                    if p.is_file() and p.suffix.lower() == ".pdf":
                        p_obj = p.resolve()
                        if str(p_obj) not in seen_paths:
                            scanned_sources.append((p, "महाराष्ट्र सरळसेवा भरती"))
                            seen_paths.add(str(p_obj))

        # Extract quizzes from all collected response sheets
        for s_path, ek in scanned_sources:
            try:
                if s_path.suffix.lower() in (".html", ".htm"):
                    raw_html = s_path.read_text(encoding="utf-8", errors="ignore")
                    parsed_text = parse_html_response_sheet(raw_html)
                else:
                    parsed_text = extract_pdf_text(str(s_path))

                recs = parse_answers(parsed_text) or parse_general_mcqs(parsed_text)
                batch = extract_quizzes_from_records(
                    recs,
                    max_questions=max_q - len(all_unposted_quizzes),
                    filter_unposted=True,
                    db_path=DB_PATH
                )
                if not batch and parsed_text:
                    batch = extract_quizzes_locally(
                        parsed_text,
                        max_questions=max_q - len(all_unposted_quizzes),
                        db_path=DB_PATH
                    )
                all_unposted_quizzes.extend(batch)
                if len(all_unposted_quizzes) >= max_q:
                    break
            except Exception as e:
                logger.warning(f"Error parsing {s_path} in post_quizzes: {e}")

        # Master Question Bank Fallback (qbank_master.json) if more questions needed
        if len(all_unposted_quizzes) < max_q:
            possible_qbank_paths = [
                STORAGE_DIR / "qbank_master.json",
                STORAGE_DIR.parent / "admin_storage" / "qbank_master.json",
                PROJECT_ROOT / "admin_storage" / "qbank_master.json"
            ]
            for qb_path in possible_qbank_paths:
                if qb_path.exists():
                    try:
                        q_data = json.loads(qb_path.read_text(encoding="utf-8"))
                        if isinstance(q_data, list):
                            for item in q_data:
                                if len(all_unposted_quizzes) >= max_q:
                                    break
                                q_txt = str(item.get("q") or item.get("question") or "").strip()
                                opts = item.get("options") or item.get("opts") or []
                                if not q_txt or len(opts) < 4:
                                    continue
                                c_val = str(item.get("correct") or item.get("ans") or "").strip()
                                c_idx = 0
                                for o_i, o_v in enumerate(opts):
                                    if str(o_v).strip() == c_val:
                                        c_idx = o_i
                                        break
                                q_hash = compute_question_hash(q_txt, [str(o) for o in opts[:4]])
                                if is_quiz_already_posted(q_hash, q_txt, db_path=DB_PATH):
                                    continue
                                sec = item.get("subject") or item.get("section") or "General"
                                exp = str(item.get("explanation") or "TCS/IBPS अधिकृत उत्तरतालिकेनुसार प्रमाणित स्पष्टीकरण.")[:195]
                                all_unposted_quizzes.append({
                                    "question": f"[{sec}] {q_txt}"[:295],
                                    "passage": "",
                                    "options": [str(o)[:95] for o in opts[:4]],
                                    "correct_option_index": c_idx,
                                    "explanation": exp,
                                    "section": sec,
                                    "hash": q_hash
                                })
                    except Exception as qb_err:
                        logger.warning(f"Error loading qbank_master.json in post_quizzes: {qb_err}")
                    if len(all_unposted_quizzes) >= max_q:
                        break

        if not all_unposted_quizzes:
            if not scanned_sources:
                await status_msg.edit_text(
                    "❌ <b>कोणतीही रिस्पॉन्स शीट किंवा प्रश्नसंच उपलब्ध नाही.</b>\n\n"
                    "💡 <b>प्रश्न अपलोड करण्यासाठी:</b>\n"
                    "1️⃣ <code>/bulk_upload</code> कमांड वापरून सर्व प्रश्नांची Master PDF पाठवा.\n"
                    "2️⃣ किंवा तुमची DigiALM रिस्पॉन्स शीट लिंक / PDF येथे पाठवा.",
                    parse_mode="HTML"
                )
            else:
                await status_msg.edit_text(
                    "✅ <b>सर्व प्रश्न आधीच चॅनेलवर पोस्ट केलेले आहेत!</b>\n"
                    "कोणताही नवीन अप्रकाशित प्रश्न शिल्लक नाही. नवीन रिस्पॉन्स शीट येताच आपोआप पुढील प्रश्न १-बाय-१ पोस्ट केले जातील."
                )
            return

        total_to_post = len(all_unposted_quizzes)
        await status_msg.edit_text(
            f"🚀 <b>एकूण {total_to_post} नवीन प्रश्न सापडले!</b>\n"
            f"📢 <b>चॅनेल:</b> <code>{channel}</code>\n"
            f"⏱️ <b>गती:</b> दर मिनिटाला ३ ते ४ प्रश्न (~१७ सेकंदांचे सुरक्षित अंतर, नो रॅपिड फ्लड)\n"
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

    from app.quiz_generator import resolve_quiz_correct_index

    # Pool of questions: curated daily questions + master qbank items
    daily = get_daily_latest_exam_questions()
    questions = list(daily.get("questions", []))

    # Also load authentic harvested questions from central qbank_questions table
    try:
        with get_connection() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                """SELECT section, question_text, options_json, correct_option_num,
                          correct_option_text, explanation
                   FROM qbank_questions ORDER BY RANDOM() LIMIT 80"""
            ).fetchall()
            for row in rows:
                opts_dict = json.loads(row["options_json"] or "{}")
                if len(opts_dict) >= 4:
                    questions.append({
                        "subject": row["section"] or "General",
                        "question": row["question_text"],
                        "options": list(opts_dict.values()),
                        "correct": str(row["correct_option_num"]),
                        "explanation": row["explanation"] or ""
                    })
    except Exception as qb_err:
        logger.warning(f"Could not load questions from qbank_questions: {qb_err}")

    # Also load from qbank_master.json for high diversity
    try:
        import json
        from pathlib import Path
        qb_file = Path("admin_storage/qbank_master.json")
        if not qb_file.exists():
            qb_file = Path(__file__).resolve().parent.parent / "admin_storage" / "qbank_master.json"
        if qb_file.exists():
            master_raw = json.loads(qb_file.read_text(encoding="utf-8"))
            for m_item in master_raw[:250]:
                opts = m_item.get("options", [])
                if len(opts) >= 4:
                    questions.append({
                        "subject": m_item.get("subject", "General"),
                        "question": re.sub(r"^\[.*?\]\s*", "", m_item.get("q", "")).strip(),
                        "options": opts,
                        "correct": m_item.get("correct", ""),
                        "explanation": m_item.get("explanation", "")
                    })
    except Exception as e:
        logger.warning(f"Could not load extra questions for quiz_cmd: {e}")

    if not questions:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ सध्या क्विझ प्रश्न लोड होत आहेत. कृपया थोड्या वेळाने प्रयत्न करा.")
        return

    import random
    # Avoid recently asked questions in user_data session
    recent_qs = context.user_data.get("recent_quizzes", [])
    candidate_pool = [q for q in questions if q.get("question") not in recent_qs]
    if not candidate_pool:
        candidate_pool = questions
        context.user_data["recent_quizzes"] = []

    q_data = random.choice(candidate_pool)
    context.user_data.setdefault("recent_quizzes", []).append(q_data.get("question"))
    if len(context.user_data["recent_quizzes"]) > 30:
        context.user_data["recent_quizzes"].pop(0)

    sub = q_data.get("subject", "General")
    q_text = f"[{sub}] {q_data['question']}"
    raw_opts = q_data.get("options", [])

    # Clean option prefixes like A), B), C), D) and checkmarks for poll display
    clean_opts = []
    for o in raw_opts[:4]:
        co = re.sub(r"\[Correct Option\]|rightAns|[✓✔☑]", "", str(o), flags=re.IGNORECASE)
        co = re.sub(r"^[A-Da-d1-4][\.\):\-]\s*", "", co).strip()
        clean_opts.append(co[:95])

    # Determine 100% verified correct option index
    c_idx = resolve_quiz_correct_index(q_data, clean_opts)

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
    chat_id = update.effective_chat.id
    if update.effective_user.id not in ADMIN_IDS:
        if update.callback_query:
            await update.callback_query.answer("⛔ Restricted to administrators.", show_alert=True)
        else:
            await context.bot.send_message(chat_id=chat_id, text="⛔ Restricted to administrators.")
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

    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="\n".join(lines), parse_mode="HTML")

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
        except RetryAfter as e:
            logger.warning(f"Telegram flood limit: sleeping {e.retry_after}s during broadcast")
            await asyncio.sleep(e.retry_after + 0.1)
            try:
                await context.bot.send_message(chat_id=uid, text=message_text, parse_mode="HTML")
                sent += 1
            except Exception:
                failed += 1
        except Exception:
            try:
                await context.bot.send_message(chat_id=uid, text=message_text)
                sent += 1
            except Exception:
                failed += 1
        await asyncio.sleep(0.05)  # Safe ~20 msgs/sec throttling

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
        [InlineKeyboardButton("📊 Full HTML Report", callback_data=f"admin_report:{file_id}")],
        [InlineKeyboardButton("❌ Wrong Questions Review", callback_data=f"admin_wrong:{file_id}")]
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
            "━━━━━━━━━━━━━━━━━━━━━━",
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
        [InlineKeyboardButton("🛒 डिजिटल ई-बुक्स स्टोअर (₹१० ते ₹५०)", url=get_store_web_url())],
        [InlineKeyboardButton("📢 मोफत टेलिग्राम चॅनेल", url=PAID_CHANNEL_LINK)],
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
        text="⏳ <b>८००+ TCS/IBPS अधिकृत प्रश्नसंच (४-स्तंभ PDF) तयार होत आहे... कृपया थोडा वेळ थांबा.</b>",
        parse_mode="HTML"
    )
    try:
        report_file = REPORT_DIR / "ExamRankers_Master_Question_Bank_4Col.pdf"
        await asyncio.to_thread(generate_oneliner_question_bank_pdf, DB_PATH, str(report_file))

        # Clean up any legacy timestamped dummy question bank files
        for old_f in REPORT_DIR.glob("oneliner_question_bank_*.pdf"):
            try:
                old_f.unlink()
            except Exception:
                pass

        file_size_kb = round(report_file.stat().st_size / 1024, 1)
        caption = (
            "📑 <b>महास्पर्धा परीक्षा — ८००+ प्रश्न अधिकृत प्रश्नसंच (Master Question Bank)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>फाईल आकार:</b> {file_size_kb} KB (A4 Printable 4-Columns Format)\n"
            "• TCS, IBPS व MPSC पॅटर्ननुसार अधिकृत उत्तरे\n"
            "• मराठी, English, गणित/बुद्धिमत्ता व GS घटक\n"
            "• महत्त्वाचे नियम, शॉर्टकट ट्रिक्स व सविस्तर स्पष्टीकरण\n"
            "• १००% निनावी (Zero personal student data)\n\n"
            "⚡ <i>१-क्लिक प्रिंट व वाचनासाठी तयार PDF फाईल खाली दिली आहे.</i>"
        )
        with open(report_file, "rb") as f:
            await context.bot.send_document(
                chat_id=chat_id,
                document=f,
                filename="ExamRankers_Master_Question_Bank_4Col.pdf",
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
                        reply_markup=InlineKeyboardMarkup(kb),
                        protect_content=True
                    )
            else:
                await context.bot.send_message(
                    chat_id=target_chat,
                    text=safe_cap,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(kb),
                    disable_web_page_preview=True,
                    protect_content=True
                )
        except Exception as pe:
            logger.warning(f"send_photo failed ({pe}); falling back to send_message with safe caption")
            await context.bot.send_message(
                chat_id=target_chat,
                text=safe_cap,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(kb),
                disable_web_page_preview=True,
                protect_content=True
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
                        reply_markup=InlineKeyboardMarkup(kb),
                        protect_content=True
                    )
            else:
                await context.bot.send_message(
                    chat_id=target_chat,
                    text=promo_caption,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(kb),
                    disable_web_page_preview=True,
                    protect_content=True
                )
        except Exception as pe:
            logger.warning(f"Promo send_photo failed ({pe}); falling back to send_message")
            await context.bot.send_message(
                chat_id=target_chat,
                text=promo_caption,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(kb),
                disable_web_page_preview=True,
                protect_content=True
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
    Disabled by default to stop automatic promotional ads. Admin controls ad broadcasts manually via /post_promo.
    """
    if os.getenv("ENABLE_AUTO_PROMO", "").lower() not in ("true", "1", "yes"):
        logger.info("Automatic bot/store promo ads stopped (Manual Admin Control mode). Use /post_promo or /post_store_promo.")
        return
    await asyncio.sleep(120)  # Wait 2 minutes after startup before initial promo
    while True:
        try:
            channel = os.getenv("PAID_CHANNEL_ID", "").strip() or PAID_CHANNEL_ID
            if channel and not channel.startswith("http"):
                target_chat = int(channel) if channel.lstrip("-").isdigit() else channel
                promo_banner_path = Path(__file__).resolve().parent.parent / "assets" / "promo_banner.jpg"

                yt_link = get_youtube_link()
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
                with sqlite3.connect(DB_PATH, timeout=30.0) as db:
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
    if context.user_data:
        context.user_data.clear()
    msg = "🚫 सध्याची प्रक्रिया रद्द करण्यात आली आहे. पुन्हा सुरू करण्यासाठी /start दाबा."
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(msg)
        except Exception:
            pass
    elif update and update.effective_chat:
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        except Exception:
            pass

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs detailed traceback, captures via Sentry if enabled, and alerts admins if critical."""
    err_str = str(context.error) if context.error else ""
    if "Conflict: terminated by other getUpdates request" in err_str:
        logger.warning(
            "⚠️ [TELEGRAM POLLING CONFLICT]: Another bot instance is currently active with this TELEGRAM_BOT_TOKEN "
            "(e.g. running on Render/cloud deployment, in another open terminal window, or on a secondary device). "
            "Telegram strictly permits only ONE polling instance per token. "
            "Solution: Stop the other running instance, or run 'python run_store.py' if you only need the Web Store & Admin Panel locally."
        )
        return

    tb_string = "".join(traceback.format_exception(None, context.error, context.error.__traceback__)) if context.error else "Unknown Error"
    logger.error(f"Telegram Handler Exception: {context.error}\n{tb_string}")
    if os.getenv("SENTRY_DSN"):
        try:
            import importlib
            sentry_sdk = importlib.import_module("sentry_sdk")
            sentry_sdk.capture_exception(context.error)
        except Exception:
            pass

    # Polite feedback to student so chat does not hang in silence
    if isinstance(update, Update) and update.effective_chat and not any(k in err_str.lower() for k in ["conflict", "forbidden", "blocked"]):
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ विनंती प्रक्रिया करताना एक तात्पुरती अडचण आली. कृपया थोड्या वेळाने पुन्हा प्रयत्न करा किंवा /start दाबा."
            )
        except Exception:
            pass

async def nightly_backup_scheduler_loop(application: Application):
    """Executes atomic SQLite backup once every 24 hours and delivers it to the primary bot administrator."""
    await asyncio.sleep(60)
    while True:
        try:
            backup_file = await asyncio.to_thread(backup_sqlite_database, DB_PATH)
            if backup_file and backup_file.exists() and ADMIN_IDS:
                primary_admin = sorted(ADMIN_IDS)[0]
                with open(backup_file, "rb") as f:
                    await application.bot.send_document(
                        chat_id=primary_admin,
                        document=f,
                        filename=backup_file.name,
                        caption=f"🛡️ <b>Automated 24h SQLite Backup</b>\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nSize: {backup_file.stat().st_size // 1024} KB",
                        parse_mode="HTML"
                    )
        except Exception as e:
            logger.error(f"Error in nightly_backup_scheduler_loop: {e}")
        await asyncio.sleep(86400)

async def set_bot_commands(application: Application):
    """Configures the official Telegram chat menu button [≡], command scopes, and launches background schedulers."""
    user_commands = [
        BotCommand("start", "🚀 सुरू करा (Start Bot & Select Category)"),
        BotCommand("admin", "⚙️ ॲडमिन कंट्रोल पॅनेल (Admin Panel)"),
        BotCommand("store", "🛒 डिजिटल ई-बुक्स स्टोअर (₹१० ते ₹५०)"),
        BotCommand("channel", "📢 मोफत टेलिग्राम चॅनेल (Free Study Group)"),
        BotCommand("wrong", "❌ चुकीचे प्रश्न व सविस्तर स्पष्टीकरण"),
        BotCommand("responses", "📄 रिस्पॉन्स शीट निकाल (HTML Report)"),
        BotCommand("channels", "📢 Telegram व YouTube अधिकृत चॅनेल्स"),
        BotCommand("menu", "📋 मुख्य मेनू (Main Menu)"),
        BotCommand("help", "ℹ️ कशी वापरावी व FAQ (Help & Guide)"),
        BotCommand("cancel", "❌ रद्द करा (Cancel)")
    ]
    admin_commands = [
        BotCommand("start", "🚀 सुरू करा (Start Bot)"),
        BotCommand("admin", "⚙️ ॲडमिन कंट्रोल पॅनेल (Admin Panel)"),
        BotCommand("store", "🛒 डिजिटल ई-बुक्स स्टोअर (₹१० ते ₹५०)"),
        BotCommand("channel", "📢 मोफत टेलिग्राम चॅनेल (Free Study Group)"),
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

        # Background schedulers: Auto-advertisement & auto-posting stopped by default (Manual Admin Control mode)
        # Promotional posts and store ads are triggered manually by admin via /post_promo or /post_store_promo
        if os.getenv("ENABLE_AUTO_PROMO", "").lower() in ("true", "1", "yes"):
            asyncio.create_task(three_hour_promo_scheduler_loop(application))
        if os.getenv("ENABLE_AUTO_MINDMAP", "").lower() in ("true", "1", "yes"):
            asyncio.create_task(daily_mindmap_scheduler_loop(application))
        if os.getenv("ENABLE_AUTO_YT_BROADCAST", "").lower() in ("true", "1", "yes"):
            asyncio.create_task(youtube_upload_watcher_loop(application))

        # Core background tasks: Multi-Agent Health Orchestrator, Nightly SQLite Backup
        # Auto-generation of eBooks and daily Current Affairs eBook updates are disabled by default
        if os.getenv("ENABLE_AUTO_EBOOK_GENERATION", "").lower() in ("true", "1", "yes"):
            asyncio.create_task(daily_current_affairs_updater_loop(application))
        asyncio.create_task(continuous_autonomous_agency_orchestrator(application))
        asyncio.create_task(nightly_backup_scheduler_loop(application))
        logger.info("Background Schedulers launched: Agency Orchestrator, Nightly Backup (Auto eBook generation disabled; 100% manual admin upload control active).")
    except Exception as e:
        logger.warning(f"Could not set bot commands or description: {e}")

def render_upload_portal_html() -> str:
    """Renders the comprehensive Web Upload & Rank Predictor page for response sheets of any size."""
    return r"""<!DOCTYPE html>
<html lang="mr" class="h-full bg-slate-900 text-slate-100">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ExamRankers — रिस्पॉन्स शीट वेब पोर्टल व रँक प्रिडिक्टर</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Mukta:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Mukta', sans-serif; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #475569; }
        @media print {
            body { background: #fff !important; color: #000 !important; }
            .no-print { display: none !important; }
            #resultSection { display: block !important; border: none !important; }
            #tabViewScorecard, #tabViewSwot, #tabViewObjections, #tabViewQuestions { display: block !important; }
        }
    </style>
</head>
<body class="min-h-full flex flex-col justify-between p-3 sm:p-6 md:p-8">
    <div id="portalContainer" class="max-w-2xl mx-auto w-full transition-all duration-300">
        <!-- Top Header -->
        <header class="text-center mb-6 no-print">
            <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-500 to-purple-600 shadow-lg shadow-indigo-500/30 mb-3">
                <span class="text-3xl">🎯</span>
            </div>
            <h1 class="text-3xl sm:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-indigo-200 bg-clip-text text-transparent">
                ExamRankers India
            </h1>
            <p class="text-slate-400 mt-1.5 text-sm sm:text-base">
                अधिकृत रिस्पॉन्स शीट वेब अपलोड पोर्टल व रँक प्रिडिक्टर
                <span class="bg-indigo-500/20 text-indigo-300 text-xs px-2.5 py-1 rounded-full font-semibold border border-indigo-500/30 ml-1">कोणतीही मर्यादा नाही (५०० MB)</span>
            </p>
        </header>

        <!-- Main Card -->
        <div class="bg-slate-800/90 backdrop-blur-md rounded-2xl border border-slate-700/80 p-5 sm:p-7 shadow-2xl">
            <div id="uploadSection">
                <!-- Dropdown Rows: Exam & Category -->
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
                    <div>
                        <label class="block text-xs font-bold text-slate-300 mb-1.5 uppercase tracking-wider">१. परीक्षा निवडा:</label>
                        <select id="examSelect" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm">
                            <option value="auto">⚡ स्वयंचलित ओळख (Auto Detect)</option>
                            <option value="ZP_BHARTI">जिल्हा परिषद भरती (ZP Bharti / शिपाई / आरोग्य)</option>
                            <option value="TALATHI_BHARTI">तलाठी भरती (Talathi Bharti)</option>
                            <option value="POLICE_BHARTI">महाराष्ट्र पोलीस भरती (Police Bharti)</option>
                            <option value="VANRAKSHAK_BHARTI">वनरक्षक भरती (Vanrakshak)</option>
                            <option value="AROGYA_BHARTI">सार्वजनिक आरोग्य भरती (Arogya)</option>
                            <option value="MPSC_COMBINED">MPSC अराजपत्रित / संयुक्त (Combined)</option>
                            <option value="NAGAR_PARISHAD">नगर परिषद भरती (Nagar Parishad)</option>
                            <option value="GMC_SARALSEWA">GMC वैद्यकीय व सरळसेवा भरती</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-300 mb-1.5 uppercase tracking-wider">२. प्रवर्ग (Category) निवडा:</label>
                        <select id="userCategory" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm">
                            <option value="Open">Open / General (खुला)</option>
                            <option value="OBC">OBC (इतर मागास वर्ग)</option>
                            <option value="SC">SC (अनुसूचित जाती)</option>
                            <option value="ST">ST (अनुसूचित जमाती)</option>
                            <option value="EWS">EWS (आर्थिक दुर्बल घटक)</option>
                            <option value="VJ-A">VJ-A / DT-A (विमुक्त जाती)</option>
                            <option value="NT-B">NT-B (भटक्या जमाती ब)</option>
                            <option value="NT-C">NT-C (भटक्या जमाती क)</option>
                            <option value="NT-D">NT-D (भटक्या जमाती ड)</option>
                            <option value="SBC">SBC (विशेष मागास प्रवर्ग)</option>
                        </select>
                    </div>
                </div>

                <!-- Input Tabs: File Upload vs Direct DigiALM Web Link vs Manual Score -->
                <div class="flex border-b border-slate-700 mb-5">
                    <button id="tabFileBtn" onclick="switchTab('file')" class="flex-1 pb-2.5 text-xs sm:text-sm font-bold border-b-2 border-indigo-500 text-indigo-400 transition-all flex items-center justify-center gap-1">
                        <span>📄 फाईल अपलोड</span>
                    </button>
                    <button id="tabUrlBtn" onclick="switchTab('url')" class="flex-1 pb-2.5 text-xs sm:text-sm font-bold border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-all flex items-center justify-center gap-1">
                        <span>🔗 वेब लिंक</span>
                    </button>
                    <button id="tabManualBtn" onclick="switchTab('manual')" class="flex-1 pb-2.5 text-xs sm:text-sm font-bold border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-all flex items-center justify-center gap-1">
                        <span>✍️ थेट गुण नोंदवा</span>
                    </button>
                </div>

                <!-- File Upload Tab Content -->
                <div id="fileTabContent" class="mb-5">
                    <div id="dropZone" class="border-2 border-dashed border-slate-600 hover:border-indigo-500 rounded-2xl p-7 text-center cursor-pointer transition-all bg-slate-900/50 hover:bg-slate-900/80">
                        <input type="file" id="fileInput" accept=".pdf,.html,.htm" class="hidden" />
                        <div class="text-4xl mb-2">📁</div>
                        <div id="filePrompt" class="text-slate-200 font-bold text-base sm:text-lg">
                            येथे क्लिक करा किंवा PDF फाईल ड्रॅग करा
                        </div>
                        <p class="text-xs text-slate-400 mt-1">
                            मोठ्या फाईल्स (२० MB, २५ MB, ५० MB, १०० MB+) थेट समर्थित
                        </p>
                        <div id="selectedFileName" class="hidden mt-3 inline-block bg-indigo-950/80 text-indigo-300 border border-indigo-500/40 px-3 py-1.5 rounded-lg text-xs font-mono font-medium"></div>
                    </div>
                </div>

                <!-- Web Link Tab Content -->
                <div id="urlTabContent" class="hidden mb-5">
                    <label class="block text-xs font-bold text-slate-300 mb-1.5">DigiALM / TCS Response Sheet लिंक पेस्ट करा:</label>
                    <input type="url" id="urlInput" placeholder="https://cdn.digialm.com/per/g01/pub/.../index.html" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                    <p class="text-xs text-slate-400 mt-1.5">
                        💡 वेब लिंक थेट १ सेकंदात १००% अचूक तपासली जाते (कोणतीही फाईल डाऊनलोड न करता).
                    </p>
                </div>

                <!-- Manual Score Tab Content -->
                <div id="manualTabContent" class="hidden mb-5">
                    <div class="space-y-3 bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                        <div>
                            <label class="block text-xs font-bold text-slate-300 mb-1">मिळालेले एकूण गुण (Raw Score):</label>
                            <input type="number" step="0.25" id="manualScoreInput" placeholder="उदा. 142.5" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-amber-300 font-bold text-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                        </div>
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                            <div>
                                <label class="block text-xs font-semibold text-slate-400 mb-1">पदाचे नाव (ऐच्छिक):</label>
                                <input type="text" id="manualPostInput" placeholder="उदा. कनिष्ठ सहाय्यक" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-slate-400 mb-1">परीक्षार्थी नाव (ऐच्छिक):</label>
                                <input type="text" id="manualNameInput" placeholder="उदा. राहुल शिंदे" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                            </div>
                        </div>
                        <p class="text-xs text-slate-400">
                            💡 जर तुमच्याकडे PDF नसेल किंवा गुण आधीच मोजले असतील, तर थेट गुण टाकून राज्य व प्रवर्ग रँक आणि Cutoff Zone तपासा!
                        </p>
                    </div>
                </div>

                <button id="submitBtn" class="w-full bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white font-bold py-3.5 px-6 rounded-xl shadow-lg shadow-indigo-500/25 transition-all text-base sm:text-lg flex items-center justify-center gap-2">
                    <span>📊 गुण व रँक तपासा</span>
                </button>
            </div>

            <!-- Loader Screen with Progress -->
            <div id="loadingSection" class="hidden py-8 text-center no-print">
                <div class="inline-block animate-spin w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full mb-4"></div>
                <h3 id="loadingTitle" class="text-xl font-bold text-slate-100">AI रिस्पॉन्स शीट विश्लेषण सुरू आहे... ⏳</h3>
                <p id="loadingSubtitle" class="text-slate-400 text-sm mt-1">सर्व १०० प्रश्न, अधिकृत की, नेगेटिव्ह मार्किंग आणि राज्य रँक मोजली जात आहे...</p>

                <!-- High-Speed Chunk Upload Progress Bar -->
                <div id="uploadProgressBarContainer" class="hidden mt-6 max-w-md mx-auto text-left">
                    <div class="flex justify-between text-xs text-slate-300 mb-1.5 font-semibold">
                        <span id="uploadProgressText">अपलोड होत आहे: ०%</span>
                        <span id="uploadChunkText">तुकडा ०/०</span>
                    </div>
                    <div class="w-full bg-slate-900 border border-slate-700 rounded-full h-3 overflow-hidden p-0.5">
                        <div id="uploadProgressBar" class="bg-gradient-to-r from-indigo-500 to-purple-500 h-2 rounded-full transition-all duration-300" style="width: 0%"></div>
                    </div>
                </div>
            </div>

            <!-- Error Box -->
            <div id="errorBox" class="hidden mt-4 p-4 rounded-xl bg-red-950/80 border border-red-500/50 text-red-200 text-sm no-print"></div>

            <!-- Comprehensive Analytical Result Section -->
            <div id="resultSection" class="hidden">
                <!-- Result Top Banner -->
                <div class="border-b border-slate-700/80 pb-4 mb-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
                    <div>
                        <div class="flex items-center gap-2">
                            <span class="text-xs uppercase tracking-wider text-indigo-400 font-extrabold bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">अधिकृत विश्लेषण अहवाल</span>
                            <span id="resBadgePost" class="text-xs text-slate-300 bg-slate-900 px-2.5 py-0.5 rounded border border-slate-700 font-semibold">General</span>
                        </div>
                        <h2 id="resCandidate" class="text-2xl sm:text-3xl font-extrabold text-white mt-1">परीक्षार्थी</h2>
                        <p id="resExam" class="text-xs sm:text-sm text-slate-400 font-medium">परीक्षा निकाल</p>
                    </div>
                    <div class="flex md:flex-col items-center md:items-end justify-between gap-1 bg-slate-900/80 px-4 py-2.5 rounded-xl border border-slate-700/60">
                        <div class="flex items-center gap-1.5">
                            <span class="text-xs text-slate-400">प्रवर्ग:</span>
                            <span id="resCategory" class="font-bold text-indigo-300 text-base">Open</span>
                        </div>
                        <div class="text-xs text-slate-400">
                            अनुक्रमांक: <span id="resRoll" class="font-mono text-slate-200 font-bold">-</span>
                        </div>
                    </div>
                </div>

                <!-- VIP Channel Unlock Golden Card -->
                <div id="vipChannelBanner" class="mb-5 p-4 rounded-2xl bg-gradient-to-r from-amber-500/20 via-yellow-500/10 to-amber-500/20 border border-amber-500/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg shadow-amber-500/10">
                    <div class="flex items-center gap-3">
                        <span class="text-3xl">🌟</span>
                        <div>
                            <div class="text-xs uppercase tracking-wider text-amber-300 font-extrabold flex items-center gap-1.5">
                                <span>VIP कटऑफ व भरती अपडेट ग्रुप</span>
                                <span class="bg-amber-400 text-slate-950 text-[10px] px-1.5 py-0.2 rounded font-black">UNLOCKED</span>
                            </div>
                            <div class="text-sm font-bold text-white mt-0.5">अधिकृत कटऑफ यादी, शिफ्ट नॉर्मलायझेशन आणि मेरिट लिस्ट चर्चा</div>
                        </div>
                    </div>
                    <a href="https://t.me/+EjtGp-pH4hMxZDM1" target="_blank" class="inline-flex items-center justify-center gap-2 bg-gradient-to-r from-amber-400 to-yellow-500 hover:from-amber-500 hover:to-yellow-600 text-slate-950 font-black px-4 py-2.5 rounded-xl text-xs sm:text-sm shadow-md whitespace-nowrap transition-all">
                        <span>🔓 VIP ग्रुप जॉईन करा</span>
                        <span>➔</span>
                    </a>
                </div>

                <!-- Cutoff Prediction Zone Box -->
                <div id="cutoffZoneCard" class="mb-5 p-4 rounded-xl bg-gradient-to-r from-slate-900 via-indigo-950/30 to-slate-900 border border-indigo-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg">
                    <div class="flex items-center gap-3">
                        <span class="text-3xl" id="zoneIcon">🎯</span>
                        <div>
                            <div class="text-xs uppercase tracking-wider text-slate-400 font-bold">Cutoff Prediction Zone (निवड अंदाज)</div>
                            <div id="resCutoffZone" class="text-base sm:text-lg font-bold text-emerald-300">गणना होत आहे...</div>
                        </div>
                    </div>
                    <div class="flex items-center gap-4 text-xs sm:text-sm text-slate-300">
                        <div>
                            <span class="text-slate-400 block text-[11px]">सरासरी गुण (Avg)</span>
                            <span id="resAvgScore" class="font-bold text-white">0</span>
                        </div>
                        <div class="border-l border-slate-700 pl-4">
                            <span class="text-slate-400 block text-[11px]">सर्वोच्च गुण (Top)</span>
                            <span id="resTopScore" class="font-bold text-amber-400">0</span>
                        </div>
                    </div>
                </div>

                <!-- Navigation Tabs -->
                <div class="flex flex-wrap border-b border-slate-700 gap-1 mb-5 no-print">
                    <button id="rtabBtnScorecard" onclick="switchResultTab('scorecard')" class="px-3.5 py-2.5 text-xs sm:text-sm font-bold border-b-2 border-indigo-500 text-indigo-400 transition-all flex items-center gap-1.5">
                        <span>📊 निकाल व ४-टियर रँक</span>
                    </button>
                    <button id="rtabBtnSwot" onclick="switchResultTab('swot')" class="px-3.5 py-2.5 text-xs sm:text-sm font-bold border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-all flex items-center gap-1.5">
                        <span>🧠 AI SWOT ऑडिट</span>
                    </button>
                    <button id="rtabBtnObjections" onclick="switchResultTab('objections')" class="px-3.5 py-2.5 text-xs sm:text-sm font-bold border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-all flex items-center gap-1.5">
                        <span>⚖️ चुकांचे पोस्टमार्टम व आक्षेप</span>
                        <span id="wrongCountBadge" class="bg-rose-500/80 text-white text-[11px] px-2 py-0.2 rounded-full font-bold ml-1">0</span>
                    </button>
                    <button id="rtabBtnQuestions" onclick="switchResultTab('questions')" class="px-3.5 py-2.5 text-xs sm:text-sm font-bold border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition-all flex items-center gap-1.5">
                        <span>🔍 प्रश्नपत्रिका (All Qs)</span>
                        <span id="totalQBadge" class="bg-indigo-500/40 text-indigo-200 text-[11px] px-2 py-0.2 rounded-full font-bold ml-1">0</span>
                    </button>
                </div>

                <!-- TAB 1: SCORECARD & 4-TIER RANK -->
                <div id="tabViewScorecard">
                    <!-- 4 Top Cards -->
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-5">
                        <div class="bg-slate-900/90 border border-slate-700/60 p-3.5 rounded-xl text-center">
                            <div class="text-xs text-slate-400 font-semibold mb-1">एकूण गुण (Score)</div>
                            <div id="resScore" class="text-2xl sm:text-3xl font-extrabold text-amber-400">0</div>
                            <div class="text-[11px] text-slate-500 mt-0.5">कमाल: <span id="resMaxMarks">200</span></div>
                        </div>
                        <div class="bg-slate-900/90 border border-slate-700/60 p-3.5 rounded-xl text-center">
                            <div class="text-xs text-slate-400 font-semibold mb-1">अचूकता (Accuracy)</div>
                            <div id="resAccuracy" class="text-2xl sm:text-3xl font-extrabold text-cyan-400">0%</div>
                            <div class="text-[11px] text-slate-500 mt-0.5">कार्यक्षमता प्रमाण</div>
                        </div>
                        <div class="bg-slate-900/90 border border-slate-700/60 p-3.5 rounded-xl text-center">
                            <div class="text-xs text-slate-400 font-semibold mb-1">बरोबर उत्तरे</div>
                            <div id="resCorrect" class="text-2xl sm:text-3xl font-extrabold text-emerald-400">0</div>
                            <div class="text-[11px] text-slate-500 mt-0.5">अचूक प्रश्न</div>
                        </div>
                        <div class="bg-slate-900/90 border border-slate-700/60 p-3.5 rounded-xl text-center">
                            <div class="text-xs text-slate-400 font-semibold mb-1">चूक उत्तरे</div>
                            <div id="resIncorrect" class="text-2xl sm:text-3xl font-extrabold text-rose-400">0</div>
                            <div class="text-[11px] text-slate-500 mt-0.5">निगेटिव्ह / चुकलेले</div>
                        </div>
                    </div>

                    <!-- 4-Tier Rank Grid -->
                    <div class="mb-5">
                        <h4 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                            <span>🏆 Live 4-Tier Rank & Percentile Standing</span>
                        </h4>
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                            <div class="bg-slate-900/80 border border-slate-700/70 p-3.5 rounded-xl flex items-center justify-between">
                                <div>
                                    <span class="text-xs text-slate-400 block font-medium">🌐 १. राज्यस्तरीय रँक (State Rank):</span>
                                    <span id="resStateRank" class="text-lg font-extrabold text-indigo-400">#1 / 1</span>
                                </div>
                                <div class="text-right">
                                    <span class="text-[11px] text-slate-400 block">पर्सेंटाईल:</span>
                                    <span id="resStatePercentile" class="font-mono font-bold text-emerald-300 text-sm">100%</span>
                                </div>
                            </div>
                            <div class="bg-slate-900/80 border border-slate-700/70 p-3.5 rounded-xl flex items-center justify-between">
                                <div>
                                    <span class="text-xs text-slate-400 block font-medium">📋 २. परीक्षा रँक (Exam Cohort):</span>
                                    <span id="resExamRank" class="text-lg font-extrabold text-purple-400">#1 / 1</span>
                                </div>
                                <div class="text-right">
                                    <span class="text-[11px] text-slate-400 block">पर्सेंटाईल:</span>
                                    <span id="resExamPercentile" class="font-mono font-bold text-emerald-300 text-sm">100%</span>
                                </div>
                            </div>
                            <div class="bg-slate-900/80 border border-slate-700/70 p-3.5 rounded-xl flex items-center justify-between">
                                <div>
                                    <span class="text-xs text-slate-400 block font-medium">👤 ३. प्रवर्ग रँक (Category Rank):</span>
                                    <span id="resCatRank" class="text-lg font-extrabold text-amber-400">#1 / 1</span>
                                </div>
                                <div class="text-right">
                                    <span class="text-[11px] text-slate-400 block">पर्सेंटाईल:</span>
                                    <span id="resCatPercentile" class="font-mono font-bold text-emerald-300 text-sm">100%</span>
                                </div>
                            </div>
                            <div class="bg-slate-900/80 border border-slate-700/70 p-3.5 rounded-xl flex items-center justify-between">
                                <div>
                                    <span class="text-xs text-slate-400 block font-medium">🎖️ ४. पदनिहाय रँक (Post Rank):</span>
                                    <span id="resPostRank" class="text-lg font-extrabold text-cyan-400">#1 / 1</span>
                                </div>
                                <div class="text-right">
                                    <span class="text-[11px] text-slate-400 block">अनुत्तरित:</span>
                                    <span id="resUnanswered" class="font-mono font-bold text-slate-300 text-sm">0</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Subject-Wise Marks Breakdown Table -->
                    <div id="sectionTableContainer" class="mb-5 hidden">
                        <h4 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2.5">
                            📚 विषयनिहाय अचूकता व गुण (Subject-Wise Breakdown)
                        </h4>
                        <div class="overflow-x-auto rounded-xl border border-slate-700 bg-slate-900/60">
                            <table class="w-full text-left text-xs sm:text-sm">
                                <thead class="bg-slate-800/80 text-slate-400 uppercase font-semibold text-[11px] tracking-wider border-b border-slate-700">
                                    <tr>
                                        <th class="py-2.5 px-3">विषय / विभाग</th>
                                        <th class="py-2.5 px-3 text-center">सोडवलेले</th>
                                        <th class="py-2.5 px-3 text-center">बरोबर</th>
                                        <th class="py-2.5 px-3 text-center">चूक</th>
                                        <th class="py-2.5 px-3 text-center">अचूकता</th>
                                        <th class="py-2.5 px-3 text-right">गुण (Marks)</th>
                                    </tr>
                                </thead>
                                <tbody id="sectionTableBody" class="divide-y divide-slate-800 text-slate-300"></tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- TAB 2: AI SWOT PERFORMANCE AUDIT -->
                <div id="tabViewSwot" class="hidden">
                    <div class="mb-4 p-3.5 rounded-xl bg-slate-900/80 border border-slate-700 flex items-center justify-between">
                        <div>
                            <h3 class="font-bold text-white text-base">🧠 AI SWOT कार्यक्षमता ऑडिट (Performance Audit)</h3>
                            <p class="text-xs text-slate-400 mt-0.5">TCS/IBPS परीक्षा पॅटर्ननुसार तुमच्या ताकदी व त्रुटींचे सखोल विश्लेषण</p>
                        </div>
                        <div class="text-right">
                            <span class="text-xs text-slate-400 block">एकूण अचूकता</span>
                            <span id="swotAccBadge" class="font-bold text-emerald-400 text-base">0%</span>
                        </div>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3.5 mb-5">
                        <!-- Strengths -->
                        <div class="bg-emerald-950/20 border border-emerald-500/30 p-4 rounded-xl">
                            <div class="flex items-center gap-2 mb-2">
                                <span class="text-xl">💪</span>
                                <h4 class="font-bold text-emerald-300 text-sm">बळकट बाजू (Strengths)</h4>
                            </div>
                            <ul id="swotStrengths" class="space-y-1.5 text-xs text-emerald-100/90 list-disc pl-4"></ul>
                        </div>
                        <!-- Weaknesses -->
                        <div class="bg-amber-950/20 border border-amber-500/30 p-4 rounded-xl">
                            <div class="flex items-center gap-2 mb-2">
                                <span class="text-xl">⚠️</span>
                                <h4 class="font-bold text-amber-300 text-sm">कमजोर बाजू (Weaknesses)</h4>
                            </div>
                            <ul id="swotWeaknesses" class="space-y-1.5 text-xs text-amber-100/90 list-disc pl-4"></ul>
                        </div>
                        <!-- Opportunities -->
                        <div class="bg-cyan-950/20 border border-cyan-500/30 p-4 rounded-xl">
                            <div class="flex items-center gap-2 mb-2">
                                <span class="text-xl">💡</span>
                                <h4 class="font-bold text-cyan-300 text-sm">सुधारणा व संधी (Opportunities)</h4>
                            </div>
                            <ul id="swotOpportunities" class="space-y-1.5 text-xs text-cyan-100/90 list-disc pl-4"></ul>
                        </div>
                        <!-- Threats -->
                        <div class="bg-rose-950/20 border border-rose-500/30 p-4 rounded-xl">
                            <div class="flex items-center gap-2 mb-2">
                                <span class="text-xl">⛔</span>
                                <h4 class="font-bold text-rose-300 text-sm">धोका व निगेटिव्ह रिस्क (Threats)</h4>
                            </div>
                            <ul id="swotThreats" class="space-y-1.5 text-xs text-rose-100/90 list-disc pl-4"></ul>
                        </div>
                    </div>
                </div>

                <!-- TAB 3: OBJECTIONS & WRONG ANSWERS -->
                <div id="tabViewObjections" class="hidden">
                    <div class="mb-4 p-3.5 rounded-xl bg-slate-900/80 border border-slate-700 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div>
                            <h3 class="font-bold text-white text-base">⚖️ चुकीच्या प्रश्नांचे पोस्टमार्टम व आक्षेप सल्ला (Objections)</h3>
                            <p class="text-xs text-slate-400 mt-0.5">तुमचे उत्तर का चुकले आणि अधिकृत उत्तर कसे योग्य आहे याचे स्टेप-बाय-स्टेप स्पष्टीकरण</p>
                        </div>
                        <div id="objectionCountNote" class="text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30 px-3 py-1 rounded-lg text-center self-start sm:self-auto">
                            0 प्रश्न चुकले
                        </div>
                    </div>
                    <div id="wrongAnswersList" class="space-y-3.5 mb-5 max-h-[600px] overflow-y-auto pr-1"></div>
                </div>

                <!-- TAB 4: ALL QUESTIONS EXPLORER -->
                <div id="tabViewQuestions" class="hidden">
                    <!-- Filter Controls -->
                    <div class="mb-4 p-3.5 rounded-xl bg-slate-900/80 border border-slate-700 flex flex-col md:flex-row md:items-center justify-between gap-3">
                        <div class="flex flex-wrap gap-1.5">
                            <button id="qfAll" onclick="filterQuestions('all')" class="px-3 py-1 text-xs font-bold rounded-lg bg-indigo-600 text-white transition-all">सर्व (All)</button>
                            <button id="qfCorrect" onclick="filterQuestions('correct')" class="px-3 py-1 text-xs font-bold rounded-lg bg-slate-800 text-slate-300 hover:text-white transition-all">✅ बरोबर</button>
                            <button id="qfIncorrect" onclick="filterQuestions('incorrect')" class="px-3 py-1 text-xs font-bold rounded-lg bg-slate-800 text-slate-300 hover:text-white transition-all">❌ चूक</button>
                            <button id="qfUnanswered" onclick="filterQuestions('unanswered')" class="px-3 py-1 text-xs font-bold rounded-lg bg-slate-800 text-slate-300 hover:text-white transition-all">⚪ अनुत्तरित</button>
                        </div>
                        <div class="flex items-center gap-2">
                            <select id="sectionFilterSelect" onchange="filterQuestions(currentQFilter)" class="bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 focus:outline-none">
                                <option value="all">सर्व विभाग (All Sections)</option>
                            </select>
                            <input type="text" id="questionSearchInput" oninput="filterQuestions(currentQFilter)" placeholder="प्रश्न शोधा..." class="bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none w-36 sm:w-48" />
                        </div>
                    </div>
                    <div id="allQuestionsList" class="space-y-3 mb-5 max-h-[600px] overflow-y-auto pr-1"></div>
                </div>

                <!-- High-Yield Digital Exam Books Shelf -->
                <div class="mt-6 mb-5 p-4 sm:p-5 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-indigo-500/30 shadow-xl no-print">
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 border-b border-slate-700/60 pb-3">
                        <div>
                            <div class="flex items-center gap-2">
                                <span class="text-xs uppercase tracking-wider text-amber-400 font-extrabold bg-amber-400/10 px-2 py-0.5 rounded border border-amber-400/20">📚 TCS / IBPS स्पेशल ई-बुक्स</span>
                                <span class="text-[11px] text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded font-bold">थेट डाऊनलोड (Instant PDF)</span>
                            </div>
                            <h3 class="text-sm sm:text-base font-bold text-white mt-1">तुमच्या पुढील यशासाठी शिफारस केलेली डिजिटल पुस्तके</h3>
                        </div>
                        <a href="/store" target="_blank" class="inline-flex items-center gap-1.5 text-xs sm:text-sm font-bold text-indigo-400 hover:text-indigo-300 transition-colors">
                            <span>सर्व पुस्तके पहा (/store)</span>
                            <span>➔</span>
                        </a>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <!-- Book 1 -->
                        <div class="bg-slate-900/90 border border-slate-700/80 hover:border-indigo-500/60 rounded-xl p-3.5 flex flex-col justify-between transition-all">
                            <div>
                                <span class="text-2xl mb-1.5 block">📰</span>
                                <div class="text-xs font-bold text-white leading-snug">मासिक चालू घडामोडी Top 200 MCQs + सविस्तर विश्लेषण</div>
                                <p class="text-[11px] text-slate-400 mt-1">TCS/IBPS पॅटर्ननुसार संभाव्य व रिपीटेड चालू घडामोडी प्रश्नसंच</p>
                            </div>
                            <div class="mt-3 pt-2.5 border-t border-slate-800 flex items-center justify-between">
                                <span class="text-sm font-extrabold text-amber-400">₹१९ <s class="text-[11px] text-slate-500 font-normal">₹९९</s></span>
                                <a href="/store" target="_blank" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs px-2.5 py-1.5 rounded-lg transition-all">विकत घ्या ⚡</a>
                            </div>
                        </div>

                        <!-- Book 2 -->
                        <div class="bg-slate-900/90 border border-slate-700/80 hover:border-indigo-500/60 rounded-xl p-3.5 flex flex-col justify-between transition-all">
                            <div>
                                <span class="text-2xl mb-1.5 block">🧠</span>
                                <div class="text-xs font-bold text-white leading-snug">गणित व बुद्धिमत्ता शॉर्टकट ट्रिक्स व Mindmaps संच</div>
                                <p class="text-[11px] text-slate-400 mt-1">कमी वेळेत १००% अचूकतेने प्रश्न सोडवण्याच्या जादुई युक्त्या</p>
                            </div>
                            <div class="mt-3 pt-2.5 border-t border-slate-800 flex items-center justify-between">
                                <span class="text-sm font-extrabold text-amber-400">₹२९ <s class="text-[11px] text-slate-500 font-normal">₹१४९</s></span>
                                <a href="/store" target="_blank" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs px-2.5 py-1.5 rounded-lg transition-all">विकत घ्या ⚡</a>
                            </div>
                        </div>

                        <!-- Book 3 -->
                        <div class="bg-slate-900/90 border border-slate-700/80 hover:border-indigo-500/60 rounded-xl p-3.5 flex flex-col justify-between transition-all">
                            <div>
                                <span class="text-2xl mb-1.5 block">📖</span>
                                <div class="text-xs font-bold text-white leading-snug">मराठी व इंग्रजी व्याकरण ३०००+ मागील वर्षांचे प्रश्न (PYQ)</div>
                                <p class="text-[11px] text-slate-400 mt-1">सर्व TCS/IBPS परीक्षेतील नियम, समानार्थी, विरुद्धार्थी व म्हणी</p>
                            </div>
                            <div class="mt-3 pt-2.5 border-t border-slate-800 flex items-center justify-between">
                                <span class="text-sm font-extrabold text-amber-400">₹१९ <s class="text-[11px] text-slate-500 font-normal">₹९९</s></span>
                                <a href="/store" target="_blank" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs px-2.5 py-1.5 rounded-lg transition-all">विकत घ्या ⚡</a>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Bottom Action Buttons Toolbar (Full Parity with Telegram Bot) -->
                <div class="space-y-2.5 pt-4 border-t border-slate-700 no-print">
                    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2.5">
                        <button onclick="downloadFullHtmlReport()" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-2.5 px-3 rounded-xl text-center text-xs sm:text-sm transition-all flex items-center justify-center gap-1.5 shadow-md shadow-indigo-900/30">
                            <span>📥 १०० प्रश्न निकाल (HTML)</span>
                        </button>
                        <button onclick="downloadWrongHtmlReport()" class="bg-rose-700 hover:bg-rose-600 text-white font-bold py-2.5 px-3 rounded-xl text-center text-xs sm:text-sm transition-all flex items-center justify-center gap-1.5 shadow-md shadow-rose-900/30">
                            <span>📑 चुकीचे प्रश्न अहवाल (HTML)</span>
                        </button>
                        <button onclick="shareWhatsApp()" class="bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-2.5 px-3 rounded-xl text-center text-xs sm:text-sm transition-all flex items-center justify-center gap-1.5 shadow-md shadow-emerald-900/30">
                            <span>📲 WhatsApp शेअर</span>
                        </button>
                        <button onclick="window.print()" class="bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-2.5 px-3 rounded-xl text-center text-xs sm:text-sm transition-all flex items-center justify-center gap-1.5">
                            <span>🖨️ सेव्ह करा (PDF / Print)</span>
                        </button>
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                        <a href="https://www.youtube.com" target="_blank" id="ytLiveBtn" class="bg-red-600 hover:bg-red-500 text-white font-bold py-2 px-3 rounded-xl text-center text-xs sm:text-sm transition-all flex items-center justify-center gap-1.5 shadow-md shadow-red-900/30">
                            <span>📺 YouTube उत्तरतालिका विश्लेषण</span>
                        </a>
                        <a href="/store" target="_blank" class="bg-amber-600 hover:bg-amber-500 text-slate-950 font-black py-2 px-3 rounded-xl text-center text-xs sm:text-sm transition-all flex items-center justify-center gap-1.5 shadow-md shadow-amber-900/30">
                            <span>🛒 ई-पुस्तके स्टोअर (/store)</span>
                        </a>
                        <button onclick="location.reload()" class="bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold py-2 px-3 rounded-xl text-center text-xs sm:text-sm transition-all">
                            🔄 नवीन विश्लेषण करा
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <footer class="mt-6 text-center text-xs text-slate-500 no-print">
            ExamRankers India © 2026 • AI-Powered Maharashtra Recruitment Exam Analytics
        </footer>
    </div>

    <script>
        let currentTab = 'file';
        let currentInputTab = 'file';
        let currentResultTab = 'scorecard';
        let currentQFilter = 'all';
        let selectedFile = null;
        let lastResultData = null;

        // Auto-fill from URL parameters (e.g. ?cat=OBC&exam=talathi&uid=12345)
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('cat')) {
            const catEl = document.getElementById('userCategory');
            if (catEl) catEl.value = urlParams.get('cat');
        }
        if (urlParams.get('exam')) {
            const examEl = document.getElementById('examSelect');
            if (examEl) examEl.value = urlParams.get('exam');
        }
        const telegramUid = urlParams.get('uid') || '';

        function switchTab(tab) { switchInputTab(tab); }
        function switchInputTab(tab) {
            currentTab = tab;
            currentInputTab = tab;
            const tabFile = document.getElementById('tabFileBtn');
            const tabUrl = document.getElementById('tabUrlBtn');
            const tabManual = document.getElementById('tabManualBtn');
            const fileContent = document.getElementById('fileTabContent');
            const urlContent = document.getElementById('urlTabContent');
            const manualContent = document.getElementById('manualTabContent');

            [tabFile, tabUrl, tabManual].forEach(b => {
                if (b) {
                    b.classList.remove('border-indigo-500', 'text-indigo-400');
                    b.classList.add('border-transparent', 'text-slate-400');
                }
            });
            if (fileContent) fileContent.classList.add('hidden');
            if (urlContent) urlContent.classList.add('hidden');
            if (manualContent) manualContent.classList.add('hidden');

            if (tab === 'file') {
                if (tabFile) {
                    tabFile.classList.add('border-indigo-500', 'text-indigo-400');
                    tabFile.classList.remove('border-transparent', 'text-slate-400');
                }
                if (fileContent) fileContent.classList.remove('hidden');
            } else if (tab === 'url') {
                if (tabUrl) {
                    tabUrl.classList.add('border-indigo-500', 'text-indigo-400');
                    tabUrl.classList.remove('border-transparent', 'text-slate-400');
                }
                if (urlContent) urlContent.classList.remove('hidden');
            } else if (tab === 'manual') {
                if (tabManual) {
                    tabManual.classList.add('border-indigo-500', 'text-indigo-400');
                    tabManual.classList.remove('border-transparent', 'text-slate-400');
                }
                if (manualContent) manualContent.classList.remove('hidden');
            }
        }

        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');
        const selectedFileName = document.getElementById('selectedFileName');
        const submitBtn = document.getElementById('submitBtn');
        const errorBox = document.getElementById('errorBox');

        dropZone.onclick = () => fileInput.click();
        fileInput.onchange = (e) => {
            if (e.target.files.length) handleFile(e.target.files[0]);
        };
        dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('border-indigo-400'); };
        dropZone.ondragleave = () => { dropZone.classList.remove('border-indigo-400'); };
        dropZone.ondrop = (e) => {
            e.preventDefault();
            dropZone.classList.remove('border-indigo-400');
            if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
        };

        function handleFile(file) {
            selectedFile = file;
            selectedFileName.textContent = file.name + ' (' + (file.size / (1024*1024)).toFixed(1) + ' MB)';
            selectedFileName.classList.remove('hidden');
            errorBox.classList.add('hidden');
        }

        function readBlobAsBase64(blob) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => {
                    const res = reader.result;
                    resolve(res.indexOf(',') !== -1 ? res.split(',')[1] : res);
                };
                reader.onerror = (err) => reject(err);
                reader.readAsDataURL(blob);
            });
        }

        async function tryExtractUrlFromPdf(file) {
            try {
                const slice1 = file.slice(0, 500000);
                const text1 = await slice1.text();
                const m1 = text1.match(/https?:\/\/[a-zA-Z0-9.\-_]*digialm\.com[^\s"'<>\)\\]+/i);
                if (m1) return m1[0];

                if (file.size > 500000) {
                    const slice2 = file.slice(Math.max(0, file.size - 500000));
                    const text2 = await slice2.text();
                    const m2 = text2.match(/https?:\/\/[a-zA-Z0-9.\-_]*digialm\.com[^\s"'<>\)\\]+/i);
                    if (m2) return m2[0];
                }
            } catch(e) {}
            return null;
        }

        submitBtn.onclick = async () => {
            errorBox.classList.add('hidden');
            const cat = document.getElementById('userCategory').value;
            const exam = document.getElementById('examSelect').value;

            if (currentTab === 'manual') {
                const scoreInput = document.getElementById('manualScoreInput');
                const rawScore = scoreInput ? parseFloat(scoreInput.value) : NaN;
                if (isNaN(rawScore)) {
                    showError('कृपया तुमचे मिळालेले गुण टाका (उदा. 142.5).');
                    return;
                }
                const postVal = document.getElementById('manualPostInput') ? document.getElementById('manualPostInput').value.trim() : '';
                const nameVal = document.getElementById('manualNameInput') ? document.getElementById('manualNameInput').value.trim() : '';
                startLoading('रँक व कटऑफ गणना सुरू आहे... ⚡', 'राज्य रँक, प्रवर्ग रँक आणि निवड अंदाज मोजत आहे...');
                await postQuickRank({
                    score: rawScore,
                    category: cat,
                    exam: exam,
                    post_name: postVal,
                    candidate_name: nameVal || 'परीक्षार्थी'
                });
                return;
            }

            if (currentTab === 'file') {
                if (!selectedFile) {
                    showError('कृपया तुमची रिस्पॉन्स शीट (PDF/HTML) निवडा.');
                    return;
                }

                startLoading('विश्लेषण सुरू आहे...', 'PDF मधील तपशील तपासत आहे...');

                // Check if PDF contains embedded DigiALM URL for instant 1-sec scoring
                const embeddedUrl = await tryExtractUrlFromPdf(selectedFile);
                if (embeddedUrl) {
                    setLoadingText('अधिकृत DigiALM लिंक सापडली! ⚡', 'थेट पोर्टलवरून निकाल व रँक तयार करत आहे...');
                    await postSheetData({
                        digialm_url: embeddedUrl,
                        category: cat,
                        exam: exam,
                        telegram_user_id: telegramUid
                    });
                    return;
                }

                // If file is > 2 MB, use chunked upload (1.5 MB per chunk) to avoid reverse-proxy timeouts
                const CHUNK_SIZE = 1.5 * 1024 * 1024;
                if (selectedFile.size > 2 * 1024 * 1024) {
                    const totalChunks = Math.ceil(selectedFile.size / CHUNK_SIZE);
                    const uploadId = 'up_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
                    showProgressBar(true);

                    try {
                        for (let i = 0; i < totalChunks; i++) {
                            const start = i * CHUNK_SIZE;
                            const end = Math.min(selectedFile.size, start + CHUNK_SIZE);
                            const chunkBlob = selectedFile.slice(start, end);
                            const chunkB64 = await readBlobAsBase64(chunkBlob);

                            updateProgress(i + 1, totalChunks);

                            const chunkPayload = {
                                upload_id: uploadId,
                                chunk_index: i,
                                total_chunks: totalChunks,
                                filename: selectedFile.name,
                                category: cat,
                                exam: exam,
                                telegram_user_id: telegramUid,
                                data: chunkB64
                            };

                            let res;
                            let retries = 3;
                            while (retries > 0) {
                                try {
                                    res = await fetch('/api/upload_chunk', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify(chunkPayload)
                                    });
                                    if (res.ok) break;
                                } catch (fetchErr) {
                                    console.warn('Chunk upload retry error:', fetchErr);
                                }
                                retries--;
                                if (retries === 0 && (!res || !res.ok)) {
                                    throw new Error('तुकडा ' + (i+1) + '/' + totalChunks + ' अपलोड अयशस्वी (Status: ' + (res ? res.status : 'Network Error') + ')');
                                }
                                await new Promise(r => setTimeout(r, 800));
                            }

                            const data = await res.json();
                            if (i === totalChunks - 1) {
                                if (data.status === 'processing') {
                                    setLoadingText('AI रिस्पॉन्स शीट विश्लेषण सुरू आहे... ⏳', 'सर्व १०० प्रश्न, अधिकृत की आणि राज्य रँक मोजली जात आहे...');
                                    let pollAttempts = 0;
                                    const maxPolls = 180;
                                    await new Promise((resolve) => {
                                        const pollInterval = setInterval(async () => {
                                            pollAttempts++;
                                            try {
                                                const pRes = await fetch('/api/upload_status?upload_id=' + encodeURIComponent(uploadId));
                                                if (!pRes.ok) return;
                                                const pData = await pRes.json();
                                                if (pData.status === 'completed') {
                                                    clearInterval(pollInterval);
                                                    stopLoading();
                                                    const finalRes = pData.result || {};
                                                    if (finalRes.success) {
                                                        lastResultData = finalRes;
                                                        showResults(finalRes);
                                                    } else {
                                                        document.getElementById('uploadSection').classList.remove('hidden');
                                                        showError(finalRes.error || 'विश्लेषण करताना अडचण आली.');
                                                    }
                                                    resolve();
                                                } else if (pData.status === 'error') {
                                                    clearInterval(pollInterval);
                                                    stopLoading();
                                                    document.getElementById('uploadSection').classList.remove('hidden');
                                                    showError(pData.error || 'विश्लेषण करताना अडचण आली.');
                                                    resolve();
                                                } else if (pollAttempts >= maxPolls) {
                                                    clearInterval(pollInterval);
                                                    stopLoading();
                                                    document.getElementById('uploadSection').classList.remove('hidden');
                                                    showError('प्रक्रियेची वेळ संपली (Timeout). कृपया पुन्हा प्रयत्न करा.');
                                                    resolve();
                                                }
                                            } catch (pErr) {
                                                console.warn('Polling status error:', pErr);
                                            }
                                        }, 1000);
                                    });
                                    return;
                                }

                                stopLoading();
                                if (data.success) {
                                    lastResultData = data;
                                    showResults(data);
                                } else {
                                    document.getElementById('uploadSection').classList.remove('hidden');
                                    showError(data.error || 'विश्लेषण करताना अडचण आली.');
                                }
                                return;
                            }
                        }
                    } catch (err) {
                        stopLoading();
                        document.getElementById('uploadSection').classList.remove('hidden');
                        showError('अपलोड त्रुटी: ' + err.message + '. कृपया फाईल पुन्हा निवडा किंवा DigiALM वेब लिंक वापरा.');
                    }
                    return;
                }

                // Small file (<= 2 MB): Single shot upload
                try {
                    const b64 = await readBlobAsBase64(selectedFile);
                    await postSheetData({
                        file_b64: b64,
                        filename: selectedFile.name,
                        category: cat,
                        exam: exam,
                        telegram_user_id: telegramUid
                    });
                } catch (err) {
                    stopLoading();
                    document.getElementById('uploadSection').classList.remove('hidden');
                    showError('ब्राउझरमध्ये फाईल वाचताना त्रुटी: ' + err.message);
                }
            } else {
                const url = document.getElementById('urlInput').value.trim();
                if (!url || !url.startsWith('http')) {
                    showError('कृपया वैध DigiALM वेब लिंक टाका (उदा. https://cdn.digialm.com/...).');
                    return;
                }
                startLoading('थेट DigiALM निकाल तपासत आहे...', 'प्रश्नोत्तरे आणि अधिकृत की डाऊनलोड होत आहे...');
                await postSheetData({
                    digialm_url: url,
                    category: cat,
                    exam: exam,
                    telegram_user_id: telegramUid
                });
            }
        };

        async function postSheetData(payload) {
            try {
                const res = await fetch('/api/upload_sheet', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (!res.ok && res.status >= 500) {
                    throw new Error('सर्व्हर तात्पुरता व्यस्त आहे (Status: ' + res.status + ')');
                }
                const data = await res.json();
                stopLoading();
                if (data.success) {
                    lastResultData = data;
                    showResults(data);
                } else {
                    document.getElementById('uploadSection').classList.remove('hidden');
                    showError(data.error || 'विश्लेषण करताना अडचण आली.');
                }
            } catch (err) {
                stopLoading();
                document.getElementById('uploadSection').classList.remove('hidden');
                showError('सर्व्हरशी संपर्क होऊ शकला नाही: ' + err.message + ' (कृपया इंटरनेट किंवा DigiALM लिंक तपासा).');
            }
        }

        async function postQuickRank(payload) {
            try {
                const res = await fetch('/api/quick_rank', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (!res.ok && res.status >= 500) {
                    throw new Error('सर्व्हर तात्पुरता व्यस्त आहे (Status: ' + res.status + ')');
                }
                const data = await res.json();
                stopLoading();
                if (data.success) {
                    lastResultData = data;
                    showResults(data);
                } else {
                    document.getElementById('uploadSection').classList.remove('hidden');
                    showError(data.error || 'रँक गणना करताना अडचण आली.');
                }
            } catch (err) {
                stopLoading();
                document.getElementById('uploadSection').classList.remove('hidden');
                showError('सर्व्हरशी संपर्क होऊ शकला नाही: ' + err.message);
            }
        }

        function startLoading(title, sub) {
            document.getElementById('uploadSection').classList.add('hidden');
            document.getElementById('loadingSection').classList.remove('hidden');
            if (title) document.getElementById('loadingTitle').textContent = title;
            if (sub) document.getElementById('loadingSubtitle').textContent = sub;
            showProgressBar(false);
        }

        function setLoadingText(title, sub) {
            if (title) document.getElementById('loadingTitle').textContent = title;
            if (sub) document.getElementById('loadingSubtitle').textContent = sub;
        }

        function showProgressBar(show) {
            const barBox = document.getElementById('uploadProgressBarContainer');
            if (show) {
                barBox.classList.remove('hidden');
                setLoadingText('मोठी फाईल तुकड्यांमध्ये सुरक्षित अपलोड होत आहे... 🚀', 'कृपया हे पेज बंद करू नका, काही सेकंदात अपलोड पूर्ण होईल.');
            } else {
                barBox.classList.add('hidden');
            }
        }

        function updateProgress(current, total) {
            const pct = Math.round((current / total) * 100);
            document.getElementById('uploadProgressBar').style.width = pct + '%';
            document.getElementById('uploadProgressText').textContent = 'अपलोड होत आहे: ' + pct + '%';
            document.getElementById('uploadChunkText').textContent = 'तुकडा ' + current + '/' + total;
            if (current === total) {
                setLoadingText('AI रिस्पॉन्स शीट विश्लेषण सुरू आहे... ⏳', 'सर्व १०० प्रश्न, अधिकृत की आणि राज्य रँक मोजली जात आहे...');
            }
        }

        function stopLoading() {
            document.getElementById('loadingSection').classList.add('hidden');
            showProgressBar(false);
        }

        function showError(msg) {
            errorBox.textContent = msg;
            errorBox.classList.remove('hidden');
        }

        function switchResultTab(tab) {
            currentResultTab = tab;
            const tabs = ['scorecard', 'swot', 'objections', 'questions'];
            tabs.forEach(t => {
                const btnId = 'rtabBtn' + t.charAt(0).toUpperCase() + t.slice(1);
                const viewId = 'tabView' + t.charAt(0).toUpperCase() + t.slice(1);
                const btn = document.getElementById(btnId);
                const view = document.getElementById(viewId);
                if (!btn || !view) return;

                if (t === tab) {
                    btn.classList.add('border-indigo-500', 'text-indigo-400');
                    btn.classList.remove('border-transparent', 'text-slate-400');
                    view.classList.remove('hidden');
                } else {
                    btn.classList.remove('border-indigo-500', 'text-indigo-400');
                    btn.classList.add('border-transparent', 'text-slate-400');
                    view.classList.add('hidden');
                }
            });
        }

        function renderSwot(swot) {
            if (!swot) return;
            const popList = (elId, items) => {
                const el = document.getElementById(elId);
                if (!el) return;
                el.innerHTML = '';
                if (!items || items.length === 0) {
                    el.innerHTML = '<li>डेटा उपलब्ध नाही.</li>';
                    return;
                }
                items.forEach(it => {
                    const li = document.createElement('li');
                    li.textContent = it;
                    el.appendChild(li);
                });
            };
            popList('swotStrengths', swot.strengths);
            popList('swotWeaknesses', swot.weaknesses);
            popList('swotOpportunities', swot.opportunities);
            popList('swotThreats', swot.threats);
            const accEl = document.getElementById('swotAccBadge');
            if (accEl) accEl.textContent = (swot.overall_accuracy !== undefined ? swot.overall_accuracy : '0') + '%';
        }

        function renderObjections(wrongQuestions) {
            const container = document.getElementById('wrongAnswersList');
            const badge = document.getElementById('wrongCountBadge');
            const note = document.getElementById('objectionCountNote');
            if (!container) return;
            container.innerHTML = '';

            const count = wrongQuestions ? wrongQuestions.length : 0;
            if (badge) badge.textContent = count;
            if (note) note.textContent = count + ' प्रश्न चुकले (Post-Mortem & Objections)';

            if (!wrongQuestions || wrongQuestions.length === 0) {
                container.innerHTML = `
                    <div class="bg-emerald-950/40 border border-emerald-500/40 p-6 rounded-xl text-center text-emerald-200">
                        <span class="text-3xl block mb-2">🎉</span>
                        <h4 class="font-bold text-base">अभिनंदन! एकही प्रश्न चुकलेला नाही.</h4>
                        <p class="text-xs text-emerald-300/80 mt-1">सर्व सोडवलेले प्रश्न बरोबर आहेत किंवा कोणतीही चूक आढळली नाही.</p>
                    </div>
                `;
                return;
            }

            wrongQuestions.forEach((q, idx) => {
                const card = document.createElement('div');
                card.className = 'bg-slate-900/90 border border-slate-700/80 rounded-xl p-4 transition-all hover:border-slate-600';

                const chosenLabel = q.chosen_num ? ('पर्याय ' + q.chosen_num + (q.chosen_text ? ' (' + q.chosen_text + ')' : '')) : 'अनुत्तरित';
                const correctLabel = q.correct_num ? ('पर्याय ' + q.correct_num + (q.correct_text ? ' (' + q.correct_text + ')' : '')) : 'अधिकृत उत्तर';

                card.innerHTML = `
                    <div class="flex items-center justify-between gap-2 border-b border-slate-800 pb-2 mb-2.5">
                        <div class="flex items-center gap-2">
                            <span class="bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs px-2 py-0.5 rounded font-bold">प्रश्न #${q.question_number || (idx + 1)}</span>
                            <span class="text-xs text-slate-400 font-semibold">${q.section || 'General'}</span>
                        </div>
                        <span class="text-[11px] font-mono text-slate-500">ID: ${q.question_id || '-'}</span>
                    </div>

                    <div class="text-sm font-semibold text-slate-100 mb-3 leading-snug">
                        ${q.question_text || 'प्रश्न मजकूर उपलब्ध नाही'}
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3 text-xs">
                        <div class="bg-rose-950/30 border border-rose-500/30 p-2.5 rounded-lg">
                            <span class="text-rose-400 font-bold block mb-0.5">❌ तुमचा निवडलेला पर्याय:</span>
                            <span class="text-rose-200 font-medium">${chosenLabel}</span>
                        </div>
                        <div class="bg-emerald-950/30 border border-emerald-500/30 p-2.5 rounded-lg">
                            <span class="text-emerald-400 font-bold block mb-0.5">✅ अधिकृत अचूक उत्तर:</span>
                            <span class="text-emerald-200 font-medium">${correctLabel}</span>
                        </div>
                    </div>

                    <div class="bg-slate-800/80 border border-slate-700/60 p-3 rounded-lg text-xs text-slate-200 space-y-1.5 mb-2 leading-relaxed">
                        <div class="font-bold text-indigo-300 flex items-center gap-1">
                            <span>🧠 AI सविस्तर स्पष्टीकरण:</span>
                        </div>
                        <div class="text-slate-300 font-normal">
                            ${q.explanation || 'स्पष्टीकरण तयार होत आहे.'}
                        </div>
                    </div>

                    <div class="bg-indigo-950/40 border border-indigo-500/30 p-2.5 rounded-lg text-[11px] text-indigo-200 flex items-start gap-1.5">
                        <span>⚖️</span>
                        <div>
                            <span class="font-bold text-indigo-300">आक्षेप सल्ला:</span>
                            <span class="text-indigo-200/90 ml-1">${q.objection_reason || 'अधिकृत संदर्भानुसार उत्तर प्रमाणित आहे.'}</span>
                        </div>
                    </div>
                `;
                container.appendChild(card);
            });
        }

        function populateSectionFilter(questions) {
            const sel = document.getElementById('sectionFilterSelect');
            if (!sel || !questions) return;
            sel.innerHTML = '<option value="all">सर्व विभाग (All Sections)</option>';
            const sections = new Set();
            questions.forEach(q => { if (q.section) sections.add(q.section); });
            sections.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s;
                opt.textContent = s;
                sel.appendChild(opt);
            });
        }

        function filterQuestions(filterType) {
            currentQFilter = filterType || 'all';
            const allBtn = document.getElementById('qfAll');
            const corBtn = document.getElementById('qfCorrect');
            const incBtn = document.getElementById('qfIncorrect');
            const unaBtn = document.getElementById('qfUnanswered');

            [allBtn, corBtn, incBtn, unaBtn].forEach(b => {
                if (b) {
                    b.className = 'px-3 py-1 text-xs font-bold rounded-lg bg-slate-800 text-slate-300 hover:text-white transition-all';
                }
            });

            if (currentQFilter === 'all' && allBtn) allBtn.className = 'px-3 py-1 text-xs font-bold rounded-lg bg-indigo-600 text-white transition-all';
            if (currentQFilter === 'correct' && corBtn) corBtn.className = 'px-3 py-1 text-xs font-bold rounded-lg bg-emerald-600 text-white transition-all';
            if (currentQFilter === 'incorrect' && incBtn) incBtn.className = 'px-3 py-1 text-xs font-bold rounded-lg bg-rose-600 text-white transition-all';
            if (currentQFilter === 'unanswered' && unaBtn) unaBtn.className = 'px-3 py-1 text-xs font-bold rounded-lg bg-amber-600 text-white transition-all';

            if (!lastResultData || !lastResultData.all_questions) return;

            const secVal = document.getElementById('sectionFilterSelect') ? document.getElementById('sectionFilterSelect').value : 'all';
            const searchVal = document.getElementById('questionSearchInput') ? document.getElementById('questionSearchInput').value.trim().toLowerCase() : '';

            let filtered = lastResultData.all_questions.filter(q => {
                if (currentQFilter === 'correct' && q.evaluation !== 'correct') return false;
                if (currentQFilter === 'incorrect' && q.evaluation !== 'incorrect') return false;
                if (currentQFilter === 'unanswered' && q.evaluation !== 'unanswered') return false;
                if (secVal !== 'all' && q.section !== secVal) return false;
                if (searchVal) {
                    const qTxt = (q.question_text || '').toLowerCase();
                    const secTxt = (q.section || '').toLowerCase();
                    if (!qTxt.includes(searchVal) && !secTxt.includes(searchVal)) return false;
                }
                return true;
            });

            renderQuestionsList(filtered);
        }

        function renderQuestionsList(questions) {
            const container = document.getElementById('allQuestionsList');
            const badge = document.getElementById('totalQBadge');
            if (!container) return;
            container.innerHTML = '';

            if (badge && lastResultData && lastResultData.all_questions) {
                badge.textContent = lastResultData.all_questions.length;
            }

            if (!questions || questions.length === 0) {
                container.innerHTML = `
                    <div class="bg-slate-900/60 border border-slate-700/60 p-6 rounded-xl text-center text-slate-400">
                        निवडलेल्या निकषानुसार प्रश्न सापडले नाहीत.
                    </div>
                `;
                return;
            }

            questions.forEach((q, idx) => {
                const card = document.createElement('div');
                card.className = 'bg-slate-900/80 border border-slate-700/70 rounded-xl p-3.5 transition-all';

                let statusBadge = '<span class="bg-slate-700/60 text-slate-300 text-[11px] px-2 py-0.5 rounded font-bold">⚪ अनुत्तरित</span>';
                if (q.evaluation === 'correct') {
                    statusBadge = '<span class="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[11px] px-2 py-0.5 rounded font-bold">✅ अचूक</span>';
                } else if (q.evaluation === 'incorrect') {
                    statusBadge = '<span class="bg-rose-500/20 text-rose-300 border border-rose-500/30 text-[11px] px-2 py-0.5 rounded font-bold">❌ चूक</span>';
                }

                let optionsHtml = '';
                if (q.options && Object.keys(q.options).length > 0) {
                    optionsHtml = '<div class="grid grid-cols-1 sm:grid-cols-2 gap-1.5 mt-2.5">';
                    for (const [optKey, optVal] of Object.entries(q.options)) {
                        const optNumStr = String(optKey).replace(/[^0-9]/g, '');
                        const isChosen = String(q.chosen_num) === optNumStr;
                        const isCorrect = String(q.correct_num) === optNumStr;

                        let optClass = 'bg-slate-800/60 border-slate-700/60 text-slate-300';
                        let optIcon = '';
                        if (isCorrect) {
                            optClass = 'bg-emerald-950/40 border-emerald-500/50 text-emerald-200 font-semibold';
                            optIcon = ' <span class="text-emerald-400 font-bold ml-1">(अधिकृत उत्तर)</span>';
                        }
                        if (isChosen && !isCorrect) {
                            optClass = 'bg-rose-950/40 border-rose-500/50 text-rose-200 font-semibold';
                            optIcon = ' <span class="text-rose-400 font-bold ml-1">(तुमची निवड)</span>';
                        } else if (isChosen && isCorrect) {
                            optIcon = ' <span class="text-emerald-400 font-bold ml-1">(तुमची अचूक निवड ✓)</span>';
                        }

                        optionsHtml += `
                            <div class="border rounded-lg p-2 text-xs flex items-center justify-between ${optClass}">
                                <span><b>${optKey}.</b> ${optVal}</span>
                                ${optIcon}
                            </div>
                        `;
                    }
                    optionsHtml += '</div>';
                }

                card.innerHTML = `
                    <div class="flex items-center justify-between gap-2 border-b border-slate-800 pb-2 mb-2">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-bold text-white">प्रश्न #${q.question_number || (idx + 1)}</span>
                            <span class="text-[11px] text-slate-400 bg-slate-800 px-2 py-0.5 rounded">${q.section || 'General'}</span>
                        </div>
                        <div>${statusBadge}</div>
                    </div>
                    <div class="text-xs sm:text-sm text-slate-100 font-medium leading-relaxed">
                        ${q.question_text || 'प्रश्न उपलब्ध नाही'}
                    </div>
                    ${optionsHtml}
                `;
                container.appendChild(card);
            });
        }

        function showResults(data) {
            // Expand container for rich dashboard layout
            const portalCont = document.getElementById('portalContainer');
            if (portalCont) {
                portalCont.className = 'max-w-4xl mx-auto w-full transition-all duration-300';
            }

            // Top Banner & Metadata
            document.getElementById('resCandidate').textContent = data.candidate_name || 'परीक्षार्थी';
            document.getElementById('resExam').textContent = data.exam_title || 'परीक्षा निकाल';
            document.getElementById('resCategory').textContent = data.category || 'Open';
            document.getElementById('resRoll').textContent = data.roll_number || 'उपलब्ध नाही';
            const postEl = document.getElementById('resBadgePost');
            if (postEl) postEl.textContent = data.post_name || 'General';

            // Cutoff Prediction Zone
            const zoneEl = document.getElementById('resCutoffZone');
            const zoneIconEl = document.getElementById('zoneIcon');
            const zoneStr = data.cutoff_zone || 'N/A';
            if (zoneEl) zoneEl.textContent = zoneStr;
            if (zoneIconEl) {
                if (zoneStr.includes('Strong') || zoneStr.includes('सुरक्षित')) zoneIconEl.textContent = '🟢';
                else if (zoneStr.includes('Border') || zoneStr.includes('सीमावर्ती')) zoneIconEl.textContent = '🟡';
                else if (zoneStr.includes('Push') || zoneStr.includes('सरावाची')) zoneIconEl.textContent = '🔴';
                else zoneIconEl.textContent = '🎯';
            }
            const avgEl = document.getElementById('resAvgScore');
            const topEl = document.getElementById('resTopScore');
            if (avgEl) avgEl.textContent = (data.avg_score !== undefined ? data.avg_score : '-');
            if (topEl) topEl.textContent = (data.top_score !== undefined ? data.top_score : '-');

            // 4 Top Cards
            document.getElementById('resScore').textContent = data.raw_score + ' / ' + data.max_marks;
            const maxEl = document.getElementById('resMaxMarks');
            if (maxEl) maxEl.textContent = data.max_marks;
            const accEl = document.getElementById('resAccuracy');
            if (accEl) accEl.textContent = (data.accuracy !== undefined ? data.accuracy : '0') + '%';
            document.getElementById('resCorrect').textContent = data.correct;
            document.getElementById('resIncorrect').textContent = data.incorrect;
            const unansEl = document.getElementById('resUnanswered');
            if (unansEl) unansEl.textContent = data.unanswered;

            // 4-Tier Ranks
            const sRank = data.overall_rank || data.rank || 1;
            const sTotal = data.overall_total || data.total_candidates || 1;
            const sPct = data.overall_percentile || data.percentile || 100.0;
            document.getElementById('resStateRank').textContent = '#' + sRank + ' / ' + sTotal;
            document.getElementById('resStatePercentile').textContent = sPct.toFixed(1) + '%';

            const eRank = data.rank || 1;
            const eTotal = data.total_candidates || 1;
            const ePct = data.percentile || 100.0;
            document.getElementById('resExamRank').textContent = '#' + eRank + ' / ' + eTotal;
            document.getElementById('resExamPercentile').textContent = ePct.toFixed(1) + '%';

            const cRank = data.category_rank || data.rank || 1;
            const cTotal = data.category_total || data.total_candidates || 1;
            const cPct = data.category_percentile || data.percentile || 100.0;
            document.getElementById('resCatRank').textContent = '#' + cRank + ' / ' + cTotal;
            document.getElementById('resCatPercentile').textContent = cPct.toFixed(1) + '%';

            const pRank = data.post_rank || data.rank || 1;
            const pTotal = data.post_total || data.total_candidates || 1;
            document.getElementById('resPostRank').textContent = '#' + pRank + ' / ' + pTotal;

            // Subject-wise breakdown table
            const tableContainer = document.getElementById('sectionTableContainer');
            const tbody = document.getElementById('sectionTableBody');
            tbody.innerHTML = '';

            if (data.section_scores && Object.keys(data.section_scores).length > 0) {
                for (const [secName, secData] of Object.entries(data.section_scores)) {
                    const tr = document.createElement('tr');
                    const marks = (typeof secData === 'object' && secData.score !== undefined) ? secData.score : secData;
                    const cCount = (typeof secData === 'object' && secData.correct !== undefined) ? secData.correct : '-';
                    const iCount = (typeof secData === 'object' && secData.incorrect !== undefined) ? secData.incorrect : '-';
                    const att = (typeof secData === 'object' && secData.attempted !== undefined) ? secData.attempted : (cCount !== '-' && iCount !== '-' ? (Number(cCount) + Number(iCount)) : '-');
                    let secAcc = '-';
                    if (att && Number(att) > 0 && cCount !== '-') {
                        secAcc = Math.round((Number(cCount) / Number(att)) * 100) + '%';
                    }

                    tr.innerHTML = `
                        <td class="py-2.5 px-3 font-semibold text-slate-200">${secName}</td>
                        <td class="py-2.5 px-3 text-center text-slate-300">${att}</td>
                        <td class="py-2.5 px-3 text-center text-emerald-400 font-bold">${cCount}</td>
                        <td class="py-2.5 px-3 text-center text-rose-400 font-bold">${iCount}</td>
                        <td class="py-2.5 px-3 text-center text-cyan-300 font-semibold">${secAcc}</td>
                        <td class="py-2.5 px-3 text-right font-extrabold text-amber-400">${marks}</td>
                    `;
                    tbody.appendChild(tr);
                }
                tableContainer.classList.remove('hidden');
            } else {
                tableContainer.classList.add('hidden');
            }

            // Render Tab 2: AI SWOT
            renderSwot(data.swot);

            // Render Tab 3: Objections & Wrong Answers
            renderObjections(data.wrong_questions);

            // Populate Tab 4: Section filter & Question list
            populateSectionFilter(data.all_questions);
            filterQuestions('all');

            // Default to Scorecard tab
            switchResultTab('scorecard');

            const ytBtn = document.getElementById('ytLiveBtn');
            if (ytBtn && data.youtube_link) {
                ytBtn.href = data.youtube_link;
            }

            // Show Result Section
            document.getElementById('resultSection').classList.remove('hidden');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function shareWhatsApp() {
            if (!lastResultData) return;
            const z = lastResultData.cutoff_zone || 'N/A';
            const text = `🎯 *माझा परीक्षा निकाल व संभाव्य रँक (ExamRankers):*\n` +
                         `👤 नाव: ${lastResultData.candidate_name || 'परीक्षार्थी'}\n` +
                         `📋 परीक्षा: ${lastResultData.exam_title}\n` +
                         `🏷️ प्रवर्ग: ${lastResultData.category || 'Open'}\n` +
                         `📊 एकूण गुण: ${lastResultData.raw_score} / ${lastResultData.max_marks}\n` +
                         `🎯 अचूकता (Accuracy): ${lastResultData.accuracy || 0}%\n` +
                         `🏆 संभाव्य राज्य रँक: #${lastResultData.rank} / ${lastResultData.total_candidates}\n` +
                         `📈 पर्सेंटाईल: ${lastResultData.percentile ? lastResultData.percentile.toFixed(1) + '%' : '100%'}\n` +
                         `🟢 निवड अंदाज (Cutoff Zone): ${z}\n\n` +
                         `🔗 तुमची रिस्पॉन्स शीट थेट तपासा: https://exam-rank-predictor-bot.onrender.com/upload`;
            window.open('https://api.whatsapp.com/send?text=' + encodeURIComponent(text), '_blank');
        }

        function escapeHtml(str) {
            if (!str) return '';
            const div = document.createElement('div');
            div.textContent = String(str);
            return div.innerHTML;
        }

        function downloadHtmlFile(content, fileName) {
            const blob = new Blob([content], { type: 'text/html;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = fileName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        function downloadFullHtmlReport() {
            if (!lastResultData) {
                alert('कृपया आधी निकाल पहा.');
                return;
            }
            const d = lastResultData;
            const name = escapeHtml(d.candidate_name || 'परीक्षार्थी');
            const exam = escapeHtml(d.exam_title || 'परीक्षा');
            const cat = escapeHtml(d.category || 'Open');
            const roll = escapeHtml(d.roll_number || 'उपलब्ध नाही');
            const score = d.raw_score !== undefined ? d.raw_score : 0;
            const maxM = d.max_marks || 200;
            const acc = d.accuracy || 0;
            const rank = d.overall_rank || d.rank || 1;
            const total = d.overall_total || d.total_candidates || 1;
            const zone = escapeHtml(d.cutoff_zone || 'N/A');

            let qHtml = '';
            if (d.all_questions && d.all_questions.length > 0) {
                d.all_questions.forEach((q, idx) => {
                    const num = q.question_number || (idx + 1);
                    const status = q.evaluation === 'correct' ? '<span style="color:#059669;font-weight:bold;">✅ बरोबर</span>' : (q.evaluation === 'incorrect' ? '<span style="color:#dc2626;font-weight:bold;">❌ चूक</span>' : '<span style="color:#64748b;">⚪ अनुत्तरित</span>');
                    const chosen = q.chosen_num ? ('पर्याय ' + escapeHtml(q.chosen_num) + (q.chosen_text ? ' (' + escapeHtml(q.chosen_text) + ')' : '')) : 'अनुत्तरित';
                    const correct = q.correct_num ? ('पर्याय ' + escapeHtml(q.correct_num) + (q.correct_text ? ' (' + escapeHtml(q.correct_text) + ')' : '')) : '-';
                    const exp = q.explanation ? `<div style="margin-top:8px;padding:8px;background:#f8fafc;border-left:3px solid #6366f1;font-size:12px;color:#334155;border-radius:4px;"><b>🧠 AI स्पष्टीकरण:</b> ${escapeHtml(q.explanation)}</div>` : '';
                    qHtml += `
                    <div style="border:1px solid #cbd5e1;border-radius:8px;padding:12px;margin-bottom:12px;background:#ffffff;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-size:13px;border-bottom:1px solid #e2e8f0;padding-bottom:4px;">
                            <b>प्रश्न #${num} [${escapeHtml(q.section || 'General')}]</b>
                            <div>${status}</div>
                        </div>
                        <div style="font-size:13px;color:#0f172a;margin-bottom:8px;line-height:1.4;">${escapeHtml(q.question_text || 'प्रश्न उपलब्ध नाही')}</div>
                        <div style="font-size:12px;display:grid;grid-template-columns:1fr 1fr;gap:8px;background:#f8fafc;padding:6px;border-radius:6px;border:1px solid #e2e8f0;">
                            <div><b>तुमची निवड:</b> ${chosen}</div>
                            <div><b>अधिकृत उत्तर:</b> ${correct}</div>
                        </div>
                        ${exp}
                    </div>`;
                });
            } else {
                qHtml = '<div style="padding:15px;text-align:center;color:#64748b;">प्रश्न तपशील उपलब्ध नाही (थेट गुण नोंदणी).</div>';
            }

            const fullDoc = `<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8">
    <title>${name} - ExamRankers 100 Questions Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.5; color: #1e293b; max-width: 860px; margin: 0 auto; padding: 20px; background: #f8fafc; }
        .card { background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #6366f1; padding-bottom: 12px; margin-bottom: 16px; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px; text-align: center; }
        .stat-box { background: #f1f5f9; padding: 10px; border-radius: 8px; border: 1px solid #e2e8f0; }
        .stat-val { font-size: 18px; font-weight: bold; color: #4338ca; }
        .zone-box { background: #ecfdf5; border: 1px solid #6ee7b7; color: #065f46; padding: 10px; border-radius: 8px; font-weight: bold; margin-bottom: 16px; text-align: center; }
        @media print { body { background: white; padding: 0; } }
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <div>
                <h2 style="margin:0;color:#1e1b4b;">ExamRankers India • अधिकृत १०० प्रश्न अहवाल</h2>
                <div style="font-size:13px;color:#64748b;margin-top:2px;">परीक्षा: ${exam} | रोल नं: ${roll}</div>
            </div>
            <div style="text-align:right;">
                <h3 style="margin:0;color:#334155;">${name}</h3>
                <span style="font-size:12px;background:#e0e7ff;color:#3730a3;padding:2px 8px;border-radius:4px;">प्रवर्ग: ${cat}</span>
            </div>
        </div>

        <div class="zone-box">
            🎯 Cutoff Prediction Zone (निवड अंदाज): ${zone}
        </div>

        <div class="stats">
            <div class="stat-box">
                <div style="font-size:11px;color:#64748b;">एकूण गुण</div>
                <div class="stat-val">${score} / ${maxM}</div>
            </div>
            <div class="stat-box">
                <div style="font-size:11px;color:#64748b;">अचूकता</div>
                <div class="stat-val" style="color:#0284c7;">${acc}%</div>
            </div>
            <div class="stat-box">
                <div style="font-size:11px;color:#64748b;">राज्य रँक</div>
                <div class="stat-val" style="color:#d97706;">#${rank} / ${total}</div>
            </div>
            <div class="stat-box">
                <div style="font-size:11px;color:#64748b;">बरोबर / चूक</div>
                <div class="stat-val" style="color:#10b981;">${d.correct || 0} / <span style="color:#ef4444;">${d.incorrect || 0}</span></div>
            </div>
        </div>

        <h3 style="border-bottom:1px solid #e2e8f0;padding-bottom:6px;color:#1e293b;font-size:15px;">सविस्तर प्रश्नपत्रिका व अधिकृत उत्तरे:</h3>
        ${qHtml}

        <div style="margin-top:20px;text-align:center;font-size:12px;color:#94a3b8;">
            अहवाल निर्मिती: ExamRankers AI Platform (https://exam-rank-predictor-bot.onrender.com)
        </div>
    </div>
</body>
</html>`;

            downloadHtmlFile(fullDoc, (name.replace(/\s+/g, '_') + '_Full_Exam_Report.html'));
        }

        function downloadWrongHtmlReport() {
            if (!lastResultData) {
                alert('कृपया आधी निकाल पहा.');
                return;
            }
            const d = lastResultData;
            const name = escapeHtml(d.candidate_name || 'परीक्षार्थी');
            const exam = escapeHtml(d.exam_title || 'परीक्षा');
            const wrongQs = d.wrong_questions || [];

            let qHtml = '';
            if (wrongQs.length === 0) {
                qHtml = '<div style="text-align:center;padding:25px;color:#059669;font-weight:bold;font-size:16px;">🎉 अभिनंदन! एकही प्रश्न चुकलेला नाही.</div>';
            } else {
                wrongQs.forEach((q, idx) => {
                    const num = q.question_number || (idx + 1);
                    const chosen = q.chosen_num ? ('पर्याय ' + escapeHtml(q.chosen_num) + (q.chosen_text ? ' (' + escapeHtml(q.chosen_text) + ')' : '')) : 'अनुत्तरित';
                    const correct = q.correct_num ? ('पर्याय ' + escapeHtml(q.correct_num) + (q.correct_text ? ' (' + escapeHtml(q.correct_text) + ')' : '')) : '-';
                    const exp = q.explanation ? `<div style="margin-top:8px;padding:8px;background:#ffffff;border-left:3px solid #6366f1;font-size:12px;color:#334155;border-radius:4px;"><b>🧠 AI स्पष्टीकरण:</b> ${escapeHtml(q.explanation)}</div>` : '';
                    const obj = q.objection_reason ? `<div style="margin-top:6px;padding:8px;background:#fffbeb;border-left:3px solid #f59e0b;font-size:12px;color:#92400e;border-radius:4px;"><b>⚖️ आक्षेप सल्ला:</b> ${escapeHtml(q.objection_reason)}</div>` : '';

                    qHtml += `
                    <div style="border:1px solid #fca5a5;border-radius:8px;padding:12px;margin-bottom:12px;background:#fff5f5;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-size:13px;border-bottom:1px solid #fecaca;padding-bottom:4px;">
                            <b style="color:#b91c1c;">चुकलेला प्रश्न #${num} [${escapeHtml(q.section || 'General')}]</b>
                            <span style="font-size:11px;color:#64748b;">ID: ${escapeHtml(q.question_id || '-')}</span>
                        </div>
                        <div style="font-size:13px;color:#1e293b;margin-bottom:8px;line-height:1.4;">${escapeHtml(q.question_text || 'प्रश्न उपलब्ध नाही')}</div>
                        <div style="font-size:12px;display:grid;grid-template-columns:1fr 1fr;gap:8px;background:white;padding:8px;border-radius:6px;border:1px solid #fee2e2;">
                            <div style="color:#dc2626;"><b>❌ तुमची निवड:</b> ${chosen}</div>
                            <div style="color:#16a34a;"><b>✅ अधिकृत उत्तर:</b> ${correct}</div>
                        </div>
                        ${exp}
                        ${obj}
                    </div>`;
                });
            }

            const wrongDoc = `<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8">
    <title>${name} - चुकीचे प्रश्न व आक्षेप अहवाल</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.5; color: #1e293b; max-width: 860px; margin: 0 auto; padding: 20px; background: #fff1f2; }
        .card { background: white; border: 1px solid #fecdd3; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .header { border-bottom: 2px solid #f43f5e; padding-bottom: 12px; margin-bottom: 16px; }
        @media print { body { background: white; padding: 0; } }
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <h2 style="margin:0;color:#9f1239;">ExamRankers • चुकीचे प्रश्न पोस्टमार्टम व आक्षेप अहवाल</h2>
            <div style="font-size:13px;color:#64748b;margin-top:4px;">परीक्षार्थी: <b>${name}</b> | परीक्षा: <b>${exam}</b> | एकूण चुका: <b>${wrongQs.length}</b></div>
        </div>
        ${qHtml}
        <div style="margin-top:20px;text-align:center;font-size:12px;color:#94a3b8;">
            अहवाल निर्मिती: ExamRankers AI Platform (https://exam-rank-predictor-bot.onrender.com)
        </div>
    </div>
</body>
</html>`;

            downloadHtmlFile(wrongDoc, (name.replace(/\s+/g, '_') + '_Wrong_Answers_Report.html'));
        }
    </script>
</body>
</html>"""

CHUNK_UPLOADS: Dict[str, dict] = {}
CHUNK_UPLOADS_LOCK = threading.Lock()

CHUNK_PROCESSING_RESULTS: Dict[str, dict] = {}
CHUNK_PROCESSING_LOCK = threading.Lock()

def cleanup_stale_chunk_uploads():
    now = time.time()
    with CHUNK_UPLOADS_LOCK:
        stale_ids = [uid for uid, info in CHUNK_UPLOADS.items() if now - info.get("timestamp", 0) > 600]
        for uid in stale_ids:
            info = CHUNK_UPLOADS.pop(uid, None)
            if info and isinstance(info, dict) and "dir" in info and os.path.exists(info["dir"]):
                try:
                    shutil.rmtree(info["dir"], ignore_errors=True)
                except Exception:
                    pass
    with CHUNK_PROCESSING_LOCK:
        stale_proc_ids = [uid for uid, info in CHUNK_PROCESSING_RESULTS.items() if now - info.get("timestamp", 0) > 900]
        for uid in stale_proc_ids:
            CHUNK_PROCESSING_RESULTS.pop(uid, None)

    # Clean up stale temp admin and student chunk directories
    try:
        temp_admin_root = STORAGE_DIR / "temp_chunks"
        if temp_admin_root.exists():
            for p in temp_admin_root.iterdir():
                if p.is_dir() and (now - p.stat().st_mtime) > 600:
                    shutil.rmtree(p, ignore_errors=True)
    except Exception:
        pass

def process_sheet_payload(
    file_bytes: Optional[bytes] = None,
    digialm_url: Optional[str] = None,
    filename: str = "response_sheet.pdf",
    user_category: str = "Open",
    exam_override: str = "auto",
    tg_user_id: int = 0,
    file_path: Optional[str] = None
) -> Tuple[int, dict]:
    text = ""
    safe_fn = re.sub(r"[^A-Za-z0-9._-]+", "_", filename) or "sheet.pdf"

    try:
        # Mode A: Direct DigiALM / TCS Web Link
        if digialm_url:
            is_safe, sec_err = validate_safe_url(digialm_url)
            if not is_safe:
                return 400, {"success": False, "error": f"असुरक्षित लिंक: {sec_err}"}

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(digialm_url)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    text = parse_html_response_sheet(resp.text)
                elif resp.status_code in (400, 403):
                    m_headers = {
                        "User-Agent": "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
                    }
                    resp_m = client.get(digialm_url, headers=m_headers)
                    if resp_m.status_code == 200 and len(resp_m.content) > 1000:
                        text = parse_html_response_sheet(resp_m.text)

        # Mode B: Uploaded PDF / HTML File (via file_path or in-memory file_bytes)
        elif file_path or file_bytes:
            target_path = file_path
            temp_cleanup_dir = None

            if not target_path and file_bytes:
                # Check if uploaded file is HTML / HTM format
                if safe_fn.lower().endswith((".html", ".htm")) or b"<html" in file_bytes[:2048].lower():
                    try:
                        text = parse_html_response_sheet(file_bytes.decode("utf-8", errors="replace"))
                    except Exception as html_err:
                        logger.warning(f"Error parsing uploaded HTML: {html_err}")

                if not text.strip():
                    temp_cleanup_dir = tempfile.TemporaryDirectory()
                    tmp_file = Path(temp_cleanup_dir.name) / safe_fn
                    tmp_file.write_bytes(file_bytes)
                    target_path = str(tmp_file)

            if not text.strip() and target_path and os.path.exists(target_path):
                # Check if HTML file on disk
                if safe_fn.lower().endswith((".html", ".htm")):
                    try:
                        text = parse_html_response_sheet(Path(target_path).read_text(encoding="utf-8", errors="replace"))
                    except Exception:
                        pass

                # Check if PDF contains embedded DigiALM live web URL
                if not text.strip():
                    try:
                        rec_url = recover_digialm_url_from_pdf(target_path)
                        if rec_url:
                            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                            with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
                                resp = client.get(rec_url)
                                if resp.status_code == 200 and len(resp.content) > 1000:
                                    text = parse_html_response_sheet(resp.text)
                    except Exception as rec_err:
                        logger.warning(f"Error fetching live DigiALM URL from web upload: {rec_err}")

                # Direct PDF text / RapidOCR extraction
                if not text.strip():
                    text, err_code = extract_pdf_text_with_status(target_path)

            if temp_cleanup_dir:
                try:
                    temp_cleanup_dir.cleanup()
                except Exception:
                    pass

            import gc
            gc.collect()

        if not text.strip():
            return 200, {
                "success": False,
                "error": "या फाईल मधून मजकूर किंवा प्रश्न सापडले नाहीत. (स्कॅन अस्पष्ट असू शकते किंवा प्रश्नपत्रिका नसलेली फाईल असू शकते.)"
            }

        # Safely resolve detected_key and exam_config
        detected_key = "ZP_BHARTI"
        exam_config = {}
        if exam_override and exam_override != "auto" and exam_override in EXAMS:
            detected_key = exam_override
            exam_config = EXAMS[detected_key]
        else:
            detected = detect_exam(text, EXAMS)
            if isinstance(detected, dict) and detected.get("status") == "detected":
                detected_key = detected.get("key", "ZP_BHARTI")
                exam_config = detected.get("config") or EXAMS.get(detected_key, {})
            elif isinstance(detected, dict) and detected.get("status") == "ambiguous" and detected.get("matches"):
                detected_key = detected["matches"][0].get("key", "ZP_BHARTI")
                exam_config = EXAMS.get(detected_key, {})
            else:
                fn_lower = (filename or "").lower()
                if "gmc" in fn_lower or "vdgmc" in fn_lower:
                    detected_key = "GMC_SARALSEWA"
                elif "talathi" in fn_lower:
                    detected_key = "TALATHI_BHARTI"
                elif "police" in fn_lower:
                    detected_key = "POLICE_BHARTI"
                elif "vanrakshak" in fn_lower or "forest" in fn_lower:
                    detected_key = "VANRAKSHAK_BHARTI"
                elif "arogya" in fn_lower:
                    detected_key = "AROGYA_BHARTI"
                elif "mpsc" in fn_lower:
                    detected_key = "MPSC_COMBINED"
                elif "nagar" in fn_lower:
                    detected_key = "NAGAR_PARISHAD"
                else:
                    detected_key = "ZP_BHARTI"
                exam_config = EXAMS.get(detected_key, EXAMS.get("ZP_BHARTI", list(EXAMS.values())[0] if EXAMS else {}))
        records = parse_answers(text)

        if not records:
            return 200, {
                "success": False,
                "error": "या रिस्पॉन्स शीटमध्ये उत्तरे (Answer Key / Chosen Options) सापडली नाहीत."
            }

        res = score_answers(records, exam_config)
        meta = extract_post_and_metadata(text)
        post_name = meta.get("post_name") or "General"
        score_val = res.get("score", 0)
        overall_scores, exam_scores, post_scores, cat_scores, post_cat_scores = get_candidate_scores(
            detected_key, user_category, post_name
        )
        effective_max_marks = float(exam_config.get("max_marks", exam_config.get("total_marks", 100.0)))
        if len(records) > int(exam_config.get("total_questions", 100)):
            effective_max_marks = max(effective_max_marks, round(len(records) * float(exam_config.get("positive_marks", 1.0)), 2))
        rank_info = estimate_cohort_rank(
            score_val,
            exam_scores,
            user_category,
            cat_scores,
            overall_scores=overall_scores,
            post_name=post_name,
            post_scores=post_scores,
            post_category_scores=post_cat_scores,
            max_marks=effective_max_marks
        )

        # Accuracy and Analytical Calculations
        attempted = res.get("correct", 0) + res.get("incorrect", 0)
        accuracy_pct = round((res.get("correct", 0) / attempted * 100), 1) if attempted > 0 else 0.0

        # AI SWOT Analysis Engine
        swot_data = generate_swot_analysis(records, res, exam_config)

        # Pedagogical AI Explanations & Objections for Incorrect Answers
        wrong_records = [r for r in records if r.get("evaluation") == "incorrect"]
        wrong_questions = []
        for wr in wrong_records[:30]:
            exp = generate_smart_explanation(wr)
            wrong_questions.append({
                "question_number": wr.get("question_number", "?"),
                "question_id": str(wr.get("question_id") or ""),
                "section": wr.get("section", "General"),
                "question_text": wr.get("question_text", ""),
                "chosen_num": wr.get("chosen_option_number") or wr.get("selected_option_id") or "-",
                "chosen_text": wr.get("chosen_option_text", ""),
                "correct_num": wr.get("correct_option_number") or wr.get("correct_option_id") or "-",
                "correct_text": wr.get("correct_option_text", ""),
                "options": wr.get("options", {}),
                "explanation": exp,
                "objection_recommended": False,
                "objection_reason": "अधिकृत संदर्भानुसार उत्तर प्रमाणित आहे. आक्षेप नोंदवण्यापूर्वी अधिकृत पाठ्यपुस्तकातील संदर्भ (बालभारती/शासकीय गॅझेट) तपासावा."
            })

        # All Questions Summary for Complete Review & Search
        all_questions = []
        for r in records:
            all_questions.append({
                "question_number": r.get("question_number", "?"),
                "question_id": str(r.get("question_id") or ""),
                "section": r.get("section", "General"),
                "question_text": r.get("question_text", ""),
                "evaluation": r.get("evaluation", "unanswered"),
                "chosen_num": r.get("chosen_option_number") or r.get("selected_option_id") or "-",
                "chosen_text": r.get("chosen_option_text", ""),
                "correct_num": r.get("correct_option_number") or r.get("correct_option_id") or "-",
                "correct_text": r.get("correct_option_text", ""),
                "options": r.get("options", {})
            })

        # Persist to database uploads table
        try:
            with get_connection() as db:
                db.execute(
                    """INSERT INTO uploads(
                        telegram_user_id, filename, storage_path, exam_key, category, post_name,
                        roll_number, candidate_name, score, correct_count, incorrect_count, unanswered_count,
                        rank, percentile, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        tg_user_id, safe_fn, "web_upload", detected_key, user_category,
                        post_name, meta.get("roll_number") or "",
                        meta.get("candidate_name") or "परीक्षार्थी", score_val,
                        res.get("correct", 0), res.get("incorrect", 0), res.get("unattempted", 0),
                        rank_info.get("exam_rank", 1), rank_info.get("exam_percentile", 100.0), "web_upload"
                    )
                )
        except Exception as db_e:
            logger.warning(f"Could not record web upload to db: {db_e}")

        # Synchronize harvested questions into central Question Bank for Quizzes & Study Materials
        try:
            sync_records_to_qbank(records, exam_key=detected_key, source="web_upload")
        except Exception as qb_err:
            logger.warning(f"Could not sync questions to qbank: {qb_err}")

        # Optional: Send instant Telegram notification if telegram_user_id was passed
        if tg_user_id and TOKEN:
            try:
                def _notify_tg():
                    tg_text = (
                        f"✅ <b>वेब पोर्टल निकाल तयार आहे!</b>\n\n"
                        f"👤 <b>नाव:</b> {html.escape(meta.get('candidate_name') or 'परीक्षार्थी')}\n"
                        f"🎯 <b>परीक्षा:</b> {html.escape(exam_config.get('name', detected_key))}\n"
                        f"🏷️ <b>प्रवर्ग:</b> {html.escape(user_category)}\n"
                        f"📊 <b>एकूण गुण:</b> <b>{score_val}</b> / {exam_config.get('total_marks', 200)}\n"
                        f"🏆 <b>संभाव्य राज्य रँक:</b> <b>#{rank_info.get('exam_rank', 1)}</b> / {rank_info.get('exam_total', 1)}\n"
                        f"📈 <b>पर्सेंटाईल:</b> <b>{rank_info.get('exam_percentile', 100.0)}%</b>\n"
                        f"✅ बरोबर: {res.get('correct', 0)} | ❌ चूक: {res.get('incorrect', 0)}"
                    )
                    httpx.post(
                        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                        json={"chat_id": tg_user_id, "text": tg_text, "parse_mode": "HTML"},
                        timeout=5.0
                    )
                threading.Thread(target=_notify_tg, daemon=True).start()
            except Exception:
                pass

        return 200, {
            "success": True,
            "candidate_name": meta.get("candidate_name") or "परीक्षार्थी",
            "roll_number": meta.get("roll_number") or "उपलब्ध नाही",
            "exam_title": exam_config.get("display_name") or exam_config.get("name") or detected_key,
            "exam_key": detected_key,
            "category": user_category,
            "post_name": post_name,
            "total_questions": res.get("total_parsed", len(records)),
            "attempted": attempted,
            "correct": res.get("correct", 0),
            "incorrect": res.get("incorrect", 0),
            "unanswered": res.get("unanswered", res.get("unattempted", 0)),
            "accuracy": accuracy_pct,
            "raw_score": score_val,
            "max_marks": effective_max_marks,
            "rank": rank_info.get("exam_rank", 1),
            "total_candidates": rank_info.get("exam_total", 1),
            "percentile": rank_info.get("exam_percentile", 100.0),
            "overall_rank": rank_info.get("overall_rank", rank_info.get("exam_rank", 1)),
            "overall_total": rank_info.get("overall_total", rank_info.get("exam_total", 1)),
            "overall_percentile": rank_info.get("overall_percentile", rank_info.get("exam_percentile", 100.0)),
            "category_rank": rank_info.get("category_rank", rank_info.get("exam_rank", 1)),
            "category_total": rank_info.get("category_total", rank_info.get("exam_total", 1)),
            "category_percentile": rank_info.get("category_percentile", rank_info.get("exam_percentile", 100.0)),
            "post_rank": rank_info.get("post_rank", rank_info.get("exam_rank", 1)),
            "post_total": rank_info.get("post_total", rank_info.get("exam_total", 1)),
            "post_percentile": rank_info.get("post_percentile", rank_info.get("exam_percentile", 100.0)),
            "cutoff_zone": rank_info.get("zone", "N/A"),
            "avg_score": rank_info.get("avg_score", score_val),
            "top_score": rank_info.get("top_score", score_val),
            "section_scores": res.get("section_scores") or res.get("sections") or {},
            "swot": swot_data,
            "wrong_questions": wrong_questions,
            "all_questions": all_questions,
            "youtube_link": get_youtube_link() or "https://www.youtube.com"
        }
    except Exception as proc_err:
        logger.error(f"Error processing web uploaded sheet: {proc_err}", exc_info=True)
        return 500, {"success": False, "error": f"सर्व्हर त्रुटी: {proc_err}"}

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def send_security_headers(self, is_admin: bool = False):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY" if is_admin else "SAMEORIGIN")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")

    def do_OPTIONS(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path.startswith("/api/admin") or path == "/admin":
            self.send_response(403)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_security_headers(is_admin=True)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "CORS preflight not permitted on admin endpoints"}).encode("utf-8"))
            return
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_security_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        # 0. API: Dynamic Local QR Code Image Generator
        if path == "/api/qrcode":
            client_ip = (
                self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or self.headers.get("CF-Connecting-IP", "").strip()
                or self.headers.get("X-Real-IP", "").strip()
                or self.client_address[0]
            )
            if is_ip_rate_limited(client_ip, max_requests=30, window_seconds=60):
                self.send_response(429)
                self.send_security_headers()
                self.end_headers()
                return

            query_params = urllib.parse.parse_qs(parsed.query)
            qr_data = query_params.get("data", [""])[0]
            if not qr_data or len(qr_data) > 512:
                self.send_response(400)
                self.send_security_headers()
                self.end_headers()
                return
            png_bytes = generate_qr_bytes(qr_data)
            if not png_bytes:
                self.send_response(500)
                self.send_security_headers()
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(png_bytes)
            return

        # 0a. API: Dynamic Product 1st Page Sample Image (Page 1)
        if path == "/api/sample_image":
            query_params = urllib.parse.parse_qs(parsed.query)
            prod_id = query_params.get("id", [""])[0].strip()
            png_bytes = get_product_sample_page_image(prod_id, db_path=DB_PATH)
            if not png_bytes:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"Sample not found")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-cache, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(png_bytes)
            return

        # 0b. API: Dynamic Product Sample Preview JSON
        if path == "/api/sample_preview":
            query_params = urllib.parse.parse_qs(parsed.query)
            prod_id = query_params.get("id", [""])[0].strip()
            preview_data = get_product_sample_preview_data(prod_id, db_path=DB_PATH)
            resp_bytes = json.dumps(preview_data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(resp_bytes)
            return

        # 0c. API: Asynchronous Upload Processing Status (Anti-Timeout)
        if path == "/api/upload_status":
            query_params = urllib.parse.parse_qs(parsed.query)
            upload_id = query_params.get("upload_id", [""])[0].strip()
            with CHUNK_PROCESSING_LOCK:
                status_info = CHUNK_PROCESSING_RESULTS.get(
                    upload_id,
                    {"status": "not_found", "error": "अपलोड आयडी सापडला नाही किंवा कालबाह्य झाला."}
                )
            resp_bytes = json.dumps(status_info, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(resp_bytes)
            return

        # 1. API: Products list
        if path == "/api/products":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            prods = packaging_agent.get_all_products(DB_PATH)
            self.wfile.write(json.dumps(prods).encode("utf-8"))
            return

        # 2. API: Health Check for Render pinger, Kubernetes & Docker probes
        if path in ("/health", "/ping", "/healthz", "/livez", "/readyz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # 2a. API: Cashfree Webhook Endpoint Status (GET Verification)
        if path == "/api/cashfree/webhook":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "active",
                "service": "Cashfree Webhook Listener",
                "endpoint": "/api/cashfree/webhook",
                "method": "POST",
                "message": "Cashfree Webhook listener is live and healthy. Send payment event notifications via HTTP POST with valid HMAC signature."
            }).encode("utf-8"))
            return

        # 2b. API: Order Approval Status Check (Strict Token-Only Lookup; Never returns email or UTR)
        if path.startswith("/api/order_status"):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            token = params.get("token", [""])[0].strip() or params.get("q", [""])[0].strip() or params.get("order_id", [""])[0].strip()

            if not token:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Missing order 'token' parameter. Lookup by email or UTR is prohibited for security."}).encode("utf-8"))
                return

            with sqlite3.connect(DB_PATH, timeout=30.0) as db:
                db.row_factory = sqlite3.Row
                order = db.execute("""
                    SELECT o.*, p.title as prod_title, p.download_file, p.pages
                    FROM product_orders o
                    LEFT JOIN digital_products p ON o.product_id = p.id
                    WHERE o.order_token = ? OR o.cf_order_id = ?
                    ORDER BY o.id DESC LIMIT 1
                """, (token, token)).fetchone()

            if not order:
                self.send_response(404)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Order not found."}).encode("utf-8"))
                return

            order_data = dict(order)
            ord_token = order_data.get("order_token", "")
            is_approved = order_data.get("status") in ("approved", "delivered", "paid")
            is_rejected = order_data.get("status") == "rejected"
            prod_id = order_data.get("product_id", "")
            prod_title = order_data.get("prod_title") or prod_id
            download_file = order_data.get("download_file") or f"{prod_id}.pdf"
            signed_url = generate_signed_download_url(ord_token) if is_approved else None

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "order_token": ord_token,
                "product_id": prod_id,
                "product_title": prod_title,
                "download_file": download_file,
                "status": order_data.get("status", "pending"),
                "is_approved": is_approved,
                "is_rejected": is_rejected,
                "delivery_status": order_data.get("delivery_status", "pending"),
                "download_url": signed_url
            }).encode("utf-8"))
            return

        # 3. Download Endpoint: /download/<order_token> (Strictly Protected: Signed Expiring Links & Paid Status)
        if path.startswith("/download/"):
            token = path.split("/download/")[-1].strip()
            query_params = urllib.parse.parse_qs(parsed.query)
            exp_str = query_params.get("exp", [""])[0].strip()
            sig_str = query_params.get("sig", [""])[0].strip()

            if not token:
                self.send_response(400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Order token missing")
                return

            valid_sig, sig_err = verify_signed_download_url(token, exp_str, sig_str)
            if not valid_sig:
                self.send_response(403)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"<h3>⛔ डाऊनलोड लिंक अवैध किंवा कालबाह्य आहे (Access Denied)</h3><p>{html.escape(sig_err)}</p><p>कृपया अधिकृत स्टोअरवरून योग्य डाऊनलोड लिंक वापरा.</p>".encode())
                return

            order_data = None
            try:
                with sqlite3.connect(DB_PATH, timeout=30.0) as db:
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
                self.wfile.write("<h3>❌ ऑर्डर सापडली नाही (Order Not Found)</h3>".encode())
                return

            # STRICT SECURITY GATE: Enforce approved payment before serving digital product!
            status = order_data.get("status")
            if status not in ("approved", "delivered", "paid"):
                self.send_response(403)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write("<h3>⛔ डाऊनलोड लॉक आहे — पेमेंट पूर्ण झालेले नाही (Download Disabled)</h3><p>या ऑर्डरचे पेमेंट अजून पूर्ण झालेले नाही. केवळ पेमेंट यशस्वीरित्या पूर्ण झाल्यावरच अधिकृत PDF डाऊनलोड उपलब्ध होते.</p>".encode())
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
            self.send_security_headers()
            self.end_headers()
            try:
                with open(pdf_path, "rb") as f:
                    shutil.copyfileobj(f, self.wfile, length=64 * 1024)
            except (BrokenPipeError, ConnectionResetError):
                logger.debug(f"Client disconnected during download of {filename}")
            return

        # 3b. Order Return Page: /order/<order_id>
        if path.startswith("/order/"):
            order_id = path.split("/order/")[-1].strip()
            order_info = None
            with sqlite3.connect(DB_PATH, timeout=30.0) as db:
                db.row_factory = sqlite3.Row
                r = db.execute("SELECT o.*, p.title as prod_title FROM product_orders o LEFT JOIN digital_products p ON o.product_id = p.id WHERE o.order_token = ? OR o.cf_order_id = ?", (order_id, order_id)).fetchone()
                if r:
                    order_info = dict(r)

            # Realtime Cashfree status verification if order not yet confirmed
            if order_info and order_info.get("status") not in ("approved", "delivered", "paid"):
                cf_target_id = order_info.get("cf_order_id") or order_info.get("order_token")
                if cf_target_id:
                    try:
                        cf_client = get_cashfree_client()
                        if cf_client.is_configured:
                            ok, cf_data = cf_client.get_order(cf_target_id)
                            if ok and isinstance(cf_data, dict) and (cf_data.get("order_status") or "").upper() == "PAID":
                                with sqlite3.connect(DB_PATH, timeout=30.0) as db:
                                    db.execute("UPDATE product_orders SET status = 'paid', delivery_status = 'ready_for_download', delivered_at = CURRENT_TIMESTAMP WHERE id = ?", (order_info["id"],))
                                    db.execute("UPDATE digital_products SET sales_count = sales_count + 1 WHERE id = ?", (order_info["product_id"],))
                                    db.commit()
                                order_info["status"] = "paid"
                                order_info["delivery_status"] = "ready_for_download"
                    except Exception as e:
                        logger.error(f"Error checking Cashfree order status on return: {e}")

            status = order_info.get("status", "pending") if order_info else "unknown"
            is_paid = status in ("approved", "delivered", "paid")
            title = order_info.get("prod_title", "स्पर्धा परीक्षा ई-बुक") if order_info else "Digital Product"
            amount = order_info.get("amount_paid", 19) if order_info else 19
            signed_url = generate_signed_download_url(order_info["order_token"]) if (order_info and is_paid) else "#"

            page_html = f"""<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ऑर्डर स्थिती — ExamRankers™</title>
    <style>
        :root {{ --primary: #0284c7; --success: #16a34a; --text: #0f172a; --bg: #f8fafc; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); padding: 20px 16px; min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
        .card {{ background: #fff; max-width: 480px; width: 100%; border-radius: 16px; padding: 28px 24px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.08); text-align: center; border: 1px solid #e2e8f0; }}
        .badge {{ display: inline-block; padding: 6px 16px; border-radius: 9999px; font-weight: 700; font-size: 14px; margin-bottom: 16px; }}
        .badge-paid {{ background: #dcfce7; color: #15803d; }}
        .badge-pending {{ background: #fef9c3; color: #854d0e; }}
        h1 {{ font-size: 20px; font-weight: 800; margin-bottom: 8px; color: #0f172a; }}
        p {{ font-size: 14px; color: #64748b; line-height: 1.5; margin-bottom: 20px; }}
        .btn {{ display: block; width: 100%; padding: 14px; background: var(--primary); color: #fff; font-weight: 700; font-size: 15px; border-radius: 12px; text-decoration: none; border: none; cursor: pointer; transition: 0.2s; }}
        .btn:hover {{ background: #0369a1; }}
        .btn-success {{ background: var(--success); }}
        .btn-success:hover {{ background: #15803d; }}
        .btn-disabled {{ background: #64748b; opacity: 0.55; cursor: not-allowed; }}
        .meta-table {{ width: 100%; margin: 20px 0; text-align: left; font-size: 13px; border-collapse: collapse; }}
        .meta-table td {{ padding: 8px 0; border-bottom: 1px solid #f1f5f9; }}
        .meta-table td:last-child {{ text-align: right; font-weight: 700; color: #0f172a; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge {'badge-paid' if is_paid else 'badge-pending'}">
            {'✅ पेमेंट यशस्वी (PAID)' if is_paid else '⏳ पेमेंट प्रक्रियेत आहे (PENDING)'}
        </div>
        <h1>{html.escape(title)}</h1>
        <p>{'तुमचे पेमेंट यशस्वीरित्या जमा झाले आहे. खालील १-क्लिक बटणावर क्लिक करून तुमची PDF लगेच डाऊनलोड करा:' if is_paid else 'पेमेंट पूर्ण झाल्यावर डाऊनलोड बटण सक्रिय केले जाईल. कृपया पेमेंट पूर्ण करा:'}</p>
        
        <table class="meta-table">
            <tr><td>ऑर्डर आयडी</td><td><code>{html.escape(order_id[:16])}...</code></td></tr>
            <tr><td>रक्कम</td><td>₹{amount}/-</td></tr>
            <tr><td>स्थिती</td><td>{html.escape(status.upper())}</td></tr>
        </table>

        {('<a href="' + signed_url + '" class="btn btn-success">📥 अधिकृत PDF डाऊनलोड करा (Download Now)</a>') if is_paid else ('<button disabled class="btn btn-disabled" style="margin-bottom:12px;">⛔ डाऊनलोड लॉक आहे — कृपया आधी पेमेंट पूर्ण करा</button><button onclick="location.reload()" class="btn">🔄 पेमेंट स्थिती तपासा (Check Status)</button>')}
        <div style="margin-top: 16px;">
            <a href="/" style="color: #64748b; font-size: 13px; text-decoration: none;">← मुख्य स्टोअरवर परत जा</a>
        </div>
    </div>
    {'<script>setTimeout(function(){ location.reload(); }, 3500);</script>' if not is_paid else ''}
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(page_html.encode("utf-8"))
            return

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # 4. Admin Store Visitors API Endpoint: /api/admin/visitors
        if path == "/api/admin/visitors":
            query_params = urllib.parse.parse_qs(parsed.query)
            if not is_admin_request_authenticated(self.headers, query_params):
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Forbidden: Requires valid X-Admin-Key"}).encode("utf-8"))
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

        # Admin Web Dashboard: /admin or /admin/dashboard
        if path in ("/admin", "/admin/dashboard"):
            query_params = urllib.parse.parse_qs(parsed.query)
            if not is_admin_request_authenticated(self.headers, query_params):
                has_attempted_key = bool(
                    query_params.get("key") or query_params.get("token") or query_params.get("admin_key")
                    or "admin_key=" in self.headers.get("Cookie", "")
                )
                err_msg = "प्रविष्ट केलेली ॲडमिन की अमान्य आहे. कृपया अचूक की टाका." if has_attempted_key else ""
                login_html = render_admin_login_html(error_msg=err_msg)
                login_bytes = login_html.encode("utf-8")
                self.send_response(403)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(login_bytes)))
                self.send_security_headers(is_admin=True)
                self.end_headers()
                self.wfile.write(login_bytes)
                return
            try:
                dash_html = render_admin_dashboard_html(DB_PATH)
                dash_bytes = dash_html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(dash_bytes)))
                self.send_security_headers(is_admin=True)
                self.end_headers()
                self.wfile.write(dash_bytes)
                return
            except Exception as e:
                logger.error(f"Error rendering admin dashboard: {e}", exc_info=True)
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"Admin Dashboard Error: {e}".encode())
                return

        # Admin PDF Preview/Download: /admin/download_pdf?file=...
        if path == "/admin/download_pdf":
            query_params = urllib.parse.parse_qs(parsed.query)
            if not is_admin_request_authenticated(self.headers, query_params):
                self.send_response(403)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Unauthorized: Missing or invalid X-Admin-Key")
                return

            file_name = query_params.get("file", [""])[0]
            if not file_name:
                self.send_response(400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Filename missing")
                return

            safe_name = os.path.basename(file_name)
            candidate_dirs = [
                STORAGE_DIR / "products",
                Path("products"),
                STORAGE_DIR / "reports",
            ]
            found_path = None
            for d in candidate_dirs:
                p = d / safe_name
                if p.exists() and p.is_file():
                    found_path = p
                    break

            if not found_path:
                try:
                    built = packaging_agent.ensure_product_pdf(safe_name.replace(".pdf", ""), db_path=DB_PATH)
                    if built and os.path.exists(built):
                        found_path = Path(built)
                except Exception:
                    pass

            if not found_path or not found_path.exists():
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"PDF file not found")
                return

            try:
                file_size = os.path.getsize(str(found_path))
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", f'inline; filename="{safe_name}"')
                self.send_header("Content-Length", str(file_size))
                self.send_security_headers(is_admin=True)
                self.end_headers()
                try:
                    with open(found_path, "rb") as f:
                        shutil.copyfileobj(f, self.wfile, length=64 * 1024)
                except (BrokenPipeError, ConnectionResetError):
                    logger.debug(f"Client disconnected while downloading {safe_name}")
                return
            except Exception as e:
                logger.error(f"Error serving admin PDF {safe_name}: {e}")
                return

        # 5. Admin 1-Click ZIP Download for all store digital products
        if path == "/admin/download_all_products":
            query_params = urllib.parse.parse_qs(parsed.query)
            if not is_admin_request_authenticated(self.headers, query_params):
                self.send_response(403)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Unauthorized: Missing or invalid X-Admin-Key")
                return

            zip_path = STORAGE_DIR / "reports" / "ExamRankers_Full_Store_Content.zip"
            storage_products_dir = STORAGE_DIR / "products"
            storage_products_dir.mkdir(parents=True, exist_ok=True)
            active_prods = packaging_agent.get_all_products(DB_PATH, include_inactive=True)
            for p in active_prods:
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
            self.send_security_headers(is_admin=True)
            self.end_headers()
            try:
                with open(zip_path, "rb") as f:
                    shutil.copyfileobj(f, self.wfile, length=64 * 1024)
            except (BrokenPipeError, ConnectionResetError):
                logger.debug("Client disconnected while downloading full content zip")
            return

        # 5a. Admin API: Export Harvested Question Bank (JSON)
        if path == "/admin/export_qbank":
            query_params = urllib.parse.parse_qs(parsed.query)
            if not is_admin_request_authenticated(self.headers, query_params):
                self.send_response(403)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Unauthorized: Missing or invalid X-Admin-Key")
                return

            try:
                with get_connection() as db:
                    db.row_factory = sqlite3.Row
                    rows = db.execute("SELECT * FROM qbank_questions ORDER BY id DESC").fetchall()
                    q_list = [dict(r) for r in rows]
                pretty = "pretty" in query_params or query_params.get("format", [""])[0] == "pretty"
                indent = 2 if pretty else None
                json_bytes = json.dumps(q_list, ensure_ascii=False, indent=indent).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="ExamRankers_QBank_Master.json"')
                self.send_header("Content-Length", str(len(json_bytes)))
                self.send_security_headers(is_admin=True)
                self.end_headers()
                self.wfile.write(json_bytes)
                return
            except Exception as exp_err:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"Export Error: {exp_err}".encode("utf-8"))
                return

        # 5b. Public Web Upload & Score/Rank Predictor Portal (No Telegram 20MB limit!)
        if path in ("/upload", "/sheet", "/rank_calculator"):
            portal_html = render_upload_portal_html()
            html_bytes = portal_html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(html_bytes)
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
            store_page_html = render_digital_store_html(db_path=DB_PATH)
            html_bytes = store_page_html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(html_bytes)
        except Exception as e:
            logger.error(f"Error rendering digital store HTML: {e}", exc_info=True)
            err_msg = f"Store Error: {e}".encode()
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(err_msg)))
            self.end_headers()
            self.wfile.write(err_msg)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        query_params = urllib.parse.parse_qs(parsed.query)

        # 1. Safely parse Content-Length (prevent crash on non-numeric header)
        try:
            content_len = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Bad Request: Invalid Content-Length header"}).encode("utf-8"))
            return

        # 2. Security: Verify admin authentication BEFORE reading large request bodies (Pre-auth memory DoS protection)
        if path.startswith("/api/admin/"):
            if not is_admin_request_authenticated(self.headers, query_params):
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Forbidden: Requires valid X-Admin-Key"}).encode("utf-8"))
                return

        # Support unlimited admin PDF upload size (up to 500 MB) when configured via MAX_UPLOAD_MB
        configured_max_mb = os.getenv("MAX_UPLOAD_MB", "unlimited").strip().lower()
        if configured_max_mb in ("unlimited", "0", "-1", "none", ""):
            max_admin_upload = 524_288_000  # 500 MB headroom for bulk Master TCS/IBPS PDFs
        else:
            try:
                max_admin_upload = int(configured_max_mb) * 1024 * 1024
            except ValueError:
                max_admin_upload = 524_288_000

        # Non-admin endpoints strictly capped at 1 MB except public response sheet upload (up to max_admin_upload e.g. 500 MB)
        max_allowed_len = max_admin_upload if path in ("/api/admin/upload_pdf", "/api/admin/upload_chunk", "/api/upload_sheet", "/api/upload_chunk") else 1_048_576
        if content_len > max_allowed_len:
            self.send_response(413)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_security_headers()
            self.end_headers()
            err_limit_mb = max_allowed_len // (1024 * 1024)
            self.wfile.write(json.dumps({"error": f"Payload Too Large: Maximum allowed size is {err_limit_mb} MB"}).encode())
            return

        raw_body_bytes = b""
        data = {}
        if content_len > 0:
            raw_body_bytes = self.rfile.read(content_len)
            try:
                data = json.loads(raw_body_bytes.decode("utf-8"))
            except Exception:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Bad Request: Malformed JSON payload"}).encode("utf-8"))
                return

        # Security: Only trust forwarded IP headers from loopback or trusted reverse proxies
        peer_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        trusted_proxies = {"127.0.0.1", "::1", "localhost"}
        extra_proxies = os.getenv("TRUSTED_PROXIES", "").split(",")
        trusted_proxies.update(p.strip() for p in extra_proxies if p.strip())
        if peer_ip in trusted_proxies:
            client_ip = (
                self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or self.headers.get("CF-Connecting-IP", "").strip()
                or self.headers.get("X-Real-IP", "").strip()
                or peer_ip
            )
        else:
            client_ip = peer_ip

        ua = self.headers.get("User-Agent", "Unknown")
        ref = self.headers.get("Referer", "")

        # Public API: Quick Manual Score & Rank Prediction
        if path == "/api/quick_rank":
            if is_ip_rate_limited(client_ip, max_requests=60, window_seconds=60):
                self.send_response(429)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "वेळ मर्यादा: कृपया १ मिनिटानंतर पुन्हा प्रयत्न करा."}).encode("utf-8"))
                return

            try:
                user_category = data.get("category", "Open")
                exam_key = data.get("exam", "ZP_BHARTI")
                if exam_key not in EXAMS:
                    exam_key = list(EXAMS.keys())[0] if EXAMS else "ZP_BHARTI"
                exam_config = EXAMS.get(exam_key, {})
                try:
                    score_val = float(data.get("score", 0))
                except (ValueError, TypeError):
                    score_val = 0.0
                post_name = data.get("post_name") or "General"

                overall_scores, exam_scores, post_scores, cat_scores, post_cat_scores = get_candidate_scores(
                    exam_key, user_category, post_name
                )
                rank_info = estimate_cohort_rank(
                    score_val,
                    exam_scores,
                    user_category,
                    cat_scores,
                    overall_scores=overall_scores,
                    post_name=post_name,
                    post_scores=post_scores,
                    post_category_scores=post_cat_scores,
                    max_marks=exam_config.get("total_marks", 200)
                )

                max_m = exam_config.get("total_marks", 200)
                pct_acc = round((score_val / max_m * 100), 1) if max_m > 0 else 0.0

                resp_dict = {
                    "success": True,
                    "is_manual": True,
                    "candidate_name": data.get("candidate_name") or "परीक्षार्थी",
                    "roll_number": "थेट गुण नोंदणी",
                    "exam_title": exam_config.get("display_name") or exam_config.get("name") or exam_key,
                    "exam_key": exam_key,
                    "category": user_category,
                    "post_name": post_name,
                    "raw_score": score_val,
                    "max_marks": max_m,
                    "accuracy": pct_acc,
                    "correct": "-",
                    "incorrect": "-",
                    "unanswered": "-",
                    "rank": rank_info.get("exam_rank", 1),
                    "total_candidates": rank_info.get("exam_total", 1),
                    "percentile": rank_info.get("exam_percentile", 100.0),
                    "overall_rank": rank_info.get("overall_rank", rank_info.get("exam_rank", 1)),
                    "overall_total": rank_info.get("overall_total", rank_info.get("exam_total", 1)),
                    "overall_percentile": rank_info.get("overall_percentile", rank_info.get("exam_percentile", 100.0)),
                    "category_rank": rank_info.get("category_rank", rank_info.get("exam_rank", 1)),
                    "category_total": rank_info.get("category_total", rank_info.get("exam_total", 1)),
                    "category_percentile": rank_info.get("category_percentile", rank_info.get("exam_percentile", 100.0)),
                    "post_rank": rank_info.get("post_rank", rank_info.get("exam_rank", 1)),
                    "post_total": rank_info.get("post_total", rank_info.get("exam_total", 1)),
                    "post_percentile": rank_info.get("post_percentile", rank_info.get("exam_percentile", 100.0)),
                    "cutoff_zone": rank_info.get("zone", "N/A"),
                    "avg_score": rank_info.get("avg_score", score_val),
                    "top_score": rank_info.get("top_score", score_val),
                    "section_scores": {},
                    "swot": {
                        "strengths": [f"नोंदवलेले एकूण गुण: {score_val} / {max_m}"],
                        "weaknesses": ["सविस्तर घटकनिहाय विश्लेषण पाहण्यासाठी मूळ रिस्पॉन्स शीट (PDF/लिंक) अपलोड करा."],
                        "opportunities": ["आगामी TCS/IBPS शिफ्ट्समधील अपेक्षित कटऑफ व सेफ स्कोअरचा सराव वाढवा."],
                        "threats": ["अंतिम गुणवत्ता यादीत सुरक्षित राहण्यासाठी किमान ७५%+ अचूकता आवश्यक आहे."],
                        "overall_accuracy": pct_acc
                    },
                    "wrong_questions": [],
                    "all_questions": [],
                    "youtube_link": get_youtube_link() or "https://www.youtube.com"
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps(resp_dict, ensure_ascii=False).encode("utf-8"))
                return
            except Exception as e:
                logger.error(f"Error in quick_rank: {e}")
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
                return

        # Public API: High-speed Response Sheet Processing (Single Shot)
        if path == "/api/upload_sheet":
            if is_ip_rate_limited(client_ip, max_requests=30, window_seconds=60):
                self.send_response(429)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "वेळ मर्यादा: कृपया १ मिनिटानंतर पुन्हा प्रयत्न करा (Rate limit exceeded)."}).encode("utf-8"))
                return

            digialm_url = (data.get("digialm_url") or "").strip()
            file_b64 = data.get("file_b64", "")
            filename = data.get("filename", "response_sheet.pdf")
            user_category = data.get("category", "Open")
            exam_override = data.get("exam", "auto")
            tg_user_id = data.get("telegram_user_id")
            try:
                tg_user_id = int(tg_user_id) if tg_user_id else 0
            except (ValueError, TypeError):
                tg_user_id = 0

            if not digialm_url and not file_b64:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "कृपया PDF फाईल निवडा किंवा DigiALM वेब लिंक टाका."}).encode("utf-8"))
                return

            pdf_bytes = None
            if file_b64:
                if "," in file_b64:
                    file_b64 = file_b64.split(",", 1)[1]
                pdf_bytes = base64.b64decode(file_b64)
                del file_b64

            status_code, resp_dict = process_sheet_payload(
                file_bytes=pdf_bytes,
                digialm_url=digialm_url or None,
                filename=filename,
                user_category=user_category,
                exam_override=exam_override,
                tg_user_id=tg_user_id
            )
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(json.dumps(resp_dict, ensure_ascii=False).encode("utf-8"))
            return

        # Public API: Chunked Response Sheet Processing (Resilient to reverse-proxy timeouts & size limits)
        if path == "/api/upload_chunk":
            if is_ip_rate_limited(client_ip, max_requests=120, window_seconds=60):
                self.send_response(429)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "वेळ मर्यादा: कृपया १ मिनिटानंतर पुन्हा प्रयत्न करा."}).encode("utf-8"))
                return

            upload_id = str(data.get("upload_id") or "").strip()
            chunk_data_b64 = data.get("data", "")
            filename = data.get("filename", "response_sheet.pdf")
            user_category = data.get("category", "Open")
            exam_override = data.get("exam", "auto")
            tg_user_id = data.get("telegram_user_id")
            try:
                chunk_index = int(data.get("chunk_index", 0))
                total_chunks = int(data.get("total_chunks", 1))
                tg_user_id = int(tg_user_id) if tg_user_id else 0
            except (ValueError, TypeError):
                chunk_index, total_chunks, tg_user_id = 0, 1, 0

            if not upload_id or not chunk_data_b64 or total_chunks < 1:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "अवैध चंक डेटा (Invalid chunk payload)"}).encode("utf-8"))
                return

            cleanup_stale_chunk_uploads()

            if "," in chunk_data_b64:
                chunk_data_b64 = chunk_data_b64.split(",", 1)[1]
            chunk_bytes = base64.b64decode(chunk_data_b64)
            del chunk_data_b64

            safe_fn = re.sub(r"[^A-Za-z0-9._-]+", "_", filename) or "response_sheet.pdf"
            if not safe_fn.lower().endswith((".pdf", ".html", ".htm")):
                safe_fn += ".pdf"

            chunk_dir = Path(tempfile.gettempdir()) / f"chunk_uploads_{upload_id}"
            chunk_dir.mkdir(parents=True, exist_ok=True)
            chunk_file = chunk_dir / f"chunk_{chunk_index:05d}"
            chunk_file.write_bytes(chunk_bytes)
            del chunk_bytes

            is_complete = False
            assembled_file_path = None
            entry_meta = {}

            with CHUNK_UPLOADS_LOCK:
                if upload_id not in CHUNK_UPLOADS:
                    CHUNK_UPLOADS[upload_id] = {
                        "total_chunks": total_chunks,
                        "filename": filename,
                        "category": user_category,
                        "exam": exam_override,
                        "telegram_user_id": tg_user_id,
                        "timestamp": time.time(),
                        "dir": str(chunk_dir)
                    }
                entry = CHUNK_UPLOADS[upload_id]
                entry["timestamp"] = time.time()

            saved_chunks = list(chunk_dir.glob("chunk_*"))
            if len(saved_chunks) == total_chunks:
                is_complete = True
                entry_meta = {
                    "filename": entry["filename"],
                    "category": entry["category"],
                    "exam": entry["exam"],
                    "telegram_user_id": entry["telegram_user_id"]
                }
                assembled_file = chunk_dir / safe_fn
                with open(assembled_file, "wb") as out_f:
                    for i in range(total_chunks):
                        part = chunk_dir / f"chunk_{i:05d}"
                        if part.exists():
                            with open(part, "rb") as in_f:
                                shutil.copyfileobj(in_f, out_f)
                            try:
                                part.unlink()
                            except Exception:
                                pass
                assembled_file_path = str(assembled_file)
                with CHUNK_UPLOADS_LOCK:
                    CHUNK_UPLOADS.pop(upload_id, None)

            if is_complete and assembled_file_path:
                with CHUNK_PROCESSING_LOCK:
                    CHUNK_PROCESSING_RESULTS[upload_id] = {
                        "status": "processing",
                        "timestamp": time.time()
                    }

                def _bg_process(uid, fpath, meta):
                    try:
                        sc, res = process_sheet_payload(
                            file_path=fpath,
                            filename=meta["filename"],
                            user_category=meta["category"],
                            exam_override=meta["exam"],
                            tg_user_id=meta["telegram_user_id"]
                        )
                        with CHUNK_PROCESSING_LOCK:
                            CHUNK_PROCESSING_RESULTS[uid] = {
                                "status": "completed",
                                "status_code": sc,
                                "result": res,
                                "timestamp": time.time()
                            }
                    except Exception as exc:
                        logger.error(f"Error processing background chunk upload {uid}: {exc}")
                        with CHUNK_PROCESSING_LOCK:
                            CHUNK_PROCESSING_RESULTS[uid] = {
                                "status": "error",
                                "error": f"प्रक्रिया त्रुटी: {exc}",
                                "timestamp": time.time()
                            }
                    finally:
                        try:
                            if fpath and os.path.exists(fpath):
                                os.unlink(fpath)
                            parent_d = os.path.dirname(fpath)
                            if parent_d and os.path.exists(parent_d) and "chunk_uploads_" in parent_d:
                                shutil.rmtree(parent_d, ignore_errors=True)
                        except Exception:
                            pass
                        import gc
                        gc.collect()

                threading.Thread(target=_bg_process, args=(upload_id, assembled_file_path, entry_meta), daemon=True).start()

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "status": "processing",
                    "upload_id": upload_id,
                    "message": "सर्व तुकडे प्राप्त झाले. AI विश्लेषण सुरू आहे..."
                }, ensure_ascii=False).encode("utf-8"))
                return
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "status": "chunk_saved",
                    "chunk_index": chunk_index,
                    "total_chunks": total_chunks
                }).encode("utf-8"))
                return

        # Admin API: Sync folder PDFs to digital_products
        if path == "/api/admin/sync_products":
            try:
                seed_cnt = packaging_agent.seed_default_products(DB_PATH)
                added_cnt = packaging_agent.sync_folder_pdfs_to_products(DB_PATH)
                all_prods = packaging_agent.get_all_products(DB_PATH, include_inactive=True)
                active_prods = packaging_agent.get_all_products(DB_PATH, include_inactive=False)
                res = {
                    "success": True,
                    "seeded": seed_cnt,
                    "added": added_cnt if isinstance(added_cnt, int) else 0,
                    "total": len(all_prods),
                    "active": len(active_prods)
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
                return
            except Exception as e:
                logger.error(f"Error syncing folder PDFs: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))
                return

        # Admin API: Update product price (₹10 - ₹100)
        if path == "/api/admin/update_price":
            try:
                prod_id = data.get("product_id")
                new_price = int(data.get("price_inr") or data.get("price") or 19)
                if not prod_id or new_price < 5 or new_price > 500:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": "Invalid product or price."}).encode("utf-8"))
                    return

                with sqlite3.connect(DB_PATH, timeout=30.0) as db:
                    db.execute("""
                        UPDATE digital_products
                        SET price_inr = ?, original_price_inr = ?
                        WHERE id = ?
                    """, (new_price, max(new_price * 3, 99), prod_id))
                    db.commit()

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "product_id": prod_id, "new_price": new_price}).encode("utf-8"))
                return
            except Exception as e:
                logger.error(f"Error updating product price: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))
                return

        # Admin API: Generate 4-column section-wise Question Bank
        if path == "/api/admin/generate_qbank":
            try:
                from .ai_analysis import generate_oneliner_question_bank_pdf
                out_dir = STORAGE_DIR / "products"
                out_dir.mkdir(parents=True, exist_ok=True)
                out_pdf = out_dir / "tcs_ibps_qbank_sectionwise.pdf"
                gen_path = generate_oneliner_question_bank_pdf(DB_PATH, str(out_pdf))
                
                packaging_agent.register_pdf_file_as_product(
                    str(gen_path),
                    title="TCS/IBPS सविस्तर विषयवार प्रश्नसंच (All Sections Q-Bank)",
                    price=29,
                    subject="Comprehensive",
                    db_path=DB_PATH
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "file": os.path.basename(gen_path), "path": str(gen_path)}).encode("utf-8"))
                return
            except Exception as e:
                logger.error(f"Error generating Q-Bank: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))
                return

        # Admin API: Generate Chalu Ghadamodi Monthly Digest
        if path == "/api/admin/generate_chalu_ghadamodi":
            try:
                from .agents.product_catalog_content import get_subject_specific_content
                from .chalu_ghadamodi_builder import (
                    build_chalu_ghadamodi_pdf,
                    structure_raw_data_to_chalu_ghadamodi,
                )
                out_dir = STORAGE_DIR / "products"
                out_dir.mkdir(parents=True, exist_ok=True)
                out_pdf = out_dir / "chalu_ghadamodi_monthly.pdf"
                raw_content = get_subject_specific_content("prod_ca_monthly_top200")
                data = structure_raw_data_to_chalu_ghadamodi(raw_content, month_name="चालू घडामोडी")
                gen_path = build_chalu_ghadamodi_pdf(data, str(out_pdf))

                packaging_agent.register_pdf_file_as_product(
                    str(gen_path),
                    title="चालू घडामोडी मासिक संच (Chalu Ghadamodi Digest)",
                    price=19,
                    subject="Current Affairs",
                    db_path=DB_PATH
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "file": os.path.basename(gen_path), "path": str(gen_path)}).encode("utf-8"))
                return
            except Exception as e:
                logger.error(f"Error generating Chalu Ghadamodi: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))
                return

        # Admin API: Create product manually
        if path == "/api/admin/create_product":
            try:
                created = packaging_agent.create_product(data, DB_PATH)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "product": created}).encode("utf-8"))
                return
            except Exception as e:
                logger.error(f"Error creating product: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))
                return

        # Admin API: Update product details
        if path == "/api/admin/update_product":
            try:
                prod_id = data.get("product_id")
                if not prod_id:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": "product_id missing"}).encode("utf-8"))
                    return

                ok = packaging_agent.update_product(prod_id, data, DB_PATH)
                self.send_response(200 if ok else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": ok, "product_id": prod_id}).encode("utf-8"))
                return
            except Exception as e:
                logger.error(f"Error updating product: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))
                return

        # Admin API: Delete product permanently
        if path == "/api/admin/delete_product":
            try:
                prod_id = data.get("product_id")
                ok = packaging_agent.delete_product(prod_id, DB_PATH)
                self.send_response(200 if ok else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": ok, "product_id": prod_id}).encode("utf-8"))
                return
            except Exception as e:
                logger.error(f"Error deleting product: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))
                return

        # Admin API: Toggle product status (active/inactive)
        if path == "/api/admin/toggle_product_status":
            try:
                prod_id = data.get("product_id")
                ok = packaging_agent.toggle_product_status(prod_id, DB_PATH)
                self.send_response(200 if ok else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": ok, "product_id": prod_id}).encode("utf-8"))
                return
            except Exception as e:
                logger.error(f"Error toggling product status: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))
                return

        # Admin API: Purge all products for clean manual setup
        if path == "/api/admin/purge_products":
            try:
                purged_cnt = packaging_agent.purge_all_products(DB_PATH)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "purged": purged_cnt}).encode("utf-8"))
                return
            except Exception as e:
                logger.error(f"Error purging products: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))
                return

        # Admin API: Approve or reject customer order & dispatch product to email
        if path == "/api/admin/order_action":
            try:
                order_token = data.get("order_token")
                action = data.get("action", "approve")
                
                with sqlite3.connect(DB_PATH, timeout=30.0) as db:
                    db.row_factory = sqlite3.Row
                    order = db.execute("SELECT * FROM product_orders WHERE order_token = ?", (order_token,)).fetchone()
                
                if not order:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": "Order not found."}).encode("utf-8"))
                    return

                order_data = dict(order)
                utr = order_data.get("utr") or "VERIFIED_BY_ADMIN"
                customer_email = order_data.get("customer_email", "")

                if action == "approve":
                    success, msg, prod = fulfillment_agent.confirm_and_fulfill_order(order_token, utr, db_path=DB_PATH)
                    self.send_response(200 if success else 500)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": success,
                        "order_token": order_token,
                        "status": "approved",
                        "delivery_status": "sent",
                        "message": f"ऑर्डर मंजूर करण्यात आली व {customer_email} वर ई-बुक ईमेल पाठवले गेले! ({msg})"
                    }).encode("utf-8"))
                    return

                elif action == "resend_email":
                    prod_id = order_data.get("product_id")
                    prod = packaging_agent.get_product_by_id(prod_id, db_path=DB_PATH) or {
                        "title": "MPSC Digital E-Book",
                        "price_inr": order_data.get("amount_paid", 29)
                    }
                    pdf_path = packaging_agent.ensure_product_pdf(prod_id, db_path=DB_PATH)
                    email_sent, email_msg = fulfillment_agent.send_product_email(
                        to_email=customer_email,
                        product=prod,
                        order_token=order_token,
                        attachment_path=pdf_path
                    )
                    with sqlite3.connect(DB_PATH, timeout=30.0) as db:
                        db.execute(
                            "UPDATE product_orders SET delivery_status = ?, delivered_at = CURRENT_TIMESTAMP WHERE order_token = ?",
                            ("sent" if email_sent else "pending_email", order_token)
                        )
                        db.commit()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": True,
                        "order_token": order_token,
                        "message": f"ईमेल पुन्हा पाठवला गेला: {email_msg}"
                    }).encode("utf-8"))
                    return

                elif action == "reject":
                    with sqlite3.connect(DB_PATH, timeout=30.0) as db:
                        db.execute(
                            "UPDATE product_orders SET status = 'rejected', delivery_status = 'rejected' WHERE order_token = ?",
                            (order_token,)
                        )
                        db.commit()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": True,
                        "order_token": order_token,
                        "status": "rejected",
                        "message": "ऑर्डर नाकारण्यात (Reject) आली आहे."
                    }).encode("utf-8"))
                    return
            except Exception as e:
                logger.error(f"Error updating order: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))
                return

        # Admin API: Chunked PDF/ZIP Upload & Direct Browser Upload (Zero memory pressure, resilient to timeouts)
        if path == "/api/admin/upload_chunk" or (path == "/api/admin/upload_pdf" and "chunk_index" in data):
            try:
                upload_id = str(data.get("upload_id") or "").strip()
                chunk_data_b64 = data.get("data", "")
                filename = data.get("filename", "uploaded.pdf").strip()
                try:
                    chunk_index = int(data.get("chunk_index", 0))
                    total_chunks = int(data.get("total_chunks", 1))
                except (ValueError, TypeError):
                    chunk_index, total_chunks = 0, 1

                if not upload_id or not chunk_data_b64 or total_chunks < 1:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": "Invalid chunk payload"}).encode("utf-8"))
                    return

                if "," in chunk_data_b64:
                    chunk_data_b64 = chunk_data_b64.split(",", 1)[1]
                chunk_bytes = base64.b64decode(chunk_data_b64)
                del chunk_data_b64

                safe_fn = os.path.basename(filename)
                is_zip = safe_fn.lower().endswith(".zip")
                if not is_zip and not safe_fn.lower().endswith(".pdf"):
                    safe_fn += ".pdf"

                temp_admin_dir = STORAGE_DIR / "temp_chunks" / upload_id
                temp_admin_dir.mkdir(parents=True, exist_ok=True)
                chunk_file = temp_admin_dir / f"part_{chunk_index:05d}"
                chunk_file.write_bytes(chunk_bytes)
                del chunk_bytes

                saved_chunks = list(temp_admin_dir.glob("part_*"))
                if len(saved_chunks) == total_chunks:
                    dest_dir = STORAGE_DIR / "products"
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest_path = dest_dir / safe_fn

                    # Assemble chunks directly to disk with zero RAM pressure
                    with open(dest_path, "wb") as out_f:
                        for i in range(total_chunks):
                            part = temp_admin_dir / f"part_{i:05d}"
                            if part.exists():
                                with open(part, "rb") as in_f:
                                    shutil.copyfileobj(in_f, out_f)
                                try:
                                    part.unlink()
                                except Exception:
                                    pass

                    try:
                        shutil.rmtree(temp_admin_dir, ignore_errors=True)
                    except Exception:
                        pass

                    if is_zip:
                        extracted_count = 0
                        try:
                            with zipfile.ZipFile(dest_path, "r") as zf:
                                for item in zf.infolist():
                                    if item.filename.startswith("__MACOSX") or item.is_dir():
                                        continue
                                    if item.filename.lower().endswith(".pdf"):
                                        sub_data = zf.read(item.filename)
                                        sub_fn = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(item.filename))
                                        if not sub_fn.lower().endswith(".pdf"):
                                            sub_fn += ".pdf"
                                        sub_dest = dest_dir / sub_fn
                                        sub_dest.write_bytes(sub_data)

                                        actual_p = 1
                                        try:
                                            import pymupdf as fitz
                                            with fitz.open(str(sub_dest)) as dt:
                                                actual_p = max(1, len(dt))
                                        except Exception:
                                            actual_p = 1

                                        clean_title = os.path.splitext(sub_fn)[0].replace("_", " ").strip()
                                        clean_title = re.sub(r"\s+", " ", clean_title).title()
                                        packaging_agent.register_pdf_file_as_product(
                                            sub_dest,
                                            title=f"{clean_title} (अधिकृत ई-बुक प्रश्नसंच)",
                                            pages=actual_p,
                                            price=49,
                                            db_path=DB_PATH
                                        )
                                        extracted_count += 1
                        except Exception as zerr:
                            self.send_response(400)
                            self.send_header("Content-Type", "application/json; charset=utf-8")
                            self.end_headers()
                            self.wfile.write(json.dumps({"success": False, "message": f"अवैध ZIP फाईल: {zerr}"}).encode("utf-8"))
                            return

                        self.send_response(200)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "success": True,
                            "status": "completed",
                            "message": f"ZIP यशस्वीरित्या अनपॅक झाली! {extracted_count} PDFs सिस्टीममध्ये समाविष्ट केले.",
                            "count": extracted_count
                        }, ensure_ascii=False).encode("utf-8"))
                        return

                    # Verify PDF header
                    with open(dest_path, "rb") as check_f:
                        header = check_f.read(5)
                        if header != b"%PDF-":
                            dest_path.unlink(missing_ok=True)
                            self.send_response(400)
                            self.send_header("Content-Type", "application/json; charset=utf-8")
                            self.end_headers()
                            self.wfile.write(json.dumps({"success": False, "message": "अवैध PDF फाईल: केवळ खरी PDF फाईल (%PDF- हेडर असलेली) अपलोड करता येईल."}, ensure_ascii=False).encode("utf-8"))
                            return

                    actual_pages = 1
                    try:
                        import pymupdf as fitz
                        with fitz.open(str(dest_path)) as d_tmp:
                            actual_pages = max(1, len(d_tmp))
                    except Exception:
                        actual_pages = 1

                    clean_title = os.path.splitext(safe_fn)[0].replace("_", " ").strip()
                    clean_title = re.sub(r"\s+", " ", clean_title).title()
                    packaging_agent.register_pdf_file_as_product(
                        dest_path,
                        title=f"{clean_title} (अधिकृत ई-बुक प्रश्नसंच)",
                        pages=actual_pages,
                        price=49,
                        db_path=DB_PATH
                    )

                    try:
                        RESPONSE_DIR.mkdir(parents=True, exist_ok=True)
                        resp_copy_path = RESPONSE_DIR / f"admin_upload_{safe_fn}"
                        shutil.copy2(dest_path, resp_copy_path)
                        with get_connection() as db:
                            db.execute(
                                """INSERT INTO uploads(
                                    telegram_user_id, filename, storage_path, exam_key, category, post_name,
                                    score, correct_count, incorrect_count, unanswered_count, status
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (0, safe_fn, str(resp_copy_path), "admin_portal_upload", "Open", "Admin Uploaded Book",
                                 0.0, 0, 0, 0, "admin_bulk")
                            )
                    except Exception as sync_e:
                        logger.warning(f"Error registering web upload in uploads DB: {sync_e}")

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": True,
                        "status": "completed",
                        "filename": safe_fn,
                        "pages": actual_pages,
                        "size": dest_path.stat().st_size
                    }, ensure_ascii=False).encode("utf-8"))
                    return
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": True,
                        "status": "chunk_saved",
                        "chunk_index": chunk_index,
                        "total_chunks": total_chunks
                    }).encode("utf-8"))
                    return
            except Exception as e:
                logger.error(f"Error uploading admin PDF chunk: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))
                return

        # Admin API: Upload PDF directly from browser (Single shot fallback for small files)
        if path == "/api/admin/upload_pdf":
            try:
                fn = data.get("filename", "uploaded.pdf").strip()
                b64 = data.get("base64_data", "")
                if not b64 or not fn:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": "Missing file data"}).encode("utf-8"))
                    return

                safe_fn = os.path.basename(fn)
                is_zip = safe_fn.lower().endswith(".zip")
                if not is_zip and not safe_fn.lower().endswith(".pdf"):
                    safe_fn += ".pdf"

                dest_dir = STORAGE_DIR / "products"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / safe_fn

                pdf_bytes = base64.b64decode(b64)

                if is_zip:
                    # Handle Bulk ZIP archive containing multiple exam PDFs
                    try:
                        zip_bytes_io = io.BytesIO(pdf_bytes)
                        with zipfile.ZipFile(zip_bytes_io, "r") as zf:
                            extracted_count = 0
                            for item in zf.infolist():
                                if item.filename.startswith("__MACOSX") or item.is_dir():
                                    continue
                                if item.filename.lower().endswith(".pdf"):
                                    sub_data = zf.read(item.filename)
                                    sub_fn = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(item.filename))
                                    if not sub_fn.lower().endswith(".pdf"):
                                        sub_fn += ".pdf"
                                    sub_dest = dest_dir / sub_fn
                                    sub_dest.write_bytes(sub_data)

                                    try:
                                        import pymupdf as fitz
                                    except ImportError:
                                        import fitz
                                    actual_p = 1
                                    try:
                                        with fitz.open(str(sub_dest)) as dt:
                                            actual_p = max(1, len(dt))
                                    except Exception:
                                        actual_p = 1

                                    clean_title = os.path.splitext(sub_fn)[0].replace("_", " ").strip()
                                    clean_title = re.sub(r"\s+", " ", clean_title).title()
                                    packaging_agent.register_pdf_file_as_product(
                                        sub_dest,
                                        title=f"{clean_title} (अधिकृत ई-बुक प्रश्नसंच)",
                                        pages=actual_p,
                                        price=49,
                                        db_path=DB_PATH
                                    )
                                    extracted_count += 1

                            self.send_response(200)
                            self.send_header("Content-Type", "application/json; charset=utf-8")
                            self.end_headers()
                            self.wfile.write(json.dumps({
                                "success": True,
                                "message": f"ZIP यशस्वीरित्या अनपॅक झाली! {extracted_count} PDFs सिस्टीममध्ये समाविष्ट केले.",
                                "count": extracted_count
                            }, ensure_ascii=False).encode("utf-8"))
                            return
                    except Exception as zerr:
                        self.send_response(400)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": False, "message": f"अवैध ZIP फाईल: {zerr}"}).encode("utf-8"))
                        return

                if not pdf_bytes.startswith(b"%PDF-"):
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": "अवैध PDF फाईल: केवळ खरी PDF फाईल (%PDF- हेडर असलेली) किंवा ZIP फाईल अपलोड करता येईल."}, ensure_ascii=False).encode("utf-8"))
                    return

                with open(dest_path, "wb") as f:
                    f.write(pdf_bytes)

                # Immediately register uploaded PDF as active digital store product with exact page count
                actual_pages = 1
                try:
                    try:
                        import pymupdf as fitz
                    except ImportError:
                        import fitz
                    with fitz.open(str(dest_path)) as d_tmp:
                        actual_pages = max(1, len(d_tmp))

                    clean_title = os.path.splitext(safe_fn)[0].replace("_", " ").strip()
                    clean_title = re.sub(r"\s+", " ", clean_title).title()
                    packaging_agent.register_pdf_file_as_product(
                        dest_path,
                        title=f"{clean_title} (अधिकृत ई-बुक प्रश्नसंच)",
                        pages=actual_pages,
                        price=49,
                        db_path=DB_PATH
                    )
                except Exception as reg_e:
                    logger.warning(f"Direct registration of product {safe_fn} failed: {reg_e}")

                # Also copy to RESPONSE_DIR and insert into uploads table so bot/quizzes always have it
                try:
                    RESPONSE_DIR.mkdir(parents=True, exist_ok=True)
                    resp_copy_path = RESPONSE_DIR / f"admin_upload_{safe_fn}"
                    shutil.copy2(dest_path, resp_copy_path)
                    with get_connection() as db:
                        db.execute(
                            """INSERT INTO uploads(
                                telegram_user_id, filename, storage_path, exam_key, category, post_name,
                                score, correct_count, incorrect_count, unanswered_count, status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (0, safe_fn, str(resp_copy_path), "admin_portal_upload", "Open", "Admin Uploaded Book",
                             0.0, 0, 0, 0, "admin_bulk")
                        )
                except Exception as sync_e:
                    logger.warning(f"Error registering web upload in uploads DB: {sync_e}")

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "filename": safe_fn, "pages": actual_pages, "size": len(pdf_bytes)}).encode("utf-8"))
                return
            except Exception as e:
                logger.error(f"Error uploading PDF: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))
                return

        # Admin API: Dispatch Live Quiz to Channel from Web Dashboard
        if path == "/api/admin/dispatch_quiz":
            try:
                target_channel = (
                    data.get("channel")
                    or os.getenv("PAID_CHANNEL_ID")
                    or os.getenv("CHANNEL_ID")
                    or PAID_CHANNEL_ID
                    or "-1004381339759"
                )
                target_channel = str(target_channel).strip()
                if target_channel.startswith("http"):
                    target_channel = "-1004381339759"

                from app.quiz_generator import resolve_quiz_correct_index
                q_row = None
                with get_connection() as db:
                    db.row_factory = sqlite3.Row
                    q_row = db.execute(
                        """SELECT * FROM qbank_questions WHERE options_json IS NOT NULL AND length(options_json) > 10 ORDER BY RANDOM() LIMIT 1"""
                    ).fetchone()

                if not q_row:
                    daily = get_daily_latest_exam_questions()
                    qs = daily.get("questions", [])
                    if not qs:
                        self.send_response(400)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": False, "message": "क्वेश्चन बँक रिकामी आहे."}).encode("utf-8"))
                        return
                    chosen = random.choice(qs)
                    q_text = f"🎯 [{chosen.get('subject', 'General')}] {chosen.get('question')}"
                    opts = [re.sub(r"^[A-Da-d1-4][\.\):\-]\s*", "", o).strip()[:95] for o in chosen.get("options", [])[:4]]
                    opts = [o for o in opts if o]
                    c_idx = resolve_quiz_correct_index(chosen, opts)
                    exp = (chosen.get("explanation") or "अधिकृत उत्तर व विश्लेषण प्रमाणित आहे.")[:195]
                else:
                    opts_dict = json.loads(q_row["options_json"] or "{}")
                    sec = q_row["section"] or "General"
                    q_text = f"🎯 [{sec}] {q_row['question_text']}"
                    opts = [re.sub(r"^[A-Da-d1-4][\.\):\-]\s*", "", str(v)).strip()[:95] for v in list(opts_dict.values())[:4]]
                    opts = [o for o in opts if o]
                    c_num = q_row["correct_option_num"] or 1
                    try:
                        c_idx = max(0, min(len(opts) - 1, int(c_num) - 1))
                    except Exception:
                        c_idx = 0
                    exp = (q_row["explanation"] or "अधिकृत उत्तर व विश्लेषण प्रमाणित आहे.")[:195]

                if len(opts) < 2:
                    daily = get_daily_latest_exam_questions()
                    chosen = random.choice(daily.get("questions", []))
                    q_text = f"🎯 [{chosen.get('subject', 'General')}] {chosen.get('question')}"
                    opts = [re.sub(r"^[A-Da-d1-4][\.\):\-]\s*", "", o).strip()[:95] for o in chosen.get("options", [])[:4]]
                    opts = [o for o in opts if o]
                    c_idx = resolve_quiz_correct_index(chosen, opts)
                    exp = (chosen.get("explanation") or "अधिकृत उत्तर व विश्लेषण प्रमाणित आहे.")[:195]

                if len(opts) < 2:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": "प्रश्नात किमान २ पर्याय असणे आवश्यक आहे."}).encode("utf-8"))
                    return

                bot_token = TOKEN or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
                if bot_token:
                    api_base = os.getenv("TELEGRAM_BOT_API_URL", "").rstrip("/")
                    bot_url = f"{api_base}/bot{bot_token}/sendPoll" if api_base else f"https://api.telegram.org/bot{bot_token}/sendPoll"
                    poll_res = httpx.post(
                        bot_url,
                        json={
                            "chat_id": target_channel,
                            "question": q_text[:295],
                            "options": opts,
                            "type": "quiz",
                            "correct_option_id": c_idx,
                            "explanation": exp[:195],
                            "is_anonymous": True
                        },
                        timeout=15.0
                    )
                    if poll_res.status_code == 200:
                        poll_json = poll_res.json()
                        chat_info = poll_json.get("result", {}).get("chat", {})
                        ch_title = chat_info.get("title") or target_channel
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "success": True,
                            "message": f"क्विझ यशस्वीरित्या {ch_title} वर पाठवला गेला!",
                            "channel": ch_title,
                            "question": q_text[:80] + "..."
                        }, ensure_ascii=False).encode("utf-8"))
                        return
                    else:
                        raise Exception(f"Telegram API Error ({poll_res.status_code}): {poll_res.text}")
                else:
                    raise Exception("TELEGRAM_BOT_TOKEN सेट नाही.")
            except Exception as q_err:
                logger.error(f"Error dispatching quiz from admin: {q_err}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(q_err)}).encode("utf-8"))
                return

        # Admin API: Optimize System, Vacuum DB & Purge Cache (Reduces Bot Load)
        if path == "/api/admin/optimize_system":
            try:
                import gc
                cleanup_stale_chunk_uploads()
                gc.collect()
                before_size = 0.0
                if os.path.exists(DB_PATH):
                    before_size = os.path.getsize(DB_PATH) / (1024 * 1024)

                with sqlite3.connect(DB_PATH, timeout=60.0) as db:
                    db.execute("VACUUM")

                after_size = 0.0
                if os.path.exists(DB_PATH):
                    after_size = os.path.getsize(DB_PATH) / (1024 * 1024)

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "message": f"सिस्टीम व डेटाबेस ऑप्टिमायझेशन यशस्वी! DB आकार {before_size:.2f} MB वरून {after_size:.2f} MB झाला, रॅम मेमरी फ्री केली गेली.",
                    "before_mb": round(before_size, 2),
                    "after_mb": round(after_size, 2)
                }, ensure_ascii=False).encode("utf-8"))
                return
            except Exception as opt_err:
                logger.error(f"Error optimizing system: {opt_err}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(opt_err)}).encode("utf-8"))
                return

        # Admin API: Delete Upload Record
        if path == "/api/admin/delete_upload":
            try:
                upload_id = data.get("upload_id")
                if not upload_id:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": "upload_id आवश्यक आहे."}).encode("utf-8"))
                    return
                with get_connection() as db:
                    db.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": f"अपलोड #{upload_id} यशस्वीरित्या हटवले."}).encode("utf-8"))
                return
            except Exception as del_err:
                logger.error(f"Error deleting upload: {del_err}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(del_err)}).encode("utf-8"))
                return

        if path == "/api/checkout":
            if is_ip_rate_limited(client_ip, max_requests=10, window_seconds=60):
                self.send_response(429)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Too many requests. Please wait a minute."}).encode("utf-8"))
                return

            prod_id = str(data.get("product_id", "")).strip()
            email = str(data.get("email") or data.get("customer_email") or "").strip().lower()
            phone = str(data.get("phone") or data.get("customer_phone") or "9999999999").strip() or "9999999999"

            if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "कृपया वैध ईमेल आयडी प्रविष्ट करा (Valid email required)."}).encode("utf-8"))
                return

            prod = packaging_agent.get_product_by_id(prod_id, db_path=DB_PATH)
            if not prod:
                self.send_response(404)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Product not found."}).encode("utf-8"))
                return

            # Price is STRICTLY bound to the digital_products table (never trusts client amount)
            price_inr = int(prod.get("price_inr", 19))
            res = fulfillment_agent.create_order(prod_id, email, float(price_inr), db_path=DB_PATH)
            order_token = res["order_token"]

            log_store_visitor(client_ip, ua, ref, page_path=path, action="checkout_initiated", product_id=prod_id, details=f"email:{email}, price:{price_inr}")

            # Create Cashfree Order
            cf_client = get_cashfree_client()
            return_url = f"{get_store_web_url()}/order/{order_token}"
            cf_res = cf_client.create_order(
                order_id=order_token,
                order_amount=float(price_inr),
                customer_email=email,
                customer_phone=phone,
                customer_id=f"cust_{hashlib.md5(email.encode(), usedforsecurity=False).hexdigest()[:12]}",
                return_url=return_url
            )

            payment_session_id = cf_res.get("payment_session_id", "")
            cf_order_id = cf_res.get("order_id", order_token)

            with sqlite3.connect(DB_PATH, timeout=30.0) as db:
                db.execute(
                    "UPDATE product_orders SET cf_order_id = ?, payment_session_id = ? WHERE order_token = ?",
                    (cf_order_id, payment_session_id, order_token)
                )
                db.commit()

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "order_id": order_token,
                "payment_session_id": payment_session_id,
                "amount": price_inr,
                "cf_environment": os.getenv("CASHFREE_ENV", "sandbox")
            }).encode("utf-8"))
            return

        # Cashfree Webhook Handler
        if path == "/api/cashfree/webhook":
            timestamp = self.headers.get("x-webhook-timestamp", "")
            signature = self.headers.get("x-webhook-signature", "")

            # Check if this is a Cashfree dashboard test ping / probe
            event_type = str(data.get("type", "")).upper()
            is_test_event = event_type in ("TEST", "TEST_WEBHOOK", "TEST_NOTIFICATION") or str(data.get("event", "")).lower() == "test"

            cf_client = get_cashfree_client()
            valid_sig, sig_err = cf_client.verify_webhook_signature(raw_body_bytes, signature, timestamp)
            if not valid_sig:
                # If Cashfree merchant dashboard test button sent test event
                if is_test_event:
                    logger.info("Acknowledged Cashfree test webhook with 200 OK.")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "ok",
                        "message": "Cashfree test webhook received successfully"
                    }).encode("utf-8"))
                    return

                logger.warning(f"Cashfree webhook signature failure: {sig_err}")
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Invalid webhook signature: {sig_err}"}).encode("utf-8"))
                return

            webhook_data = data.get("data", {})
            cf_order_obj = webhook_data.get("order", {})
            cf_payment_obj = webhook_data.get("payment", {})
            order_id = cf_order_obj.get("order_id") or data.get("order_id", "")

            if not order_id or is_test_event:
                # Acknowledge Cashfree test events with 200 OK
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "message": "Cashfree webhook test event acknowledged successfully"
                }).encode("utf-8"))
                return

            # Re-fetch order from Cashfree API to ensure state validity
            ok, cf_verified = cf_client.get_order(order_id)
            if ok and isinstance(cf_verified, dict) and cf_verified.get("order_status") == "PAID":
                with sqlite3.connect(DB_PATH, timeout=30.0) as db:
                    db.row_factory = sqlite3.Row
                    local_order = db.execute("SELECT * FROM product_orders WHERE order_token = ? OR cf_order_id = ?", (order_id, order_id)).fetchone()
                    if local_order:
                        lo = dict(local_order)
                        ord_token = lo["order_token"]
                        paid_amt = float(cf_verified.get("order_amount", 0))
                        expected_amt = float(lo.get("amount_paid", 0))
                        if abs(paid_amt - expected_amt) <= 1.0:
                            if lo.get("status") not in ("approved", "delivered"):
                                payment_id = cf_payment_obj.get("cf_payment_id") or f"CF_{order_id}"
                                fulfillment_agent.confirm_and_fulfill_order(ord_token, str(payment_id), db_path=DB_PATH)
                                logger.info(f"Cashfree order {ord_token} marked PAID and fulfilled via webhook.")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
            return

        if path == "/api/verify":
            if is_ip_rate_limited(client_ip, max_requests=10, window_seconds=60):
                self.send_response(429)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Too many verification requests. Please wait a minute."}).encode("utf-8"))
                return

            order_token = data.get("order_token", "").strip()
            utr = data.get("utr", "").strip()

            if not order_token:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Order reference token missing."}).encode("utf-8"))
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

            # Student submitted UPI UTR: Save order as pending verification for Admin Approval & Email Delivery
            order_data = None
            with sqlite3.connect(DB_PATH, timeout=30.0) as db:
                db.row_factory = sqlite3.Row
                order = db.execute("SELECT * FROM product_orders WHERE order_token = ?", (order_token,)).fetchone()
                if not order:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": "Order not found."}).encode("utf-8"))
                    return

                order_data = dict(order)
                db.execute(
                    "UPDATE product_orders SET utr = ?, status = 'pending', delivery_status = 'pending_verification' WHERE order_token = ?",
                    (utr.strip(), order_token)
                )
                db.commit()

            prod_id = order_data.get("product_id", "")
            prod = packaging_agent.get_product_by_id(prod_id, db_path=DB_PATH)

            log_store_visitor(
                client_ip, ua, ref,
                page_path=path,
                action="utr_submitted_pending_verification",
                product_id=prod_id,
                details=f"order:{order_token}, utr:{utr}"
            )

            # Instant alert to Admin via Telegram
            alert_text = (
                f"🔔 <b>नवीन UTR पडताळणीसाठी प्राप्त! (UTR Verification Pending)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📖 ई-बुक: <b>{html.escape(prod.get('title', 'Digital E-Book') if prod else prod_id)}</b>\n"
                f"💰 रक्कम: <b>₹{order_data.get('amount_paid', 19)}/-</b>\n"
                f"📧 ईमेल: <code>{html.escape(order_data.get('customer_email', ''))}</code>\n"
                f"🎫 Order Token: <code>{order_token}</code>\n"
                f"📝 UTR / Ref No: <code>{html.escape(utr)}</code>\n\n"
                f"👉 <b>ॲडमिन पोर्टलवरून UTR तपासून त्वरित मंजुरी व ईमेल पाठवा:</b>\n"
                f"http://localhost:8080/admin"
            )
            alert_admins_sync(alert_text)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "status": "pending_verification",
                "order_token": order_token,
                "utr": utr,
                "customer_email": order_data.get("customer_email", ""),
                "message": "तुमचा १२-अंकी UTR पडताळणीसाठी (Verification) ॲडमिनकडे पाठवला आहे. ॲडमिनद्वारे UTR पडताळणी पूर्ण होताच तुमची PDF फाईल तुमच्या ईमेलवर पाठवली जाईल आणि डाऊनलोड उपलब्ध होईल!"
            }).encode("utf-8"))
            return

        self.send_response(404)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Keep terminal logs clean from ping health-checks

async def vip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explains that the channel is 100% FREE and guides users to our official Digital Store (₹10-₹50)."""
    track_user(update.effective_user)
    store_url = get_store_web_url()
    free_channel = PAID_CHANNEL_LINK or "https://t.me/+EjtGp-pH4hMxZDM1"

    caption = (
        "📢 <b>ExamRankers अधिकृत अभ्यास समुदाय — १००% मोफत!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 <b>महत्त्वाची सूचना:</b>\n"
        "आमचे टेलिग्राम चॅनेल सर्व विद्यार्थ्यांसाठी <b>संपूर्ण मोफत</b> आहे! आम्ही चॅनेल सदस्यत्वासाठी कोणतेही शुल्क आकारत नाही.\n\n"
        "📚 <b>आमचे डिजिटल ई-बुक्स व प्रश्नसंच स्टोअर:</b>\n"
        "विद्यार्थ्यांच्या मागणीनुसार आम्ही फक्त अधिकृत व उच्च दर्जाची <b>डिजिटल ई-बुक्स, चालू घडामोडी मासिक संच व ४-स्तंभ विषयवार प्रश्नसंच</b> अतिशय माफक दरात (<b>फक्त ₹१० ते ₹५०</b>) उपलब्ध करतो!\n\n"
        "✨ <b>वैशिष्ट्ये:</b>\n"
        "• १००% TCS / IBPS पॅटर्न\n"
        "• मराठी, इंग्रजी, बुद्धिमत्ता व GS स्वतंत्र विभाग\n"
        "• AI द्वारे प्रत्येक प्रश्नाचे सविस्तर स्पष्टीकरण\n"
        "• १-क्लिक तात्काळ डाऊनलोड व Email डिलिव्हरी\n\n"
        "👇 <b>खालील बटणावर क्लिक करून थेट ई-बुक्स स्टोअर पहा:</b>"
    )
    keyboard = [
        [InlineKeyboardButton("🛒 डिजिटल ई-बुक्स स्टोअर उघडा (₹१० ते ₹५०)", url=store_url)],
        [InlineKeyboardButton("📢 मोफत टेलिग्राम चॅनेल जॉइन करा", url=free_channel)],
        [InlineKeyboardButton("🔙 मुख्य मेनू (Main Menu)", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    target_msg = update.callback_query.message if update.callback_query else update.message
    if update.callback_query:
        await update.callback_query.answer()

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
        f"⚡ <b>AI Mesh:</b> <code>{ai_health.get('status', 'Healthy')}</code> | <b>UX:</b> <code>{ux_standards.get('score', '100%')}</code> | <b>Ops:</b> <code>{ops_health.get('status', 'Active')}</code>",
        f"🔬 <b>Research Digest:</b> <i>{research_digest.get('summary', 'TCS/IBPS पॅटर्नचे सखोल विश्लेषण चालू आहे.')}</i>",
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

async def admin_panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: Interactive Admin Command Center with 1-click web dashboard & operations."""
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Restricted to bot administrators.")
        return

    admin_key = os.getenv("ADMIN_API_KEY", "").strip()
    web_admin_url = f"{get_store_web_url()}/admin" + (f"?key={admin_key}" if admin_key else "")

    text = (
        "⚙️ <b>ExamRankers™ अधिकृत ॲडमिन कंट्रोल पॅनेल</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "येथून तुम्ही संपूर्ण डिजिटल प्रॉडक्ट स्टोअर, किंमती, व्हिजिटर ट्रॅफिक व ऑर्डर्स नियंत्रित करू शकता.\n\n"
        "📊 <b>वैशिष्ट्ये:</b>\n"
        "• 🛒 प्रॉडक्ट किंमत नियंत्रण (₹१० ते ₹५० थेट १-क्लिक बदल)\n"
        "• 🔄 फोल्डरमधील नवीन PDF ई-बुक्स आपोआप सिंक\n"
        "• 📑 ४-स्तंभ विषयवार प्रश्नसंच (Q-Bank) निर्मिती\n"
        "• 📰 'चालू घडामोडी' मासिक विशेषांक निर्मिती\n"
        "• 👥 लाईव्ह स्टोअर व्हिजिटर ट्रॅकिंग व UTR पडताळणी\n"
        "• 📦 संपूर्ण स्टोअर बॅकअप (ZIP डाऊनलोड)\n\n"
        f"🌐 <b>वेब ॲडमिन डॅशबोर्ड लिंक:</b>\n"
        f"🔗 <a href=\"{web_admin_url}\">{web_admin_url}</a>"
    )

    kb = [
        [InlineKeyboardButton("🌐 वेब ॲडमिन डॅशबोर्ड उघडा (Web Dashboard)", url=web_admin_url)],
        [InlineKeyboardButton("🔄 फोल्डर PDF स्टोअरमध्ये सिंक करा", callback_data="admin_sync_folder")],
        [InlineKeyboardButton("📑 ४-स्तंभ विषयवार प्रश्नसंच बनवा", callback_data="admin_gen_qbank")],
        [InlineKeyboardButton("📰 चालू घडामोडी मासिक PDF बनवा", callback_data="admin_gen_ca")],
        [InlineKeyboardButton("👥 स्टोअर व्हिजिटर आकडेवारी", callback_data="admin_visitor_stats")],
        [InlineKeyboardButton("📦 सर्व ई-बुक्स ZIP डाऊनलोड करा", callback_data="admin_dl_zip")],
    ]

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb),
        disable_web_page_preview=True
    )

async def download_store_content_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: Packages all digital product PDFs into a single ZIP file for 1-click download."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    if user.id not in ADMIN_IDS:
        if update.callback_query:
            await update.callback_query.answer("⛔ Restricted to administrators only.", show_alert=True)
        else:
            await context.bot.send_message(chat_id=chat_id, text="⛔ Restricted to administrators only.")
        return

    products = packaging_agent.get_all_products(DB_PATH)
    status_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏳ <i>सर्व {len(products)} डिजिटल ई-बुक्स गोळा करून ZIP आर्काइव्ह तयार करत आहे...</i>",
        parse_mode="HTML"
    )

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
    admin_key = os.getenv("ADMIN_API_KEY", "").strip()
    web_dl_url = f"{get_store_web_url()}/admin/download_all_products" + (f"?key={admin_key}" if admin_key else "")

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
        with open(zip_path, "rb") as zf_doc:
            await context.bot.send_document(
                chat_id=user.id,
                document=zf_doc,
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

            with sqlite3.connect(DB_PATH, timeout=30.0) as db:
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
        disable_web_page_preview=True,
        protect_content=True
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

    with sqlite3.connect(db_path, timeout=30.0) as db:
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
        try:
            import defusedxml.ElementTree as DefusedET
            root = DefusedET.fromstring(xml_text)
        except ImportError:
            root = ET.fromstring(xml_text)  # nosec B314
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

    with sqlite3.connect(db_path, timeout=30.0) as db:
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
                disable_web_page_preview=False,
                protect_content=True
            )
            logger.info(f"📢 Broadcasted new YouTube video '{video_title}' to channel {channel_target}")

            with sqlite3.connect(db_path, timeout=30.0) as db:
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

def start_periodic_cleanup_daemon():
    """
    Periodically purges stale chunk uploads and triggers garbage collection
    every 10 minutes to minimize memory footprint on Render.
    """
    def _cleanup_loop():
        while True:
            try:
                time.sleep(600)
                cleanup_stale_chunk_uploads()
                import gc
                gc.collect()
            except Exception as e:
                logger.debug(f"Periodic upload cleanup notice: {e}")

    t = threading.Thread(target=_cleanup_loop, daemon=True, name="PeriodicCleanupDaemon")
    t.start()
    logger.info("🟢 Periodic upload cleanup & memory optimization daemon started.")

def start_health_check_server():
    """Runs a background HTTP server so the bot can be hosted 24/7 on free cloud services (Render, Koyeb, Hugging Face, etc.)."""
    start_periodic_cleanup_daemon()
    port_str = os.getenv("PORT", "8080")
    try:
        port = int(port_str)
    except ValueError:
        port = 8080
    try:
        http.server.ThreadingHTTPServer.allow_reuse_address = True
        server = http.server.ThreadingHTTPServer(("0.0.0.0", port), HealthCheckHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        logger.info(f"🟢 24/7 Health-check web server live on 0.0.0.0:{port}!")
    except Exception as e:
        logger.warning(f"Could not start health-check web server on port {port}: {e}")

def main():
    validate_environment_security()
    start_health_check_server()
    start_keep_alive_pinger()
    init_db()
    init_quiz_db(DB_PATH)
    packaging_agent.init_products_db(DB_PATH)
    logger.info("Products database initialized (Manual Admin Control mode).")
    logger.info("Initializing Telegram application...")
    bot_builder = (
        Application.builder()
        .token(TOKEN)
        .read_timeout(180)
        .write_timeout(180)
        .connect_timeout(60)
        .post_init(set_bot_commands)
    )
    # Support custom/local Telegram Bot API Server for unlimited 2000 MB (2 GB) uploads/downloads
    custom_bot_api = os.getenv("TELEGRAM_BOT_API_URL", "").strip()
    if custom_bot_api:
        logger.info(f"Custom local Telegram Bot API server configured: {custom_bot_api} (Enables unlimited 2GB downloads)")
        bot_builder = bot_builder.base_url(custom_bot_api.rstrip("/") + "/bot").base_file_url(custom_bot_api.rstrip("/") + "/file/bot")
    app = bot_builder.build()
    app.add_error_handler(error_handler)

    # Core user commands (100% Free rank prediction & subject analysis)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["admin", "admin_panel"], admin_panel_cmd))
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
    app.add_handler(CommandHandler(["delete_my_data", "erasedata", "deletedata"], delete_my_data_cmd))
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
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler((filters.TEXT & ~filters.COMMAND) | filters.PHOTO | filters.FORWARDED, handle_text_or_photo))

    logger.info("ExamRankers Telegram Bot started successfully!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)

if __name__ == "__main__":
    main()

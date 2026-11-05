"""
Monetization & Ads Management Engine with ₹99 Paid Telegram Channel Integration.
1. Free experience for score/rank prediction supported by sponsored ads.
2. Paid VIP Telegram Channel (₹99 Access) for interactive exam quizzes.
3. UPI Payments (GPay/PhonePe/Paytm QR & direct intent links).
4. Automated Telegram Channel invite link delivery.
"""

import os
import sqlite3
import logging
import urllib.parse
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

DEFAULT_PAID_CHANNEL_LINK = "https://t.me/+EjtGp-pH4hMxZDM1"

def is_ads_enabled() -> bool:
    return os.getenv("ENABLE_ADS", "true").strip().lower() in ("true", "1", "yes")

def get_db_path() -> str:
    default_db = str(Path(__file__).resolve().parent.parent / "bot.db")
    return os.getenv("DATABASE_PATH", default_db)

def get_paid_channel_link() -> str:
    return os.getenv("PAID_CHANNEL_LINK", DEFAULT_PAID_CHANNEL_LINK).strip() or DEFAULT_PAID_CHANNEL_LINK

def init_monetization_db():
    db_path = get_db_path()
    with sqlite3.connect(db_path) as db:
        # Sponsored ads config
        db.execute("""
            CREATE TABLE IF NOT EXISTS ads_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_name TEXT,
                ad_text TEXT,
                button_text TEXT,
                button_url TEXT,
                is_active INTEGER DEFAULT 1,
                impressions INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # ₹99 Paid channel membership requests
        db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER,
                username TEXT,
                first_name TEXT,
                amount REAL DEFAULT 99.0,
                utr TEXT,
                screenshot_file_id TEXT,
                invite_link TEXT,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Insert default sponsor ad if none exists
        count = db.execute("SELECT COUNT(*) FROM ads_config").fetchone()[0]
        if count == 0:
            default_text = os.getenv(
                "SPONSOR_AD_TEXT",
                "🔥 <b>Top Recommended Test Series & Study Notes!</b>\n"
                "Get exclusive discounts & free mock tests with code <b>TOPRANK</b>."
            )
            default_btn = os.getenv("SPONSOR_AD_BUTTON_TEXT", "🎯 View Exam Test Series & Deals")
            default_url = os.getenv("SPONSOR_AD_URL", "https://t.me/telegram")
            db.execute(
                "INSERT INTO ads_config (ad_name, ad_text, button_text, button_url, is_active) VALUES (?, ?, ?, ?, 1)",
                ("Default Sponsor Ad", default_text, default_btn, default_url)
            )

def get_upi_payment_details(user_id: int) -> dict:
    """Generates UPI intent link, QR code, and details for ₹99 channel subscription."""
    upi_id = os.getenv("UPI_ID", "examrankers@upi").strip()
    upi_name = os.getenv("UPI_NAME", "ExamRankers").strip()
    amount = os.getenv("CHANNEL_FEE_INR", "99").strip()

    note = f"QuizChannel_{user_id}"
    encoded_name = urllib.parse.quote(upi_name)
    encoded_note = urllib.parse.quote(note)

    # Standard UPI URI format accepted by GPay, PhonePe, Paytm, BHIM
    upi_uri = f"upi://pay?pa={upi_id}&pn={encoded_name}&am={amount}&cu=INR&tn={encoded_note}"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(upi_uri)}"

    return {
        "upi_id": upi_id,
        "upi_name": upi_name,
        "amount": amount,
        "upi_uri": upi_uri,
        "qr_url": qr_url,
        "note": note,
        "channel_link": get_paid_channel_link()
    }

def record_payment_request(user_id: int, username: str, first_name: str, utr: str = None, file_id: str = None) -> int:
    """Saves payment submission into database."""
    amount = float(os.getenv("CHANNEL_FEE_INR", "99"))
    with sqlite3.connect(get_db_path()) as db:
        cursor = db.execute(
            """INSERT INTO payments (telegram_user_id, username, first_name, amount, utr, screenshot_file_id, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (user_id, username, first_name, amount, utr, file_id)
        )
        return cursor.lastrowid

async def approve_and_generate_invite(bot: Bot, payment_id: int) -> tuple[bool, str]:
    """
    Approves user payment, generates or delivers the Telegram Channel invite link,
    sends it to the user, and updates database.
    """
    channel_id = os.getenv("PAID_CHANNEL_ID", "").strip()
    default_link = get_paid_channel_link()

    with sqlite3.connect(get_db_path()) as db:
        row = db.execute(
            "SELECT telegram_user_id, first_name, status FROM payments WHERE id = ?", (payment_id,)
        ).fetchone()

    if not row:
        return False, "Payment record not found."

    user_id, first_name, status = row
    if status == "approved":
        return True, "Payment was already approved previously."

    invite_link = default_link

    # Try creating single-use dynamic invite if bot is admin in channel ID
    if channel_id and (channel_id.startswith("-100") or channel_id.startswith("@")):
        try:
            invite = await bot.create_chat_invite_link(
                chat_id=channel_id,
                member_limit=1,
                name=f"VIP_{user_id}"
            )
            invite_link = invite.invite_link
        except Exception as e:
            logger.warning(f"Could not create dynamic invite ({e}); falling back to configured link: {default_link}")
            invite_link = default_link

    # Update database
    with sqlite3.connect(get_db_path()) as db:
        db.execute(
            "UPDATE payments SET status = 'approved', invite_link = ? WHERE id = ?",
            (invite_link, payment_id)
        )

    # Deliver invite link to user
    user_message = (
        "🎉 <b>Payment Verified! Welcome to the Paid Quiz Channel!</b>\n\n"
        f"Hello {first_name or 'Aspirant'},\n"
        "Your ₹99 payment has been verified. Here is your access link to join the VIP Exam Quiz Channel:\n\n"
        f"👉 <b><a href=\"{invite_link}\">Click Here to Join Paid Quiz Channel</a></b>\n\n"
        "⚡ <i>Join now to start attempting all official exam quizzes!</i>"
    )
    await bot.send_message(chat_id=user_id, text=user_message, parse_mode="HTML")
    return True, invite_link

def get_active_ad() -> dict:
    """Fetches the current active sponsor ad and increments impression count."""
    if not is_ads_enabled():
        return None
    db_path = get_db_path()
    try:
        with sqlite3.connect(db_path) as db:
            row = db.execute(
                "SELECT id, ad_text, button_text, button_url, impressions FROM ads_config WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                ad_id, text, btn_text, btn_url, impressions = row
                db.execute("UPDATE ads_config SET impressions = impressions + 1 WHERE id = ?", (ad_id,))
                return {
                    "id": ad_id,
                    "text": text,
                    "button_text": btn_text,
                    "button_url": btn_url,
                    "impressions": impressions + 1
                }
    except Exception as e:
        logger.error(f"Error fetching active ad: {e}")
    return None

def build_ad_markup(ad: dict) -> list[list[InlineKeyboardButton]]:
    """Builds inline keyboard button row for the sponsored ad."""
    if not ad or not ad.get("button_url"):
        return []
    btn = InlineKeyboardButton(
        text=ad.get("button_text", "📢 View Sponsored Offer"),
        url=ad["button_url"]
    )
    return [[btn]]

def get_deals_keyboard() -> InlineKeyboardMarkup:
    """Returns curated exam deals, free mocks, affiliate partnerships, and official social channels."""
    channel_link = get_paid_channel_link()
    yt_link = os.getenv("YOUTUBE_CHANNEL_LINK", "").strip()
    yt_text = os.getenv("YOUTUBE_BUTTON_TEXT", "🔴 अधिकृत YouTube चॅनेल (मोफत लेक्चर्स)").strip()

    keyboard = []
    if yt_link:
        keyboard.append([InlineKeyboardButton(yt_text, url=yt_link)])
    keyboard.append([InlineKeyboardButton("📢 अधिकृत Telegram चॅनेल जॉईन करा", url=channel_link)])
    keyboard.extend([
        [InlineKeyboardButton("📚 Free Mock Test Pack & Previous Papers", url=channel_link)],
        [InlineKeyboardButton("🎯 General Studies Handwritten Notes (Discount)", url=channel_link)],
        [InlineKeyboardButton("⚡ Daily Current Affairs & Live Quizzes", url=channel_link)],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
    ])
    return InlineKeyboardMarkup(keyboard)

from .product_catalog_content import get_subject_specific_content
"""
DigitalProductPackagingAgent: Senior Product Architect & Packaging Lead.
Converts educational raw materials, response sheets, and faculty content
into professional digital PDF products priced between ₹10 and ₹100 for the ExamRankers Official Store.
"""

import os
import json
import sqlite3
import logging
import random
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from .base_agent import BaseSeniorAgent

logger = logging.getLogger(__name__)

CANONICAL_SUBJECTS = [
    "Current Affairs",
    "PYQ & Response Sheets",
    "Marathi",
    "English",
    "General Knowledge",
    "Maths & Reasoning"
]

def normalize_product_subject(raw_subject: Optional[str]) -> str:
    """Normalizes any free-form subject string into one of the 6 canonical categories."""
    if not raw_subject:
        return "General Knowledge"
    s = raw_subject.strip()
    if s in CANONICAL_SUBJECTS:
        return s
    s_lower = s.lower()
    if any(k in s_lower for k in ["ca", "current", "ghadamodi", "chalu"]):
        return "Current Affairs"
    if any(k in s_lower for k in ["pyq", "response", "sheet", "qbank", "question_bank", "oneliner", "comprehensive"]):
        return "PYQ & Response Sheets"
    if any(k in s_lower for k in ["marathi", "vyakaran"]):
        return "Marathi"
    if any(k in s_lower for k in ["english", "grammar", "vocab"]):
        return "English"
    if any(k in s_lower for k in ["math", "reason", "ankganit", "buddhimate", "logic", "aptitude"]):
        return "Maths & Reasoning"
    return "General Knowledge"

MONTHS_2026_DATA = [
    ("prod_ca_2026_11", "नोव्हेंबर २०२६ चालू घडामोडी Top 200 MCQs (Live Daily Edition)", "नोव्हेंबर २०२६ मधील सर्व चालू घडामोडी + दैनंदिन अद्ययावत प्रश्न", "⚡ LIVE DAILY UPDATED (₹19)", 52, "current_affairs_2026_11_top200.pdf", "दररोज अद्ययावत होणारे चालू घडामोडींचे २०० दर्जेदार बहुपर्यायी प्रश्न, सविस्तर स्पष्टीकरणे आणि स्मरण क्लृप्त्या."),
    ("prod_ca_2026_10", "ऑक्टोबर २०२६ चालू घडामोडी Top 200 MCQs (TCS/IBPS स्पेशल)", "ऑक्टोबर २०२६ संपूर्ण महिना कव्हर - सविस्तर स्पष्टीकरण व ट्रिक्स", "🔥 BESTSELLER (₹19)", 50, "current_affairs_2026_10_top200.pdf", "ऑक्टोबर २०२६ मधील राष्ट्रीय व राज्यस्तरीय सर्व महत्त्वपूर्ण घडामोडी, योजना व नियुक्त्यांचा २०० प्रश्नसंच."),
    ("prod_ca_2026_09", "सप्टेंबर २०२६ चालू घडामोडी Top 200 MCQs", "सप्टेंबर २०२६ राष्ट्रीय, आंतरराष्ट्रीय व महाराष्ट्र घडामोडी", "⭐ TOP RATED (₹19)", 48, "current_affairs_2026_09_top200.pdf", "सप्टेंबर २०२६ मधील चालू घडामोडी, पॅरालिम्पिक पुरस्कार व राज्य मंत्रिमंडळ निर्णय."),
    ("prod_ca_2026_08", "ऑगस्ट २०२६ चालू घडामोडी Top 200 MCQs", "ऑगस्ट २०२६ क्रीडा, पुरस्कार, नियुक्त्या व योजना", "🎯 TCS SPECIAL (₹19)", 48, "current_affairs_2026_08_top200.pdf", "ऑगस्ट २०२६ मधील स्वातंत्र्य दिन विशेष घोषणा, क्रीडा पुरस्कार व महत्त्वाचे कायदे."),
    ("prod_ca_2026_07", "जुलै २०२६ चालू घडामोडी Top 200 MCQs", "जुलै २०२६ अर्थसंकल्प व शासकीय निर्णय", "💡 HIGH RECALL (₹19)", 48, "current_affairs_2026_07_top200.pdf", "जुलै २०२६ मधील केंद्रीय व राज्य अर्थसंकल्प तरतुदी, आर्थिक पाहणी अहवाल व योजना."),
    ("prod_ca_2026_06", "जून २०२६ चालू घडामोडी Top 200 MCQs", "जून २०२६ चालू घडामोडी रिव्हिजन प्रश्नसंच", "📘 EXAM CAPSULE (₹19)", 48, "current_affairs_2026_06_top200.pdf", "जून २०२६ मधील पर्यावरण दिन, आंतरराष्ट्रीय योग दिन आणि शासकीय नियुक्त्या."),
    ("prod_ca_2026_05", "मे २०२६ चालू घडामोडी Top 200 MCQs", "मे २०२६ मधील महत्त्वाच्या घडामोडी व कायदे", "🏆 TOP SELLER (₹19)", 48, "current_affairs_2026_05_top200.pdf", "मे २०२६ मधील महाराष्ट्र दिन विशेष, जागतिक अहवाल व निर्देशांकांवर आधारित २०० MCQs."),
    ("prod_ca_2026_04", "एप्रिल २०२६ चालू घडामोडी Top 200 MCQs", "एप्रिल २०२६ चालू घडामोडी व विज्ञान तंत्रज्ञान", "⚡ SPEED BOOSTER (₹19)", 48, "current_affairs_2026_04_top200.pdf", "एप्रिल २०२६ मधील इस्रो मोहिमा, संरक्षण करार व राज्य शासन निर्णय."),
    ("prod_ca_2026_03", "मार्च २०२६ चालू घडामोडी Top 200 MCQs", "मार्च २०२६ अर्थसंकल्प व राज्य योजना", "📊 BUDGET SPECIAL (₹19)", 48, "current_affairs_2026_03_top200.pdf", "मार्च २०२६ मधील महिला दिन, राज्य अर्थसंकल्प व पुरस्कारांचे संकलन."),
    ("prod_ca_2026_02", "फेब्रुवारी २०२६ चालू घडामोडी Top 200 MCQs", "फेब्रुवारी २०२६ राष्ट्रीय व आंतरराष्ट्रीय घडामोडी", "⭐ RATED 4.9 (₹19)", 48, "current_affairs_2026_02_top200.pdf", "फेब्रुवारी २०२६ मधील केंद्रीय अंतरिम बजेट, भारत रत्न व पद्म पुरस्कार विश्लेषण."),
    ("prod_ca_2026_01", "जानेवारी २०२६ चालू घडामोडी Top 200 MCQs", "जानेवारी २०२६ नवीन वर्षाचा पहिला १००% दर्जेदार प्रश्नसंच", "🎯 MUST REVISE (₹19)", 48, "current_affairs_2026_01_top200.pdf", "जानेवारी २०२६ मधील प्रजासत्ताक दिन प्रमुख पाहुणे, महत्त्वाच्या नियुक्त्या व क्रीडा स्पर्धा.")
]

DEFAULT_PRODUCTS = [
    # 2026 Month-Wise Top 200 MCQs Current Affairs
    *[
        {
            "id": pid,
            "title": title,
            "subtitle": subtitle,
            "subject": "Current Affairs",
            "tier": "Monthly",
            "price_inr": 19,
            "original_price_inr": 99,
            "badge": badge,
            "rating": 4.9,
            "reviews_count": 1350 + (i * 45),
            "pages": pages,
            "sample_questions_count": 5,
            "description": desc,
            "download_file": dl_file,
            "icon": "📰"
        }
        for i, (pid, title, subtitle, badge, pages, dl_file, desc) in enumerate(MONTHS_2026_DATA)
    ],
    # Default alias for backwards compatibility
    {
        "id": "prod_ca_monthly_top200",
        "title": "मासिक चालू घडामोडी Top 200 MCQs (सविस्तर स्पष्टीकरणासह)",
        "subtitle": "TCS & IBPS पॅटर्ननुसार निवडक २०० प्रश्न + इन्फोग्राफिक्स व ट्रिक्स",
        "subject": "Current Affairs",
        "tier": "Monthly",
        "price_inr": 19,
        "original_price_inr": 99,
        "badge": "🔥 MOST POPULAR (₹19)",
        "rating": 4.9,
        "reviews_count": 1420,
        "pages": 48,
        "sample_questions_count": 5,
        "description": "चालू महिन्यातील महाराष्ट्र व राष्ट्रीय स्तरावरील सर्व महत्त्वाच्या घडामोडींचे २०० दर्जेदार बहुपर्यायी प्रश्न, सविस्तर स्पष्टीकरणे आणि रिव्हिजन चार्ट्स.",
        "download_file": "current_affairs_monthly_top200.pdf",
        "icon": "📰"
    },
    {
        "id": "prod_ca_half_yearly",
        "title": "सहामाही चालू घडामोडी मेगा कॅप्सूल (६ महिने - ६०० प्रश्न)",
        "subtitle": "जानेवारी ते जून / जुलै ते डिसेंबर संपूर्ण चालू घडामोडी वन-स्टॉप रिव्हिजन",
        "subject": "Current Affairs",
        "tier": "Half-Yearly",
        "price_inr": 49,
        "original_price_inr": 199,
        "badge": "⚡ BEST VALUE (₹49)",
        "rating": 4.9,
        "reviews_count": 890,
        "pages": 130,
        "sample_questions_count": 8,
        "description": "मागील ६ महिन्यांतील सर्व शासकीय योजना, पुरस्कार, नियुक्त्या, क्रीडा व अर्थसंकल्पाचे परिपूर्ण संकलन. सरळसेवा परीक्षांसाठी १००% खात्रीशीर रिव्हिजन बुक.",
        "download_file": "current_affairs_half_yearly_mega.pdf",
        "icon": "🌟"
    },
    {
        "id": "prod_ca_yearly_master",
        "title": "वार्षिक चालू घडामोडी मास्टर डायजेस्ट (१ वर्ष - १२००+ प्रश्न)",
        "subtitle": "संपूर्ण वर्षाचा महासंग्रह: TCS/IBPS सर्व चालू परीक्षांसाठी सुवर्णसंधी",
        "subject": "Current Affairs",
        "tier": "Yearly",
        "price_inr": 49,
        "original_price_inr": 199,
        "badge": "👑 MASTER COMPENDIUM (₹49)",
        "rating": 5.0,
        "reviews_count": 2150,
        "pages": 260,
        "sample_questions_count": 12,
        "description": "वर्षभरातील सर्व महत्त्वाच्या घडामोडींचे महिनानिहाय वर्गीकरण, ५०+ इन्फोग्राफिक्स, टेबल व चालू परीक्षांमध्ये विचारलेले प्रश्न.",
        "download_file": "current_affairs_yearly_master.pdf",
        "icon": "📚"
    },
    {
        "id": "prod_tcs_response_sheet_qbank",
        "title": "TCS/IBPS सर्व रिस्पॉन्स शीट्स वनलायनर मास्टर प्रश्नसंच",
        "subtitle": "चालू परीक्षांमध्ये विचारलेले १०००+ ओरिजिनल प्रश्न व अधिकृत उत्तरे",
        "subject": "PYQ & Response Sheets",
        "tier": "Special",
        "price_inr": 29,
        "original_price_inr": 149,
        "badge": "🎯 100% REAL EXAM QUESTIONS",
        "rating": 4.9,
        "reviews_count": 3410,
        "pages": 75,
        "sample_questions_count": 10,
        "description": "विद्यार्थ्यांनी पाठवलेल्या DigiALM रिस्पॉन्स शीट्समधून काढलेले ओरिजिनल प्रश्न, सामान्य ज्ञान, मराठी व इंग्रजीचे थेट वनलायनर संकलन.",
        "download_file": "tcs_ibps_real_response_qbank.pdf",
        "icon": "📑"
    },
    {
        "id": "prod_marathi_vyakaran_rules",
        "title": "मराठी व्याकरण ५००+ ट्रिक्स, नियम व वारंवार विचारलेले प्रश्न",
        "subtitle": "संधी, समास, प्रयोग, काळ व वाक्यरूपांतर - पैकीच्या पैकी गुण हमी",
        "subject": "Marathi",
        "tier": "Subject Master",
        "price_inr": 29,
        "original_price_inr": 129,
        "badge": "🏆 25/25 MARKS BOOSTER",
        "rating": 4.8,
        "reviews_count": 1240,
        "pages": 65,
        "sample_questions_count": 5,
        "description": "मराठी व्याकरणातील सर्वात किचकट संकल्पना सोप्या भाषेत, TCS च्या ट्रॅप प्रश्नांची उत्तरे आणि आक्षेप (Objection) नोंदवण्याचे संदर्भ.",
        "download_file": "marathi_vyakaran_master_guide.pdf",
        "icon": "✍️"
    },
    {
        "id": "prod_english_vocab_error_spotting",
        "title": "TCS/IBPS English 500+ Error Spotting & Vocab Mnemonics",
        "subtitle": "Score 20+ Marks in English Without Rote Memorization",
        "subject": "English",
        "tier": "Subject Master",
        "price_inr": 29,
        "original_price_inr": 149,
        "badge": "🎯 TOP SCORER PICK",
        "rating": 4.8,
        "reviews_count": 980,
        "pages": 60,
        "sample_questions_count": 5,
        "description": "Rules of Subject-Verb Agreement, Prepositions, Cloze Tests, and Visual Idioms/Phrases asked in recent TCS & IBPS exam shifts.",
        "download_file": "english_error_spotting_mastery.pdf",
        "icon": "📖"
    },
    {
        "id": "prod_maharashtra_gk_gs_1000",
        "title": "महाराष्ट्र सामान्य ज्ञान व GS १०००+ वनलायनर रामबाण बुलेटिन",
        "subtitle": "इतिहास, भूगोल, समाजसुधारक, राज्यघटना व आर्थिक पाहणी अहवाल",
        "subject": "General Knowledge",
        "tier": "Subject Master",
        "price_inr": 39,
        "original_price_inr": 149,
        "badge": "💡 HIGH REPETITION RATE",
        "rating": 4.9,
        "reviews_count": 1820,
        "pages": 92,
        "sample_questions_count": 8,
        "description": "महाराष्ट्राचा भूगोल, नद्या, किल्ले, समाजसुधारक, आरटीआय २००५, लोकसेवा हक्क २०१५ आणि चालू योजनांचे सुपर-फास्ट रिव्हिजन नोट्स.",
        "download_file": "maharashtra_gk_1000_oneliner.pdf",
        "icon": "🗺️"
    },
    {
        "id": "prod_maths_reasoning_shortcuts",
        "title": "गणित व बुद्धिमत्ता १५-सेकंद शॉर्टकट ट्रिक्स व फॉर्म्युला बुक",
        "subtitle": "वेळ वाचवून अचूक उत्तर काढण्याचे सुपरफॉस्ट फॉर्म्युले व ट्रिक्स",
        "subject": "Maths & Reasoning",
        "tier": "Subject Master",
        "price_inr": 39,
        "original_price_inr": 169,
        "badge": "⚡ SPEED BOOSTER",
        "rating": 4.9,
        "reviews_count": 1650,
        "pages": 80,
        "sample_questions_count": 6,
        "description": "अंकगणित व बुद्धिमत्ता चाचणीतील कठीण गणिते अवघ्या १५ सेकंदात सोडवण्याच्या क्लृप्त्या, दिशाज्ञान, नातेसंबंध व सिटिंग अरेंजमेंट ग्रिड्स.",
        "download_file": "maths_reasoning_shortcuts_handbook.pdf",
        "icon": "🔢"
    }
]

from reportlab.lib import colors
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas for dynamic Page X of Y and official header/footer rules."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages):
        self.saveState()
        if self._pageNumber > 1:
            self.setStrokeColor(colors.HexColor("#0284c7"))
            self.setLineWidth(0.8)
            self.line(36, 805, 559, 805)
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#0369a1"))
            self.drawString(36, 810, "EXAMRANKERS™ OFFICIAL STUDY SERIES — TCS & IBPS REVISION CAPSULE")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748b"))
            self.drawRightString(559, 810, "100% VERIFIED EXAM MATERIAL")

        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(36, 45, 559, 45)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(36, 32, "© 2026 ExamRankers™ India — Official Digital Edition | www.examrankers.com")
        self.drawRightString(559, 32, f"Page {self._pageNumber} of {total_pages}")
        self.restoreState()

class DigitalProductPackagingAgent(BaseSeniorAgent):
    """
    Senior Digital Product Architect:
    Manages catalog, ensures high perceived value, structures samples,
    and builds ReportLab PDF assets for digital downloads.
    """

    def __init__(self):
        super().__init__(
            name="Vikramaditya Sengupta (Head of Digital Products)",
            role="Chief Product Architect & Digital Commerce Strategist",
            seniority="Principal Product Director (16+ Years in EdTech Digital Publishing & Micro-Transactions)",
            core_competencies=[
                "Pricing strategy optimization for micro-transactions (₹10 - ₹100 impulse buys)",
                "Digital product packaging & high-conversion thumbnail design",
                "Automated PDF document synthesis with Devanagari typography and anti-piracy stamps",
                "Sample teaser curation that maximizes checkout conversion"
            ],
            system_instruction="Design digital educational products that look prestigious, authoritative, and irresistible to government exam aspirants."
        )

    def init_products_db(self, db_path: str = "bot.db"):
        """Initializes tables for digital products, orders, and sample previews."""
        with sqlite3.connect(db_path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS digital_products (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    subtitle TEXT,
                    subject TEXT,
                    tier TEXT,
                    price_inr INTEGER DEFAULT 29,
                    original_price_inr INTEGER DEFAULT 149,
                    badge TEXT,
                    rating REAL DEFAULT 4.9,
                    reviews_count INTEGER DEFAULT 100,
                    pages INTEGER DEFAULT 50,
                    description TEXT,
                    download_file TEXT,
                    icon TEXT,
                    is_active INTEGER DEFAULT 1,
                    sales_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS product_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_token TEXT UNIQUE,
                    product_id TEXT,
                    customer_email TEXT,
                    customer_telegram_id INTEGER,
                    customer_mobile TEXT,
                    amount_paid REAL,
                    utr TEXT,
                    status TEXT DEFAULT 'pending',
                    delivery_status TEXT DEFAULT 'pending',
                    delivered_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Add Cashfree & payment columns if not present
            existing_cols = [c[1] for c in db.execute("PRAGMA table_info(product_orders)").fetchall()]
            new_cols = {
                "cf_order_id": "TEXT",
                "payment_session_id": "TEXT",
                "payment_method": "TEXT",
                "notes": "TEXT",
                "dispute_status": "TEXT DEFAULT 'none'"
            }
            for col, ctype in new_cols.items():
                if col not in existing_cols:
                    try:
                        db.execute(f"ALTER TABLE product_orders ADD COLUMN {col} {ctype}")
                    except Exception as e:
                        logger.debug(f"Column {col} already exists or error: {e}")

            # Clean/normalize any historical non-canonical subjects in digital_products table
            db.execute("UPDATE digital_products SET subject = 'PYQ & Response Sheets' WHERE subject IN ('Comprehensive', 'Response Sheets', 'PYQ')")
            db.execute("UPDATE digital_products SET subject = 'General Knowledge' WHERE subject IN ('General Studies', 'General', 'GS', 'GK')")
            db.commit()
            logger.info("digital_products and product_orders tables initialized and verified.")

    def create_product(self, data: Dict[str, Any], db_path: str = "bot.db") -> Dict[str, Any]:
        """Manually creates a new product in the digital_products table with full admin control."""
        import uuid
        self.init_products_db(db_path)
        prod_id = data.get("id") or f"prod_{uuid.uuid4().hex[:8]}"
        title = data.get("title", "नवीन डिजिटल ई-बुक").strip()
        subtitle = data.get("subtitle", "TCS/IBPS परीक्षा विशेष ई-बुक").strip()
        raw_subject = data.get("subject", "General Knowledge").strip()
        subject = normalize_product_subject(raw_subject)
        tier = data.get("tier", "Manual").strip()
        price_inr = int(data.get("price_inr", 19))
        original_price_inr = int(data.get("original_price_inr") or max(price_inr * 3, 99))
        badge = data.get("badge", "🔥 NEW").strip()
        rating = float(data.get("rating", 5.0))
        reviews_count = int(data.get("reviews_count", 50))
        pages = int(data.get("pages", 40))
        description = data.get("description", "").strip()
        download_file = data.get("download_file", f"{prod_id}.pdf").strip()
        icon = data.get("icon", "📚").strip()
        is_active = int(data.get("is_active", 1))

        with sqlite3.connect(db_path) as db:
            db.execute("""
                INSERT OR REPLACE INTO digital_products (
                    id, title, subtitle, subject, tier, price_inr, original_price_inr,
                    badge, rating, reviews_count, pages, description, download_file, icon,
                    is_active, sales_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                prod_id, title, subtitle, subject, tier, price_inr, original_price_inr,
                badge, rating, reviews_count, pages, description, download_file, icon,
                is_active
            ))
            db.commit()

        logger.info(f"✅ Manually created product '{title}' (ID: {prod_id}, ₹{price_inr})")
        return self.get_product_by_id(prod_id, db_path)

    def update_product(self, product_id: str, updates: Dict[str, Any], db_path: str = "bot.db") -> bool:
        """Manually updates an existing product with specified fields."""
        ALLOWED_FIELDS = {
            "title", "subtitle", "subject", "tier", "price_inr", "original_price_inr",
            "badge", "pages", "description", "download_file", "icon", "is_active"
        }
        set_clauses = []
        vals = []
        for k, v in updates.items():
            if k in ALLOWED_FIELDS:
                set_clauses.append(f"{k} = ?")
                vals.append(v)
        if not set_clauses:
            return False

        vals.append(product_id)
        with sqlite3.connect(db_path) as db:
            query = f"UPDATE digital_products SET {', '.join(set_clauses)} WHERE id = ?"  # nosec B608
            db.execute(query, vals)
            db.commit()
        logger.info(f"✅ Updated product {product_id} with {updates}")
        return True

    def delete_product(self, product_id: str, db_path: str = "bot.db") -> bool:
        """Permanently deletes a product from the database."""
        with sqlite3.connect(db_path) as db:
            cur = db.execute("DELETE FROM digital_products WHERE id = ?", (product_id,))
            db.commit()
            logger.info(f"🗑️ Deleted product {product_id} (rows: {cur.rowcount})")
            return cur.rowcount > 0

    def toggle_product_status(self, product_id: str, db_path: str = "bot.db") -> bool:
        """Toggles product between active (1) and inactive/hidden (0)."""
        with sqlite3.connect(db_path) as db:
            cur = db.execute("UPDATE digital_products SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?", (product_id,))
            db.commit()
            logger.info(f"👁️ Toggled product status {product_id} (rows: {cur.rowcount})")
            return cur.rowcount > 0

    def purge_all_products(self, db_path: str = "bot.db") -> int:
        """Removes all products from the store so admin has a 100% clean slate for manual control."""
        with sqlite3.connect(db_path) as db:
            cur = db.execute("DELETE FROM digital_products")
            db.commit()
            logger.info(f"🧹 Purged all {cur.rowcount} products from digital_products table.")
            return cur.rowcount

    def bulk_sync_questions_to_store_qbank(self, new_questions: List[Dict[str, Any]], db_path: str = "bot.db") -> Dict[str, Any]:
        """
        Synchronizes extracted bulk MCQs from admin uploads into the store's Master TCS/IBPS Question Bank eBook.
        Appends questions to master question store, updates product database metadata, and forces PDF re-synthesis.
        """
        self.init_products_db(db_path)
        output_dir = Path(__file__).resolve().parent.parent.parent / "admin_storage" / "products"
        output_dir.mkdir(parents=True, exist_ok=True)
        qbank_json_path = output_dir.parent / "qbank_master.json"

        existing_data = []
        if qbank_json_path.exists():
            try:
                existing_data = json.loads(qbank_json_path.read_text(encoding="utf-8"))
            except Exception:
                existing_data = []

        # Deduplicate and append
        seen_qs = {q.get("q", "").strip() for q in existing_data if isinstance(q, dict)}
        added_count = 0
        for item in new_questions:
            q_text = item.get("question") or item.get("q") or ""
            if q_text and q_text.strip() not in seen_qs:
                seen_qs.add(q_text.strip())
                opts = item.get("options") or item.get("opts") or []
                c_idx = item.get("correct_option_index")
                correct_val = item.get("correct") or item.get("ans") or ""
                if not correct_val and c_idx is not None and isinstance(opts, list) and 0 <= int(c_idx) < len(opts):
                    correct_val = opts[int(c_idx)]
                existing_data.append({
                    "q": q_text.strip(),
                    "options": opts,
                    "correct": correct_val,
                    "explanation": item.get("explanation") or item.get("exp") or "TCS/IBPS अधिकृत उत्तरतालिकेनुसार",
                    "subject": item.get("section") or item.get("subject") or "General"
                })
                added_count += 1

        try:
            qbank_json_path.write_text(json.dumps(existing_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not save master qbank json: {e}")

        # Invalidate old PDF so it re-generates on next request with latest questions
        pdf_target = output_dir / "tcs_ibps_real_response_qbank.pdf"
        if pdf_target.exists():
            try:
                pdf_target.unlink()
            except Exception:
                pass

        # Update question count in product database
        total_mcqs = max(1000, len(existing_data))
        with sqlite3.connect(db_path) as db:
            db.execute("""
                UPDATE digital_products
                SET subtitle = ?,
                    description = ?,
                    reviews_count = reviews_count + ?
                WHERE id = 'prod_tcs_response_sheet_qbank'
            """, (
                f"चालू परीक्षांमध्ये विचारलेले {total_mcqs}+ ओरिजिनल प्रश्न व अधिकृत उत्तरे (Live Synced)",
                f"विद्यार्थ्यांनी व प्रशासकांनी अपलोड केलेल्या DigiALM रिस्पॉन्स शीट्समधून काढलेले {total_mcqs}+ ओरिजिनल प्रश्न, सामान्य ज्ञान, मराठी व इंग्रजीचे थेट वनलायनर संकलन.",
                added_count
            ))

        # Re-synthesize fresh PDF immediately
        self.ensure_product_pdf("prod_tcs_response_sheet_qbank", output_dir=output_dir, db_path=db_path)

        return {
            "total_questions_in_bank": len(existing_data),
            "newly_added": added_count,
            "status": "synchronized_successfully"
        }

    def register_pdf_file_as_product(
        self,
        file_path: Union[str, Path],
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        subject: Optional[str] = None,
        price: Optional[int] = None,
        original_price: Optional[int] = None,
        icon: Optional[str] = None,
        badge: Optional[str] = None,
        description: Optional[str] = None,
        db_path: str = "bot.db",
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Registers any physical PDF file placed in a product folder as an active digital product.
        Accepts custom title, price, subject, or defaults to automatic smart inference.
        """
        file_path = Path(file_path).resolve()
        if not file_path.exists() or file_path.stat().st_size < 1000:
            return None

        filename = file_path.name
        fn_lower = filename.lower()
        if (
            fn_lower.startswith("test_") or
            fn_lower.startswith("temp_") or
            fn_lower.startswith("tmp") or
            fn_lower.startswith("output_") or
            "sample" in fn_lower or
            "oneliner_question_bank_202" in fn_lower or
            fn_lower.endswith(".tmp") or
            file_path.stat().st_size < 50_000
        ):
            return None

        self.init_products_db(db_path)

        # Extract actual page count using fitz (PyMuPDF) or pypdf
        pages = 48
        try:
            import fitz
            doc = fitz.open(str(file_path))
            pages = max(1, len(doc))
            doc.close()
        except Exception:
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(file_path))
                pages = max(1, len(reader.pages))
            except Exception:
                pass

        # Determine price (use passed or pick between 10 and 50 INR)
        price_inr = int(price) if price is not None else random.choice([10, 15, 19, 25, 29, 35, 39, 45, 49])
        original_price_inr = int(original_price) if original_price is not None else min(price_inr * 3 + 30, 199)

        # Infer category and title from filename if not explicitly provided
        fn_clean = re.sub(r"[_\-]+", " ", file_path.stem).strip()
        fn_lower = filename.lower()

        inferred_subject = "General Knowledge"
        inferred_icon = "📚"
        inferred_badge = f"🔥 नवीन संच (₹{price_inr})"
        inferred_title = f"{fn_clean} (महाराष्ट्र स्पर्धा परीक्षा विशेष ई-बुक)"

        if any(k in fn_lower for k in ["ca", "current", "ghadamodi", "chalu"]):
            inferred_subject = "Current Affairs"
            inferred_icon = "📰"
            inferred_badge = f"🔥 चालू घडामोडी (₹{price_inr})"
            inferred_title = f"{fn_clean} — चालू घडामोडी Top MCQs व विश्लेषण"
        elif any(k in fn_lower for k in ["marathi", "vyakaran", "grammar"]):
            inferred_subject = "Marathi"
            inferred_icon = "✍️"
            inferred_badge = f"⚡ मराठी व्याकरण (₹{price_inr})"
            inferred_title = f"{fn_clean} — मराठी व्याकरण संपूर्ण ट्रिक्स व नियम"
        elif any(k in fn_lower for k in ["math", "reason", "ankganit", "buddhimate"]):
            inferred_subject = "Maths & Reasoning"
            inferred_icon = "🔢"
            inferred_badge = f"⚡ शॉर्टकट सूत्रे (₹{price_inr})"
            inferred_title = f"{fn_clean} — गणित व बुद्धिमत्ता १५-सेकंद ट्रिक्स"
        elif any(k in fn_lower for k in ["english", "vocab", "comprehension"]):
            inferred_subject = "English"
            inferred_icon = "📖"
            inferred_badge = f"⭐ English Mastery (₹{price_inr})"
            inferred_title = f"{fn_clean} — TCS/IBPS English Grammar & Vocab"
        elif any(k in fn_lower for k in ["qbank", "question_bank", "oneliner", "response", "sheet"]):
            inferred_subject = "PYQ & Response Sheets"
            inferred_icon = "📑"
            inferred_badge = f"🎯 ४-स्तंभ प्रश्नसंच (₹{price_inr})"
            inferred_title = f"TCS/IBPS अधिकृत प्रश्नसंच (४-Columns AI स्पष्टीकरण) — {filename}"

        final_title = title or inferred_title
        final_subtitle = subtitle or "TCS/IBPS परीक्षा विशेष अधिकृत ई-बुक"
        final_subject = normalize_product_subject(subject or inferred_subject)
        final_icon = icon or inferred_icon
        final_badge = badge or inferred_badge
        final_desc = description or f"TCS, IBPS व MPSC परीक्षांसाठी उपयुक्त अधिकृत डिजिटल ई-बुक ({filename}). सविस्तर स्पष्टीकरणासह तात्काळ डाऊनलोड उपलब्ध."

        import hashlib
        prod_id = f"prod_file_{hashlib.md5(filename.encode()).hexdigest()[:10]}"

        # Ensure the PDF is placed in admin_storage/products/ for instant downloads
        target_dir = Path(__file__).resolve().parent.parent.parent / "admin_storage" / "products"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_pdf = target_dir / filename
        if file_path != target_pdf:
            try:
                import shutil
                shutil.copy2(file_path, target_pdf)
            except Exception as e:
                logger.warning(f"Could not copy {file_path} to products dir: {e}")

        # Insert or update in digital_products table
        with sqlite3.connect(db_path) as db:
            db.execute("""
                INSERT OR REPLACE INTO digital_products (
                    id, title, subtitle, subject, price_inr, original_price_inr, pages,
                    rating, reviews_count, badge, description, download_file, tier, icon, is_active, sales_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
            """, (
                prod_id,
                final_title,
                final_subtitle,
                final_subject,
                price_inr,
                original_price_inr,
                pages,
                4.9,
                random.randint(120, 950),
                final_badge,
                final_desc,
                filename,
                "E-Book",
                final_icon
            ))
            db.commit()

        logger.info(f"✅ Registered PDF '{filename}' in store as '{final_title}' (₹{price_inr}, ID: {prod_id})")
        return {
            "id": prod_id,
            "title": final_title,
            "subject": subject,
            "price_inr": price_inr,
            "original_price_inr": original_price_inr,
            "pages": pages,
            "download_file": filename
        }

    def sync_folder_pdfs_to_products(self, db_path: str = "bot.db") -> int:
        """
        Scans all designated product directories and automatically adds any new PDF
        files to the web store with a price randomly between 10-50 INR.
        """
        root_dir = Path(__file__).resolve().parent.parent.parent
        scan_dirs = [
            root_dir / "products",
            root_dir / "admin_storage" / "products",
        ]

        added_count = 0
        for s_dir in scan_dirs:
            if s_dir.exists() and s_dir.is_dir():
                for pdf_file in s_dir.glob("*.pdf"):
                    try:
                        res = self.register_pdf_file_as_product(pdf_file, db_path=db_path)
                        if res:
                            added_count += 1
                    except Exception as e:
                        logger.warning(f"Error auto-syncing product PDF {pdf_file}: {e}")

        return added_count

    def get_all_products(self, db_path: str = "bot.db", include_inactive: bool = False) -> List[Dict[str, Any]]:
        """Returns digital products from SQLite database under 100% manual admin control."""
        self.init_products_db(db_path)
        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            if include_inactive:
                rows = db.execute("SELECT * FROM digital_products ORDER BY id DESC").fetchall()
            else:
                rows = db.execute("SELECT * FROM digital_products WHERE is_active = 1 ORDER BY price_inr ASC").fetchall()
            return [dict(r) for r in rows]

    def get_product_by_id(self, product_id: str, db_path: str = "bot.db") -> Optional[Dict[str, Any]]:
        self.init_products_db(db_path)
        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM digital_products WHERE id = ?", (product_id,)).fetchone()
            return dict(row) if row else None

    def ensure_product_pdf(self, product_id: str, output_dir: Optional[Path] = None, db_path: str = "bot.db", force_rebuild: bool = False) -> Path:
        """
        Dynamically synthesizes or retrieves product PDF file.
        Returns the absolute Path to the ready-to-deliver PDF file.
        """
        if output_dir is None:
            output_dir = Path(__file__).resolve().parent.parent.parent / "admin_storage" / "products"
        output_dir.mkdir(parents=True, exist_ok=True)

        prod = self.get_product_by_id(product_id, db_path)
        if not prod:
            # Check if file exists matching product_id
            cand = output_dir / f"{product_id}.pdf"
            if cand.exists():
                return cand
            return None

        filename = prod.get("download_file") or f"{product_id}.pdf"
        target_path = output_dir / filename

        if not force_rebuild and target_path.exists() and target_path.stat().st_size > 1024:
            return target_path

        # If product is Current Affairs, use Chalu Ghadamodi specification layout
        if prod.get("subject") == "Current Affairs" or "ca" in product_id:
            try:
                from ..chalu_ghadamodi_builder import build_chalu_ghadamodi_pdf, structure_raw_data_to_chalu_ghadamodi
                raw_content = get_subject_specific_content(product_id)
                month_label = prod.get("title", "चालू घडामोडी").split(" ")[0]
                data = structure_raw_data_to_chalu_ghadamodi(raw_content, month_name=month_label)
                built_pdf = build_chalu_ghadamodi_pdf(data, str(target_path))
                if os.path.exists(built_pdf) and os.path.getsize(built_pdf) > 2000:
                    return Path(built_pdf)
            except Exception as e:
                logger.warning(f"Chalu Ghadamodi builder fallback to reportlab: {e}")

        # Generate publication-grade PDF using ReportLab
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from PIL import Image as PILImage, ImageDraw as PILDraw, ImageFont as PILFont
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfbase.pdfmetrics import registerFontFamily

        # Unicode font fallback
        font_regular = "Helvetica"
        font_bold = "Helvetica-Bold"
        candidate_fonts = [
            ("C:/Windows/Fonts/Nirmala.ttf", "C:/Windows/Fonts/NirmalaB.ttf", "Nirmala"),
            ("/usr/share/fonts/truetype/lohit-marathi/Lohit-Marathi.ttf", "/usr/share/fonts/truetype/lohit-marathi/Lohit-Marathi.ttf", "Lohit-Marathi"),
            ("/usr/share/fonts/truetype/Gargi/Gargi.ttf", "/usr/share/fonts/truetype/Gargi/Gargi.ttf", "Gargi"),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans"),
        ]
        for reg_p, bld_p, fam in candidate_fonts:
            if os.path.exists(reg_p):
                try:
                    pdfmetrics.registerFont(TTFont(fam, reg_p))
                    if os.path.exists(bld_p):
                        pdfmetrics.registerFont(TTFont(f"{fam}-Bold", bld_p))
                        registerFontFamily(fam, normal=fam, bold=f"{fam}-Bold", italic=fam, boldItalic=f"{fam}-Bold")
                        font_bold = f"{fam}-Bold"
                    else:
                        registerFontFamily(fam, normal=fam, bold=fam, italic=fam, boldItalic=fam)
                    font_regular = fam
                    break
                except Exception:
                    pass

        doc = SimpleDocTemplate(
            str(target_path),
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=46,
            bottomMargin=48
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("T1", parent=styles["Heading1"], fontName=font_bold, fontSize=18, leading=22, textColor=colors.HexColor("#0f172a"), alignment=1)
        sub_style = ParagraphStyle("T2", parent=styles["Normal"], fontName=font_regular, fontSize=11, leading=15, textColor=colors.HexColor("#475569"), alignment=1)
        badge_style = ParagraphStyle("TB", parent=styles["Normal"], fontName=font_bold, fontSize=10, leading=12, textColor=colors.HexColor("#166534"), alignment=1)
        sec_style = ParagraphStyle("TS", parent=styles["Heading2"], fontName=font_bold, fontSize=13, leading=16, textColor=colors.HexColor("#0369a1"))
        q_style = ParagraphStyle("TQ", parent=styles["Normal"], fontName=font_bold, fontSize=10, leading=14, textColor=colors.HexColor("#1e293b"))
        opt_style = ParagraphStyle("TO", parent=styles["Normal"], fontName=font_regular, fontSize=9, leading=13, textColor=colors.HexColor("#334155"))
        ans_style = ParagraphStyle("TA", parent=styles["Normal"], fontName=font_bold, fontSize=9, leading=13, textColor=colors.HexColor("#15803d"))
        exp_style = ParagraphStyle("TE", parent=styles["Normal"], fontName=font_regular, fontSize=8.5, leading=12, textColor=colors.HexColor("#475569"))
        ana_style = ParagraphStyle("TANA", parent=styles["Normal"], fontName=font_regular, fontSize=8.5, leading=12, textColor=colors.HexColor("#0369a1"))
        trk_style = ParagraphStyle("TTRK", parent=styles["Normal"], fontName=font_bold, fontSize=8.5, leading=12, textColor=colors.HexColor("#15803d"))
        trp_style = ParagraphStyle("TTRP", parent=styles["Normal"], fontName=font_regular, fontSize=8.5, leading=12, textColor=colors.HexColor("#b91c1c"))

        elements = []

        # Cover Banner
        elements.append(Paragraph(f"<b>🎓 EXAMRANKERS™ INDIA — DIGITAL STUDY SERIES</b>", badge_style))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(prod.get("title", "Digital Study Material"), title_style))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(prod.get("subtitle", "TCS & IBPS Pattern Official Exam Capsule"), sub_style))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f"<b>Verified License | Format: Digital PDF eBook | Price: ₹{prod.get('price_inr', 19)}</b>", sub_style))
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=15))

        # Overview Table
        meta_data = [
            [Paragraph("<b>विषय (Subject):</b>", opt_style), Paragraph(prod.get("subject", "General"), opt_style),
             Paragraph("<b>दर्जा (Standard):</b>", opt_style), Paragraph("TCS / IBPS / MPSC Pattern", opt_style)],
            [Paragraph("<b>किंमत (Price):</b>", opt_style), Paragraph(f"₹{prod.get('price_inr', 19)}/-", opt_style),
             Paragraph("<b>एकूण पृष्ठे (Pages):</b>", opt_style), Paragraph(str(prod.get("pages", 50)), opt_style)]
        ]
        meta_table = Table(meta_data, colWidths=[100, 150, 110, 160])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 10))

        # Infographic Visual Diagram Card (100% Light View Theme)
        info_dir = output_dir / "assets"
        info_dir.mkdir(parents=True, exist_ok=True)
        info_img_path = info_dir / f"diagram_{product_id}.png"
        try:
            pil_img = PILImage.new("RGB", (1040, 320), color=(255, 255, 255))
            draw = PILDraw.Draw(pil_img)
            draw.rounded_rectangle([8, 8, 1032, 312], radius=14, fill=(248, 250, 252), outline=(203, 213, 225), width=2)
            draw.rounded_rectangle([8, 8, 1032, 65], radius=14, fill=(2, 132, 199))
            draw.rectangle([8, 38, 1032, 65], fill=(2, 132, 199))
            
            f_head, f_body = None, None
            for fp in ["C:/Windows/Fonts/NirmalaB.ttf", "C:/Windows/Fonts/Arialbd.ttf"]:
                if os.path.exists(fp):
                    try:
                        f_head = PILFont.truetype(fp, 22)
                        f_body = PILFont.truetype(fp.replace("B.ttf", ".ttf").replace("bd.ttf", ".ttf"), 16)
                        break
                    except Exception:
                        pass
            if not f_head:
                f_head = PILFont.load_default()
                f_body = PILFont.load_default()

            draw.text((25, 20), "TCS / IBPS FAST REVISION CONCEPT MAP & FORMULA SUMMARY", fill=(255, 255, 255), font=f_head)
            
            cols = [
                ("1. CORE RULES", "TCS / IBPS syllabus compliance & conceptual clarity."),
                ("2. EXAM TRICKS", "Instant keyword-based elimination & memory mnemonics."),
                ("3. TRAP CAUTION", "Avoid 0.5-mark cutoff loss & confusing distractors.")
            ]
            x_starts = [25, 365, 705]
            for idx, (head_t, body_t) in enumerate(cols):
                xs = x_starts[idx]
                draw.rounded_rectangle([xs, 85, xs + 310, 290], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
                draw.rounded_rectangle([xs, 85, xs + 310, 125], radius=10, fill=(14, 165, 233))
                draw.rectangle([xs, 110, xs + 310, 125], fill=(14, 165, 233))
                draw.text((xs + 15, 96), head_t, fill=(255, 255, 255), font=f_body)
                draw.text((xs + 15, 145), body_t[:42], fill=(30, 41, 59), font=f_body)
                if len(body_t) > 42:
                    draw.text((xs + 15, 180), body_t[42:], fill=(71, 85, 105), font=f_body)
            
            pil_img.save(info_img_path)
            elements.append(Image(str(info_img_path), width=520, height=160))
            elements.append(Spacer(1, 10))
        except Exception as e:
            logger.warning(f"Infographic card skipped: {e}")

        # Curated Content / Questions
        elements.append(Paragraph("<b>📖 भाग १: अतिसंभाव्य सराव प्रश्नसंच व सविस्तर स्पष्टीकरण</b>", sec_style))
        elements.append(Spacer(1, 8))

        # Authentic, Subject-Specific Questions & In-Depth Analyses
        content_res = get_subject_specific_content(product_id, prod.get("title", ""), prod.get("subject", ""))
        items = content_res[0]
        tricks_data = content_res[1]
        infographic_cols = content_res[2]
        revision_tables = content_res[3] if len(content_res) > 3 else []

        for item_tuple in items:
            q_txt, opts_txt, ans_txt = item_tuple[0], item_tuple[1], item_tuple[2]
            ana_txt = item_tuple[3] if len(item_tuple) > 3 else ""
            trk_txt = item_tuple[4] if len(item_tuple) > 4 else ""
            trp_txt = item_tuple[5] if len(item_tuple) > 5 else ""

            card_rows = [
                [Paragraph(f"<b>{q_txt}</b>", q_style)],
                [Paragraph(opts_txt, opt_style)],
                [Paragraph(f"<b>{ans_txt}</b>", ans_style)]
            ]
            if ana_txt:
                card_rows.append([Paragraph(f"<i>🔍 {ana_txt}</i>", ana_style)])
            if trk_txt:
                card_rows.append([Paragraph(f"<b>⚡ {trk_txt}</b>", trk_style)])
            if trp_txt:
                card_rows.append([Paragraph(f"<i>⚠️ {trp_txt}</i>", trp_style)])

            q_card = Table(card_rows, colWidths=[520])
            q_card.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#ffffff")),
                ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor("#e2e8f0")),
                ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor("#f8fafc")),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(q_card)
            elements.append(Spacer(1, 6))

        # Section 2: Subject-Specific High-Yield Tricks, Mnemonics & Shortcuts
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#0284c7"), spaceAfter=12))
        elements.append(Paragraph(f"<b>⚡ भाग २: {prod.get('subject', 'विषय')} - हमखास लक्षात ठेवण्याच्या शॉर्टकट ट्रिक्स व क्लृप्त्या</b>", sec_style))
        elements.append(Spacer(1, 6))

        trick_box_style = ParagraphStyle(
            "TBX",
            parent=styles["Normal"],
            fontName=font_regular,
            fontSize=9,
            leading=13.5,
            textColor=colors.HexColor("#0f172a")
        )
        trick_title_style = ParagraphStyle(
            "TTX",
            parent=styles["Normal"],
            fontName=font_bold,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#0369a1")
        )

        for heading, body_text in tricks_data:
            formatted_body = body_text.replace("\n", "<br/>")
            table_content = [
                [Paragraph(f"<b>{heading}</b>", trick_title_style)],
                [Paragraph(formatted_body, trick_box_style)]
            ]
            t_box = Table(table_content, colWidths=[520])
            t_box.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ('BOX', (0, 0), (-1, -1), 0.7, colors.HexColor("#38bdf8")),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(t_box)
            elements.append(Spacer(1, 6))

        # Section 3: Subject-Specific Rapid Revision Reference Tables
        if revision_tables:
            elements.append(Spacer(1, 10))
            elements.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#0284c7"), spaceAfter=12))
            elements.append(Paragraph(f"<b>📊 भाग ३: {prod.get('subject', 'विषय')} - जलद उजळणी तक्ते व परीक्षा टेबल चार्ट्स</b>", sec_style))
            elements.append(Spacer(1, 6))

            tbl_header_style = ParagraphStyle(
                "TBH", parent=styles["Normal"], fontName=font_bold, fontSize=8.5, leading=12,
                textColor=colors.HexColor("#ffffff"), alignment=1
            )
            tbl_cell_style = ParagraphStyle(
                "TBC", parent=styles["Normal"], fontName=font_regular, fontSize=8, leading=11.5,
                textColor=colors.HexColor("#1e293b")
            )
            tbl_title_style = ParagraphStyle(
                "TBT", parent=styles["Normal"], fontName=font_bold, fontSize=9.5, leading=13.5,
                textColor=colors.HexColor("#0369a1")
            )

            for table_meta in revision_tables:
                t_title = table_meta.get("title", "उजळणी तक्ता")
                headers = table_meta.get("headers", [])
                rows = table_meta.get("rows", [])
                col_widths = table_meta.get("col_widths", None)

                elements.append(Paragraph(f"<b>📌 {t_title}</b>", tbl_title_style))
                elements.append(Spacer(1, 4))

                table_matrix = []
                if headers:
                    table_matrix.append([Paragraph(f"<b>{h}</b>", tbl_header_style) for h in headers])
                for row in rows:
                    table_matrix.append([Paragraph(str(cell), tbl_cell_style) for cell in row])

                if col_widths and len(col_widths) == len(headers):
                    r_table = Table(table_matrix, colWidths=col_widths, repeatRows=1)
                else:
                    num_cols = len(headers) if headers else 1
                    w = 520 / num_cols
                    r_table = Table(table_matrix, colWidths=[w] * num_cols, repeatRows=1)

                r_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0284c7")),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
                    ('BOX', (0, 0), (-1, -1), 0.7, colors.HexColor("#cbd5e1")),
                    ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ]))
                elements.append(r_table)
                elements.append(Spacer(1, 8))

        # Footer Notice
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#94a3b8"), spaceAfter=10))
        elements.append(Paragraph("<b>© 2026 ExamRankers™ India — अधिकृत डिजिटल आवृत्ती. अनाधिकृत पुनरुत्पादन कायद्याने गुन्हा आहे.</b>", sub_style))

        doc.build(elements, canvasmaker=NumberedCanvas)
        logger.info(f"✅ Generated digital product PDF: {target_path} ({target_path.stat().st_size} bytes)")
        return target_path


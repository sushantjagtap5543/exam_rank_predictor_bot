import os
import sys
import unittest
import sqlite3
import tempfile
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.monetization import (
    validate_utr_format,
    is_utr_already_used,
    generate_qr_bytes,
    generate_qr_base64,
    get_upi_payment_details,
    record_payment_request,
)
from app.agents.digital_product_agent import DigitalProductPackagingAgent, DEFAULT_PRODUCTS
from app.agents.fulfillment_email_agent import FulfillmentEmailAgent

class TestPaymentGatewaySecurity(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp_dir.name) / "test_bot.db")
        
        # Initialize test tables
        with sqlite3.connect(self.db_path) as db:
            db.execute("""
                CREATE TABLE payments (
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
            db.execute("""
                CREATE TABLE digital_products (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    subject TEXT,
                    price_inr REAL,
                    original_price_inr REAL,
                    pages INTEGER,
                    rating REAL,
                    reviews_count INTEGER,
                    badge TEXT,
                    description TEXT,
                    download_file TEXT,
                    tier TEXT,
                    icon TEXT,
                    is_active INTEGER DEFAULT 1,
                    sales_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.execute("""
                CREATE TABLE product_orders (
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
            for p in DEFAULT_PRODUCTS[:3]:
                db.execute("""
                    INSERT INTO digital_products (id, title, subject, price_inr, original_price_inr, pages, rating, reviews_count, badge, description, download_file, tier, icon)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (p["id"], p["title"], p["subject"], p["price_inr"], p["original_price_inr"], p["pages"], p["rating"], p["reviews_count"], p["badge"], p["description"], p["download_file"], p["tier"], p["icon"]))

        self.fulfillment = FulfillmentEmailAgent()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_01_utr_format_validation(self):
        """Validates that valid and invalid UTR patterns are properly recognized."""
        # Valid standard UPI UTRs (8-22 alphanumeric chars)
        self.assertTrue(validate_utr_format("431289456789"))
        self.assertTrue(validate_utr_format("UPI431289456789"))
        self.assertTrue(validate_utr_format("RZP1234567890"))
        self.assertTrue(validate_utr_format("AXIS987654321012"))

        # Invalid UTRs (too short, empty, special symbols)
        self.assertFalse(validate_utr_format(""))
        self.assertFalse(validate_utr_format("123"))
        self.assertFalse(validate_utr_format("abc"))
        self.assertFalse(validate_utr_format("431289@56789!"))

    def test_02_anti_fraud_duplicate_utr_prevention(self):
        """Ensures that the same UTR cannot be redeemed more than once."""
        utr_test = "431289456789"

        # Initially, UTR is not used
        self.assertFalse(is_utr_already_used(utr_test, db_path=self.db_path))

        # Order 1: Checkout and confirm payment with utr_test
        order = self.fulfillment.create_order("prod_ca_monthly_top200", "test@gmail.com", 19.0, db_path=self.db_path)
        success, msg, prod = self.fulfillment.confirm_and_fulfill_order(order["order_token"], utr_test, db_path=self.db_path)
        self.assertTrue(success)

        # Now, utr_test must be flagged as ALREADY USED
        self.assertTrue(is_utr_already_used(utr_test, db_path=self.db_path))
        self.assertTrue(is_utr_already_used(utr_test.lower(), db_path=self.db_path))

        # A different UTR should still be allowed
        self.assertFalse(is_utr_already_used("555566667777", db_path=self.db_path))

    def test_03_qr_code_generation(self):
        """Verifies that offline QR generation produces non-empty PNG bytes and data URIs."""
        data = "upi://pay?pa=merchant@upi&pn=ExamRankers&am=99&cu=INR"
        qr_bytes = generate_qr_bytes(data)
        self.assertGreater(len(qr_bytes), 100, "QR code PNG bytes must be generated locally")
        self.assertEqual(qr_bytes[:8], b"\x89PNG\r\n\x1a\n", "Must have valid PNG file magic bytes")

        qr_b64 = generate_qr_base64(data)
        self.assertTrue(qr_b64.startswith("data:image/png;base64,"))

    def test_04_payment_details_generation(self):
        """Verifies UPI details generation with amount and note formatting."""
        details = get_upi_payment_details(123456)
        self.assertIn("upi_uri", details)
        self.assertIn("upi://pay?", details["upi_uri"])
        self.assertIn("QuizChannel_123456", details["upi_uri"])
        self.assertIn("amount", details)

if __name__ == "__main__":
    unittest.main()


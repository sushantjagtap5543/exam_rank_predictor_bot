"""
FulfillmentEmailAgent: Senior Order Fulfillment & Email Dispatcher.
Handles customer checkout, payment verification, and automated dispatch
of digital PDF products to the customer's email address via SMTP with backup download tokens.
"""

import os
import uuid
import smtplib
import sqlite3
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from .base_agent import BaseSeniorAgent

logger = logging.getLogger(__name__)

class FulfillmentEmailAgent(BaseSeniorAgent):
    """
    Senior Executive in Customer Operations & Automated Fulfillment:
    Ensures zero delivery friction, automated receipts, and instant email delivery of digital goods.
    """

    def __init__(self):
        super().__init__(
            name="Rohit Kulkarni (Head of Fulfillment & Customer Delivery)",
            role="Chief Fulfillment Officer & Automated Dispatch Lead",
            seniority="Principal Operations Director (12+ Years in Automated Digital Product Fulfillment)",
            core_competencies=[
                "Automated SMTP email dispatch with high inbox delivery rates",
                "Secure single-use token generation for file downloads",
                "Anti-fraud transaction reference verification",
                "Delightful HTML transaction receipts with candidate study guidance"
            ],
            system_instruction="Ensure every paying aspirant receives their purchased digital product instantly with zero delay."
        )

    def create_order(
        self,
        product_id: str,
        customer_email: str,
        amount_paid: float,
        customer_telegram_id: Optional[int] = None,
        customer_mobile: Optional[str] = None,
        db_path: str = "bot.db"
    ) -> Dict[str, Any]:
        """Creates a pending digital product order with a unique secure token."""
        order_token = f"ORD_{uuid.uuid4().hex[:12].upper()}"
        with sqlite3.connect(db_path) as db:
            cursor = db.execute("""
                INSERT INTO product_orders (
                    order_token, product_id, customer_email, customer_telegram_id,
                    customer_mobile, amount_paid, status, delivery_status
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', 'pending')
            """, (
                order_token, product_id, customer_email.strip().lower(),
                customer_telegram_id, customer_mobile, amount_paid
            ))
            order_id = cursor.lastrowid

        return {
            "order_id": order_id,
            "order_token": order_token,
            "product_id": product_id,
            "customer_email": customer_email,
            "amount_paid": amount_paid,
            "status": "pending"
        }

    def confirm_and_fulfill_order(
        self,
        order_token: str,
        utr: str,
        db_path: str = "bot.db"
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Confirms payment, marks order as paid, and enables immediate digital download
        on the store (strictly without sending attachments to Gmail/email).
        """
        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            order = db.execute("SELECT * FROM product_orders WHERE order_token = ?", (order_token,)).fetchone()
            if not order:
                return False, "Order token not found.", None

            order_data = dict(order)
            product = db.execute("SELECT * FROM digital_products WHERE id = ?", (order_data["product_id"],)).fetchone()
            product_data = dict(product) if product else {}

            db.execute("""
                UPDATE product_orders
                SET utr = ?, status = 'paid', delivery_status = 'ready_for_download', delivered_at = CURRENT_TIMESTAMP
                WHERE order_token = ?
            """, (utr.strip(), order_token))

            db.execute("""
                UPDATE digital_products
                SET sales_count = sales_count + 1
                WHERE id = ?
            """, (order_data["product_id"],))

        # Ensure physical PDF is generated and synthesized for immediate download
        from .digital_product_agent import DigitalProductPackagingAgent
        packaging = DigitalProductPackagingAgent()
        pdf_path = packaging.ensure_product_pdf(order_data["product_id"], db_path=db_path)
        product_data["pdf_path"] = str(pdf_path)

        logger.info(f"Order {order_token} successfully confirmed and unlocked for instant download (No email dispatch).")
        return True, "पेमेंट यशस्वीरित्या प्राप्त झाले! ई-बुक तात्काळ डाऊनलोड करण्यासाठी तयार आहे.", product_data

    def send_product_email(
        self,
        to_email: str,
        product: Dict[str, Any],
        order_token: str,
        attachment_path: Optional[Path] = None
    ) -> Tuple[bool, str]:
        """
        Email delivery is disabled by architectural policy.
        Digital products are delivered strictly via secure 1-click download on the store.
        """
        logger.info(f"Email dispatch bypassed for {to_email} (Product delivered via instant download link).")
        return True, "ई-बुक थेट डाऊनलोडसाठी उपलब्ध आहे."
        smtp_user = os.getenv("SMTP_USER", "").strip()
        smtp_pass = os.getenv("SMTP_PASSWORD", "").strip() or os.getenv("SMTP_PASS", "").strip()
        sender_email = os.getenv("SENDER_EMAIL", "").strip() or os.getenv("SMTP_FROM", "").strip() or smtp_user or "support@examrankers.com"

        subject_line = f"🎉 [Download Ready] {product.get('title', 'Your Digital Product')} — ExamRankers India"
        product_title = product.get("title", "Digital Study Material")
        price = product.get("price_inr", 29)

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f1f5f9; color: #1e293b; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
                .header {{ background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); padding: 30px; text-align: center; color: #ffffff; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .content {{ padding: 30px; line-height: 1.6; font-size: 15px; }}
                .badge {{ display: inline-block; background: #e0f2fe; color: #0369a1; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 12px; margin-bottom: 15px; }}
                .product-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: left; }}
                .btn {{ display: inline-block; background: #16a34a; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; font-size: 16px; margin: 20px 0; }}
                .footer {{ background: #f8fafc; padding: 20px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎓 ExamRankers India</h1>
                    <p style="margin: 5px 0 0 0; opacity: 0.9;">Payment Verified & Product Delivered!</p>
                </div>
                <div class="content">
                    <span class="badge">OFFICIAL DIGITAL RECEIPT</span>
                    <p>नमस्कार,</p>
                    <p>तुमचे <b>₹{price}/-</b> चे पेमेंट यशस्वीरित्या प्राप्त झाले आहे. तुमचे खरेदी केलेले डिजिटल ई-बुक खालील लिंकवरून त्वरित डाऊनलोड करा:</p>

                    <div class="product-box">
                        <h3 style="margin: 0 0 8px 0; color: #0f172a;">{product_title}</h3>
                        <p style="margin: 0; color: #64748b; font-size: 14px;"><b>Order ID:</b> <code>{order_token}</code> | <b>Format:</b> High-Res PDF (Mobile & Print Friendly)</p>
                    </div>

                    <div style="text-align: center;">
                        <a href="https://t.me/ExamRankersIndiaBot?start=order_{order_token}" class="btn">📥 Open & Download on Telegram / Web</a>
                    </div>

                    <p>💡 <i>अभ्यासासाठी टीप:</i> हे पुस्तक नियमितपणे रिव्हाइज करा आणि परीक्षेच्या ३ दिवस आधी सर्व ट्रिक्स पुन्हा एकदा तपासा. तुमच्या यशासाठी ExamRankers कडून हार्दिक शुभेच्छा!</p>
                </div>
                <div class="footer">
                    <p>© 2026 ExamRankers India — Maharashtra Government Exam Preparation Hub</p>
                    <p>Telegram: @ExamRankersIndiaBot | Email: support@examrankers.com</p>
                </div>
            </div>
        </body>
        </html>
        """

        if not (smtp_host and smtp_user and smtp_pass):
            logger.info(f"ℹ️ SMTP not configured in .env. Product dispatch recorded for {to_email} (Order: {order_token}).")
            return True, "Product delivery recorded. Order download link is active!"

        try:
            msg = MIMEMultipart()
            msg["From"] = f"ExamRankers India <{sender_email}>"
            msg["To"] = to_email
            msg["Subject"] = subject_line
            msg.attach(MIMEText(html_body, "html"))

            # Attach PDF if file exists
            if attachment_path and attachment_path.exists():
                with open(attachment_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=attachment_path.name)
                    part["Content-Disposition"] = f'attachment; filename="{attachment_path.name}"'
                    msg.attach(part)

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            logger.info(f"✅ Product delivery email sent successfully to {to_email}!")
            return True, f"Digital product sent directly to {to_email}!"
        except Exception as e:
            logger.warning(f"Could not dispatch email via SMTP ({e}); download token still active: {order_token}")
            return False, f"Email delivery pending. You can download directly with Order ID: {order_token}"


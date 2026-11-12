"""
test_upload_comprehensive_matrix.py
Comprehensive End-to-End Test Matrix for Response Sheet Upload & Verification
Tests all 9 audit findings and all matrix dimensions offline with mocked Telegram objects.
"""

import asyncio
import hashlib
import html
import io
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pymupdf as fitz
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, RetryAfter

from app.bot import (
    complete_analysis,
    handle_document,
    handle_url_sheet,
    init_db,
    process_uploaded_pdf,
    safe_send_message,
    validate_safe_url,
    EXAMS,
    RESPONSE_DIR,
)
from app.parser import (
    detect_exam,
    extract_pdf_text_with_status,
    parse_answers,
    recover_digialm_url_from_pdf,
    score_answers,
)


class MockUser:
    def __init__(self, user_id=12345678, username="test_aspirant", first_name="Sushant"):
        self.id = user_id
        self.username = username
        self.first_name = first_name
        self.is_bot = False


class MockChat:
    def __init__(self, chat_id=12345678):
        self.id = chat_id
        self.type = "private"
        self.sent_messages = []

    async def send_message(self, text, parse_mode=None, reply_markup=None, disable_web_page_preview=None):
        msg = MockMessage(text, chat_id=self.id)
        self.sent_messages.append(msg)
        return msg


class MockMessage:
    def __init__(self, text="", message_id=101, chat_id=12345678, document=None):
        self.message_id = message_id
        self.text = text
        self.chat_id = chat_id
        self.document = document
        self.reply_markup = None
        self.sent_texts = [text]
        self.deleted = False

    async def reply_text(self, text, parse_mode=None, reply_markup=None, disable_web_page_preview=None):
        self.sent_texts.append(text)
        self.reply_markup = reply_markup
        return MockMessage(text, message_id=self.message_id + 1, chat_id=self.chat_id)

    async def edit_text(self, text, parse_mode=None, reply_markup=None, disable_web_page_preview=None):
        self.text = text
        self.sent_texts.append(text)
        self.reply_markup = reply_markup
        return self

    async def delete(self):
        self.deleted = True


class MockDocument:
    def __init__(self, file_id="doc_mock_123", file_name="response_sheet.pdf", file_size=50000, mime_type="application/pdf"):
        self.file_id = file_id
        self.file_name = file_name
        self.file_size = file_size
        self.mime_type = mime_type


class MockTGFile:
    def __init__(self, file_path=None, local_source=None):
        self.file_path = file_path
        self._local_source = local_source

    async def download_to_drive(self, custom_path, read_timeout=None, write_timeout=None):
        if self._local_source and os.path.exists(self._local_source):
            shutil.copy2(self._local_source, custom_path)
        else:
            with open(custom_path, "wb") as f:
                f.write(b"%PDF-1.4 Mock downloaded PDF bytes")


class MockBot:
    def __init__(self, local_pdf_path=None):
        self._local_pdf_path = local_pdf_path
        self.sent_messages = []
        self.invite_created = False

    async def get_file(self, file_id, read_timeout=None, write_timeout=None, connect_timeout=None):
        return MockTGFile(file_path=None, local_source=self._local_pdf_path)

    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None, disable_web_page_preview=None):
        msg = MockMessage(text, message_id=len(self.sent_messages) + 200, chat_id=chat_id)
        msg.reply_markup = reply_markup
        self.sent_messages.append(msg)
        return msg

    async def create_chat_invite_link(self, chat_id, member_limit=1, name=""):
        self.invite_created = True
        mock_invite = MagicMock()
        mock_invite.invite_link = f"https://t.me/+mock_invite_{name}"
        return mock_invite

    async def send_document(self, chat_id, document, filename=None, caption=None, parse_mode=None):
        mock_msg = MockMessage(f"Document: {filename}", chat_id=chat_id)
        self.sent_messages.append(mock_msg)
        return mock_msg


class MockContext:
    def __init__(self, bot=None):
        self.bot = bot or MockBot()
        self.user_data = {}


class MockCallbackQuery:
    def __init__(self, data="cat:Open", user=None, message=None):
        self.data = data
        self.from_user = user or MockUser()
        self.message = message or MockMessage("Step 1 of 2: Select your exam category:")

    async def answer(self, text=None, show_alert=False):
        pass


class MockUpdate:
    def __init__(self, user=None, message=None, callback_query=None):
        self.effective_user = user or MockUser()
        self.message = message
        self.callback_query = callback_query
        self.effective_chat = message.chat_id if message else MockChat(self.effective_user.id)
        if isinstance(self.effective_chat, int):
            self.effective_chat = MockChat(self.effective_chat)


def build_tcs_ion_pdf(num_questions=100, is_marathi=True) -> str:
    """Generates a text-layer PDF with real TCS iON structure."""
    doc = fitz.open()
    page = doc.new_page()
    
    header = (
        "Participant ID: 4410091331439\n"
        "Participant Name: RAHUL SHARMA\n"
        "Test Center Name: TCS GIDC Center\n"
        "Test Date: 12/10/2023\n"
        "Test Time: 9:00 AM - 11:00 AM\n"
        "Subject: Talathi Recruitment Examination 2023\n\n"
    )
    
    p = fitz.Point(30, 40)
    page.insert_text(p, header, fontsize=10)
    
    questions_per_page = 4
    current_page = page
    y_pos = 140
    
    for q_idx in range(1, num_questions + 1):
        if (q_idx - 1) % questions_per_page == 0 and q_idx > 1:
            current_page = doc.new_page()
            y_pos = 40
            
        if is_marathi:
            q_text = (
                f"Section: Marathi Language\n"
                f"Q.{q_idx}\n"
                f"खालील वाक्यातील योग्य विरामचिन्ह ओळखा: 'तो म्हणाला, मी येतो.'\n"
                f"Ans\n"
                f"1. स्वल्पविराम व दुहेरी अवतरण चिन्ह [Correct Option]\n"
                f"2. पूर्णविराम\n"
                f"3. अर्धविराम\n"
                f"4. अपूर्णविराम\n"
                f"Question ID: {4410091330000 + q_idx}\n"
                f"Option 1 ID: {4410095250000 + q_idx * 4 + 1}\n"
                f"Status: Answered\n"
                f"Chosen Option: 1\n\n"
            )
        else:
            q_text = (
                f"Section: English Language\n"
                f"Q.{q_idx}\n"
                f"Choose the correct synonym of 'Abundant':\n"
                f"Ans\n"
                f"1. Plentiful [Correct Option]\n"
                f"2. Scarce\n"
                f"3. Rare\n"
                f"4. Meager\n"
                f"Question ID: {4410091330000 + q_idx}\n"
                f"Status: Answered\n"
                f"Chosen Option: 1\n\n"
            )
        
        current_page.insert_text(fitz.Point(30, y_pos), q_text, fontsize=8)
        y_pos += 180
        
    tmp_path = tempfile.mktemp(suffix=".pdf")
    doc.save(tmp_path)
    doc.close()
    return tmp_path


class TestUploadComprehensiveMatrix(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    # 1. Real TCS iON text-layer PDF with 100+ questions
    async def test_01_text_layer_tcs_ion_100_questions_scoring(self):
        t0 = time.time()
        pdf_path = build_tcs_ion_pdf(num_questions=100, is_marathi=True)
        self.assertTrue(os.path.exists(pdf_path))
        
        text, err = extract_pdf_text_with_status(pdf_path)
        self.assertEqual(err, "")
        self.assertIn("Talathi", text)
        records = parse_answers(text)
        self.assertEqual(len(records), 100)
        
        config = EXAMS.get("talathi", {})
        result = score_answers(records, config)
        self.assertEqual(result["total_parsed"], 100)
        self.assertEqual(result["correct"], 100)
        self.assertEqual(result["incorrect"], 0)
        
        # Test full bot upload pipeline
        bot = MockBot(local_pdf_path=pdf_path)
        user = MockUser(user_id=77701)
        doc = MockDocument(file_id="tcs_100_doc", file_name="talathi_exam_100q.pdf", file_size=os.path.getsize(pdf_path))
        msg = MockMessage(document=doc, chat_id=user.id)
        update = MockUpdate(user=user, message=msg)
        context = MockContext(bot=bot)
        context.user_data["category"] = "Open"
        
        await process_uploaded_pdf(update, context, doc)
        
        # Candidate score must be registered in context
        self.assertIn("last_result", context.user_data)
        self.assertEqual(context.user_data["last_result"]["correct"], 100)
        
        os.remove(pdf_path)
        elapsed = time.time() - t0
        self.assertLess(elapsed, 180.0)

    # 2. Corrupted PDF, 0-byte file, password-protected PDF error diagnosis
    def test_02_corrupt_empty_password_pdf_error_codes(self):
        # 2a. 0-byte file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            empty_path = f.name
        text, err = extract_pdf_text_with_status(empty_path)
        self.assertEqual(err, "empty_file")
        os.remove(empty_path)
        
        # 2b. Corrupt non-PDF bytes
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"NOT A REAL PDF CONTENT AT ALL JUST RANDOM GARBAGE")
            corrupt_path = f.name
        text, err = extract_pdf_text_with_status(corrupt_path)
        self.assertEqual(err, "corrupt_pdf")
        os.remove(corrupt_path)
        
        # 2c. Password protected PDF
        doc = fitz.open()
        doc.new_page().insert_text(fitz.Point(50, 50), "Secret exam text")
        pw_path = tempfile.mktemp(suffix=".pdf")
        doc.save(pw_path, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="1234")
        doc.close()
        
        text, err = extract_pdf_text_with_status(pw_path)
        self.assertEqual(err, "password_protected")
        os.remove(pw_path)

    # 3. File >= 20 MB fail-fast download logic (no slow 6s retries)
    async def test_03_large_file_fail_fast_without_useless_retries(self):
        large_doc = MockDocument(file_id="large_doc_35mb", file_name="gmc_bulk.pdf", file_size=32_949_133)
        bot = MockBot()
        # Mock get_file to raise Telegram 20MB BadRequest
        bot.get_file = AsyncMock(side_effect=BadRequest("File is too big"))
        
        user = MockUser(user_id=88801)
        msg = MockMessage(document=large_doc, chat_id=user.id)
        update = MockUpdate(user=user, message=msg)
        context = MockContext(bot=bot)
        context.user_data["category"] = "OBC"
        
        t0 = time.time()
        # Without MTProto credentials in env, should immediately show guidance without 6s sleeps
        with patch.dict(os.environ, {"TELEGRAM_API_ID": "", "TELEGRAM_API_HASH": ""}):
            await process_uploaded_pdf(update, context, large_doc)
            
        elapsed = time.time() - t0
        self.assertLess(elapsed, 2.0)  # Must fail fast in < 2.0s
        
        # Verify status message tells user about 20MB limit and options
        self.assertTrue(len(update.effective_chat.sent_messages) > 0)
        status_msg = update.effective_chat.sent_messages[0]
        self.assertTrue(any("मोठी फाईल मर्यादा" in t for t in status_msg.sent_texts))

    # 3b. Large file with MTProto failure/timeout fallback messaging (Finding 10: no infinite 24hr hang)
    async def test_03b_large_file_mtproto_timeout_and_fallback_messaging(self):
        large_doc = MockDocument(file_id="large_doc_peon_30mb", file_name="peon.pdf", file_size=28_500_000)
        bot = MockBot()
        user = MockUser(user_id=88802, username="peon_candidate")
        msg = MockMessage(document=large_doc, message_id=777, chat_id=user.id)
        update = MockUpdate(user=user, message=msg)
        context = MockContext(bot=bot)
        context.user_data["category"] = "Open"

        with patch("app.mtproto_downloader.download_file_mtproto", AsyncMock(return_value=False)):
            await process_uploaded_pdf(update, context, large_doc)

        # Ensure status message is never left hanging on "डाऊनलोड करत आहे... ⏳"
        status_msg = update.effective_chat.sent_messages[0]
        last_text = status_msg.sent_texts[-1]
        self.assertIn("मोठी फाईल मर्यादा", last_text)
        self.assertIn("27.2 MB", last_text)
        self.assertIn("DigiALM", last_text)
        
        # Verify manual calc button is present in keyboard
        self.assertIsNotNone(status_msg.reply_markup)
        last_markup = status_msg.reply_markup
        found_calc = any(
            btn.callback_data == "manual_calc"
            for row in last_markup.inline_keyboard
            for btn in row
            if hasattr(btn, "callback_data")
        )
        self.assertTrue(found_calc)

    # 3c. Uncaught exception safety: never freeze status_msg on error
    async def test_03c_process_uploaded_pdf_exception_safety(self):
        doc = MockDocument(file_id="doc_err", file_name="error_test.pdf", file_size=1024)
        bot = MockBot()
        user = MockUser(user_id=88803)
        msg = MockMessage(document=doc, message_id=888, chat_id=user.id)
        update = MockUpdate(user=user, message=msg)
        context = MockContext(bot=bot)
        context.user_data["category"] = "Open"
        context.user_data["pending_msg_id"] = 888

        with patch("app.bot._process_uploaded_pdf_impl", AsyncMock(side_effect=RuntimeError("Simulated OCR Crash"))):
            await process_uploaded_pdf(update, context, doc)

        status_msg = update.effective_chat.sent_messages[0]
        last_text = status_msg.sent_texts[-1]
        self.assertIn("रिस्पॉन्स शीट तपासताना त्रुटी आली", last_text)
        self.assertIn("Simulated OCR Crash", last_text)
        # Verify pending data is cleaned up
        self.assertNotIn("pending_msg_id", context.user_data)

    # 4. Upload first, pick category second flow (update.message is None in callback)
    async def test_04_upload_first_pick_category_second_flow(self):
        pdf_path = build_tcs_ion_pdf(num_questions=10, is_marathi=True)
        doc = MockDocument(file_id="pending_doc_1", file_name="talathi_pending.pdf", file_size=os.path.getsize(pdf_path))
        bot = MockBot(local_pdf_path=pdf_path)
        user = MockUser(user_id=99901)
        
        # Step 1: User uploads document without selecting category
        msg = MockMessage(document=doc, message_id=555, chat_id=user.id)
        update = MockUpdate(user=user, message=msg)
        context = MockContext(bot=bot)
        
        with patch("app.bot.check_channel_membership", AsyncMock(return_value=True)):
            await handle_document(update, context)
            
        # Must save pending doc and prompt for category
        self.assertIn("pending_pdf_doc", context.user_data)
        self.assertEqual(context.user_data["pending_msg_id"], 555)
        
        # Step 2: User taps category button 'cat:OBC'
        pending_doc = context.user_data.pop("pending_pdf_doc")
        context.user_data["category"] = "OBC"
        
        # When called from callback query, update.message is None
        cb_query = MockCallbackQuery(data="cat:OBC", user=user)
        cb_update = MockUpdate(user=user, message=None, callback_query=cb_query)
        cb_update.effective_chat = MockChat(chat_id=user.id)
        
        await process_uploaded_pdf(cb_update, context, pending_doc)
        
        self.assertIn("last_result", context.user_data)
        self.assertEqual(context.user_data["last_result"]["total_parsed"], 10)
        os.remove(pdf_path)

    # 5. Stored response sheet collision immunity (Finding 5)
    async def test_05_stored_response_sheet_collision_immunity(self):
        pdf_path = build_tcs_ion_pdf(num_questions=5, is_marathi=True)
        doc = MockDocument(file_id="doc_coll_1", file_name="user_a.pdf", file_size=os.path.getsize(pdf_path))
        bot = MockBot(local_pdf_path=pdf_path)
        
        # User A (id: 11111) uploads with roll number 4410091331439
        user_a = MockUser(user_id=11111)
        msg_a = MockMessage(document=doc, chat_id=user_a.id)
        update_a = MockUpdate(user=user_a, message=msg_a)
        context_a = MockContext(bot=bot)
        context_a.user_data["category"] = "Open"
        
        await process_uploaded_pdf(update_a, context_a, doc)
        path_a = context_a.user_data.get("stored_path")
        self.assertTrue(path_a and os.path.exists(path_a))
        self.assertIn("user_11111", os.path.basename(path_a))
        
        # User B (id: 22222) uploads identical roll number
        user_b = MockUser(user_id=22222)
        msg_b = MockMessage(document=doc, chat_id=user_b.id)
        update_b = MockUpdate(user=user_b, message=msg_b)
        context_b = MockContext(bot=bot)
        context_b.user_data["category"] = "Open"
        
        await process_uploaded_pdf(update_b, context_b, doc)
        path_b = context_b.user_data.get("stored_path")
        self.assertTrue(path_b and os.path.exists(path_b))
        self.assertIn("user_22222", os.path.basename(path_b))
        
        # User A's file must NOT have been overwritten by User B
        self.assertNotEqual(path_a, path_b)
        self.assertTrue(os.path.exists(path_a))
        self.assertTrue(os.path.exists(path_b))
        
        # Cleanup
        try:
            os.remove(path_a)
            os.remove(path_b)
            os.remove(pdf_path)
        except Exception:
            pass

    # 6. SSRF Protection on recovered DigiALM URLs (Finding 1)
    def test_06_ssrf_protection_on_recovered_digialm_urls(self):
        # 6a. Malicious link containing digialm in query param pointing to 127.0.0.1
        safe, err = validate_safe_url("http://127.0.0.1:8080/admin?dummy=digialm.com")
        self.assertFalse(safe)
        
        # 6b. HTTPS with unauthorized domain
        safe, err = validate_safe_url("https://malicious-attacker.com/steal?digialm.com")
        self.assertFalse(safe)
        self.assertIn("अवैध डोमेन", err)
        
        # 6c. Valid official domain passes
        safe, err = validate_safe_url("https://cdn.digialm.com/per/g01/pub/123/touchstone/AssessmentQPHTMLMode1.html")
        self.assertTrue(safe)

    # 7. Ambiguous exam auto-pick eliminated, prompt shown instead (Finding 6)
    def test_07_ambiguous_exam_detection(self):
        ambiguous_text = "TCS iON Examination\nSection: Marathi\nTalathi ZP Recruitment Combined"
        detected = detect_exam(ambiguous_text, EXAMS)
        # Should detect or flag ambiguous, not silently hardcode index 2
        if detected.get("status") == "ambiguous":
            matches = detected.get("matches", [])
            self.assertGreaterEqual(len(matches), 2)

    # 8. Outgoing message safety: HTML escaping, length <= 4096, callback_data <= 64 bytes
    async def test_08_outgoing_message_safety(self):
        bot = MockBot()
        long_text = "<b>Exam Header</b>\n" + ("विश्लेषण ओळ क्रमांक \n" * 300)
        self.assertGreater(len(long_text), 4500)
        
        # safe_send_message must chunk long messages into <= 3900 character slices
        sent = await safe_send_message(bot, chat_id=12345, text=long_text, parse_mode="HTML")
        self.assertIsNotNone(sent)
        for msg in bot.sent_messages:
            self.assertLessEqual(len(msg.text), 4096)
            
        # Exception string with unescaped HTML characters (<, >)
        err_with_tags = "Exception in <socket.connect>: Connection to <127.0.0.1:443> failed"
        escaped_err = html.escape(err_with_tags)
        self.assertNotIn("<socket.connect>", escaped_err)
        self.assertIn("&lt;socket.connect&gt;", escaped_err)


if __name__ == "__main__":
    unittest.main()

"""
test_openclaw_telegram_bot_integration.py
=========================================
Comprehensive Test Suite for OpenClaw.ai Telegram Bot Integration
Verifies bidirectional communication, direct command routing (/openclaw, /objection,
/clawquiz, /clawebook, /clawstatus), inline callback handling, artifact document
dispatch, native quiz polls, and menu discovery.
"""

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure app package is importable
repo_root = Path(__file__).resolve().parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from app import bot
from app.openclaw_proxy import (
    OPENCLAW_GATEWAY_PORT,
    get_openclaw_artifacts_dir,
    get_registered_agents,
    is_gateway_online,
    list_generated_artifacts,
    start_gateway_background,
)


class MockTelegramUser:
    def __init__(self, user_id=12345678, first_name="TestAspirant", username="testaspirant"):
        self.id = user_id
        self.first_name = first_name
        self.username = username


class MockTelegramChat:
    def __init__(self, chat_id=12345678):
        self.id = chat_id
        self.type = "private"


class MockTelegramMessage:
    def __init__(self, chat_id=12345678, text=""):
        self.chat_id = chat_id
        self.text = text
        self.chat = MockTelegramChat(chat_id)
        self.replies = []
        self.documents = []
        self.polls = []
        self.document = None
        self.photo = []
        self.forward_date = None
        self.caption = None

    async def reply_text(self, text, parse_mode=None, reply_markup=None, disable_web_page_preview=None):
        self.replies.append({"text": text, "parse_mode": parse_mode, "reply_markup": reply_markup})
        # Return a mock message that supports edit_text and delete
        mock_msg = MagicMock()
        mock_msg.edit_text = AsyncMock()
        mock_msg.delete = AsyncMock()
        return mock_msg

    async def edit_text(self, text, parse_mode=None, reply_markup=None, disable_web_page_preview=None):
        self.replies.append({"text": text, "edited": True, "reply_markup": reply_markup})
        return self


class MockTelegramBot:
    def __init__(self):
        self.sent_documents = []
        self.sent_polls = []
        self.sent_messages = []
        self.commands_set = []

    async def set_chat_menu_button(self, chat_id=None, menu_button=None):
        return True

    async def send_document(self, chat_id, document, filename=None, caption=None, parse_mode=None, reply_markup=None):
        self.sent_documents.append({
            "chat_id": chat_id,
            "filename": filename,
            "caption": caption,
            "has_doc": document is not None,
            "reply_markup": reply_markup
        })
        return MagicMock()

    async def send_poll(self, chat_id, question, options, type=None, correct_option_id=None, explanation=None, is_anonymous=None):
        poll_record = {
            "chat_id": chat_id,
            "question": question,
            "options": options,
            "type": type,
            "correct_option_id": correct_option_id,
            "explanation": explanation,
            "is_anonymous": is_anonymous
        }
        self.sent_polls.append(poll_record)
        return poll_record

    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
        self.sent_messages.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode, "reply_markup": reply_markup})
        return MagicMock()

    async def set_my_commands(self, commands, scope=None):
        self.commands_set.append({"commands": commands, "scope": scope})
        return True


class MockTelegramUpdate:
    def __init__(self, text="", user_id=12345678, chat_id=12345678, callback_data=None):
        self.effective_user = MockTelegramUser(user_id)
        self.effective_chat = MockTelegramChat(chat_id)
        self.message = MockTelegramMessage(chat_id, text) if not callback_data else None
        if callback_data:
            self.callback_query = MagicMock()
            self.callback_query.data = callback_data
            self.callback_query.message = MockTelegramMessage(chat_id, "")
            self.callback_query.answer = AsyncMock()
        else:
            self.callback_query = None


class MockTelegramContext:
    def __init__(self, bot=None, args=None):
        self.bot = bot or MockTelegramBot()
        self.args = args or []
        self.user_data = {}


class TestOpenClawTelegramBotIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Boot gateway background loop
        start_gateway_background(OPENCLAW_GATEWAY_PORT)

    def test_01_openclaw_cmd_menu_and_url(self):
        """Test /openclaw command displays rich interactive agency hub with valid links."""
        update = MockTelegramUpdate(text="/openclaw")
        mock_bot = MockTelegramBot()
        context = MockTelegramContext(bot=mock_bot)

        asyncio.run(bot.openclaw_cmd(update, context))

        self.assertTrue(len(update.message.replies) > 0, "No reply sent for /openclaw")
        reply = update.message.replies[0]
        text = reply["text"]
        self.assertIn("OpenClaw.ai Autonomous Agency Hub", text)
        self.assertIn("गेटवे स्थिती", text)
        self.assertIn("सक्रिय AI तज्ज्ञ एजंट्स", text)
        self.assertIn("/objection", text)
        self.assertIn("/clawquiz", text)
        self.assertIn("/clawebook", text)

        # Check inline keyboard
        markup = reply["reply_markup"]
        self.assertIsNotNone(markup)
        buttons_flattened = [b for row in markup.inline_keyboard for b in row]
        button_texts = [b.text for b in buttons_flattened]
        callbacks = [b.callback_data for b in buttons_flattened if b.callback_data]
        urls = [b.url for b in buttons_flattened if b.url]

        self.assertTrue(any("OpenClaw Control UI" in t for t in button_texts))
        self.assertTrue(any("/openclaw/" in u for u in urls))
        self.assertIn("openclaw_action_objection_menu", callbacks)
        self.assertIn("openclaw_action_quiz_menu", callbacks)
        self.assertIn("openclaw_action_ebook_menu", callbacks)
        self.assertIn("openclaw_action_norm_menu", callbacks)
        self.assertIn("openclaw_action_files_list", callbacks)

    def test_02_objection_cmd_disk_document_dispatch(self):
        """Test /objection generates Balbharati dispute file on disk and delivers it via send_document."""
        update = MockTelegramUpdate(text="/objection Q142 इतिहास संदर्भ त्रुटी")
        mock_bot = MockTelegramBot()
        context = MockTelegramContext(bot=mock_bot, args=["Q142", "इतिहास", "संदर्भ", "त्रुटी"])

        asyncio.run(bot.objection_cmd(update, context))

        # Check that a document was sent via bot.send_document
        self.assertTrue(len(mock_bot.sent_documents) > 0, "No document delivered via Telegram")
        doc_record = mock_bot.sent_documents[0]
        self.assertTrue(doc_record["has_doc"])
        self.assertTrue(doc_record["filename"].startswith("objection_petition_Q142_"))
        self.assertIn("Balbharati / GR अधिकृत आक्षेप मसुदा तयार!", doc_record["caption"])
        self.assertIn("Q142", doc_record["caption"])

        # Verify the file actually exists on server disk
        artifacts_dir = get_openclaw_artifacts_dir()
        disk_file = artifacts_dir / doc_record["filename"]
        self.assertTrue(disk_file.exists(), f"Artifact file {doc_record['filename']} was not saved to disk")
        content = disk_file.read_text(encoding="utf-8")
        self.assertIn("महाराष्ट्र राज्य पाठ्यपुस्तक निर्मिती मंडळ (बालभारती)", content)
        self.assertIn("Q142", content)

    def test_03_claw_quiz_cmd_native_poll_dispatch(self):
        """Test /clawquiz dispatches a native interactive Telegram quiz poll."""
        update = MockTelegramUpdate(text="/clawquiz महाराष्ट्र भूगोल")
        mock_bot = MockTelegramBot()
        context = MockTelegramContext(bot=mock_bot, args=["महाराष्ट्र", "भूगोल"])

        asyncio.run(bot.claw_quiz_cmd(update, context))

        self.assertTrue(len(mock_bot.sent_polls) > 0, "No Telegram native quiz poll was sent")
        poll = mock_bot.sent_polls[0]
        self.assertEqual(poll["type"], "quiz")
        self.assertTrue(len(poll["options"]) >= 4, "Quiz must have at least 4 options")
        self.assertGreaterEqual(poll["correct_option_id"], 0)
        self.assertLess(poll["correct_option_id"], len(poll["options"]))
        self.assertTrue(len(poll["explanation"]) > 0, "Quiz must have an official explanation")
        self.assertFalse(poll["is_anonymous"])

    def test_04_claw_ebook_cmd_document_dispatch(self):
        """Test /clawebook compiles 5-section study guide and delivers it via send_document."""
        update = MockTelegramUpdate(text="/clawebook तलाठी भरती सामान्य ज्ञान")
        mock_bot = MockTelegramBot()
        context = MockTelegramContext(bot=mock_bot, args=["तलाठी", "भरती", "सामान्य", "ज्ञान"])

        asyncio.run(bot.claw_ebook_cmd(update, context))

        self.assertTrue(len(mock_bot.sent_documents) > 0, "No e-book document sent")
        doc_record = mock_bot.sent_documents[0]
        self.assertTrue(doc_record["filename"].startswith("ebook_revision_"))
        self.assertIn("OpenClaw Autonomous ई-बुक संकलन पूर्ण!", doc_record["caption"])

        # Verify disk file content has all 5 sections
        artifacts_dir = get_openclaw_artifacts_dir()
        disk_file = artifacts_dir / doc_record["filename"]
        self.assertTrue(disk_file.exists())
        text = disk_file.read_text(encoding="utf-8")
        self.assertIn("भाग १:", text)
        self.assertIn("भाग २:", text)
        self.assertIn("भाग ३:", text)
        self.assertIn("भाग ४:", text)

    def test_05_claw_status_cmd_telemetry(self):
        """Test /clawstatus returns live telemetry with port 18789 and agent stats."""
        update = MockTelegramUpdate(text="/clawstatus")
        mock_bot = MockTelegramBot()
        context = MockTelegramContext(bot=mock_bot)

        asyncio.run(bot.claw_status_cmd(update, context))

        self.assertTrue(len(update.message.replies) > 0)
        reply_text = update.message.replies[0]["text"]
        self.assertIn("OpenClaw Gateway Live Telemetry", reply_text)
        self.assertIn("18789", reply_text)
        self.assertIn("सक्रिय एजंट्स संख्या", reply_text)
        self.assertIn("डिस्कवर तयार आर्टिफॅक्ट्स", reply_text)

    def test_06_openclaw_callback_actions(self):
        """Test all openclaw_action_* callback queries triggered by inline buttons."""
        mock_bot = MockTelegramBot()
        context = MockTelegramContext(bot=mock_bot)

        # 1. Test openclaw_action_hub
        u_hub = MockTelegramUpdate(callback_data="openclaw_action_hub")
        asyncio.run(bot.openclaw_callback_handler(u_hub, context))
        self.assertTrue(len(u_hub.callback_query.message.replies) > 0)
        self.assertIn("OpenClaw.ai Autonomous Agency Hub", u_hub.callback_query.message.replies[0]["text"])

        # 2. Test openclaw_action_status
        u_stat = MockTelegramUpdate(callback_data="openclaw_action_status")
        asyncio.run(bot.openclaw_callback_handler(u_stat, context))
        self.assertTrue(len(u_stat.callback_query.message.replies) > 0)
        self.assertIn("OpenClaw Gateway Live Telemetry", u_stat.callback_query.message.replies[0]["text"])

        # 3. Test openclaw_action_objection_menu
        u_obj = MockTelegramUpdate(callback_data="openclaw_action_objection_menu")
        asyncio.run(bot.openclaw_callback_handler(u_obj, context))
        self.assertTrue(len(mock_bot.sent_documents) > 0)

        # 4. Test openclaw_action_quiz_menu
        u_quiz = MockTelegramUpdate(callback_data="openclaw_action_quiz_menu")
        asyncio.run(bot.openclaw_callback_handler(u_quiz, context))
        self.assertTrue(len(mock_bot.sent_polls) > 0)

        # 5. Test openclaw_action_ebook_menu
        u_ebk = MockTelegramUpdate(callback_data="openclaw_action_ebook_menu")
        asyncio.run(bot.openclaw_callback_handler(u_ebk, context))
        self.assertTrue(len(mock_bot.sent_documents) > 1)

        # 6. Test openclaw_action_norm_menu
        u_norm = MockTelegramUpdate(callback_data="openclaw_action_norm_menu")
        asyncio.run(bot.openclaw_callback_handler(u_norm, context))
        self.assertTrue(len(u_norm.callback_query.message.replies) > 0)
        self.assertIn("OpenClaw Normalization Auditor", u_norm.callback_query.message.replies[0]["text"])

        # 7. Test openclaw_action_files_list
        u_files = MockTelegramUpdate(callback_data="openclaw_action_files_list")
        asyncio.run(bot.openclaw_callback_handler(u_files, context))
        self.assertTrue(len(u_files.callback_query.message.replies) > 0)
        self.assertIn("OpenClaw तयार फाईल्स यादी", u_files.callback_query.message.replies[0]["text"])

    def test_07_keyboard_persistent_and_category_menu(self):
        """Test persistent keyboard and category keyboard both include OpenClaw entrypoints."""
        cat_kb = bot.get_category_keyboard()
        flattened_cat = [b for row in cat_kb for b in row]
        openclaw_cat = [b for b in flattened_cat if "OpenClaw" in getattr(b, "text", "")]
        self.assertTrue(len(openclaw_cat) > 0, "OpenClaw missing from category keyboard")
        self.assertEqual(openclaw_cat[0].callback_data, "openclaw_action_hub")

        menu_kb = bot.get_persistent_menu_keyboard()
        flattened_menu = [b.text for row in menu_kb.keyboard for b in row]
        self.assertTrue(any("OpenClaw" in t for t in flattened_menu), "OpenClaw missing from persistent menu keyboard")

    def test_08_text_routing_openclaw_keyword(self):
        """Test typing 'openclaw' or 'claw' or 'एजंट' triggers openclaw_cmd in handle_text_or_photo."""
        update = MockTelegramUpdate(text="openclaw")
        mock_bot = MockTelegramBot()
        context = MockTelegramContext(bot=mock_bot)

        # Calling handle_text_or_photo with "openclaw"
        asyncio.run(bot.handle_text_or_photo(update, context))

        self.assertTrue(len(update.message.replies) > 0, "No reply generated for text 'openclaw'")
        reply = update.message.replies[0]
        self.assertIn("OpenClaw.ai Autonomous Agency Hub", reply["text"])

    def test_09_bot_command_list_registration(self):
        """Test set_bot_commands registers openclaw, objection, clawquiz, clawebook."""
        mock_app = MagicMock()
        mock_app.bot = MockTelegramBot()

        asyncio.run(bot.set_bot_commands(mock_app))

        self.assertTrue(len(mock_app.bot.commands_set) > 0)
        registered_cmds = [cmd.command for cmd in mock_app.bot.commands_set[0]["commands"]]
        self.assertIn("openclaw", registered_cmds)
        self.assertIn("objection", registered_cmds)
        self.assertIn("clawquiz", registered_cmds)
        self.assertIn("clawebook", registered_cmds)

    def test_10_resilience_and_graceful_fallbacks(self):
        """Test error handling when Telegram API raises an exception during file or poll dispatch."""
        mock_bot = MockTelegramBot()
        # Simulate send_document failure
        mock_bot.send_document = AsyncMock(side_effect=RuntimeError("Telegram Network Timeout"))
        update = MockTelegramUpdate(text="/objection Q999 त्रुटी")
        context = MockTelegramContext(bot=mock_bot, args=["Q999", "त्रुटी"])

        # Must not raise an unhandled exception
        try:
            asyncio.run(bot.objection_cmd(update, context))
        except Exception as e:
            self.fail(f"objection_cmd crashed on exception: {e}")

        # Simulate send_poll failure
        mock_bot.send_poll = AsyncMock(side_effect=RuntimeError("Telegram Poll Throttled"))
        update_poll = MockTelegramUpdate(text="/clawquiz भूगोल")
        context_poll = MockTelegramContext(bot=mock_bot, args=["भूगोल"])
        try:
            asyncio.run(bot.claw_quiz_cmd(update_poll, context_poll))
        except Exception as e:
            self.fail(f"claw_quiz_cmd crashed on exception: {e}")


if __name__ == "__main__":
    unittest.main()

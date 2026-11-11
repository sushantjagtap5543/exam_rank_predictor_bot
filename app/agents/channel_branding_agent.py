"""
ChannelBrandingAgent: Senior Brand & Exam Trend Strategist.
Continuously analyzes incoming candidate response sheets to identify trending TCS & IBPS exams
and dynamically updates the Telegram Channel's Title, Description, and pinned branding.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, Tuple

from .base_agent import BaseSeniorAgent

logger = logging.getLogger(__name__)

class ChannelBrandingAgent(BaseSeniorAgent):
    """
    Senior Executive Brand Strategist:
    Specializes in algorithmic trend detection, viral naming, and audience positioning
    for Maharashtra TCS/IBPS government recruitment exams.
    """

    def __init__(self):
        super().__init__(
            name="BrandTrendMaster-3000",
            role="Chief Brand Strategist & Audience Retention Director",
            seniority="Principal Brand Director (15+ Years in Media Growth & Exam Community Strategy)",
            core_competencies=[
                "Real-time exam frequency trend analysis",
                "High-conversion Telegram channel naming (under 128 chars)",
                "Dynamic bio & hashtag optimization for search visibility",
                "Candidate FOMO & engagement positioning"
            ],
            system_instruction=(
                "Your objective is to craft irresistible, authoritative Telegram channel titles "
                "that immediately inform candidates that this channel is the #1 live hub for their ongoing exam."
            )
        )

    def detect_trending_exam(self, db_path: str = "bot.db") -> Dict[str, Any]:
        """
        Queries recent uploads to determine the most active TCS/IBPS exam in Maharashtra.
        """
        trending = {
            "exam_name": "TCS & IBPS सरळसेवा भरती",
            "count": 0,
            "detected": False
        }
        try:
            # Load display names from exams.json if present
            exams_json_path = Path(__file__).resolve().parent.parent / "exams.json"
            exams_map = {}
            if exams_json_path.exists():
                try:
                    exams_map = json.loads(exams_json_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            with sqlite3.connect(db_path, timeout=30.0) as db:
                row = db.execute("""
                    SELECT exam_key, post_name, COUNT(*) as cnt
                    FROM uploads
                    WHERE exam_key IS NOT NULL AND exam_key != ''
                    GROUP BY exam_key, post_name
                    ORDER BY MAX(created_at) DESC, cnt DESC
                    LIMIT 1
                """).fetchone()

                if row and row[0]:
                    key = row[0]
                    post = row[1] or ""
                    exam_info = exams_map.get(key, {})
                    disp_name = exam_info.get("name") or key.replace("_", " ").title()
                    if post and post not in disp_name:
                        full_name = f"{disp_name} ({post})"
                    else:
                        full_name = disp_name

                    trending["exam_name"] = full_name
                    trending["count"] = row[2]
                    trending["detected"] = True
        except Exception as e:
            logger.warning(f"Could not query uploads table: {e}")

        return trending

    async def generate_channel_branding(self, exam_name: str) -> Tuple[str, str]:
        """
        Generates optimized channel title and bio.
        """
        task = (
            f"Active Government Exam: '{exam_name}'.\n"
            "Generate:\n"
            "1. title: Channel title strictly under 110 characters. Format should be: "
            "'ExamRankers™ | TCS-IBPS [Short Exam Name] Live Key & Quizzes' or similar authoritative Marathi/English mix.\n"
            "2. description: Engaging bio under 250 characters highlighting 1-by-1 quizzes, cutoff rank, and answer key discussion.\n"
            "Return JSON with keys 'title' and 'description'."
        )

        result = await self.execute_task(task, temperature=0.3, expect_json=True)
        if isinstance(result, dict) and "title" in result and "description" in result:
            title = result["title"].strip()[:120]
            desc = result["description"].strip()[:255]
            return title, desc

        # Heuristic fallback
        clean_exam = exam_name.replace("Maharashtra", "").replace("Exam", "").strip()
        title = f"ExamRankers™ | TCS {clean_exam} Live Key & Quizzes"[:120]
        desc = (
            f"🎯 अधिकृत {clean_exam} TCS/IBPS भरती हब.\n"
            f"✅ रिस्पॉन्स शीट गुण, गुणवत्ता यादी व ४-टियर रँक.\n"
            f"⚡ 1-by-1 रिअल परीक्षा सराव क्विझ आणि स्पष्टीकरण.\n"
            f"🤖 बॉट: @ExamRankersIndiaBot"
        )[:255]
        return title, desc

    async def sync_telegram_channel_title(self, bot, channel_id: str or int, db_path: str = "bot.db") -> Dict[str, Any]:
        """
        Executes real-time sync with Telegram API to rename channel if exam has shifted.
        """
        trending = self.detect_trending_exam(db_path)
        exam_name = trending["exam_name"]

        title, desc = await self.generate_channel_branding(exam_name)
        target_chat = int(channel_id) if str(channel_id).lstrip("-").isdigit() else channel_id

        status = {
            "success": False,
            "exam_name": exam_name,
            "title": title,
            "desc": desc,
            "message": ""
        }

        try:
            chat = await bot.get_chat(chat_id=target_chat)
            current_title = chat.title or ""

            # Check if title already matches to prevent hitting Telegram rate limits
            if current_title.strip() == title.strip():
                status["success"] = True
                status["message"] = f"Channel title is already up to date: '{title}'"
                return status

            # Attempt to set title
            await bot.set_chat_title(chat_id=target_chat, title=title)
            try:
                await bot.set_chat_description(chat_id=target_chat, description=desc)
            except Exception as e_desc:
                logger.info(f"Bio update note: {e_desc}")

            status["success"] = True
            status["message"] = f"Successfully updated channel title to: '{title}'"
            logger.info(f"🏆 ChannelBrandingAgent: Renamed channel to: {title}")
        except Exception as e:
            status["message"] = f"Could not update channel info (Check if bot has 'can_change_info' admin permission): {e}"
            logger.warning(f"Channel title update warning: {e}")

        return status

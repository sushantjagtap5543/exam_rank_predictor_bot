import os
import asyncio
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_telethon_client = None

async def get_telethon_client() -> Optional[object]:
    """
    Initializes MTProto Telethon client with cryptg C-acceleration.
    Requires own TELEGRAM_API_ID and TELEGRAM_API_HASH from my.telegram.org.
    Never defaults to test/desktop ID 2040.
    """
    global _telethon_client
    api_id_str = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

    if not api_id_str or not api_hash or not token:
        logger.debug("MTProto client skipped: TELEGRAM_API_ID/TELEGRAM_API_HASH not configured.")
        return None

    try:
        api_id = int(api_id_str)
        if api_id == 2040:
            logger.warning("Rejected public desktop API_ID 2040. Please provide your own TELEGRAM_API_ID from my.telegram.org.")
            return None
    except ValueError:
        logger.warning(f"Invalid TELEGRAM_API_ID: '{api_id_str}'")
        return None

    if _telethon_client is None or not _telethon_client.is_connected():
        try:
            from telethon import TelegramClient
            storage_dir = Path(os.getenv("ADMIN_STORAGE_DIR", "admin_storage"))
            storage_dir.mkdir(parents=True, exist_ok=True)
            session_path = str(storage_dir / "bot_mtproto.session")
            _telethon_client = TelegramClient(session_path, api_id, api_hash)
            await _telethon_client.start(bot_token=token)
            logger.info("Telethon MTProto client initialized successfully with own credentials!")
        except Exception as e:
            logger.warning(f"Failed to initialize Telethon MTProto client: {e}")
            return None

    return _telethon_client

async def download_file_mtproto(chat_id: int, message_id: int, destination_path: str, timeout_seconds: float = 120.0) -> bool:
    """
    Downloads Telegram document using MTProto without the 20MB Cloud Bot API cap.
    Returns False if MTProto client is not configured or download fails.
    """
    try:
        client = await get_telethon_client()
        if not client:
            return False

        async with asyncio.timeout(timeout_seconds):
            msg = await client.get_messages(chat_id, ids=message_id)
            if not msg or not msg.media:
                logger.warning(f"Message {message_id} in {chat_id} has no downloadable media.")
                return False

            out_path = await client.download_media(msg, file=destination_path)
            return bool(out_path and Path(out_path).exists() and Path(out_path).stat().st_size > 0)
    except Exception as e:
        logger.warning(f"MTProto download failed for message {message_id}: {e}")
        return False

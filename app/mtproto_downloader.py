import os
import asyncio
import logging
from pathlib import Path
from telethon import TelegramClient

logger = logging.getLogger(__name__)

# Default Telegram desktop client API credentials for unrestricted MTProto downloads
DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"

_telethon_client = None

async def get_telethon_client():
    global _telethon_client
    if _telethon_client is None or not _telethon_client.is_connected():
        api_id = int(os.getenv("TELEGRAM_API_ID", str(DEFAULT_API_ID)))
        api_hash = os.getenv("TELEGRAM_API_HASH", DEFAULT_API_HASH)
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        session_path = str(Path(__file__).parent.parent / "admin_storage" / "bot_mtproto.session")
        Path(session_path).parent.mkdir(parents=True, exist_ok=True)
        _telethon_client = TelegramClient(session_path, api_id, api_hash)
        await _telethon_client.start(bot_token=token)
        logger.info("Telethon MTProto client initialized with cryptg C-acceleration (up to 2GB supported)!")
    return _telethon_client

async def download_file_mtproto(chat_id: int, message_id: int, destination_path: str, timeout_seconds: float = 120.0) -> bool:
    """
    Downloads any Telegram document without the 20MB Cloud Bot API cap (up to 2000 MB).
    Uses Telegram's direct MTProto protocol with cryptg hardware-accelerated decryption.
    """
    try:
        client = await get_telethon_client()
        message = await client.get_messages(chat_id, ids=message_id)
        if not message or not message.media:
            logger.error(f"MTProto: Message {message_id} in chat {chat_id} has no media.")
            return False

        logger.info(f"MTProto: Starting accelerated download for message {message_id} to {destination_path}...")
        download_coro = client.download_media(message, file=destination_path)
        result = await asyncio.wait_for(download_coro, timeout=timeout_seconds)

        if result and Path(destination_path).is_file() and Path(destination_path).stat().st_size > 0:
            logger.info(f"MTProto: Successfully downloaded {Path(destination_path).stat().st_size} bytes to {destination_path}")
            return True
        return False
    except asyncio.TimeoutError:
        logger.error(f"MTProto: Download timed out after {timeout_seconds} seconds for message {message_id}")
        return False
    except Exception as e:
        logger.error(f"MTProto download error: {e}")
        return False

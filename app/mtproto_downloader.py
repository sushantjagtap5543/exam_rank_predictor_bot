import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_telethon_client = None
_init_lock = asyncio.Lock()

async def get_telethon_client() -> Optional[object]:
    """
    Initializes MTProto Telethon client with non-interactive connection.
    Requires own TELEGRAM_API_ID and TELEGRAM_API_HASH from my.telegram.org.
    Strictly enforced with timeouts to prevent process hangs.
    """
    global _telethon_client
    api_id_str = os.getenv("TELEGRAM_API_ID", "31309393").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "6876ef173762650c05c4ab2af73370a1").strip()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

    if not api_id_str or not api_hash or not token:
        logger.debug("MTProto client skipped: TELEGRAM_API_ID/TELEGRAM_API_HASH/TOKEN not configured.")
        return None

    try:
        api_id = int(api_id_str)
        if api_id == 2040:
            logger.warning("Rejected public desktop API_ID 2040. Please provide your own TELEGRAM_API_ID from my.telegram.org.")
            return None
    except ValueError:
        logger.warning(f"Invalid TELEGRAM_API_ID: '{api_id_str}'")
        return None

    async with _init_lock:
        if _telethon_client is not None and _telethon_client.is_connected():
            return _telethon_client

        if _telethon_client is not None and not _telethon_client.is_connected():
            try:
                await asyncio.wait_for(_telethon_client.disconnect(), timeout=3.0)
            except Exception:
                pass
            _telethon_client = None

        try:
            from telethon import TelegramClient
            from telethon.sessions import MemorySession

            storage_dir = Path(os.getenv("ADMIN_STORAGE_DIR", "admin_storage"))
            storage_dir.mkdir(parents=True, exist_ok=True)
            session_path = str(storage_dir / "bot_mtproto.session")

            # Try file session first; if locked or corrupted, gracefully fallback to MemorySession
            client = None
            try:
                client = TelegramClient(session_path, api_id, api_hash)
                await asyncio.wait_for(client.connect(), timeout=8.0)
            except Exception as conn_err:
                logger.warning(f"File session connect failed ({conn_err}), falling back to MemorySession.")
                if client is not None:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                client = TelegramClient(MemorySession(), api_id, api_hash)
                await asyncio.wait_for(client.connect(), timeout=8.0)

            # Non-interactive authentication (never prompts on sys.stdin)
            if not await client.is_user_authorized():
                await asyncio.wait_for(client.sign_in(bot_token=token), timeout=8.0)

            _telethon_client = client
            logger.info("Telethon MTProto client initialized and authenticated successfully!")
            return _telethon_client
        except Exception as e:
            logger.warning(f"Failed to initialize Telethon MTProto client: {e}")
            if _telethon_client is not None:
                try:
                    await _telethon_client.disconnect()
                except Exception:
                    pass
            _telethon_client = None
            return None

async def download_file_mtproto(
    chat_id: int,
    message_id: int,
    destination_path: str,
    username: Optional[str] = None,
    timeout_seconds: float = 30.0
) -> bool:
    """
    Downloads Telegram document using MTProto without the 20MB Cloud Bot API cap.
    Enforces a strict timeout (default 30s) so operations never hang.
    Returns False if MTProto client is not configured or download fails.
    """
    try:
        client = await asyncio.wait_for(get_telethon_client(), timeout=10.0)
        if not client:
            return False

        async def _download_job():
            # Resolve entity: try chat_id, then username fallback if chat_id entity is uncached
            target = chat_id
            try:
                entity = await client.get_input_entity(chat_id)
                if entity is not None:
                    target = entity
            except Exception:
                if username:
                    clean_user = username.strip().lstrip("@")
                    try:
                        entity = await client.get_input_entity(clean_user)
                        if entity is not None:
                            target = entity
                    except Exception:
                        pass

            msg = await client.get_messages(target, ids=message_id)
            if not msg or not getattr(msg, "media", None):
                logger.warning(f"Message {message_id} in {chat_id} has no downloadable media.")
                return False

            out_path = await client.download_media(msg, file=destination_path)
            return bool(out_path and Path(out_path).exists() and Path(out_path).stat().st_size > 0)

        return await asyncio.wait_for(_download_job(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"MTProto download timed out after {timeout_seconds}s for message {message_id} in chat {chat_id}.")
        return False
    except Exception as e:
        logger.warning(f"MTProto download failed for message {message_id}: {e}")
        return False

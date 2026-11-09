import os
import sys
import tempfile
from pathlib import Path
import pytest

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Safe offline test environment
os.environ["TELEGRAM_BOT_TOKEN"] = "123456789:ABCdefGHIjklMNOpqrsTUVwxyzDummyToken"
os.environ["AI_PROVIDER_CHAIN"] = "offline"
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["DOWNLOAD_SECRET_KEY"] = "examrankers_test_signing_secret_key_32bytes"
os.environ["ADMIN_API_KEY"] = "super-secret-admin-key-test-999"
os.environ["CASHFREE_SECRET_KEY"] = "cf-test-secret-key-32bytes-mock"
os.environ["CASHFREE_APP_ID"] = "cf-app-test-mock-id"
os.environ["CASHFREE_ENV"] = "sandbox"
os.environ["PAID_CHANNEL_ID"] = "-1001234567890"

from app.bot import init_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Initializes the database and ensures offline isolation for all tests."""
    init_db()
    yield

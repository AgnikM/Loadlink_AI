import os
import sys
import pytest
import pytest_asyncio

# Direct all test database operations to an isolated temporary database
_tests_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_tests_dir, "..")))
_test_db_path = os.path.join(_tests_dir, "test_isolated.db").replace("\\", "/")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_db_path}"

from app.core.config import settings
settings.DATABASE_URL = f"sqlite+aiosqlite:///{_test_db_path}"

from seed_corridor_data import seed_database

@pytest_asyncio.fixture(autouse=True, scope="function")
async def seed_before_test():
    await seed_database()

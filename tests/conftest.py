"""Shared test fixtures.

Includes both the original infrastructure fixtures (temp_db, mock_crawler_config, etc.)
and the new auth mock fixtures from the FIXSHEET review.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from bs4 import BeautifulSoup

from webreaper.auth import AuthUser, _verify_token


# ── Pytest-asyncio configuration ───────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Database fixtures ───────────────────────────────────────

@pytest_asyncio.fixture
async def temp_db():
    """In-memory SQLite DatabaseManager for tests."""
    from webreaper.database import DatabaseManager
    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.init_async()
    await db.create_tables()
    yield db
    await db.close()


@pytest.fixture
def mock_db_session():
    """Mock database session for unit tests that don't need a real DB."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


# ── Auth mock fixtures (from FIXSHEET review) ───────────────
# These replace DEV_SKIP_AUTH with proper FastAPI dependency overrides.

TEST_USER = AuthUser(
    id="test-user-001",
    email="test@example.com",
    plan="agency",
)


@pytest.fixture()
def test_user() -> AuthUser:
    """Override this fixture to test with a different plan/user."""
    return TEST_USER


@pytest.fixture()
def app(test_user: AuthUser):
    """Provide the FastAPI app with auth dependency overridden."""
    from server.main import app as _app

    async def _mock_verify_token():
        return test_user

    _app.dependency_overrides[_verify_token] = _mock_verify_token
    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture()
def client(app):
    """Synchronous test client with auth pre-bypassed."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture()
def starter_user() -> AuthUser:
    return AuthUser(id="starter-user", email="starter@test.com", plan="starter")


@pytest.fixture()
def pro_user() -> AuthUser:
    return AuthUser(id="pro-user", email="pro@test.com", plan="pro")


@pytest.fixture()
def agency_user() -> AuthUser:
    return AuthUser(id="agency-user", email="agency@test.com", plan="agency")


# ── Crawler fixtures ────────────────────────────────────────

@pytest.fixture
def mock_crawler_config():
    """Default crawler config suitable for tests."""
    from webreaper.config import Config
    cfg = Config()
    cfg.crawler.max_depth = 2
    cfg.crawler.max_pages = 10
    cfg.crawler.concurrency = 1
    cfg.crawler.rate_limit = 100.0
    cfg.crawler.respect_robots = False
    return cfg


# ── HTTP mock fixtures ──────────────────────────────────────

@pytest.fixture
def sample_html_page():
    return """<!DOCTYPE html>
<html>
<head>
  <title>Test Page</title>
  <meta name="description" content="A test page">
</head>
<body>
  <h1>Hello World</h1>
  <h2>Section One</h2>
  <a href="/page2">Internal link</a>
  <a href="https://external.com/page">External link</a>
  <img src="/img/logo.png" alt="Logo">
  <form method="POST" action="/submit">
    <input name="email" type="email" required>
    <input name="csrf_token" type="hidden">
    <input type="submit" value="Submit">
  </form>
</body>
</html>"""


@pytest.fixture
def sample_headers():
    return {
        "Content-Type": "text/html; charset=utf-8",
        "Strict-Transport-Security": "max-age=31536000",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'self'",
    }

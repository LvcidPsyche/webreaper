import pytest
from webreaper.models import User, Scraper, UserUsage, Job
from webreaper.database import Base

def test_user_model():
    user = User(email="test@example.com")
    assert user.email == "test@example.com"
    # id is populated by SQLAlchemy default on insert, not on construction
    # To test with an explicit id:
    user2 = User(id="abc-123", email="test2@example.com")
    assert user2.id == "abc-123"

def test_scraper_model():
    scraper = Scraper(name="Test Scraper", target_url="https://example.com")
    assert scraper.name == "Test Scraper"
    assert scraper.target_url == "https://example.com"
    
def test_usage_model():
    usage = UserUsage(pages_scraped=100)
    assert usage.pages_scraped == 100

def test_job_model():
    job = Job(status="pending")
    assert job.status == "pending"

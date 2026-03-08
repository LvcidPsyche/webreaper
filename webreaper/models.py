from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from webreaper.database import Base

def _now():
    return datetime.now(timezone.utc)

def _uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = 'users'
    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)
    
    usages = relationship("UserUsage", back_populates="user")
    scrapers = relationship("Scraper", back_populates="user")

class UserUsage(Base):
    __tablename__ = 'user_usages'
    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    pages_scraped = Column(Integer, default=0, nullable=False)
    bytes_downloaded = Column(Integer, default=0, nullable=False)
    period_start = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint('user_id', 'period_start', name='uq_user_period'),
    )

    user = relationship("User", back_populates="usages")

class Scraper(Base):
    __tablename__ = 'scrapers'
    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(255), nullable=False)
    target_url = Column(String(1024), nullable=False)
    schedule = Column(String(100), nullable=True) # cron string
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)

    user = relationship("User", back_populates="scrapers")
    jobs = relationship("Job", back_populates="scraper")

class Job(Base):
    __tablename__ = 'jobs'
    id = Column(String(36), primary_key=True, default=_uuid)
    scraper_id = Column(String(36), ForeignKey('scrapers.id', ondelete='CASCADE'), nullable=False)
    status = Column(String(50), default="pending", nullable=False) # pending, running, completed, failed
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    pages_scraped = Column(Integer, default=0)
    result_data = Column(JSON, nullable=True)
    
    scraper = relationship("Scraper", back_populates="jobs")

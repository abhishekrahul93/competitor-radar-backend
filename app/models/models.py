"""
Database models — PostgreSQL tables via SQLAlchemy.
"""
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), default="")
    plan = Column(String(50), default="free")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    competitors = relationship("Competitor", back_populates="user", cascade="all, delete-orphan")


class Competitor(Base):
    __tablename__ = "competitors"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    website_url = Column(String(500), nullable=False)
    pricing_url = Column(String(500))
    careers_url = Column(String(500))
    github_url = Column(String(500))
    docs_url = Column(String(500))
    category = Column(String(100), default="general")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="competitors")
    snapshots = relationship("Snapshot", back_populates="competitor", cascade="all, delete-orphan")
    changes = relationship("Change", back_populates="competitor", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="competitor", cascade="all, delete-orphan")


class Snapshot(Base):
    __tablename__ = "snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=False)
    page_type = Column(String(50), nullable=False)
    url = Column(String(500), nullable=False)
    content_hash = Column(String(64), nullable=False)
    content_data = Column(JSON)
    raw_text = Column(Text)
    status = Column(String(20), default="success")
    error_message = Column(Text)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    
    competitor = relationship("Competitor", back_populates="snapshots")


class Change(Base):
    __tablename__ = "changes"
    
    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=False)
    page_type = Column(String(50), nullable=False)
    change_type = Column(String(100), nullable=False)
    change_category = Column(String(50))
    summary = Column(Text)
    details = Column(JSON)
    significance = Column(Float, default=0.0)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    
    competitor = relationship("Competitor", back_populates="changes")
    reports = relationship("Report", back_populates="change")


class Report(Base):
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"))
    change_id = Column(Integer, ForeignKey("changes.id"))
    report_type = Column(String(50), nullable=False)
    title = Column(Text)
    what_changed = Column(Text)
    why_it_matters = Column(Text)
    what_to_do = Column(Text)
    threat_level = Column(Text)
    full_analysis = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    competitor = relationship("Competitor", back_populates="reports")
    change = relationship("Change", back_populates="reports")
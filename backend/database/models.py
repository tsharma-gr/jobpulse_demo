from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, JSON, Text
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(JSON)

class SearchSession(Base):
    __tablename__ = "search_sessions"
    id = Column(String, primary_key=True, index=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    query_params = Column(JSON)  # Job titles, location, radius, etc.
    status = Column(String)  # STARTED, COMPLETED, FAILED
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    
    results = relationship("SearchResult", back_populates="session")

class SearchResult(Base):
    __tablename__ = "search_results"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("search_sessions.id"))
    url = Column(String, index=True)
    source = Column(String)
    discovered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String)  # EXTRACTED, VERIFIED, REJECTED
    
    session = relationship("SearchSession", back_populates="results")
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    job = relationship("Job")

class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    website = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    
    jobs = relationship("Job", back_populates="company")

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    title = Column(String, index=True)
    location = Column(String)
    salary_raw = Column(String, nullable=True)
    employment_type = Column(String, nullable=True)
    posted_date = Column(DateTime, nullable=True)
    description = Column(Text)
    
    # AI Extracted/Ranked fields
    match_score = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    seniority = Column(String, nullable=True)
    skills = Column(JSON, nullable=True)
    industry_match = Column(String, nullable=True)
    reason_for_match = Column(Text, nullable=True)
    
    # Verification
    is_active = Column(Boolean, default=True)
    
    company = relationship("Company", back_populates="jobs")

class Cache(Base):
    __tablename__ = "cache"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)  # URL or hash
    content = Column(Text)  # HTML or Markdown
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class SystemLog(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("search_sessions.id"), nullable=True)
    level = Column(String)  # INFO, WARNING, ERROR
    event = Column(String)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

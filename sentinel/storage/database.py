"""SQLAlchemy SQLite database setup and ORM models for SENTINEL."""

from __future__ import annotations

import json
import time
from typing import Any, Dict
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class IncidentEntity(Base):
    """Persistent storage for safety incidents and complete evidence audit."""
    __tablename__ = "incidents"

    incident_id = Column(String(64), primary_key=True)
    person_id = Column(String(64), index=True, nullable=False)
    incident_type = Column(String(64), index=True, nullable=False)
    risk_level = Column(String(32), index=True, nullable=False)
    risk_score = Column(Float, nullable=False)
    status = Column(String(32), default="DETECTED", nullable=False)  # DETECTED, UNDER_REVIEW, ACKNOWLEDGED, RESOLVED
    started_at = Column(Float, nullable=False)
    updated_at = Column(Float, nullable=False)
    narrative = Column(Text, default="")
    evidence_json = Column(Text, default="{}")
    recommended_action = Column(Text, default="")
    acknowledged_by = Column(String(128), nullable=True)
    acknowledged_at = Column(Float, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(Float, nullable=True)


class PersonProfileEntity(Base):
    """Person profiles, baseline statistics, and monitoring preferences."""
    __tablename__ = "person_profiles"

    person_id = Column(String(64), primary_key=True)
    full_name = Column(String(128), nullable=False)
    room_number = Column(String(32), nullable=True)
    care_notes = Column(Text, default="")
    baseline_stats_json = Column(Text, default="{}")
    created_at = Column(Float, default=time.time)
    updated_at = Column(Float, default=time.time)


class AuditLogEntity(Base):
    """Immutable audit trail for all system decisions, alerts, and operator actions."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False)
    actor = Column(String(128), default="SYSTEM")
    timestamp = Column(Float, default=time.time)
    details_json = Column(Text, default="{}")


def init_db(db_url: str = "sqlite:///sentinel.db"):
    """Initialize database schema."""
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal

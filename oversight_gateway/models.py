"""Database models for Oversight Gateway"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, Index
from .database import Base


class NearMissType(str, Enum):
    """Types of near-miss events"""
    BOUNDARY_VIOLATION = "boundary_violation"
    RESOURCE_OVERUSE = "resource_overuse"
    TIMING_ANOMALY = "timing_anomaly"
    PERMISSION_ESCALATION = "permission_escalation"
    DATA_EXPOSURE = "data_exposure"
    CASCADE_TRIGGER = "cascade_trigger"
    POLICY_DRIFT = "policy_drift"


class Action(Base):
    """Record of evaluated actions"""
    __tablename__ = "actions"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    target = Column(String, nullable=True)
    action_metadata = Column(JSON, nullable=True)
    
    # Risk scoring
    impact = Column(Float, nullable=False)
    breadth = Column(Float, nullable=False)
    probability = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)
    
    # Checkpoint
    needs_checkpoint = Column(Boolean, nullable=False)
    checkpoint_reason = Column(String, nullable=True)
    approved = Column(Boolean, nullable=True)
    approval_timestamp = Column(DateTime, nullable=True)
    approval_channel = Column(String, nullable=True)  # rest, websocket, webhook, auto
    approval_notes = Column(String, nullable=True)
    
    # Compound action tracking
    is_compound = Column(Boolean, default=False)
    compound_count = Column(Integer, default=1)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_session_target_time', 'session_id', 'target', 'created_at'),
        Index('ix_action_checkpoint', 'action', 'needs_checkpoint'),
    )


class NearMiss(Base):
    """Record of near-miss events for learning"""
    __tablename__ = "near_misses"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    target = Column(String, nullable=True)
    near_miss_type = Column(String, nullable=False)
    description = Column(String, nullable=True)
    near_miss_metadata = Column(JSON, nullable=True)
    
    # Original risk vs actual risk
    original_risk = Column(Float, nullable=True)
    actual_severity = Column(Float, nullable=False)  # 0.0-1.0
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_action_type', 'action', 'near_miss_type'),
    )


class Session(Base):
    """Session tracking for risk budgets"""
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    risk_budget = Column(Float, default=0.8)
    cumulative_risk = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)


class Webhook(Base):
    """Registered webhooks for event notifications"""
    __tablename__ = "webhooks"
    
    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False)
    events = Column(JSON, nullable=False)  # List of event types
    secret = Column(String, nullable=True)  # Optional HMAC secret
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_triggered = Column(DateTime, nullable=True)
    failure_count = Column(Integer, default=0)

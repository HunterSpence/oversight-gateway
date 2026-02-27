"""Database models for Oversight Gateway"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class NearMissType(str, Enum):
    BOUNDARY_VIOLATION = "boundary_violation"
    RESOURCE_OVERUSE = "resource_overuse"
    TIMING_ANOMALY = "timing_anomaly"
    PERMISSION_ESCALATION = "permission_escalation"
    DATA_EXPOSURE = "data_exposure"
    CASCADE_TRIGGER = "cascade_trigger"
    POLICY_DRIFT = "policy_drift"


class Action(Base):
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
    
    # Compound action tracking
    is_compound = Column(Boolean, default=False)
    compound_count = Column(Integer, default=1)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_session_target_time', 'session_id', 'target', 'created_at'),
    )


class NearMiss(Base):
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
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    risk_budget = Column(Float, default=0.8)
    cumulative_risk = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)

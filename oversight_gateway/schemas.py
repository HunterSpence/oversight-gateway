"""Pydantic schemas for API requests/responses"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class EvaluateRequest(BaseModel):
    session_id: str = Field(..., description="Session identifier")
    action: str = Field(..., description="Action to evaluate (e.g., 'send_email')")
    target: Optional[str] = Field(None, description="Target of the action (e.g., email address)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for risk scoring")


class EvaluateResponse(BaseModel):
    action_id: int
    session_id: str
    risk_score: float
    impact: float
    breadth: float
    probability: float
    needs_checkpoint: bool
    checkpoint_reason: str
    remaining_budget: float
    is_compound: bool
    compound_count: int


class ApprovalRequest(BaseModel):
    action_id: int
    approved: bool
    notes: Optional[str] = None


class ApprovalResponse(BaseModel):
    action_id: int
    approved: bool
    message: str


class NearMissRequest(BaseModel):
    session_id: str
    action: str
    near_miss_type: str = Field(..., description="One of: boundary_violation, resource_overuse, timing_anomaly, permission_escalation, data_exposure, cascade_trigger, policy_drift")
    actual_severity: float = Field(..., ge=0.0, le=1.0, description="Severity of the near-miss (0.0-1.0)")
    target: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    original_risk: Optional[float] = None


class NearMissResponse(BaseModel):
    message: str
    near_miss_id: int


class BudgetResponse(BaseModel):
    session_id: str
    risk_budget: float
    cumulative_risk: float
    remaining_budget: float
    utilization_percent: float


class StatsResponse(BaseModel):
    total_actions: int
    checkpoints_triggered: int
    checkpoints_approved: int
    checkpoints_rejected: int
    approval_rate: float
    total_near_misses: int
    near_miss_breakdown: Dict[str, int]
    average_risk_score: float


class HealthResponse(BaseModel):
    status: str
    version: str

"""Pydantic schemas for API requests/responses using Pydantic v2 style"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


# Request schemas

class EvaluateRequest(BaseModel):
    """Request to evaluate an action for risk"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    session_id: str = Field(..., description="Session identifier")
    action: str = Field(..., description="Action to evaluate (e.g., 'send_email')")
    target: Optional[str] = Field(None, description="Target of the action")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for risk scoring")


class ApprovalRequest(BaseModel):
    """Request to approve or reject an action"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    action_id: int = Field(..., description="Action ID to approve/reject")
    approved: bool = Field(..., description="True to approve, False to reject")
    notes: Optional[str] = Field(None, description="Optional approval notes")
    channel: str = Field("rest", description="Approval channel (rest, websocket, webhook, auto)")


class NearMissRequest(BaseModel):
    """Request to record a near-miss event"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    session_id: str
    action: str
    near_miss_type: str = Field(..., description="One of: boundary_violation, resource_overuse, timing_anomaly, permission_escalation, data_exposure, cascade_trigger, policy_drift")
    actual_severity: float = Field(..., ge=0.0, le=1.0, description="Severity of the near-miss (0.0-1.0)")
    target: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    original_risk: Optional[float] = None


class WebhookRegisterRequest(BaseModel):
    """Request to register a webhook"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    url: str = Field(..., description="Webhook URL")
    events: List[str] = Field(..., description="List of events to subscribe to")
    secret: Optional[str] = Field(None, description="Optional HMAC secret for verification")


# Response schemas

class EvaluateResponse(BaseModel):
    """Response from action evaluation"""
    model_config = ConfigDict(from_attributes=True)
    
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


class ApprovalResponse(BaseModel):
    """Response from approval action"""
    model_config = ConfigDict(from_attributes=True)
    
    action_id: int
    approved: bool
    message: str


class NearMissResponse(BaseModel):
    """Response from near-miss recording"""
    model_config = ConfigDict(from_attributes=True)
    
    message: str
    near_miss_id: int


class BudgetResponse(BaseModel):
    """Response with session budget information"""
    model_config = ConfigDict(from_attributes=True)
    
    session_id: str
    risk_budget: float
    cumulative_risk: float
    remaining_budget: float
    utilization_percent: float


class StatsResponse(BaseModel):
    """Response with system statistics"""
    model_config = ConfigDict(from_attributes=True)
    
    total_actions: int
    checkpoints_triggered: int
    checkpoints_approved: int
    checkpoints_rejected: int
    approval_rate: float
    total_near_misses: int
    near_miss_breakdown: Dict[str, int]
    average_risk_score: float


class HealthResponse(BaseModel):
    """Response from health check"""
    model_config = ConfigDict(from_attributes=True)
    
    status: str
    version: str


class WebhookResponse(BaseModel):
    """Response from webhook registration"""
    model_config = ConfigDict(from_attributes=True)
    
    webhook_id: int
    url: str
    events: List[str]
    message: str


class AuditLogEntry(BaseModel):
    """Single audit log entry"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    session_id: str
    action: str
    target: Optional[str]
    risk_score: float
    needs_checkpoint: bool
    approved: Optional[bool]
    created_at: datetime


class AuditExportResponse(BaseModel):
    """Response from audit log export"""
    model_config = ConfigDict(from_attributes=True)
    
    total_entries: int
    entries: List[AuditLogEntry]
    from_date: Optional[datetime]
    to_date: Optional[datetime]


class WebSocketMessage(BaseModel):
    """WebSocket message format"""
    model_config = ConfigDict(from_attributes=True)
    
    event: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

"""FastAPI application for Oversight Gateway"""
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict

from . import __version__
from .database import get_db, init_db
from .auth import verify_api_key
from .risk_engine import RiskEngine
from .models import Action, NearMiss, Session as SessionModel
from .schemas import (
    EvaluateRequest, EvaluateResponse,
    ApprovalRequest, ApprovalResponse,
    NearMissRequest, NearMissResponse,
    BudgetResponse, StatsResponse, HealthResponse
)

app = FastAPI(
    title="Oversight Gateway",
    description="AI Agent Oversight Checkpoint System",
    version=__version__,
)

# Initialize risk engine
risk_engine = RiskEngine()


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy", version=__version__)


@app.post("/evaluate", response_model=EvaluateResponse, dependencies=[Depends(verify_api_key)])
async def evaluate_action(
    request: EvaluateRequest,
    db: Session = Depends(get_db)
):
    """
    Evaluate an action for risk and determine if checkpoint is needed.
    
    Risk is calculated as: Impact × Breadth × Probability
    
    Checkpoint is triggered when:
    - Single action risk exceeds threshold (default 0.6)
    - Cumulative session risk would exceed budget (default 0.8)
    - Compound action detected
    """
    impact, breadth, probability, risk_score, needs_checkpoint, reason, remaining = (
        risk_engine.evaluate_action(
            db,
            request.session_id,
            request.action,
            request.target,
            request.metadata
        )
    )
    
    # Check for compound action
    is_compound = False
    compound_count = 1
    if request.target:
        is_compound, compound_count = risk_engine._detect_compound_action(
            db, request.session_id, request.action, request.target
        )
    
    # Store the action
    action = Action(
        session_id=request.session_id,
        action=request.action,
        target=request.target,
        metadata=request.metadata,
        impact=impact,
        breadth=breadth,
        probability=probability,
        risk_score=risk_score,
        needs_checkpoint=needs_checkpoint,
        checkpoint_reason=reason if needs_checkpoint else None,
        is_compound=is_compound,
        compound_count=compound_count,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    
    return EvaluateResponse(
        action_id=action.id,
        session_id=request.session_id,
        risk_score=risk_score,
        impact=impact,
        breadth=breadth,
        probability=probability,
        needs_checkpoint=needs_checkpoint,
        checkpoint_reason=reason,
        remaining_budget=remaining,
        is_compound=is_compound,
        compound_count=compound_count,
    )


@app.post("/approve", response_model=ApprovalResponse, dependencies=[Depends(verify_api_key)])
async def approve_action(
    request: ApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Record human approval or rejection decision for a checkpointed action.
    """
    try:
        risk_engine.record_approval(db, request.action_id, request.approved)
        
        status = "approved" if request.approved else "rejected"
        return ApprovalResponse(
            action_id=request.action_id,
            approved=request.approved,
            message=f"Action {request.action_id} {status}"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/near-miss", response_model=NearMissResponse, dependencies=[Depends(verify_api_key)])
async def record_near_miss(
    request: NearMissRequest,
    db: Session = Depends(get_db)
):
    """
    Record a near-miss event that will adjust future risk calculations.
    
    Near-miss types:
    - boundary_violation: Action violated expected boundaries
    - resource_overuse: Action consumed more resources than expected
    - timing_anomaly: Action occurred at unexpected time
    - permission_escalation: Action exceeded expected permissions
    - data_exposure: Action exposed more data than intended
    - cascade_trigger: Action triggered unexpected cascade effects
    - policy_drift: Action deviated from established policy
    """
    risk_engine.record_near_miss(
        db,
        session_id=request.session_id,
        action=request.action,
        near_miss_type=request.near_miss_type,
        actual_severity=request.actual_severity,
        target=request.target,
        description=request.description,
        metadata=request.metadata,
        original_risk=request.original_risk,
    )
    
    # Get the near-miss ID
    near_miss = db.query(NearMiss).filter(
        NearMiss.session_id == request.session_id,
        NearMiss.action == request.action
    ).order_by(NearMiss.created_at.desc()).first()
    
    return NearMissResponse(
        message="Near-miss recorded successfully",
        near_miss_id=near_miss.id if near_miss else 0
    )


@app.get("/budget/{session_id}", response_model=BudgetResponse, dependencies=[Depends(verify_api_key)])
async def get_budget(session_id: str, db: Session = Depends(get_db)):
    """Get remaining risk budget for a session"""
    session = db.query(SessionModel).filter(
        SessionModel.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    remaining = session.risk_budget - session.cumulative_risk
    utilization = (session.cumulative_risk / session.risk_budget * 100) if session.risk_budget > 0 else 0
    
    return BudgetResponse(
        session_id=session_id,
        risk_budget=session.risk_budget,
        cumulative_risk=session.cumulative_risk,
        remaining_budget=remaining,
        utilization_percent=utilization
    )


@app.get("/stats", response_model=StatsResponse, dependencies=[Depends(verify_api_key)])
async def get_stats(db: Session = Depends(get_db)):
    """Get dashboard statistics"""
    total_actions = db.query(Action).count()
    checkpoints_triggered = db.query(Action).filter(Action.needs_checkpoint == True).count()
    checkpoints_approved = db.query(Action).filter(Action.approved == True).count()
    checkpoints_rejected = db.query(Action).filter(Action.approved == False).count()
    
    approval_rate = 0.0
    if checkpoints_triggered > 0:
        decided = checkpoints_approved + checkpoints_rejected
        approval_rate = (checkpoints_approved / decided * 100) if decided > 0 else 0.0
    
    total_near_misses = db.query(NearMiss).count()
    
    # Near-miss breakdown by type
    near_miss_breakdown: Dict[str, int] = {}
    for nm_type in ["boundary_violation", "resource_overuse", "timing_anomaly", 
                    "permission_escalation", "data_exposure", "cascade_trigger", "policy_drift"]:
        count = db.query(NearMiss).filter(NearMiss.near_miss_type == nm_type).count()
        near_miss_breakdown[nm_type] = count
    
    # Average risk score
    actions = db.query(Action).all()
    avg_risk = sum(a.risk_score for a in actions) / len(actions) if actions else 0.0
    
    return StatsResponse(
        total_actions=total_actions,
        checkpoints_triggered=checkpoints_triggered,
        checkpoints_approved=checkpoints_approved,
        checkpoints_rejected=checkpoints_rejected,
        approval_rate=approval_rate,
        total_near_misses=total_near_misses,
        near_miss_breakdown=near_miss_breakdown,
        average_risk_score=avg_risk
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

"""Async FastAPI application for Oversight Gateway V2"""
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog

from . import __version__
from .database import get_db, init_db, create_tables, close_db
from .auth import verify_api_key
from .risk_engine import RiskEngine
from .models import Action, NearMiss, Session as SessionModel, Webhook
from .schemas import (
    EvaluateRequest, EvaluateResponse,
    ApprovalRequest, ApprovalResponse,
    NearMissRequest, NearMissResponse,
    BudgetResponse, StatsResponse, HealthResponse,
    WebhookRegisterRequest, WebhookResponse,
    AuditLogEntry, AuditExportResponse,
    WebSocketMessage,
)
from .config import get_config, reload_config
from .logging_config import setup_logging
from .tracing import setup_tracing, instrument_app
from .webhooks import get_webhook_manager

# Setup logging
setup_logging(json_logs=False)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("starting_oversight_gateway", version=__version__)
    
    # Initialize config
    config = get_config()
    logger.info("config_loaded", policy_path=str(config.policy_path))
    
    # Setup tracing
    setup_tracing(config.service_name, config.otlp_endpoint)
    
    # Initialize database
    init_db(config.database_url)
    await create_tables()
    
    logger.info("oversight_gateway_started")
    
    yield
    
    logger.info("shutting_down_oversight_gateway")
    await close_db()
    await get_webhook_manager().close()
    logger.info("oversight_gateway_stopped")


app = FastAPI(
    title="Oversight Gateway V2",
    description="AI Agent Oversight Checkpoint System with async engine, policy-as-code, and real-time monitoring",
    version=__version__,
    lifespan=lifespan,
)

# Instrument with OpenTelemetry
instrument_app(app)

# Initialize risk engine
risk_engine = RiskEngine()

# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections for real-time dashboard"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("websocket_connected", total_connections=len(self.active_connections))
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("websocket_disconnected", total_connections=len(self.active_connections))
    
    async def broadcast(self, message: WebSocketMessage):
        """Broadcast message to all connected clients"""
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message.model_dump(mode="json"))
            except Exception as e:
                logger.warning("websocket_send_failed", error=str(e))
                dead_connections.append(connection)
        
        # Clean up dead connections
        for conn in dead_connections:
            self.disconnect(conn)

manager = ConnectionManager()


# Health and system endpoints

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy", version=__version__)


@app.post("/config/reload", dependencies=[Depends(verify_api_key)])
async def reload_config_endpoint():
    """Reload policy configuration from disk"""
    try:
        reload_config()
        # Reinitialize risk engine with new config
        global risk_engine
        risk_engine = RiskEngine()
        logger.info("config_reloaded")
        return {"message": "Configuration reloaded successfully"}
    except Exception as e:
        logger.error("config_reload_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to reload config: {str(e)}")


# Core evaluation endpoints

@app.post("/evaluate", response_model=EvaluateResponse, dependencies=[Depends(verify_api_key)])
async def evaluate_action(
    request: EvaluateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Evaluate an action for risk and determine if checkpoint is needed.
    
    Risk is calculated as: Impact × Breadth × Probability
    
    Checkpoint is triggered when:
    - Single action risk exceeds threshold (configurable)
    - Cumulative session risk would exceed budget (configurable)
    - Compound action detected
    - Action-specific rule requires it
    """
    impact, breadth, probability, risk_score, needs_checkpoint, reason, remaining = (
        await risk_engine.evaluate_action(
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
        is_compound, compound_count = await risk_engine._detect_compound_action(
            db, request.session_id, request.action, request.target
        )
    
    # Store the action
    action = Action(
        session_id=request.session_id,
        action=request.action,
        target=request.target,
        action_metadata=request.metadata,
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
    await db.commit()
    await db.refresh(action)
    
    # Trigger webhooks if checkpoint
    if needs_checkpoint:
        webhook_manager = get_webhook_manager()
        await webhook_manager.trigger_webhooks(
            db,
            "checkpoint_triggered",
            {
                "action_id": action.id,
                "session_id": request.session_id,
                "action": request.action,
                "risk_score": risk_score,
                "reason": reason,
            }
        )
        
        # Broadcast to WebSocket clients
        await manager.broadcast(WebSocketMessage(
            event="checkpoint_triggered",
            data={
                "action_id": action.id,
                "session_id": request.session_id,
                "action": request.action,
                "risk_score": risk_score,
            }
        ))
    
    # Always broadcast evaluation events to dashboard
    await manager.broadcast(WebSocketMessage(
        event="action_evaluated",
        data={
            "action_id": action.id,
            "session_id": request.session_id,
            "action": request.action,
            "risk_score": risk_score,
            "needs_checkpoint": needs_checkpoint,
        }
    ))
    
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
    db: AsyncSession = Depends(get_db)
):
    """
    Record human approval or rejection decision for a checkpointed action.
    """
    try:
        await risk_engine.record_approval(
            db, request.action_id, request.approved, request.channel, request.notes
        )
        
        status = "approved" if request.approved else "rejected"
        
        # Trigger webhooks
        webhook_manager = get_webhook_manager()
        await webhook_manager.trigger_webhooks(
            db,
            f"action_{status}",
            {
                "action_id": request.action_id,
                "approved": request.approved,
                "channel": request.channel,
            }
        )
        
        # Broadcast to WebSocket clients
        await manager.broadcast(WebSocketMessage(
            event=f"action_{status}",
            data={
                "action_id": request.action_id,
                "approved": request.approved,
            }
        ))
        
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
    db: AsyncSession = Depends(get_db)
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
    near_miss_id = await risk_engine.record_near_miss(
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
    
    # Trigger webhooks
    webhook_manager = get_webhook_manager()
    await webhook_manager.trigger_webhooks(
        db,
        "near_miss_recorded",
        {
            "near_miss_id": near_miss_id,
            "action": request.action,
            "severity": request.actual_severity,
        }
    )
    
    # Broadcast to WebSocket clients
    await manager.broadcast(WebSocketMessage(
        event="near_miss_recorded",
        data={
            "near_miss_id": near_miss_id,
            "action": request.action,
            "type": request.near_miss_type,
            "severity": request.actual_severity,
        }
    ))
    
    return NearMissResponse(
        message="Near-miss recorded successfully",
        near_miss_id=near_miss_id
    )


# Budget and statistics endpoints

@app.get("/budget/{session_id}", response_model=BudgetResponse, dependencies=[Depends(verify_api_key)])
async def get_budget(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get remaining risk budget for a session"""
    result = await db.execute(
        select(SessionModel).where(SessionModel.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    
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
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics"""
    total_actions = await db.scalar(select(func.count()).select_from(Action))
    checkpoints_triggered = await db.scalar(
        select(func.count()).select_from(Action).where(Action.needs_checkpoint == True)
    )
    checkpoints_approved = await db.scalar(
        select(func.count()).select_from(Action).where(Action.approved == True)
    )
    checkpoints_rejected = await db.scalar(
        select(func.count()).select_from(Action).where(Action.approved == False)
    )
    
    approval_rate = 0.0
    if checkpoints_triggered > 0:
        decided = checkpoints_approved + checkpoints_rejected
        approval_rate = (checkpoints_approved / decided * 100) if decided > 0 else 0.0
    
    total_near_misses = await db.scalar(select(func.count()).select_from(NearMiss))
    
    # Near-miss breakdown by type
    near_miss_breakdown: Dict[str, int] = {}
    for nm_type in ["boundary_violation", "resource_overuse", "timing_anomaly", 
                    "permission_escalation", "data_exposure", "cascade_trigger", "policy_drift"]:
        count = await db.scalar(
            select(func.count()).select_from(NearMiss).where(NearMiss.near_miss_type == nm_type)
        )
        near_miss_breakdown[nm_type] = count
    
    # Average risk score
    result = await db.execute(select(Action.risk_score))
    risk_scores = result.scalars().all()
    avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0
    
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


# Webhook management endpoints

@app.post("/config/webhooks", response_model=WebhookResponse, dependencies=[Depends(verify_api_key)])
async def register_webhook(
    request: WebhookRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register a webhook for event notifications"""
    webhook = Webhook(
        url=request.url,
        events=request.events,
        secret=request.secret,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    
    logger.info("webhook_registered", webhook_id=webhook.id, url=webhook.url, events=request.events)
    
    return WebhookResponse(
        webhook_id=webhook.id,
        url=webhook.url,
        events=request.events,
        message="Webhook registered successfully"
    )


@app.get("/config/webhooks", dependencies=[Depends(verify_api_key)])
async def list_webhooks(db: AsyncSession = Depends(get_db)):
    """List all registered webhooks"""
    result = await db.execute(select(Webhook))
    webhooks = result.scalars().all()
    
    return {
        "webhooks": [
            {
                "id": wh.id,
                "url": wh.url,
                "events": wh.events,
                "enabled": wh.enabled,
                "created_at": wh.created_at.isoformat(),
                "failure_count": wh.failure_count,
            }
            for wh in webhooks
        ]
    }


@app.delete("/config/webhooks/{webhook_id}", dependencies=[Depends(verify_api_key)])
async def delete_webhook(webhook_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a webhook"""
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    await db.delete(webhook)
    await db.commit()
    
    logger.info("webhook_deleted", webhook_id=webhook_id)
    return {"message": f"Webhook {webhook_id} deleted"}


# Audit log export endpoint

@app.get("/audit/export", response_model=AuditExportResponse, dependencies=[Depends(verify_api_key)])
async def export_audit_log(
    format: str = Query("json", regex="^(json)$"),
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Export audit log of all evaluations, approvals, and near-misses.
    
    Args:
        format: Export format (currently only 'json' supported)
        from_date: Start date (ISO format)
        to_date: End date (ISO format)
    """
    query = select(Action)
    
    if from_date:
        from_dt = datetime.fromisoformat(from_date)
        query = query.where(Action.created_at >= from_dt)
    
    if to_date:
        to_dt = datetime.fromisoformat(to_date)
        query = query.where(Action.created_at <= to_dt)
    
    result = await db.execute(query)
    actions = result.scalars().all()
    
    entries = [
        AuditLogEntry(
            id=action.id,
            session_id=action.session_id,
            action=action.action,
            target=action.target,
            risk_score=action.risk_score,
            needs_checkpoint=action.needs_checkpoint,
            approved=action.approved,
            created_at=action.created_at,
        )
        for action in actions
    ]
    
    return AuditExportResponse(
        total_entries=len(entries),
        entries=entries,
        from_date=datetime.fromisoformat(from_date) if from_date else None,
        to_date=datetime.fromisoformat(to_date) if to_date else None,
    )


# WebSocket dashboard endpoint

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard.
    
    Streams events:
    - action_evaluated
    - checkpoint_triggered
    - action_approved
    - action_rejected
    - near_miss_recorded
    """
    await manager.connect(websocket)
    try:
        # Send welcome message
        await websocket.send_json({
            "event": "connected",
            "data": {"message": "Connected to Oversight Gateway dashboard"},
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep connection alive and listen for client messages
        while True:
            data = await websocket.receive_text()
            # Echo back (can be extended for interactive features)
            await websocket.send_json({
                "event": "echo",
                "data": {"received": data},
                "timestamp": datetime.utcnow().isoformat()
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

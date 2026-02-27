"""Oversight Gateway SDK V2 - Async Python client with WebSocket support"""
import asyncio
from typing import Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass
import httpx
import websockets
import json

__version__ = "2.0.0"


@dataclass
class EvaluationResult:
    """Result from an action evaluation"""
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
    
    @property
    def needs_approval(self) -> bool:
        """Alias for needs_checkpoint"""
        return self.needs_checkpoint


# Async SDK

class AsyncOversightClient:
    """Async client for interacting with Oversight Gateway"""
    
    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        """
        Initialize async Oversight Gateway client.
        
        Args:
            base_url: Base URL of the Oversight Gateway service
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            headers={"X-API-Key": api_key},
            timeout=timeout
        )
    
    async def evaluate(
        self,
        action: str,
        session_id: str = "default",
        target: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """
        Evaluate an action for risk.
        
        Args:
            action: Action description (e.g., "send_email")
            session_id: Session identifier (default: "default")
            target: Target of the action
            metadata: Additional metadata for risk scoring
            
        Returns:
            EvaluationResult with risk score and checkpoint decision
        """
        response = await self._client.post(
            f"{self.base_url}/evaluate",
            json={
                "session_id": session_id,
                "action": action,
                "target": target,
                "metadata": metadata or {}
            }
        )
        response.raise_for_status()
        data = response.json()
        
        return EvaluationResult(
            action_id=data["action_id"],
            session_id=data["session_id"],
            risk_score=data["risk_score"],
            impact=data["impact"],
            breadth=data["breadth"],
            probability=data["probability"],
            needs_checkpoint=data["needs_checkpoint"],
            checkpoint_reason=data["checkpoint_reason"],
            remaining_budget=data["remaining_budget"],
            is_compound=data["is_compound"],
            compound_count=data["compound_count"],
        )
    
    async def approve(
        self,
        action_id: int,
        approved: bool,
        notes: Optional[str] = None,
        channel: str = "rest"
    ) -> Dict[str, Any]:
        """
        Record approval decision for a checkpointed action.
        
        Args:
            action_id: ID of the action from evaluate()
            approved: True to approve, False to reject
            notes: Optional notes about the decision
            channel: Approval channel identifier
            
        Returns:
            Response with approval status
        """
        response = await self._client.post(
            f"{self.base_url}/approve",
            json={
                "action_id": action_id,
                "approved": approved,
                "notes": notes,
                "channel": channel
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def record_near_miss(
        self,
        action: str,
        near_miss_type: str,
        actual_severity: float,
        session_id: str = "default",
        target: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        original_risk: Optional[float] = None
    ) -> Dict[str, Any]:
        """Record a near-miss event"""
        response = await self._client.post(
            f"{self.base_url}/near-miss",
            json={
                "session_id": session_id,
                "action": action,
                "near_miss_type": near_miss_type,
                "actual_severity": actual_severity,
                "target": target,
                "description": description,
                "metadata": metadata,
                "original_risk": original_risk
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def get_budget(self, session_id: str = "default") -> Dict[str, Any]:
        """Get remaining risk budget for a session"""
        response = await self._client.get(f"{self.base_url}/budget/{session_id}")
        response.raise_for_status()
        return response.json()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        response = await self._client.get(f"{self.base_url}/stats")
        response.raise_for_status()
        return response.json()
    
    async def health_check(self) -> Dict[str, str]:
        """Check if the service is healthy"""
        response = await self._client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    async def register_webhook(
        self,
        url: str,
        events: list,
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a webhook for event notifications"""
        response = await self._client.post(
            f"{self.base_url}/config/webhooks",
            json={
                "url": url,
                "events": events,
                "secret": secret
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def export_audit_log(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Export audit log"""
        params = {}
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        
        response = await self._client.get(
            f"{self.base_url}/audit/export",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close the HTTP client"""
        await self._client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self.close()


class DashboardClient:
    """WebSocket client for real-time dashboard"""
    
    def __init__(self, ws_url: str):
        """
        Initialize dashboard WebSocket client.
        
        Args:
            ws_url: WebSocket URL (e.g., "ws://localhost:8001/ws/dashboard")
        """
        self.ws_url = ws_url
        self._websocket = None
    
    async def connect(self):
        """Connect to dashboard WebSocket"""
        self._websocket = await websockets.connect(self.ws_url)
    
    async def listen(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Listen for events from the dashboard.
        
        Yields:
            Event messages as dictionaries
        """
        if not self._websocket:
            raise RuntimeError("Not connected. Call connect() first.")
        
        async for message in self._websocket:
            yield json.loads(message)
    
    async def close(self):
        """Close WebSocket connection"""
        if self._websocket:
            await self._websocket.close()
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, *args):
        await self.close()


# Sync wrapper for backward compatibility

class OversightClient:
    """Synchronous wrapper around AsyncOversightClient"""
    
    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        self._async_client = AsyncOversightClient(base_url, api_key, timeout)
    
    def evaluate(
        self,
        action: str,
        session_id: str = "default",
        target: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """Synchronous evaluate"""
        return asyncio.run(
            self._async_client.evaluate(action, session_id, target, metadata)
        )
    
    def approve(
        self,
        action_id: int,
        approved: bool,
        notes: Optional[str] = None,
        channel: str = "rest"
    ) -> Dict[str, Any]:
        """Synchronous approve"""
        return asyncio.run(
            self._async_client.approve(action_id, approved, notes, channel)
        )
    
    def record_near_miss(
        self,
        action: str,
        near_miss_type: str,
        actual_severity: float,
        session_id: str = "default",
        target: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        original_risk: Optional[float] = None
    ) -> Dict[str, Any]:
        """Synchronous record_near_miss"""
        return asyncio.run(
            self._async_client.record_near_miss(
                action, near_miss_type, actual_severity, session_id,
                target, description, metadata, original_risk
            )
        )
    
    def get_budget(self, session_id: str = "default") -> Dict[str, Any]:
        """Synchronous get_budget"""
        return asyncio.run(self._async_client.get_budget(session_id))
    
    def get_stats(self) -> Dict[str, Any]:
        """Synchronous get_stats"""
        return asyncio.run(self._async_client.get_stats())
    
    def health_check(self) -> Dict[str, str]:
        """Synchronous health_check"""
        return asyncio.run(self._async_client.health_check())
    
    def close(self):
        """Close the client"""
        asyncio.run(self._async_client.close())
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


__all__ = [
    "AsyncOversightClient",
    "OversightClient",
    "DashboardClient",
    "EvaluationResult",
]

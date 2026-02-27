"""Oversight Gateway SDK - Python client for the Oversight Gateway API"""
import time
from typing import Optional, Dict, Any
import httpx
from dataclasses import dataclass

__version__ = "0.1.0"


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


class OversightClient:
    """Client for interacting with Oversight Gateway"""
    
    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        """
        Initialize Oversight Gateway client.
        
        Args:
            base_url: Base URL of the Oversight Gateway service (e.g., "http://localhost:8001")
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.Client(
            headers={"X-API-Key": api_key},
            timeout=timeout
        )
    
    def evaluate(
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
            target: Target of the action (e.g., email address)
            metadata: Additional metadata for risk scoring
            
        Returns:
            EvaluationResult with risk score and checkpoint decision
            
        Raises:
            httpx.HTTPError: If the API request fails
        """
        response = self._client.post(
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
    
    def approve(self, action_id: int, approved: bool, notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Record approval decision for a checkpointed action.
        
        Args:
            action_id: ID of the action from evaluate()
            approved: True to approve, False to reject
            notes: Optional notes about the decision
            
        Returns:
            Response with approval status
        """
        response = self._client.post(
            f"{self.base_url}/approve",
            json={
                "action_id": action_id,
                "approved": approved,
                "notes": notes
            }
        )
        response.raise_for_status()
        return response.json()
    
    def wait_for_approval(
        self,
        action_id: int,
        poll_interval: float = 2.0,
        timeout: float = 300.0
    ) -> bool:
        """
        Wait for human approval of a checkpointed action.
        
        This is a blocking call that polls the API until the action is approved or rejected.
        In production, you'd typically use webhooks or a message queue instead.
        
        Args:
            action_id: ID of the action to wait for
            poll_interval: Seconds between poll attempts
            timeout: Maximum seconds to wait
            
        Returns:
            True if approved, False if rejected
            
        Raises:
            TimeoutError: If approval not received within timeout
        """
        # Note: This is a simplified implementation. In production, you'd implement
        # a proper approval workflow endpoint that supports long-polling or websockets.
        print(f"⏳ Waiting for approval of action {action_id}...")
        print(f"   Please call client.approve({action_id}, approved=True/False)")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(poll_interval)
            # In a real implementation, this would poll an endpoint
            # For now, this is a placeholder
            print("   Still waiting...")
        
        raise TimeoutError(f"Approval timeout after {timeout}s")
    
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
        """
        Record a near-miss event.
        
        Args:
            action: Action that caused the near-miss
            near_miss_type: Type of near-miss (boundary_violation, resource_overuse, etc.)
            actual_severity: Severity of the near-miss (0.0-1.0)
            session_id: Session identifier
            target: Target of the action
            description: Description of what happened
            metadata: Additional metadata
            original_risk: Original risk score if available
            
        Returns:
            Response with near-miss ID
        """
        response = self._client.post(
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
    
    def get_budget(self, session_id: str = "default") -> Dict[str, Any]:
        """Get remaining risk budget for a session"""
        response = self._client.get(f"{self.base_url}/budget/{session_id}")
        response.raise_for_status()
        return response.json()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        response = self._client.get(f"{self.base_url}/stats")
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> Dict[str, str]:
        """Check if the service is healthy"""
        response = self._client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def close(self):
        """Close the HTTP client"""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()

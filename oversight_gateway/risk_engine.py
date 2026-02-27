"""Risk scoring and checkpoint logic"""
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from .models import Action, NearMiss, Session as SessionModel


class RiskEngine:
    """Core risk evaluation engine with compound detection and near-miss learning"""
    
    def __init__(
        self,
        checkpoint_threshold: float = 0.6,
        compound_window_seconds: int = 300,  # 5 minutes
        near_miss_half_life_hours: float = 24.0,
    ):
        self.checkpoint_threshold = checkpoint_threshold
        self.compound_window = timedelta(seconds=compound_window_seconds)
        self.near_miss_half_life = timedelta(hours=near_miss_half_life_hours)
    
    def evaluate_action(
        self,
        db: Session,
        session_id: str,
        action: str,
        target: Optional[str],
        metadata: Optional[Dict],
    ) -> Tuple[float, float, float, float, bool, str, float]:
        """
        Evaluate an action and return risk metrics.
        
        Returns:
            (impact, breadth, probability, risk_score, needs_checkpoint, reason, remaining_budget)
        """
        # Get or create session
        session = db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).first()
        
        if not session:
            session = SessionModel(session_id=session_id)
            db.add(session)
            db.commit()
            db.refresh(session)
        
        # Calculate base risk factors
        impact = self._calculate_impact(action, target, metadata)
        breadth = self._calculate_breadth(action, target, metadata)
        probability = self._calculate_probability(action, metadata)
        
        # Apply near-miss learning
        near_miss_multiplier = self._get_near_miss_multiplier(db, action)
        probability = min(1.0, probability * near_miss_multiplier)
        
        # Check for compound actions
        is_compound, compound_count = self._detect_compound_action(
            db, session_id, action, target
        )
        
        if is_compound:
            # Boost risk for compound actions
            breadth = min(1.0, breadth * (1.0 + 0.2 * compound_count))
        
        # Calculate final risk score
        risk_score = impact * breadth * probability
        
        # Determine if checkpoint is needed
        needs_checkpoint = False
        reason = ""
        
        if risk_score > self.checkpoint_threshold:
            needs_checkpoint = True
            reason = f"High risk score: {risk_score:.3f} > {self.checkpoint_threshold}"
        elif session.cumulative_risk + risk_score > session.risk_budget:
            needs_checkpoint = True
            reason = f"Would exceed session budget: {session.cumulative_risk + risk_score:.3f} > {session.risk_budget}"
        
        if is_compound:
            reason = f"Compound action ({compound_count}x). " + reason if reason else f"Compound action detected ({compound_count}x)"
        
        remaining_budget = session.risk_budget - session.cumulative_risk
        
        return impact, breadth, probability, risk_score, needs_checkpoint, reason, remaining_budget
    
    def _calculate_impact(self, action: str, target: Optional[str], metadata: Optional[Dict]) -> float:
        """Calculate impact factor (0.0-1.0)"""
        impact = 0.3  # Base impact
        
        # Action-based impact
        high_impact_actions = {
            "delete", "remove", "drop", "terminate", "kill", "shutdown",
            "transfer", "payment", "charge", "debit"
        }
        medium_impact_actions = {
            "modify", "update", "edit", "change", "send", "publish", "post"
        }
        
        action_lower = action.lower()
        if any(word in action_lower for word in high_impact_actions):
            impact = 0.8
        elif any(word in action_lower for word in medium_impact_actions):
            impact = 0.5
        
        # Metadata-based impact boosters
        if metadata:
            if metadata.get("contains_pii"):
                impact = min(1.0, impact + 0.2)
            if metadata.get("financial"):
                impact = min(1.0, impact + 0.3)
            if metadata.get("irreversible"):
                impact = min(1.0, impact + 0.2)
            if metadata.get("amount"):
                # Financial amount impacts score
                amount = float(metadata["amount"])
                if amount > 1000:
                    impact = min(1.0, impact + 0.2)
                if amount > 10000:
                    impact = min(1.0, impact + 0.3)
        
        return min(1.0, impact)
    
    def _calculate_breadth(self, action: str, target: Optional[str], metadata: Optional[Dict]) -> float:
        """Calculate breadth/scope factor (0.0-1.0)"""
        breadth = 0.3  # Base breadth (single target)
        
        # Target-based breadth
        if target:
            target_lower = target.lower()
            if any(word in target_lower for word in ["all", "everyone", "public", "broadcast"]):
                breadth = 0.9
            elif any(word in target_lower for word in ["group", "team", "list"]):
                breadth = 0.6
        
        # Metadata-based breadth
        if metadata:
            if metadata.get("recipients"):
                count = len(metadata["recipients"]) if isinstance(metadata["recipients"], list) else int(metadata["recipients"])
                if count > 100:
                    breadth = 0.9
                elif count > 10:
                    breadth = 0.6
                elif count > 1:
                    breadth = 0.4
            
            if metadata.get("scope") == "global":
                breadth = 1.0
            elif metadata.get("scope") == "organization":
                breadth = 0.8
        
        return min(1.0, breadth)
    
    def _calculate_probability(self, action: str, metadata: Optional[Dict]) -> float:
        """Calculate probability of harm (0.0-1.0)"""
        probability = 0.3  # Base probability
        
        # Metadata-based probability
        if metadata:
            if metadata.get("user_confirmed") is False:
                probability = min(1.0, probability + 0.3)
            if metadata.get("automated"):
                probability = min(1.0, probability + 0.2)
            if metadata.get("time_sensitive"):
                probability = min(1.0, probability + 0.1)
            if metadata.get("off_hours"):
                probability = min(1.0, probability + 0.2)
        
        return min(1.0, probability)
    
    def _detect_compound_action(
        self, db: Session, session_id: str, action: str, target: Optional[str]
    ) -> Tuple[bool, int]:
        """
        Detect if this action is part of a compound action sequence.
        
        Returns:
            (is_compound, count_in_window)
        """
        if not target:
            return False, 1
        
        cutoff_time = datetime.utcnow() - self.compound_window
        
        recent_actions = db.query(Action).filter(
            Action.session_id == session_id,
            Action.target == target,
            Action.created_at >= cutoff_time
        ).count()
        
        if recent_actions > 0:
            return True, recent_actions + 1
        
        return False, 1
    
    def _get_near_miss_multiplier(self, db: Session, action: str) -> float:
        """
        Calculate risk multiplier based on near-miss history with decay.
        
        Near-misses increase the probability score for similar actions.
        The effect decays with a half-life.
        """
        # Get recent near-misses for this action
        near_misses = db.query(NearMiss).filter(
            NearMiss.action == action
        ).all()
        
        if not near_misses:
            return 1.0
        
        multiplier = 1.0
        now = datetime.utcnow()
        
        for nm in near_misses:
            age = now - nm.created_at
            # Calculate decay using half-life
            decay_factor = 0.5 ** (age / self.near_miss_half_life)
            # Each near-miss adds to the multiplier, weighted by severity and decay
            multiplier += nm.actual_severity * 0.5 * decay_factor
        
        return min(2.0, multiplier)  # Cap at 2x
    
    def record_approval(
        self, db: Session, action_id: int, approved: bool
    ) -> None:
        """Record human approval decision"""
        action = db.query(Action).filter(Action.id == action_id).first()
        if not action:
            raise ValueError(f"Action {action_id} not found")
        
        action.approved = approved
        action.approval_timestamp = datetime.utcnow()
        
        # Update session cumulative risk if approved
        if approved:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == action.session_id
            ).first()
            if session:
                session.cumulative_risk += action.risk_score
                session.last_activity = datetime.utcnow()
        
        db.commit()
    
    def record_near_miss(
        self,
        db: Session,
        session_id: str,
        action: str,
        near_miss_type: str,
        actual_severity: float,
        target: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
        original_risk: Optional[float] = None,
    ) -> None:
        """Record a near-miss event for future risk adjustment"""
        near_miss = NearMiss(
            session_id=session_id,
            action=action,
            target=target,
            near_miss_type=near_miss_type,
            description=description,
            near_miss_metadata=metadata,
            original_risk=original_risk,
            actual_severity=actual_severity,
        )
        db.add(near_miss)
        db.commit()

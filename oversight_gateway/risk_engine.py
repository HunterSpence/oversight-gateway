"""Async risk scoring and checkpoint logic with policy-as-code"""
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog
from opentelemetry import trace

from .models import Action, NearMiss, Session as SessionModel
from .config import PolicyConfig, get_config

logger = structlog.get_logger()
tracer = trace.get_tracer(__name__)


class RiskEngine:
    """Core async risk evaluation engine with policy-based configuration"""
    
    def __init__(self, policy: Optional[PolicyConfig] = None):
        self.policy = policy or get_config().policy
    
    async def evaluate_action(
        self,
        db: AsyncSession,
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
        with tracer.start_as_current_span("evaluate_action") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("action", action)
            span.set_attribute("target", target or "")
            
            logger.info("evaluating_action", session_id=session_id, action=action, target=target)
            
            # Get or create session
            result = await db.execute(
                select(SessionModel).where(SessionModel.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                session = SessionModel(
                    session_id=session_id,
                    risk_budget=self.policy.risk_thresholds.session_budget
                )
                db.add(session)
                await db.commit()
                await db.refresh(session)
                logger.info("session_created", session_id=session_id)
            
            # Calculate base risk factors
            impact = await self._calculate_impact(action, target, metadata)
            breadth = await self._calculate_breadth(action, target, metadata)
            probability = await self._calculate_probability(action, metadata)
            
            span.set_attribute("impact", impact)
            span.set_attribute("breadth", breadth)
            span.set_attribute("probability", probability)
            
            # Apply near-miss learning
            near_miss_multiplier = await self._get_near_miss_multiplier(db, action)
            probability = min(1.0, probability * near_miss_multiplier)
            
            if near_miss_multiplier > 1.0:
                span.set_attribute("near_miss_multiplier", near_miss_multiplier)
                logger.info("near_miss_boost_applied", action=action, multiplier=near_miss_multiplier)
            
            # Check for compound actions
            is_compound, compound_count = await self._detect_compound_action(
                db, session_id, action, target
            )
            
            if is_compound:
                # Boost risk for compound actions
                boost = self.policy.compound_detection.same_resource_boost
                breadth = min(1.0, breadth * (1.0 + boost * compound_count))
                span.set_attribute("compound_boost", boost * compound_count)
                logger.info("compound_action_detected", count=compound_count, boost=boost)
            
            # Calculate final risk score
            risk_score = impact * breadth * probability
            span.set_attribute("risk_score", risk_score)
            
            # Determine if checkpoint is needed
            needs_checkpoint = False
            reason = ""
            
            # Check action-specific rules
            action_rule = self.policy.get_action_rule(action)
            if action_rule and action_rule.always_checkpoint:
                needs_checkpoint = True
                reason = f"Action rule: {action_rule.description}"
                span.set_attribute("checkpoint_reason", "action_rule")
            elif risk_score > self.policy.risk_thresholds.checkpoint_trigger:
                needs_checkpoint = True
                reason = f"High risk score: {risk_score:.3f} > {self.policy.risk_thresholds.checkpoint_trigger}"
                span.set_attribute("checkpoint_reason", "high_risk")
            elif session.cumulative_risk + risk_score > session.risk_budget:
                needs_checkpoint = True
                reason = f"Would exceed session budget: {session.cumulative_risk + risk_score:.3f} > {session.risk_budget}"
                span.set_attribute("checkpoint_reason", "budget_exceeded")
            
            if is_compound:
                reason = f"Compound action ({compound_count}x). " + (reason if reason else f"Compound action detected ({compound_count}x)")
            
            remaining_budget = session.risk_budget - session.cumulative_risk
            
            span.set_attribute("needs_checkpoint", needs_checkpoint)
            logger.info(
                "evaluation_complete",
                risk_score=risk_score,
                needs_checkpoint=needs_checkpoint,
                reason=reason
            )
            
            return impact, breadth, probability, risk_score, needs_checkpoint, reason, remaining_budget
    
    async def _calculate_impact(
        self,
        action: str,
        target: Optional[str],
        metadata: Optional[Dict]
    ) -> float:
        """Calculate impact factor (0.0-1.0) with policy-based rules"""
        with tracer.start_as_current_span("calculate_impact"):
            impact = 0.3  # Base impact
            
            # Check for action-specific rule
            action_rule = self.policy.get_action_rule(action)
            if action_rule:
                impact = max(impact, action_rule.impact_floor)
                
                # Apply metadata boosts from rule
                if metadata and action_rule.metadata_boosts:
                    for key, boost in action_rule.metadata_boosts.items():
                        if key in metadata and metadata[key]:
                            impact = min(1.0, impact + boost)
            
            # General metadata-based impact boosters
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
    
    async def _calculate_breadth(
        self,
        action: str,
        target: Optional[str],
        metadata: Optional[Dict]
    ) -> float:
        """Calculate breadth/scope factor (0.0-1.0)"""
        with tracer.start_as_current_span("calculate_breadth"):
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
                
                if metadata.get("broadcast") or metadata.get("public"):
                    breadth = min(1.0, breadth + 0.3)
            
            return min(1.0, breadth)
    
    async def _calculate_probability(self, action: str, metadata: Optional[Dict]) -> float:
        """Calculate probability of harm (0.0-1.0)"""
        with tracer.start_as_current_span("calculate_probability"):
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
    
    async def _detect_compound_action(
        self, db: AsyncSession, session_id: str, action: str, target: Optional[str]
    ) -> Tuple[bool, int]:
        """
        Detect if this action is part of a compound action sequence.
        
        Returns:
            (is_compound, count_in_window)
        """
        with tracer.start_as_current_span("detect_compound_action"):
            if not target:
                return False, 1
            
            cutoff_time = datetime.utcnow() - timedelta(
                seconds=self.policy.compound_detection.time_window_seconds
            )
            
            result = await db.execute(
                select(func.count()).select_from(Action).where(
                    Action.session_id == session_id,
                    Action.target == target,
                    Action.created_at >= cutoff_time
                )
            )
            recent_count = result.scalar()
            
            if recent_count >= self.policy.compound_detection.min_count - 1:
                return True, recent_count + 1
            
            return False, 1
    
    async def _get_near_miss_multiplier(self, db: AsyncSession, action: str) -> float:
        """
        Calculate risk multiplier based on near-miss history with decay.
        
        Near-misses increase the probability score for similar actions.
        The effect decays with a half-life.
        """
        with tracer.start_as_current_span("get_near_miss_multiplier"):
            # Get recent near-misses for this action
            result = await db.execute(
                select(NearMiss).where(NearMiss.action == action)
            )
            near_misses = result.scalars().all()
            
            if not near_misses:
                return 1.0
            
            multiplier = 1.0
            now = datetime.utcnow()
            half_life = timedelta(hours=self.policy.near_miss.half_life_hours)
            
            for nm in near_misses:
                if nm.actual_severity < self.policy.near_miss.min_severity:
                    continue
                    
                age = now - nm.created_at
                # Calculate decay using half-life
                decay_factor = 0.5 ** (age / half_life)
                # Each near-miss adds to the multiplier, weighted by severity and decay
                multiplier += nm.actual_severity * 0.5 * decay_factor
            
            return min(self.policy.near_miss.max_multiplier, multiplier)
    
    async def record_approval(
        self,
        db: AsyncSession,
        action_id: int,
        approved: bool,
        channel: str = "rest",
        notes: Optional[str] = None
    ) -> None:
        """Record human approval decision"""
        with tracer.start_as_current_span("record_approval") as span:
            span.set_attribute("action_id", action_id)
            span.set_attribute("approved", approved)
            span.set_attribute("channel", channel)
            
            result = await db.execute(
                select(Action).where(Action.id == action_id)
            )
            action = result.scalar_one_or_none()
            
            if not action:
                raise ValueError(f"Action {action_id} not found")
            
            action.approved = approved
            action.approval_timestamp = datetime.utcnow()
            action.approval_channel = channel
            action.approval_notes = notes
            
            # Update session cumulative risk if approved
            if approved:
                result = await db.execute(
                    select(SessionModel).where(SessionModel.session_id == action.session_id)
                )
                session = result.scalar_one_or_none()
                if session:
                    session.cumulative_risk += action.risk_score
                    session.last_activity = datetime.utcnow()
            
            await db.commit()
            
            logger.info(
                "approval_recorded",
                action_id=action_id,
                approved=approved,
                channel=channel
            )
    
    async def record_near_miss(
        self,
        db: AsyncSession,
        session_id: str,
        action: str,
        near_miss_type: str,
        actual_severity: float,
        target: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
        original_risk: Optional[float] = None,
    ) -> int:
        """Record a near-miss event for future risk adjustment"""
        with tracer.start_as_current_span("record_near_miss") as span:
            span.set_attribute("session_id", session_id)
            span.set_attribute("action", action)
            span.set_attribute("near_miss_type", near_miss_type)
            span.set_attribute("actual_severity", actual_severity)
            
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
            await db.commit()
            await db.refresh(near_miss)
            
            logger.info(
                "near_miss_recorded",
                near_miss_id=near_miss.id,
                action=action,
                severity=actual_severity
            )
            
            return near_miss.id

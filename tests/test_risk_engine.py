"""Test risk engine logic"""
import pytest
from oversight_gateway.risk_engine import RiskEngine
from oversight_gateway.config import PolicyConfig
from oversight_gateway.database import init_db, create_tables, get_db
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def db_session():
    """Test database session"""
    init_db("sqlite+aiosqlite:///:memory:")
    await create_tables()
    
    async for session in get_db():
        yield session


@pytest.mark.asyncio
async def test_impact_calculation(db_session: AsyncSession):
    """Test impact factor calculation"""
    engine = RiskEngine()
    
    # Low impact
    impact = await engine._calculate_impact("read_file", None, {})
    assert 0.0 <= impact <= 1.0
    
    # High impact (delete)
    impact_delete = await engine._calculate_impact("delete_file", None, {})
    assert impact_delete > impact
    
    # Financial boost
    impact_financial = await engine._calculate_impact(
        "process_payment",
        None,
        {"financial": True, "amount": 15000}
    )
    assert impact_financial > 0.7


@pytest.mark.asyncio
async def test_breadth_calculation(db_session: AsyncSession):
    """Test breadth factor calculation"""
    engine = RiskEngine()
    
    # Single user
    breadth_single = await engine._calculate_breadth("send_email", "user@example.com", {})
    assert breadth_single < 0.5
    
    # Multiple recipients
    breadth_multi = await engine._calculate_breadth(
        "send_email",
        "group@example.com",
        {"recipients": ["user1", "user2", "user3"]}
    )
    assert breadth_multi > breadth_single
    
    # Broadcast
    breadth_all = await engine._calculate_breadth("send_message", "all", {})
    assert breadth_all > 0.8


@pytest.mark.asyncio
async def test_compound_action_detection(db_session: AsyncSession):
    """Test compound action detection"""
    engine = RiskEngine()
    session_id = "test-compound"
    action = "send_email"
    target = "user@example.com"
    
    # First action - not compound
    is_compound, count = await engine._detect_compound_action(
        db_session, session_id, action, target
    )
    assert is_compound == False
    assert count == 1
    
    # Add an action to DB
    from oversight_gateway.models import Action
    db_action = Action(
        session_id=session_id,
        action=action,
        target=target,
        impact=0.5,
        breadth=0.3,
        probability=0.3,
        risk_score=0.045,
        needs_checkpoint=False
    )
    db_session.add(db_action)
    await db_session.commit()
    
    # Second action on same target - should be compound
    is_compound2, count2 = await engine._detect_compound_action(
        db_session, session_id, action, target
    )
    assert is_compound2 == True
    assert count2 > 1


@pytest.mark.asyncio
async def test_policy_based_rules(db_session: AsyncSession):
    """Test policy-based action rules"""
    engine = RiskEngine()
    
    # Delete action should have high base impact due to policy
    impact, breadth, prob, risk, checkpoint, reason, budget = await engine.evaluate_action(
        db_session,
        session_id="test-policy",
        action="delete_database",
        target="prod_db",
        metadata={}
    )
    
    # Should trigger checkpoint due to action rule
    assert checkpoint == True
    assert "delete" in reason.lower() or "action rule" in reason.lower()


@pytest.mark.asyncio
async def test_near_miss_learning(db_session: AsyncSession):
    """Test near-miss learning multiplier"""
    engine = RiskEngine()
    action = "test_action"
    
    # No near-misses yet
    multiplier1 = await engine._get_near_miss_multiplier(db_session, action)
    assert multiplier1 == 1.0
    
    # Record a near-miss
    await engine.record_near_miss(
        db_session,
        session_id="test",
        action=action,
        near_miss_type="boundary_violation",
        actual_severity=0.8
    )
    
    # Should have increased multiplier
    multiplier2 = await engine._get_near_miss_multiplier(db_session, action)
    assert multiplier2 > 1.0


@pytest.mark.asyncio
async def test_full_evaluation_flow(db_session: AsyncSession):
    """Test complete evaluation flow"""
    engine = RiskEngine()
    
    # Evaluate a medium-risk action
    impact, breadth, prob, risk, checkpoint, reason, budget = await engine.evaluate_action(
        db_session,
        session_id="test-flow",
        action="send_email",
        target="team@example.com",
        metadata={"contains_pii": True, "recipients": 20}
    )
    
    # Verify all components
    assert 0.0 <= impact <= 1.0
    assert 0.0 <= breadth <= 1.0
    assert 0.0 <= prob <= 1.0
    assert risk == impact * breadth * prob
    assert isinstance(checkpoint, bool)
    assert 0.0 <= budget <= 1.0

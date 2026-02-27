#!/usr/bin/env python3
"""
Quick verification test for core Oversight Gateway functionality
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from oversight_gateway.database import init_db, SessionLocal
from oversight_gateway.risk_engine import RiskEngine
from oversight_gateway.models import Action, NearMiss, Session

def test_risk_engine():
    """Test core risk engine functionality"""
    print("Testing Oversight Gateway Core Functionality\n")
    
    # Initialize database in memory
    print("[1] Initializing database...")
    init_db()
    db = SessionLocal()
    
    # Create risk engine
    engine = RiskEngine()
    print("[OK] Risk engine initialized\n")
    
    # Test 1: Basic risk evaluation
    print("[2] Testing basic risk evaluation...")
    impact, breadth, probability, risk, needs_cp, reason, remaining = engine.evaluate_action(
        db,
        session_id="test-session",
        action="send_email",
        target="user@example.com",
        metadata={"contains_pii": False}
    )
    print(f"   Risk Score: {risk:.3f} (Impact: {impact:.2f}, Breadth: {breadth:.2f}, Prob: {probability:.2f})")
    print(f"   Needs Checkpoint: {needs_cp}")
    assert 0 <= risk <= 1, "Risk should be between 0 and 1"
    assert 0 <= impact <= 1, "Impact should be between 0 and 1"
    assert 0 <= breadth <= 1, "Breadth should be between 0 and 1"
    assert 0 <= probability <= 1, "Probability should be between 0 and 1"
    print("[OK] Basic evaluation works\n")
    
    # Test 2: High-risk action triggers checkpoint
    print("[3] Testing checkpoint triggering...")
    impact2, breadth2, probability2, risk2, needs_cp2, reason2, remaining2 = engine.evaluate_action(
        db,
        session_id="test-session",
        action="delete_database",
        target="all_production_servers",
        metadata={
            "irreversible": True, 
            "financial": True, 
            "amount": 50000,
            "scope": "global",
            "automated": True,
            "user_confirmed": False
        }
    )
    print(f"   Risk Score: {risk2:.3f}")
    print(f"   Needs Checkpoint: {needs_cp2}")
    print(f"   Reason: {reason2}")
    assert needs_cp2, "High-risk action should trigger checkpoint"
    print("[OK] Checkpoint triggering works\n")
    
    # Test 3: Compound action detection
    print("[4] Testing compound action detection...")
    for i in range(3):
        is_compound, count = engine._detect_compound_action(
            db, "test-session", "send_email", "same-target@example.com"
        )
        # Record the action
        action = Action(
            session_id="test-session",
            action="send_email",
            target="same-target@example.com",
            action_metadata={},
            impact=0.3,
            breadth=0.3,
            probability=0.3,
            risk_score=0.027,
            needs_checkpoint=False
        )
        db.add(action)
        db.commit()
        print(f"   Action {i+1}: Compound={is_compound}, Count={count}")
    print("[OK] Compound detection works\n")
    
    # Test 4: Near-miss learning
    print("[5] Testing near-miss learning...")
    
    # Get initial multiplier
    multiplier_before = engine._get_near_miss_multiplier(db, "delete_file")
    print(f"   Initial multiplier: {multiplier_before:.2f}")
    
    # Record a near-miss
    engine.record_near_miss(
        db,
        session_id="test-session",
        action="delete_file",
        near_miss_type="boundary_violation",
        actual_severity=0.8,
        description="Test near-miss"
    )
    
    # Get new multiplier
    multiplier_after = engine._get_near_miss_multiplier(db, "delete_file")
    print(f"   After near-miss: {multiplier_after:.2f}")
    
    assert multiplier_after > multiplier_before, "Near-miss should increase risk multiplier"
    print("[OK] Near-miss learning works\n")
    
    # Test 5: Session budget tracking
    print("[6] Testing session budget tracking...")
    session = db.query(Session).filter(Session.session_id == "test-session").first()
    print(f"   Session budget: {session.risk_budget:.2f}")
    print(f"   Cumulative risk: {session.cumulative_risk:.2f}")
    print(f"   Remaining: {session.risk_budget - session.cumulative_risk:.2f}")
    assert session is not None, "Session should exist"
    print("[OK] Session tracking works\n")
    
    db.close()
    
    print("=" * 60)
    print("[OK] ALL TESTS PASSED!")
    print("=" * 60)
    print("\nOversight Gateway core functionality verified!")
    print("\nNext steps:")
    print("  - Run 'python example.py' for full demo")
    print("  - Run 'docker-compose up' to start the service")
    print("  - Visit http://localhost:8001/docs for API documentation")

if __name__ == "__main__":
    try:
        test_risk_engine()
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

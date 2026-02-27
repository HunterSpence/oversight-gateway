#!/usr/bin/env python3
"""
Example usage of Oversight Gateway

This script demonstrates:
1. Starting the server
2. Basic risk evaluation
3. Checkpoint triggering
4. Near-miss learning
5. Compound action detection
"""
import time
import subprocess
import sys
from oversight_gateway_sdk import OversightClient


def wait_for_server(client, max_retries=30):
    """Wait for server to be ready"""
    print("⏳ Waiting for server to start...")
    for i in range(max_retries):
        try:
            client.health_check()
            print("✅ Server is ready!")
            return True
        except Exception:
            if i == max_retries - 1:
                print("❌ Server failed to start")
                return False
            time.sleep(1)
    return False


def main():
    print("=" * 60)
    print("🔒 Oversight Gateway - Example Demonstration")
    print("=" * 60)
    
    # Start the server in the background
    print("\n1️⃣  Starting Oversight Gateway server...")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "oversight_gateway.main:app", "--host", "0.0.0.0", "--port", "8001"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    try:
        # Initialize client
        client = OversightClient(
            base_url="http://localhost:8001",
            api_key="dev-key-12345"
        )
        
        if not wait_for_server(client):
            return
        
        print("\n" + "=" * 60)
        print("2️⃣  Testing Basic Risk Evaluation")
        print("=" * 60)
        
        # Low-risk action
        print("\n📧 Evaluating: Send email to single user")
        result1 = client.evaluate(
            action="send_email",
            target="user@example.com",
            session_id="demo-session",
            metadata={"contains_pii": False}
        )
        print(f"   Risk Score: {result1.risk_score:.3f}")
        print(f"   Impact: {result1.impact:.2f} | Breadth: {result1.breadth:.2f} | Probability: {result1.probability:.2f}")
        print(f"   Needs Checkpoint: {result1.needs_checkpoint}")
        print(f"   Remaining Budget: {result1.remaining_budget:.3f}")
        
        # Medium-risk action
        print("\n💳 Evaluating: Small payment")
        result2 = client.evaluate(
            action="process_payment",
            target="customer@example.com",
            session_id="demo-session",
            metadata={"financial": True, "amount": 50}
        )
        print(f"   Risk Score: {result2.risk_score:.3f}")
        print(f"   Impact: {result2.impact:.2f} | Breadth: {result2.breadth:.2f} | Probability: {result2.probability:.2f}")
        print(f"   Needs Checkpoint: {result2.needs_checkpoint}")
        
        # High-risk action - triggers checkpoint
        print("\n💰 Evaluating: Large payment")
        result3 = client.evaluate(
            action="process_payment",
            target="customer@example.com",
            session_id="demo-session",
            metadata={"financial": True, "amount": 15000, "automated": True}
        )
        print(f"   Risk Score: {result3.risk_score:.3f}")
        print(f"   Impact: {result3.impact:.2f} | Breadth: {result3.breadth:.2f} | Probability: {result3.probability:.2f}")
        print(f"   ⚠️  CHECKPOINT TRIGGERED!")
        print(f"   Reason: {result3.checkpoint_reason}")
        
        print("\n" + "=" * 60)
        print("3️⃣  Testing Compound Action Detection")
        print("=" * 60)
        
        print("\n📤 Sending multiple emails to the same recipient...")
        for i in range(3):
            result = client.evaluate(
                action="send_email",
                target="same-user@example.com",
                session_id="demo-session"
            )
            print(f"   Email {i+1}: Risk={result.risk_score:.3f}, Compound={result.is_compound}, Count={result.compound_count}")
            time.sleep(0.5)
        
        print("\n" + "=" * 60)
        print("4️⃣  Testing Near-Miss Learning")
        print("=" * 60)
        
        # Evaluate an action (low initial risk)
        print("\n🗑️  Evaluating: Delete temp file")
        result_before = client.evaluate(
            action="delete_file",
            target="/tmp/data.txt",
            session_id="demo-session"
        )
        print(f"   Initial Risk Score: {result_before.risk_score:.3f}")
        
        # Record a near-miss
        print("\n⚠️  Recording near-miss: Delete action violated boundaries")
        client.record_near_miss(
            action="delete_file",
            near_miss_type="boundary_violation",
            actual_severity=0.8,
            session_id="demo-session",
            description="Accidentally deleted important file instead of temp file"
        )
        print("   Near-miss recorded!")
        
        # Evaluate same action again - should have higher risk due to learning
        print("\n🗑️  Re-evaluating: Delete temp file (after near-miss)")
        result_after = client.evaluate(
            action="delete_file",
            target="/tmp/data2.txt",
            session_id="demo-session"
        )
        print(f"   New Risk Score: {result_after.risk_score:.3f}")
        print(f"   📈 Risk increased by {((result_after.risk_score / result_before.risk_score) - 1) * 100:.1f}% due to near-miss learning!")
        
        print("\n" + "=" * 60)
        print("5️⃣  System Statistics")
        print("=" * 60)
        
        stats = client.get_stats()
        print(f"\n📊 Total Actions: {stats['total_actions']}")
        print(f"🚦 Checkpoints Triggered: {stats['checkpoints_triggered']}")
        print(f"✅ Approved: {stats['checkpoints_approved']}")
        print(f"❌ Rejected: {stats['checkpoints_rejected']}")
        print(f"📈 Approval Rate: {stats['approval_rate']:.1f}%")
        print(f"⚠️  Near-Misses: {stats['total_near_misses']}")
        print(f"📊 Average Risk Score: {stats['average_risk_score']:.3f}")
        
        print("\n📋 Near-Miss Breakdown:")
        for nm_type, count in stats['near_miss_breakdown'].items():
            if count > 0:
                print(f"   • {nm_type}: {count}")
        
        budget = client.get_budget("demo-session")
        print(f"\n💰 Session Budget:")
        print(f"   Total Budget: {budget['risk_budget']:.3f}")
        print(f"   Used: {budget['cumulative_risk']:.3f}")
        print(f"   Remaining: {budget['remaining_budget']:.3f}")
        print(f"   Utilization: {budget['utilization_percent']:.1f}%")
        
        print("\n" + "=" * 60)
        print("✅ Demonstration Complete!")
        print("=" * 60)
        print("\n🔗 API running at: http://localhost:8001")
        print("📚 API docs at: http://localhost:8001/docs")
        print("🔑 API Key: dev-key-12345")
        print("\nPress Ctrl+C to stop the server...")
        
        # Keep server running
        server.wait()
        
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down server...")
    finally:
        server.terminate()
        server.wait(timeout=5)
        print("✅ Server stopped")


if __name__ == "__main__":
    main()

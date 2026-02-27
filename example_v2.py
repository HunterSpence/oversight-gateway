#!/usr/bin/env python3
"""
Example usage of Oversight Gateway V2

Demonstrates:
1. Async client usage
2. Policy-based evaluation
3. Webhook registration
4. WebSocket dashboard streaming
5. Near-miss learning
6. Compound action detection
7. Audit log export
"""
import asyncio
from oversight_gateway_sdk import AsyncOversightClient, DashboardClient


async def main():
    print("=" * 70)
    print("🔒 Oversight Gateway V2 - Example Demonstration")
    print("=" * 70)
    
    # Initialize async client
    async with AsyncOversightClient(
        base_url="http://localhost:8001",
        api_key="dev-key-12345"
    ) as client:
        print("\n✅ Connected to Oversight Gateway V2")
        
        # Check health
        health = await client.health_check()
        print(f"   Version: {health['version']}")
        print(f"   Status: {health['status']}")
        
        print("\n" + "=" * 70)
        print("1️⃣  Testing Policy-Based Evaluation")
        print("=" * 70)
        
        # Test low-risk action
        print("\n📧 Evaluating: Send email to single user")
        result1 = await client.evaluate(
            action="send_email",
            target="user@example.com",
            session_id="demo-v2-session",
            metadata={"contains_pii": False}
        )
        print(f"   Risk Score: {result1.risk_score:.3f}")
        print(f"   Needs Checkpoint: {result1.needs_checkpoint}")
        
        # Test action matching policy rule (delete)
        print("\n🗑️  Evaluating: Delete database (policy rule: always checkpoint)")
        result2 = await client.evaluate(
            action="delete_database",
            target="production_db",
            session_id="demo-v2-session",
            metadata={"irreversible": True}
        )
        print(f"   Risk Score: {result2.risk_score:.3f}")
        print(f"   ⚠️  CHECKPOINT TRIGGERED!")
        print(f"   Reason: {result2.checkpoint_reason}")
        
        # Approve it
        await client.approve(
            result2.action_id,
            approved=True,
            notes="Reviewed and approved for demo",
            channel="rest"
        )
        print("   ✅ Action approved")
        
        print("\n" + "=" * 70)
        print("2️⃣  Testing Webhook Registration")
        print("=" * 70)
        
        print("\n🔔 Registering webhook for Slack notifications")
        webhook = await client.register_webhook(
            url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
            events=["checkpoint_triggered", "near_miss_recorded"],
            secret="demo-secret"
        )
        print(f"   Webhook ID: {webhook['webhook_id']}")
        print(f"   Events: {', '.join(webhook['events'])}")
        
        print("\n" + "=" * 70)
        print("3️⃣  Testing Compound Action Detection")
        print("=" * 70)
        
        print("\n📤 Sending multiple emails to same recipient...")
        for i in range(3):
            result = await client.evaluate(
                action="send_email",
                target="repeated@example.com",
                session_id="demo-v2-session"
            )
            print(f"   Email {i+1}: Risk={result.risk_score:.3f}, Compound={result.is_compound}, Count={result.compound_count}")
            await asyncio.sleep(0.2)
        
        print("\n" + "=" * 70)
        print("4️⃣  Testing Near-Miss Learning")
        print("=" * 70)
        
        print("\n⚠️  Recording near-miss event")
        near_miss = await client.record_near_miss(
            action="send_email",
            near_miss_type="data_exposure",
            actual_severity=0.85,
            session_id="demo-v2-session",
            description="Email accidentally sent to wrong recipient list"
        )
        print(f"   Near-Miss ID: {near_miss['near_miss_id']}")
        print("   Future evaluations of 'send_email' will have increased risk")
        
        # Re-evaluate same action
        print("\n📧 Re-evaluating 'send_email' after near-miss...")
        result_after = await client.evaluate(
            action="send_email",
            target="another@example.com",
            session_id="demo-v2-session"
        )
        print(f"   New Risk Score: {result_after.risk_score:.3f} (boosted by near-miss learning)")
        
        print("\n" + "=" * 70)
        print("5️⃣  Testing Session Budget")
        print("=" * 70)
        
        budget = await client.get_budget("demo-v2-session")
        print(f"\n💰 Session Budget:")
        print(f"   Total Budget: {budget['risk_budget']:.3f}")
        print(f"   Used: {budget['cumulative_risk']:.3f}")
        print(f"   Remaining: {budget['remaining_budget']:.3f}")
        print(f"   Utilization: {budget['utilization_percent']:.1f}%")
        
        print("\n" + "=" * 70)
        print("6️⃣  Testing System Statistics")
        print("=" * 70)
        
        stats = await client.get_stats()
        print(f"\n📊 System Statistics:")
        print(f"   Total Actions: {stats['total_actions']}")
        print(f"   Checkpoints Triggered: {stats['checkpoints_triggered']}")
        print(f"   Approval Rate: {stats['approval_rate']:.1f}%")
        print(f"   Near-Misses: {stats['total_near_misses']}")
        print(f"   Average Risk: {stats['average_risk_score']:.3f}")
        
        print("\n" + "=" * 70)
        print("7️⃣  Testing Audit Log Export")
        print("=" * 70)
        
        audit = await client.export_audit_log()
        print(f"\n📋 Audit Log Export:")
        print(f"   Total Entries: {audit['total_entries']}")
        print(f"   Latest Entries:")
        for entry in audit['entries'][-3:]:
            print(f"   • {entry['action']} @ {entry['created_at']}: risk={entry['risk_score']:.3f}")
        
        print("\n" + "=" * 70)
        print("8️⃣  WebSocket Dashboard (Demo)")
        print("=" * 70)
        print("\n📡 WebSocket dashboard available at: ws://localhost:8001/ws/dashboard")
        print("   Connect with DashboardClient to stream live events:")
        print("""
   async with DashboardClient("ws://localhost:8001/ws/dashboard") as dashboard:
       async for event in dashboard.listen():
           print(f"Event: {event['event']}")
   """)
        
        print("\n" + "=" * 70)
        print("✅ V2 Demonstration Complete!")
        print("=" * 70)
        print("\n🔗 API running at: http://localhost:8001")
        print("📚 API docs at: http://localhost:8001/docs")
        print("🔑 API Key: dev-key-12345")
        print("\n🆕 V2 Features Demonstrated:")
        print("   ✓ Async client")
        print("   ✓ Policy-based evaluation")
        print("   ✓ Webhooks")
        print("   ✓ Compound detection")
        print("   ✓ Near-miss learning")
        print("   ✓ Audit export")
        print("   ✓ WebSocket dashboard (available)")


if __name__ == "__main__":
    asyncio.run(main())

"""Test API endpoints"""
import pytest
from httpx import AsyncClient, ASGITransport
from oversight_gateway.main import app


@pytest.fixture
async def client():
    """Test client with API key"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "dev-key-12345"}
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health endpoint"""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.asyncio
async def test_evaluate_action(client):
    """Test action evaluation"""
    response = await client.post("/evaluate", json={
        "session_id": "test-session",
        "action": "send_email",
        "target": "user@example.com",
        "metadata": {"contains_pii": False}
    })
    assert response.status_code == 200
    data = response.json()
    assert "action_id" in data
    assert "risk_score" in data
    assert data["session_id"] == "test-session"


@pytest.mark.asyncio
async def test_evaluate_high_risk_action(client):
    """Test high-risk action triggers checkpoint"""
    response = await client.post("/evaluate", json={
        "session_id": "test-session-2",
        "action": "delete_database",
        "target": "production_db",
        "metadata": {"irreversible": True}
    })
    assert response.status_code == 200
    data = response.json()
    assert data["needs_checkpoint"] == True
    assert data["risk_score"] > 0.6


@pytest.mark.asyncio
async def test_approval_workflow(client):
    """Test approval recording"""
    # First create an action
    eval_response = await client.post("/evaluate", json={
        "session_id": "test-session-3",
        "action": "transfer_funds",
        "target": "account-123",
        "metadata": {"amount": 50000, "financial": True}
    })
    action_id = eval_response.json()["action_id"]
    
    # Approve it
    approve_response = await client.post("/approve", json={
        "action_id": action_id,
        "approved": True,
        "notes": "Verified transaction",
        "channel": "rest"
    })
    assert approve_response.status_code == 200
    data = approve_response.json()
    assert data["approved"] == True


@pytest.mark.asyncio
async def test_near_miss_recording(client):
    """Test near-miss recording"""
    response = await client.post("/near-miss", json={
        "session_id": "test-session-4",
        "action": "delete_file",
        "near_miss_type": "boundary_violation",
        "actual_severity": 0.8,
        "description": "Deleted wrong file"
    })
    assert response.status_code == 200
    data = response.json()
    assert "near_miss_id" in data
    assert data["message"] == "Near-miss recorded successfully"


@pytest.mark.asyncio
async def test_budget_tracking(client):
    """Test session budget endpoint"""
    # Create some actions
    await client.post("/evaluate", json={
        "session_id": "test-budget",
        "action": "send_email",
        "target": "user@example.com"
    })
    
    # Check budget
    response = await client.get("/budget/test-budget")
    assert response.status_code == 200
    data = response.json()
    assert "risk_budget" in data
    assert "cumulative_risk" in data
    assert "remaining_budget" in data


@pytest.mark.asyncio
async def test_stats_endpoint(client):
    """Test statistics endpoint"""
    response = await client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_actions" in data
    assert "checkpoints_triggered" in data
    assert "near_miss_breakdown" in data


@pytest.mark.asyncio
async def test_webhook_registration(client):
    """Test webhook registration"""
    response = await client.post("/config/webhooks", json={
        "url": "https://example.com/webhook",
        "events": ["checkpoint_triggered", "near_miss_recorded"],
        "secret": "test-secret"
    })
    assert response.status_code == 200
    data = response.json()
    assert "webhook_id" in data
    assert data["url"] == "https://example.com/webhook"


@pytest.mark.asyncio
async def test_audit_export(client):
    """Test audit log export"""
    # Create some actions first
    await client.post("/evaluate", json={
        "session_id": "audit-test",
        "action": "test_action",
        "target": "test_target"
    })
    
    # Export audit log
    response = await client.get("/audit/export?format=json")
    assert response.status_code == 200
    data = response.json()
    assert "total_entries" in data
    assert "entries" in data


@pytest.mark.asyncio
async def test_authentication_required(client):
    """Test that endpoints require authentication"""
    # Create client without API key
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as no_auth_client:
        response = await no_auth_client.get("/stats")
        assert response.status_code == 401

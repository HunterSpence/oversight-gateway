"""Test SDK functionality"""
import pytest
from oversight_gateway_sdk import AsyncOversightClient, OversightClient


@pytest.mark.asyncio
async def test_async_client_init():
    """Test async client initialization"""
    client = AsyncOversightClient(
        base_url="http://localhost:8001",
        api_key="test-key"
    )
    assert client.base_url == "http://localhost:8001"
    assert client.api_key == "test-key"
    await client.close()


def test_sync_client_init():
    """Test sync client initialization"""
    client = OversightClient(
        base_url="http://localhost:8001",
        api_key="test-key"
    )
    assert client._async_client.base_url == "http://localhost:8001"
    client.close()


@pytest.mark.asyncio
async def test_evaluation_result_dataclass():
    """Test EvaluationResult dataclass"""
    from oversight_gateway_sdk import EvaluationResult
    
    result = EvaluationResult(
        action_id=1,
        session_id="test",
        risk_score=0.45,
        impact=0.5,
        breadth=0.3,
        probability=0.3,
        needs_checkpoint=False,
        checkpoint_reason="",
        remaining_budget=0.35,
        is_compound=False,
        compound_count=1
    )
    
    assert result.action_id == 1
    assert result.needs_approval == False
    assert result.risk_score == 0.45

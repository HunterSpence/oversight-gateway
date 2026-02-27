# 🔒 Oversight Gateway

**AI Agent Oversight Checkpoint System** — A risk-aware gateway that evaluates agent actions and triggers human checkpoints when needed. Learns from near-misses to continuously improve risk assessment.

Protected by **US Patent Application 63/992,145**.

## What It Does

Oversight Gateway acts as a safety layer between AI agents and critical actions. It calculates risk scores based on Impact × Breadth × Probability, detects compound action patterns, and learns from near-miss events to prevent future issues. When risk exceeds thresholds, human approval is required before proceeding.

## Quick Start

### Docker (Recommended)

```bash
# Start the service
docker-compose up -d

# Check health
curl http://localhost:8001/health

# View logs
docker-compose logs -f
```

### Python

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python -m uvicorn oversight_gateway.main:app --host 0.0.0.0 --port 8001

# Or run the example demo
python example.py
```

The API will be available at `http://localhost:8001` with interactive docs at `http://localhost:8001/docs`.

## SDK Usage

```python
from oversight_gateway_sdk import OversightClient

# Initialize client
client = OversightClient(
    base_url="http://localhost:8001",
    api_key="your-api-key"
)

# Evaluate an action
result = client.evaluate(
    action="send_email",
    target="user@example.com",
    session_id="agent-session-1",
    metadata={
        "contains_pii": True,
        "recipients": ["user@example.com"]
    }
)

print(f"Risk Score: {result.risk_score:.3f}")
print(f"Needs Checkpoint: {result.needs_checkpoint}")

# If checkpoint is needed, wait for human approval
if result.needs_approval:
    # In production, this would notify a human via webhook/UI
    # For now, manually approve:
    client.approve(result.action_id, approved=True)

# Record a near-miss to improve future risk assessment
client.record_near_miss(
    action="send_email",
    near_miss_type="data_exposure",
    actual_severity=0.7,
    description="Email accidentally sent to wrong recipient"
)
```

## API Reference

### Authentication

All endpoints require an API key via the `X-API-Key` header.

Default development key: `dev-key-12345`

### Endpoints

#### `POST /evaluate`

Evaluate an action for risk.

**Request:**
```json
{
  "session_id": "agent-session-1",
  "action": "send_email",
  "target": "user@example.com",
  "metadata": {
    "contains_pii": true,
    "financial": false
  }
}
```

**Response:**
```json
{
  "action_id": 1,
  "session_id": "agent-session-1",
  "risk_score": 0.45,
  "impact": 0.5,
  "breadth": 0.3,
  "probability": 0.3,
  "needs_checkpoint": false,
  "checkpoint_reason": "",
  "remaining_budget": 0.55,
  "is_compound": false,
  "compound_count": 1
}
```

#### `POST /approve`

Record human approval/rejection for a checkpointed action.

**Request:**
```json
{
  "action_id": 1,
  "approved": true,
  "notes": "Reviewed and approved"
}
```

#### `POST /near-miss`

Record a near-miss event for future learning.

**Request:**
```json
{
  "session_id": "agent-session-1",
  "action": "delete_file",
  "near_miss_type": "boundary_violation",
  "actual_severity": 0.8,
  "description": "Deleted wrong file"
}
```

**Near-miss types:**
- `boundary_violation` — Action violated expected boundaries
- `resource_overuse` — Action consumed excessive resources
- `timing_anomaly` — Action occurred at unexpected time
- `permission_escalation` — Action exceeded expected permissions
- `data_exposure` — Action exposed unintended data
- `cascade_trigger` — Action triggered unexpected cascade effects
- `policy_drift` — Action deviated from established policy

#### `GET /budget/{session_id}`

Get remaining risk budget for a session.

**Response:**
```json
{
  "session_id": "agent-session-1",
  "risk_budget": 0.8,
  "cumulative_risk": 0.25,
  "remaining_budget": 0.55,
  "utilization_percent": 31.25
}
```

#### `GET /stats`

Get system-wide statistics.

**Response:**
```json
{
  "total_actions": 150,
  "checkpoints_triggered": 12,
  "checkpoints_approved": 10,
  "checkpoints_rejected": 2,
  "approval_rate": 83.3,
  "total_near_misses": 5,
  "near_miss_breakdown": {
    "boundary_violation": 2,
    "data_exposure": 3
  },
  "average_risk_score": 0.42
}
```

#### `GET /health`

Health check endpoint.

## Risk Scoring Algorithm

Risk is calculated as:

```
risk_score = impact × breadth × probability
```

Where each factor is 0.0-1.0:

- **Impact**: Severity of potential harm (e.g., financial loss, data exposure)
- **Breadth**: Scope of affected entities (single user vs. organization-wide)
- **Probability**: Likelihood of harm occurring

### Checkpoint Triggers

A checkpoint is triggered when:

1. **High single-action risk**: `risk_score > 0.6` (configurable)
2. **Budget exceeded**: `cumulative_risk + risk_score > session_budget` (default: 0.8)
3. **Compound actions**: Multiple actions on same target within time window (5 min default)

### Near-Miss Learning

When near-miss events are recorded, future risk assessments for similar actions are adjusted upward. The adjustment decays with a half-life (default: 24 hours), allowing the system to learn from recent incidents while gradually returning to baseline as time passes.

## Configuration

Environment variables:

- `DATABASE_URL` — SQLite database path (default: `sqlite:///./oversight_gateway.db`)
- `CHECKPOINT_THRESHOLD` — Risk threshold for checkpoints (default: 0.6)
- `SESSION_RISK_BUDGET` — Default session budget (default: 0.8)

## Pricing

| Tier | Price | Evaluations/mo | Features |
|------|-------|----------------|----------|
| **Free** | $0 | 3,000 | Basic risk scoring, 1 session |
| **Pro** | $99/mo | 30,000 | Near-miss learning, compound detection, 50 sessions |
| **Enterprise** | $499/mo | Unlimited | Custom risk models, SSO, priority support |

Contact: hspence21190@gmail.com

## License

**Proprietary**. See [LICENSE](LICENSE) for details.

Protected by US Patent Application 63/992,145.

Free for evaluation and personal use. Production use requires a paid license.

## Technical Details

- **Framework**: FastAPI
- **Database**: SQLite (production-ready for Postgres swap)
- **Language**: Python 3.11+
- **Dependencies**: FastAPI, SQLAlchemy, Pydantic, HTTPX

## Support

For questions, bug reports, or feature requests:

- **Email**: hspence21190@gmail.com
- **Issues**: Create an issue in the repository (when public)

---

Built by Hunter Spence | © 2026

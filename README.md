# 🔒 Oversight Gateway V2

**AI Agent Oversight Checkpoint System** — A risk-aware gateway that evaluates agent actions and triggers human checkpoints when needed. Learns from near-misses to continuously improve risk assessment.

**NEW IN V2:**
- ⚡ **Fully Async** - SQLAlchemy 2.0 + aiosqlite for high performance
- 📋 **Policy-as-Code** - Configure risk rules via YAML files
- 🔔 **Webhooks** - Get notified on Slack, email, or custom endpoints
- 🔌 **LangChain Integration** - Built-in middleware for LangChain agents
- 📊 **Real-Time Dashboard** - WebSocket streaming of live events
- 🔍 **OpenTelemetry** - Full tracing for observability
- 📝 **Audit Export** - Export compliance logs in JSON
- 🎯 **Structured Logging** - Production-ready logs with structlog

Protected by **US Patent Application 63/992,145**.

## What It Does

Oversight Gateway acts as a safety layer between AI agents and critical actions. It calculates risk scores based on Impact × Breadth × Probability, detects compound action patterns, and learns from near-miss events to prevent future issues. When risk exceeds thresholds, human approval is required before proceeding.

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/hunterspence/oversight-gateway.git
cd oversight-gateway

# Install with pip
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

### Running the Server

```bash
# Development mode
python -m uvicorn oversight_gateway.main:app --host 0.0.0.0 --port 8001 --reload

# Production mode
python -m uvicorn oversight_gateway.main:app --host 0.0.0.0 --port 8001 --workers 4
```

### Docker

```bash
# Start the service
docker-compose up -d

# Check health
curl http://localhost:8001/health

# View logs
docker-compose logs -f
```

The API will be available at `http://localhost:8001` with interactive docs at `http://localhost:8001/docs`.

## SDK Usage

### Async SDK (Recommended)

```python
import asyncio
from oversight_gateway_sdk import AsyncOversightClient

async def main():
    # Initialize async client
    async with AsyncOversightClient(
        base_url="http://localhost:8001",
        api_key="dev-key-12345"
    ) as client:
        # Evaluate an action
        result = await client.evaluate(
            action="send_email",
            target="user@example.com",
            session_id="agent-session-1",
            metadata={
                "contains_pii": True,
                "recipients": 50
            }
        )
        
        print(f"Risk Score: {result.risk_score:.3f}")
        print(f"Needs Checkpoint: {result.needs_checkpoint}")
        
        # If checkpoint is needed, handle approval
        if result.needs_approval:
            await client.approve(
                result.action_id,
                approved=True,
                notes="Reviewed and approved",
                channel="rest"
            )
        
        # Record a near-miss to improve future risk assessment
        await client.record_near_miss(
            action="send_email",
            near_miss_type="data_exposure",
            actual_severity=0.7,
            description="Email sent to wrong recipient"
        )

asyncio.run(main())
```

### Sync SDK (Backward Compatible)

```python
from oversight_gateway_sdk import OversightClient

# Initialize client
with OversightClient(
    base_url="http://localhost:8001",
    api_key="dev-key-12345"
) as client:
    # Evaluate an action
    result = client.evaluate(
        action="delete_file",
        target="/important/data.txt",
        metadata={"irreversible": True}
    )
    
    if result.needs_checkpoint:
        client.approve(result.action_id, approved=False)
```

### WebSocket Dashboard

```python
from oversight_gateway_sdk import DashboardClient
import asyncio

async def monitor_dashboard():
    async with DashboardClient("ws://localhost:8001/ws/dashboard") as dashboard:
        async for event in dashboard.listen():
            print(f"Event: {event['event']}")
            print(f"Data: {event['data']}")

asyncio.run(monitor_dashboard())
```

## LangChain Integration

```python
from oversight_gateway.integrations.langchain import OversightMiddleware
from oversight_gateway_sdk import AsyncOversightClient, EvaluationResult
from langchain.agents import create_openai_functions_agent
from langchain_openai import ChatOpenAI

# Create Oversight client
client = AsyncOversightClient("http://localhost:8001", "your-api-key")

# Define approval handler
async def approval_handler(result: EvaluationResult) -> bool:
    print(f"⚠️  Checkpoint: {result.checkpoint_reason}")
    print(f"   Risk: {result.risk_score:.3f}")
    response = input("Approve? (y/n): ")
    return response.lower() == 'y'

# Create middleware
middleware = OversightMiddleware(
    client=client,
    session_id="langchain-session",
    on_checkpoint=approval_handler
)

# Use with LangChain agent
agent = create_openai_functions_agent(
    llm=ChatOpenAI(model="gpt-4"),
    tools=[...],
    callbacks=[middleware.callback]
)

# Now all tool calls will be evaluated by Oversight Gateway
```

## Policy-as-Code

Configure risk policies via YAML files in the `policies/` directory:

```yaml
# policies/default.yaml
risk_thresholds:
  checkpoint_trigger: 0.6
  session_budget: 0.8

action_rules:
  - pattern: "delete_*"
    impact_floor: 0.8
    always_checkpoint: true
    description: "Deletion operations require approval"
  
  - pattern: "send_email"
    impact_floor: 0.5
    metadata_boosts:
      contains_pii: 0.3
      recipients_over_10: 0.2

compound_detection:
  time_window_seconds: 300
  same_resource_boost: 0.2

near_miss:
  half_life_hours: 24.0
  max_multiplier: 2.0
```

Reload policies without restart:

```bash
curl -X POST http://localhost:8001/config/reload \
  -H "X-API-Key: dev-key-12345"
```

## Webhooks

Register webhooks to get notified of events:

```python
await client.register_webhook(
    url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    events=[
        "checkpoint_triggered",
        "near_miss_recorded",
        "budget_exceeded"
    ],
    secret="your-hmac-secret"  # Optional
)
```

Available events:
- `checkpoint_triggered` - High-risk action needs approval
- `action_approved` - Action was approved
- `action_rejected` - Action was rejected
- `near_miss_recorded` - Near-miss event logged
- `budget_exceeded` - Session budget exceeded

## API Reference

### Authentication

All endpoints require an API key via the `X-API-Key` header.

Default development key: `dev-key-12345`

### Core Endpoints

#### `POST /evaluate`

Evaluate an action for risk.

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

#### `POST /approve`

Record human approval/rejection.

```json
{
  "action_id": 1,
  "approved": true,
  "notes": "Reviewed and approved",
  "channel": "rest"
}
```

#### `POST /near-miss`

Record a near-miss event.

```json
{
  "session_id": "agent-session-1",
  "action": "delete_file",
  "near_miss_type": "boundary_violation",
  "actual_severity": 0.8,
  "description": "Deleted wrong file"
}
```

#### `GET /budget/{session_id}`

Get remaining risk budget for a session.

#### `GET /stats`

Get system-wide statistics.

#### `GET /audit/export`

Export audit log.

```bash
curl "http://localhost:8001/audit/export?format=json&from=2026-01-01&to=2026-02-28" \
  -H "X-API-Key: dev-key-12345"
```

#### `POST /config/webhooks`

Register a webhook.

#### `WS /ws/dashboard`

WebSocket endpoint for real-time event streaming.

### Near-miss Types

- `boundary_violation` — Action violated expected boundaries
- `resource_overuse` — Action consumed excessive resources
- `timing_anomaly` — Action occurred at unexpected time
- `permission_escalation` — Action exceeded expected permissions
- `data_exposure` — Action exposed unintended data
- `cascade_trigger` — Action triggered unexpected cascade effects
- `policy_drift` — Action deviated from established policy

## Risk Scoring Algorithm

Risk is calculated as:

```
risk_score = impact × breadth × probability
```

Where each factor is 0.0-1.0:

- **Impact**: Severity of potential harm
- **Breadth**: Scope of affected entities
- **Probability**: Likelihood of harm occurring

### Checkpoint Triggers

A checkpoint is triggered when:

1. **High single-action risk**: `risk_score > threshold` (configurable via policy)
2. **Budget exceeded**: `cumulative_risk + risk_score > session_budget`
3. **Compound actions**: Multiple actions on same target within time window
4. **Action rule**: Policy defines `always_checkpoint: true`

### Near-Miss Learning

When near-miss events are recorded, future risk assessments for similar actions are adjusted upward. The adjustment decays with a configurable half-life (default: 24 hours).

## OpenTelemetry Tracing

Export traces to Jaeger, Zipkin, or any OTLP-compatible backend:

```bash
export OTLP_ENDPOINT="http://localhost:4317"
export SERVICE_NAME="oversight-gateway"
python -m uvicorn oversight_gateway.main:app
```

All evaluations, approvals, and near-miss recordings are instrumented with spans.

## Configuration

Environment variables:

- `DATABASE_URL` — Database URL (default: `sqlite+aiosqlite:///./oversight_gateway.db`)
- `OTLP_ENDPOINT` — OpenTelemetry OTLP endpoint
- `SERVICE_NAME` — Service name for tracing (default: `oversight-gateway`)
- `API_KEY_DEV` — Development API key
- `API_KEY_TEST` — Test API key

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# With coverage
pytest --cov=oversight_gateway --cov-report=html
```

### Code Formatting

```bash
black oversight_gateway oversight_gateway_sdk tests
ruff check oversight_gateway oversight_gateway_sdk
```

## Pricing

| Tier | Price | Evaluations/mo | Features |
|------|-------|----------------|----------|
| **Free** | $0 | 3,000 | Basic risk scoring, 1 session |
| **Pro** | $99/mo | 30,000 | Near-miss learning, compound detection, webhooks, 50 sessions |
| **Enterprise** | $499/mo | Unlimited | Custom risk models, SSO, priority support, SLA |

Contact: hspence21190@gmail.com

## License

**Proprietary**. See [LICENSE](LICENSE) for details.

Protected by US Patent Application 63/992,145.

Free for evaluation and personal use. Production use requires a paid license.

## Technical Details

- **Framework**: FastAPI (async)
- **Database**: SQLAlchemy 2.0 + aiosqlite (production-ready for Postgres)
- **Language**: Python 3.11+
- **Observability**: OpenTelemetry + Structlog
- **Dependencies**: See pyproject.toml

## Support

For questions, bug reports, or feature requests:

- **Email**: hspence21190@gmail.com
- **Issues**: Create an issue in the repository

---

**V2.0.0** - Async engine, policy-as-code, webhooks, LangChain middleware, OTel tracing, WebSocket dashboard

Built by Hunter Spence | © 2026

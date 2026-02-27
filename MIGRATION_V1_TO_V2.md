# Migration Guide: V1 to V2

## Breaking Changes

### 1. Dependencies

**V1:** `requirements.txt`  
**V2:** `pyproject.toml`

```bash
# V1
pip install -r requirements.txt

# V2
pip install -e .
```

### 2. Database URL Format

**V1:** `sqlite:///./oversight_gateway.db`  
**V2:** `sqlite+aiosqlite:///./oversight_gateway.db`

Update your `DATABASE_URL` environment variable to use the async driver.

### 3. SDK Import

**V1:**
```python
from oversight_gateway_sdk import OversightClient
client = OversightClient("http://localhost:8001", "api-key")
```

**V2 (Async - Recommended):**
```python
from oversight_gateway_sdk import AsyncOversightClient
async with AsyncOversightClient("http://localhost:8001", "api-key") as client:
    result = await client.evaluate(...)
```

**V2 (Sync - Backward Compatible):**
```python
from oversight_gateway_sdk import OversightClient
# Same as V1, but internally uses asyncio
client = OversightClient("http://localhost:8001", "api-key")
result = client.evaluate(...)
```

### 4. Approval Request Schema

**V1:**
```json
{
  "action_id": 1,
  "approved": true,
  "notes": "Optional notes"
}
```

**V2:**
```json
{
  "action_id": 1,
  "approved": true,
  "notes": "Optional notes",
  "channel": "rest"  // NEW: tracks approval source
}
```

## New Features

### 1. Policy-as-Code

Create `policies/default.yaml`:

```yaml
risk_thresholds:
  checkpoint_trigger: 0.6
  session_budget: 0.8

action_rules:
  - pattern: "delete_*"
    impact_floor: 0.8
    always_checkpoint: true
```

### 2. Webhooks

```python
await client.register_webhook(
    url="https://hooks.slack.com/services/YOUR/WEBHOOK",
    events=["checkpoint_triggered", "near_miss_recorded"]
)
```

### 3. WebSocket Dashboard

```python
from oversight_gateway_sdk import DashboardClient
async with DashboardClient("ws://localhost:8001/ws/dashboard") as dashboard:
    async for event in dashboard.listen():
        print(event)
```

### 4. LangChain Integration

```python
from oversight_gateway.integrations.langchain import OversightMiddleware
middleware = OversightMiddleware(
    gateway_url="http://localhost:8001",
    api_key="your-key"
)
# Use with LangChain agent callbacks
```

### 5. Audit Log Export

```python
audit = await client.export_audit_log(
    from_date="2026-01-01",
    to_date="2026-02-28"
)
```

### 6. OpenTelemetry Tracing

```bash
export OTLP_ENDPOINT="http://localhost:4317"
python -m uvicorn oversight_gateway.main:app
```

## Configuration Changes

### V1 Config
- Hardcoded in `RiskEngine.__init__()`
- No external configuration

### V2 Config
- YAML policy files in `policies/` directory
- Reloadable via `POST /config/reload`
- Environment variables for infrastructure:
  - `DATABASE_URL`
  - `OTLP_ENDPOINT`
  - `SERVICE_NAME`

## Database Migration

**No migration needed!** V2 is backward-compatible with V1 database schema.

New columns added:
- `actions.approval_channel`
- `actions.approval_notes`
- New table: `webhooks`

These are auto-created on startup via SQLAlchemy migrations.

## Performance Improvements

- **V1:** Sync SQLAlchemy (blocking I/O)
- **V2:** Async SQLAlchemy 2.0 + aiosqlite (non-blocking)

Expected improvements:
- 2-3x higher throughput
- Better concurrency under load
- Lower latency for compound action detection

## Testing

```bash
# V1
python test_core.py

# V2
pip install -e ".[dev]"
pytest
```

## Rollback Plan

If you need to rollback to V1:

```bash
git checkout df9d04a  # Last V1 commit
pip install -r requirements.txt
python -m uvicorn oversight_gateway.main:app
```

Database is compatible, but new V2 features (webhooks, approval channels) will not be available.

## Support

Questions? Email: hspence21190@gmail.com

# Oversight Gateway - Quick Start

## ✅ Installation Verified

All core functionality has been tested and is working:

- ✅ Risk scoring algorithm (Impact × Breadth × Probability)
- ✅ Checkpoint triggering (threshold and budget-based)
- ✅ Compound action detection
- ✅ Near-miss learning with decay
- ✅ Session budget tracking

## Try It Now

### 1. Run Core Tests
```bash
python test_core.py
```

### 2. Run Full Demo
```bash
python example.py
```

### 3. Start Production Service
```bash
# Using Docker (recommended)
docker-compose up -d

# Or directly with Python
python -m uvicorn oversight_gateway.main:app --host 0.0.0.0 --port 8001
```

### 4. Try the API
```bash
# Check health
curl http://localhost:8001/health

# Evaluate an action (use API key: dev-key-12345)
curl -X POST http://localhost:8001/evaluate \
  -H "X-API-Key: dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo",
    "action": "send_email",
    "target": "user@example.com",
    "metadata": {"contains_pii": true}
  }'
```

### 5. View Interactive API Docs
Open in browser: http://localhost:8001/docs

## SDK Example

```python
from oversight_gateway_sdk import OversightClient

client = OversightClient("http://localhost:8001", api_key="dev-key-12345")

# Evaluate an action
result = client.evaluate(
    action="delete_file",
    target="/important/data.db",
    metadata={"irreversible": True}
)

print(f"Risk: {result.risk_score:.2f}")
if result.needs_approval:
    print("⚠️ Checkpoint required!")
    # Wait for human approval...
```

## What's Included

```
oversight-gateway/
├── oversight_gateway/          # Core FastAPI service
│   ├── main.py                # API endpoints
│   ├── risk_engine.py         # Risk scoring logic
│   ├── models.py              # Database models
│   ├── database.py            # SQLite setup
│   ├── auth.py                # API key auth
│   └── schemas.py             # Pydantic schemas
├── oversight_gateway_sdk/     # Python SDK
│   └── __init__.py           # Client library
├── test_core.py              # Verification tests
├── example.py                # Full demo script
├── Dockerfile                # Container image
├── docker-compose.yml        # Service orchestration
├── requirements.txt          # Python dependencies
├── README.md                 # Full documentation
└── LICENSE                   # Proprietary license
```

## Next Steps

1. **Customize risk scoring** - Edit `risk_engine.py` to tune factors
2. **Add webhooks** - Integrate approval notifications
3. **Deploy to production** - Use Docker or Kubernetes
4. **Integrate with your agent** - Use the SDK in your code

## Support

Questions? Email: hspence21190@gmail.com

Protected by US Patent Application 63/992,145

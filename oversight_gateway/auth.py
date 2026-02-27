"""API key authentication"""
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
import os

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# In production, load from environment or database
VALID_API_KEYS = {
    os.getenv("API_KEY_DEV", "dev-key-12345"): "development",
    os.getenv("API_KEY_TEST", "test-key-67890"): "testing",
}


async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify API key from header (async)"""
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key"
        )
    
    if api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return api_key

"""Webhook management and event notification"""
import asyncio
import hmac
import hashlib
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import structlog
from opentelemetry import trace

from .models import Webhook
from .schemas import WebSocketMessage

logger = structlog.get_logger()
tracer = trace.get_tracer(__name__)


class WebhookManager:
    """Manages webhook delivery for events"""
    
    def __init__(self, timeout: float = 10.0, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=timeout)
    
    async def trigger_webhooks(
        self,
        db: AsyncSession,
        event: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Trigger all webhooks subscribed to an event.
        
        Args:
            db: Database session
            event: Event type (e.g., "checkpoint_triggered")
            data: Event data payload
        """
        with tracer.start_as_current_span("trigger_webhooks") as span:
            span.set_attribute("event", event)
            
            # Get all enabled webhooks for this event
            result = await db.execute(
                select(Webhook).where(Webhook.enabled == True)
            )
            webhooks = result.scalars().all()
            
            # Filter webhooks subscribed to this event
            subscribed = [wh for wh in webhooks if event in wh.events]
            
            if not subscribed:
                logger.debug("no_webhooks_subscribed", event=event)
                return
            
            span.set_attribute("webhook_count", len(subscribed))
            logger.info("triggering_webhooks", event=event, count=len(subscribed))
            
            # Trigger webhooks concurrently
            tasks = [
                self._deliver_webhook(db, webhook, event, data)
                for webhook in subscribed
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _deliver_webhook(
        self,
        db: AsyncSession,
        webhook: Webhook,
        event: str,
        data: Dict[str, Any]
    ) -> None:
        """Deliver webhook with retries"""
        with tracer.start_as_current_span("deliver_webhook") as span:
            span.set_attribute("webhook_id", webhook.id)
            span.set_attribute("webhook_url", webhook.url)
            span.set_attribute("event", event)
            
            payload = {
                "event": event,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
                "webhook_id": webhook.id,
            }
            
            # Add HMAC signature if secret is configured
            headers = {"Content-Type": "application/json"}
            if webhook.secret:
                signature = self._generate_signature(payload, webhook.secret)
                headers["X-Webhook-Signature"] = signature
            
            # Attempt delivery with retries
            for attempt in range(self.max_retries):
                try:
                    response = await self._client.post(
                        webhook.url,
                        json=payload,
                        headers=headers
                    )
                    response.raise_for_status()
                    
                    # Success
                    webhook.last_triggered = datetime.utcnow()
                    webhook.failure_count = 0
                    await db.commit()
                    
                    logger.info(
                        "webhook_delivered",
                        webhook_id=webhook.id,
                        url=webhook.url,
                        event=event,
                        status=response.status_code
                    )
                    span.set_attribute("success", True)
                    return
                    
                except Exception as e:
                    logger.warning(
                        "webhook_delivery_failed",
                        webhook_id=webhook.id,
                        url=webhook.url,
                        attempt=attempt + 1,
                        error=str(e)
                    )
                    
                    if attempt == self.max_retries - 1:
                        # Final failure
                        webhook.failure_count += 1
                        if webhook.failure_count >= 10:
                            webhook.enabled = False
                            logger.warning(
                                "webhook_disabled_after_failures",
                                webhook_id=webhook.id,
                                failure_count=webhook.failure_count
                            )
                        await db.commit()
                        span.set_attribute("success", False)
                    else:
                        # Retry with backoff
                        await asyncio.sleep(2 ** attempt)
    
    @staticmethod
    def _generate_signature(payload: Dict[str, Any], secret: str) -> str:
        """Generate HMAC signature for webhook payload"""
        import json
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        signature = hmac.new(
            secret.encode(),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"
    
    async def close(self) -> None:
        """Close HTTP client"""
        await self._client.aclose()


# Global webhook manager instance
_webhook_manager: WebhookManager = None


def get_webhook_manager() -> WebhookManager:
    """Get global webhook manager instance"""
    global _webhook_manager
    if _webhook_manager is None:
        _webhook_manager = WebhookManager()
    return _webhook_manager

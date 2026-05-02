"""
Webhook Notifications
=====================
Send HTTP callbacks when events occur (job completion, errors, etc.).

Author: VidyuthLabs
Date: May 1, 2026
"""

import asyncio
import logging
import hmac
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


class WebhookEvent(str, Enum):
    """Webhook event types."""
    BATCH_JOB_STARTED = "batch_job.started"
    BATCH_JOB_COMPLETED = "batch_job.completed"
    BATCH_JOB_FAILED = "batch_job.failed"
    BATCH_JOB_PROGRESS = "batch_job.progress"
    EXPERIMENT_CREATED = "experiment.created"
    EXPERIMENT_UPDATED = "experiment.updated"
    EXPERIMENT_DELETED = "experiment.deleted"
    ANALYSIS_COMPLETED = "analysis.completed"
    REPORT_GENERATED = "report.generated"
    ERROR_OCCURRED = "error.occurred"


@dataclass
class WebhookConfig:
    """Webhook configuration."""
    id: str
    url: str
    events: List[WebhookEvent]
    secret: Optional[str] = None  # For HMAC signature
    enabled: bool = True
    retry_count: int = 3
    timeout_seconds: int = 30
    headers: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "url": self.url,
            "events": [e.value for e in self.events],
            "enabled": self.enabled,
            "retry_count": self.retry_count,
            "timeout_seconds": self.timeout_seconds,
            "headers": self.headers
        }


@dataclass
class WebhookDelivery:
    """Webhook delivery record."""
    id: str
    webhook_id: str
    event: WebhookEvent
    payload: Dict[str, Any]
    url: str
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0
    delivered: bool = False
    created_at: datetime = None
    delivered_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "webhook_id": self.webhook_id,
            "event": self.event.value,
            "payload": self.payload,
            "url": self.url,
            "status_code": self.status_code,
            "response_body": self.response_body,
            "error": self.error,
            "attempts": self.attempts,
            "delivered": self.delivered,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None
        }


class WebhookManager:
    """
    Webhook manager for sending HTTP callbacks.
    
    Features:
    - Event-based notifications
    - HMAC signature verification
    - Automatic retry with exponential backoff
    - Delivery tracking
    - Timeout handling
    
    Examples:
        # Register webhook
        manager.register_webhook(
            url="https://your-server.com/webhook",
            events=[WebhookEvent.BATCH_JOB_COMPLETED],
            secret="your-secret-key"
        )
        
        # Send notification
        await manager.send_webhook(
            event=WebhookEvent.BATCH_JOB_COMPLETED,
            payload={
                "job_id": "123",
                "status": "completed",
                "results": {...}
            }
        )
    """
    
    def __init__(self):
        """Initialize webhook manager."""
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.deliveries: Dict[str, WebhookDelivery] = {}
        logger.info("Webhook manager initialized")
    
    def register_webhook(
        self,
        url: str,
        events: List[WebhookEvent],
        secret: Optional[str] = None,
        enabled: bool = True,
        retry_count: int = 3,
        timeout_seconds: int = 30,
        headers: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Register a webhook endpoint.
        
        Args:
            url: Webhook URL
            events: List of events to subscribe to
            secret: Secret key for HMAC signature (optional)
            enabled: Whether webhook is enabled
            retry_count: Number of retry attempts
            timeout_seconds: Request timeout
            headers: Additional HTTP headers
        
        Returns:
            Webhook ID
        """
        import uuid
        webhook_id = str(uuid.uuid4())
        
        webhook = WebhookConfig(
            id=webhook_id,
            url=url,
            events=events,
            secret=secret,
            enabled=enabled,
            retry_count=retry_count,
            timeout_seconds=timeout_seconds,
            headers=headers or {}
        )
        
        self.webhooks[webhook_id] = webhook
        
        logger.info(
            f"Registered webhook {webhook_id} for {url} - "
            f"Events: {[e.value for e in events]}"
        )
        
        return webhook_id
    
    async def send_webhook(
        self,
        event: WebhookEvent,
        payload: Dict[str, Any],
        webhook_id: Optional[str] = None
    ):
        """
        Send webhook notification.
        
        Args:
            event: Event type
            payload: Event payload
            webhook_id: Specific webhook ID (optional, sends to all matching webhooks if None)
        """
        # Find matching webhooks
        webhooks = []
        
        if webhook_id:
            webhook = self.webhooks.get(webhook_id)
            if webhook and webhook.enabled and event in webhook.events:
                webhooks.append(webhook)
        else:
            # Send to all webhooks subscribed to this event
            webhooks = [
                w for w in self.webhooks.values()
                if w.enabled and event in w.events
            ]
        
        if not webhooks:
            logger.debug(f"No webhooks registered for event: {event.value}")
            return
        
        # Send to all matching webhooks
        tasks = [
            self._deliver_webhook(webhook, event, payload)
            for webhook in webhooks
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _deliver_webhook(
        self,
        webhook: WebhookConfig,
        event: WebhookEvent,
        payload: Dict[str, Any]
    ):
        """
        Deliver webhook with retry logic.
        
        Args:
            webhook: Webhook configuration
            event: Event type
            payload: Event payload
        """
        import uuid
        delivery_id = str(uuid.uuid4())
        
        # Create delivery record
        delivery = WebhookDelivery(
            id=delivery_id,
            webhook_id=webhook.id,
            event=event,
            payload=payload,
            url=webhook.url
        )
        
        self.deliveries[delivery_id] = delivery
        
        # Prepare payload
        webhook_payload = {
            "event": event.value,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload
        }
        
        # Add signature if secret is provided
        headers = dict(webhook.headers or {})
        headers["Content-Type"] = "application/json"
        headers["User-Agent"] = "RAMAN-Studio-Webhook/1.0"
        
        if webhook.secret:
            signature = self._generate_signature(webhook.secret, webhook_payload)
            headers["X-Webhook-Signature"] = signature
        
        # Retry with exponential backoff
        for attempt in range(webhook.retry_count):
            delivery.attempts = attempt + 1
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        webhook.url,
                        json=webhook_payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=webhook.timeout_seconds)
                    ) as response:
                        delivery.status_code = response.status
                        delivery.response_body = await response.text()
                        
                        if 200 <= response.status < 300:
                            # Success
                            delivery.delivered = True
                            delivery.delivered_at = datetime.utcnow()
                            
                            logger.info(
                                f"Webhook delivered successfully: {webhook.url} - "
                                f"Event: {event.value}, Status: {response.status}"
                            )
                            return
                        else:
                            # HTTP error
                            logger.warning(
                                f"Webhook delivery failed: {webhook.url} - "
                                f"Status: {response.status}, Attempt: {attempt + 1}/{webhook.retry_count}"
                            )
            
            except asyncio.TimeoutError:
                delivery.error = "Request timeout"
                logger.warning(
                    f"Webhook timeout: {webhook.url} - "
                    f"Attempt: {attempt + 1}/{webhook.retry_count}"
                )
            
            except Exception as e:
                delivery.error = str(e)
                logger.error(
                    f"Webhook delivery error: {webhook.url} - "
                    f"Error: {e}, Attempt: {attempt + 1}/{webhook.retry_count}"
                )
            
            # Exponential backoff (1s, 2s, 4s, ...)
            if attempt < webhook.retry_count - 1:
                await asyncio.sleep(2 ** attempt)
        
        # All retries failed
        logger.error(
            f"Webhook delivery failed after {webhook.retry_count} attempts: "
            f"{webhook.url} - Event: {event.value}"
        )
    
    def _generate_signature(self, secret: str, payload: Dict[str, Any]) -> str:
        """
        Generate HMAC signature for webhook payload.
        
        Args:
            secret: Secret key
            payload: Webhook payload
        
        Returns:
            HMAC signature (hex)
        """
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"
    
    @staticmethod
    def verify_signature(secret: str, payload: Dict[str, Any], signature: str) -> bool:
        """
        Verify webhook signature.
        
        Args:
            secret: Secret key
            payload: Webhook payload
            signature: Signature to verify (format: "sha256=...")
        
        Returns:
            True if signature is valid
        """
        if not signature.startswith("sha256="):
            return False
        
        expected_signature = signature[7:]  # Remove "sha256=" prefix
        
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        computed_signature = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, expected_signature)
    
    def get_webhook(self, webhook_id: str) -> Optional[WebhookConfig]:
        """Get webhook configuration by ID."""
        return self.webhooks.get(webhook_id)
    
    def list_webhooks(self, enabled_only: bool = False) -> List[WebhookConfig]:
        """
        List all webhooks.
        
        Args:
            enabled_only: Only return enabled webhooks
        
        Returns:
            List of webhook configurations
        """
        webhooks = list(self.webhooks.values())
        
        if enabled_only:
            webhooks = [w for w in webhooks if w.enabled]
        
        return webhooks
    
    def update_webhook(
        self,
        webhook_id: str,
        url: Optional[str] = None,
        events: Optional[List[WebhookEvent]] = None,
        enabled: Optional[bool] = None,
        secret: Optional[str] = None
    ) -> bool:
        """
        Update webhook configuration.
        
        Args:
            webhook_id: Webhook ID
            url: New URL
            events: New event list
            enabled: Enable/disable webhook
            secret: New secret key
        
        Returns:
            True if updated, False if not found
        """
        webhook = self.webhooks.get(webhook_id)
        if not webhook:
            return False
        
        if url is not None:
            webhook.url = url
        
        if events is not None:
            webhook.events = events
        
        if enabled is not None:
            webhook.enabled = enabled
        
        if secret is not None:
            webhook.secret = secret
        
        logger.info(f"Updated webhook {webhook_id}")
        return True
    
    def delete_webhook(self, webhook_id: str) -> bool:
        """
        Delete webhook.
        
        Args:
            webhook_id: Webhook ID
        
        Returns:
            True if deleted, False if not found
        """
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]
            logger.info(f"Deleted webhook {webhook_id}")
            return True
        return False
    
    def get_delivery(self, delivery_id: str) -> Optional[WebhookDelivery]:
        """Get webhook delivery record by ID."""
        return self.deliveries.get(delivery_id)
    
    def list_deliveries(
        self,
        webhook_id: Optional[str] = None,
        event: Optional[WebhookEvent] = None,
        delivered_only: bool = False
    ) -> List[WebhookDelivery]:
        """
        List webhook deliveries.
        
        Args:
            webhook_id: Filter by webhook ID
            event: Filter by event type
            delivered_only: Only return successful deliveries
        
        Returns:
            List of webhook deliveries
        """
        deliveries = list(self.deliveries.values())
        
        if webhook_id:
            deliveries = [d for d in deliveries if d.webhook_id == webhook_id]
        
        if event:
            deliveries = [d for d in deliveries if d.event == event]
        
        if delivered_only:
            deliveries = [d for d in deliveries if d.delivered]
        
        return deliveries


# Global webhook manager instance
_webhook_manager = None


def get_webhook_manager() -> WebhookManager:
    """Get or create global webhook manager instance."""
    global _webhook_manager
    if _webhook_manager is None:
        _webhook_manager = WebhookManager()
    return _webhook_manager


# ===================================================================
#  Convenience Functions
# ===================================================================

async def notify_batch_job_started(job_id: str, job_name: str, total_files: int):
    """Send batch job started notification."""
    manager = get_webhook_manager()
    await manager.send_webhook(
        event=WebhookEvent.BATCH_JOB_STARTED,
        payload={
            "job_id": job_id,
            "job_name": job_name,
            "total_files": total_files,
            "status": "started"
        }
    )


async def notify_batch_job_completed(
    job_id: str,
    job_name: str,
    total_files: int,
    successful_files: int,
    failed_files: int,
    results: Dict[str, Any]
):
    """Send batch job completed notification."""
    manager = get_webhook_manager()
    await manager.send_webhook(
        event=WebhookEvent.BATCH_JOB_COMPLETED,
        payload={
            "job_id": job_id,
            "job_name": job_name,
            "total_files": total_files,
            "successful_files": successful_files,
            "failed_files": failed_files,
            "status": "completed",
            "results": results
        }
    )


async def notify_batch_job_failed(job_id: str, job_name: str, error: str):
    """Send batch job failed notification."""
    manager = get_webhook_manager()
    await manager.send_webhook(
        event=WebhookEvent.BATCH_JOB_FAILED,
        payload={
            "job_id": job_id,
            "job_name": job_name,
            "status": "failed",
            "error": error
        }
    )


async def notify_batch_job_progress(
    job_id: str,
    job_name: str,
    progress: int,
    processed_files: int,
    total_files: int
):
    """Send batch job progress notification."""
    manager = get_webhook_manager()
    await manager.send_webhook(
        event=WebhookEvent.BATCH_JOB_PROGRESS,
        payload={
            "job_id": job_id,
            "job_name": job_name,
            "progress": progress,
            "processed_files": processed_files,
            "total_files": total_files,
            "status": "running"
        }
    )

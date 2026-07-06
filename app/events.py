import logging
from typing import Any

logger = logging.getLogger(__name__)


def publish_event(event_type: str, payload: dict[str, Any]) -> None:
    """Stub: log event; replace body with message-broker publish for real integration."""
    logger.info("EVENT %s %s", event_type, payload)

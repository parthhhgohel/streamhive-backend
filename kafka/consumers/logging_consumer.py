import logging
from .base import BaseConsumer
from kafka.topics import Topics

logger = logging.getLogger(__name__)


class LoggingConsumer(BaseConsumer):
    """
    Subscribes to ALL topics.
    Simply logs every event — good for debugging and audit trail.
    In Phase 5 this gets replaced by ClickHouse analytics.
    """
    topic = [
        Topics.POST_CREATED,
        Topics.POST_LIKED,
        Topics.POST_UNLIKED,
        Topics.POST_COMMENTED,
        Topics.USER_FOLLOWED,
        Topics.USER_UNFOLLOWED,
    ]
    group_id = "logging-consumer-group"

    def process_event(self, event: dict):
        topic = event.get("_meta", {}).get("topic", "unknown")
        timestamp = event.get("_meta", {}).get("timestamp", "unknown")

        logger.info(
            f"[EVENT] topic={topic} timestamp={timestamp} data={event}"
        )
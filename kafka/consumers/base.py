import json
import logging
import django
import os

logger = logging.getLogger(__name__)


class BaseConsumer:
    """
    All consumers inherit from this.
    Handles setup, deserialization, error handling.
    Subclasses only implement process_event().
    """
    topic = None
    group_id = None

    def __init__(self):
        if not self.topic:
            raise NotImplementedError("Consumer must define a topic")
        if not self.group_id:
            raise NotImplementedError("Consumer must define a group_id")

    def _get_consumer(self):
        from confluent_kafka import Consumer
        from django.conf import settings

        config = {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": self.group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }

        if getattr(settings, "KAFKA_SASL_USERNAME", ""):
            config.update({
                "security.protocol": "SASL_SSL",
                "sasl.mechanism": "SCRAM-SHA-256",
                "sasl.username": settings.KAFKA_SASL_USERNAME,
                "sasl.password": settings.KAFKA_SASL_PASSWORD,
            })

        return Consumer(config)

    def process_event(self, event: dict):
        """
        Subclasses implement this.
        event is the deserialized dict payload.
        """
        raise NotImplementedError

    def run(self):
        consumer = self._get_consumer()
        consumer.subscribe([self.topic] if isinstance(self.topic, str) else self.topic)

        logger.info(f"Consumer started: group={self.group_id} topic={self.topic}")

        try:
            while True:
                msg = consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    logger.error(f"Consumer error: {msg.error()}")
                    continue

                try:
                    event = json.loads(msg.value().decode("utf-8"))
                    self.process_event(event)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message: {e}")
                except Exception as e:
                    logger.error(f"Failed to process event: {e}", exc_info=True)
                    # continue — don't crash the consumer on a bad message

        except KeyboardInterrupt:
            logger.info("Consumer shutting down...")
        finally:
            consumer.close()
import json
import logging
from datetime import datetime
from confluent_kafka import Producer
from django.conf import settings

logger = logging.getLogger(__name__)


class KafkaProducer:
    """
    Singleton Kafka producer.
    One producer instance shared across the whole Django app.
    Creating a new producer per request is expensive.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._producer = None
        return cls._instance

    def _get_producer(self):
        if self._producer is None:
            from django.conf import settings

            config = {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "acks": 1,
                "retries": 3,
                "message.timeout.ms": 5000,
            }

            if getattr(settings, "KAFKA_SASL_USERNAME", ""):
                config.update({
                    "security.protocol": "SASL_SSL",
                    "sasl.mechanism": "SCRAM-SHA-256",
                    "sasl.username": settings.KAFKA_SASL_USERNAME,
                    "sasl.password": settings.KAFKA_SASL_PASSWORD,
                })

            self._producer = Producer(config)
        return self._producer

    def _delivery_report(self, err, msg):
        if err:
            logger.error(f"Kafka delivery failed: topic={msg.topic()} error={err}")
        else:
            logger.debug(f"Kafka delivered: topic={msg.topic()} partition={msg.partition()}")

    def publish(self, topic: str, payload: dict, key: str = None):
        """
        Publish an event to a Kafka topic.

        topic   — the topic name e.g. "post.created"
        payload — dict that will be JSON serialized
        key     — optional partition key (e.g. user_id for ordering)
        """
        try:
            producer = self._get_producer()

            # always add metadata to every event
            payload["_meta"] = {
                "timestamp": datetime.utcnow().isoformat(),
                "topic": topic,
            }

            producer.produce(
                topic=topic,
                value=json.dumps(payload).encode("utf-8"),
                key=key.encode("utf-8") if key else None,
                callback=self._delivery_report,
            )

            # flush makes sure the message is actually sent
            producer.poll(0)
            # producer.flush()

        except Exception as e:
            # IMPORTANT: never let Kafka failure break the main request
            logger.error(f"Kafka publish failed: topic={topic} error={e}")


# single instance used everywhere
kafka_producer = KafkaProducer()
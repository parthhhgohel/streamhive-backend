from django.core.management.base import BaseCommand
from confluent_kafka.admin import AdminClient, NewTopic
from django.conf import settings
from kafka.topics import Topics

class Command(BaseCommand):
    help = "Create Kafka topics if they don't exist"

    def handle(self, *args, **options):
        admin = AdminClient({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS
        })

        topics_to_create = [
            NewTopic(topic, num_partitions=3, replication_factor=1)
            for topic in [
                Topics.POST_CREATED,
                Topics.POST_LIKED,
                Topics.POST_UNLIKED,
                Topics.POST_COMMENTED,
                Topics.POST_REPOSTED,
                Topics.COMMENT_LIKED,
                Topics.COMMENT_UNLIKED,
                Topics.USER_FOLLOWED,
                Topics.USER_UNFOLLOWED,
                Topics.USER_MENTIONED,
                Topics.USER_REGISTERED,
                Topics.VERIFICATION_APPROVED,
                Topics.VERIFICATION_REJECTED,
            ]
        ]

        result = admin.create_topics(topics_to_create)

        for topic, future in result.items():
            try:
                future.result()
                self.stdout.write(f"Created topic: {topic}")
            except Exception as e:
                self.stdout.write(f"Topic {topic}: {e}") # already exist
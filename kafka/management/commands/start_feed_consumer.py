from django.core.management.base import BaseCommand
from kafka.consumers.feed_consumer import FeedConsumer

class Command(BaseCommand):
    help = "Start the Kafka feed consumer (fan-out to Cassandra)"

    def handle(self, *args, **options):
        self.stdout.write("Starting feed consumer...")
        consumer = FeedConsumer()
        consumer.run()
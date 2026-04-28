from django.core.management.base import BaseCommand
from kafka.consumers.logging_consumer import LoggingConsumer

class Command(BaseCommand):
    help = "Start the Kafka logging consumer"

    def handle(self, *args, **options):
        self.stdout.write("Starting logging consumer...")
        consumer = LoggingConsumer()
        consumer.run()
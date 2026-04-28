from django.core.management.base import BaseCommand
from kafka.consumers.notification_consumer import NotificationConsumer


class Command(BaseCommand):
    help = "Start the Kafka notification consumer"

    def handle(self, *args, **options):
        self.stdout.write("Starting notification consumer...")
        consumer = NotificationConsumer()
        consumer.run()
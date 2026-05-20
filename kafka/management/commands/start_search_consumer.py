from django.core.management.base import BaseCommand
from kafka.consumers.search_consumer import SearchConsumer

class Command(BaseCommand):
    help = "start the kafka search consumer (indexes to ElasticSearch)"

    def handle(self, *args, **options):
        self.stdout.write("Starting search consumer...")
        consumer = SearchConsumer()
        consumer.run()
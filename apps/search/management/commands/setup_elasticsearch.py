from django.core.management.base import BaseCommand
from apps.search.documents import create_indexes

class Command(BaseCommand):
    help = "Create ElasticSearch indexes"

    def handle(self, *args, **options):
        self.stdout.write("Setting up Elasticsearch indexes...")
        create_indexes()
        self.stdout.write(self.style.SUCCESS(
            "Elasticsearch indexes created successfully."
        ))
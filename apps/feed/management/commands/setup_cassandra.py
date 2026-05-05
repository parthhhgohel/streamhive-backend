from django.core.management.base import BaseCommand
from apps.feed.cassandra_models import create_tables

class Command(BaseCommand):
    help = "Create Cassandra keyspace and tables"

    def handle(self, *args, **options):
        self.stdout.write("Setting up Cassandra tables...")
        create_tables()
        self.stdout.write(self.style.SUCCESS("Cassandra tables created successfully."))
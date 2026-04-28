import os
from celery import Celery

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    os.environ.get("DJANGO_SETTINGS_MODULE", "backend.settings.development")
)

app = Celery("streamhive")
app.config_from_object(os.environ["DJANGO_SETTINGS_MODULE"], namespace="CELERY")
app.autodiscover_tasks()
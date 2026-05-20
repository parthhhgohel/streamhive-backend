import logging
from elasticsearch import Elasticsearch
from django.conf import settings

logger = logging.getLogger(__name__)

class ElasticsearchClient:
    """
    Singleton Elasticsearch client.
    One client instance shared across the whole app.
    """
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_client(self):
        if self._client is None:
            try:
                self._client = Elasticsearch(
                    settings.ELASTICSEARCH_URL,
                    retry_on_timeout=True,
                    max_retries=3,
                )
                logger.info("Elasticsearch connected successfully")
            except Exception as e:
                logger.error(f"Elasticsearch connection failed: {e}")
                raise
        return self._client

    def is_healthy(self):
        try:
            if not settings.ELASTICSEARCH_URL:
                return False # skip ES entirely, use fallback -> FOR PRODUCTION ONLY BECAUSE OF FREE TIER ON RENDER
            client = self.get_client()
            return client.ping()
        except Exception:
            return False
        
es_client = ElasticsearchClient()
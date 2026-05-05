import logging
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.policies import DCAwareRoundRobinPolicy
from django.conf import settings

logger = logging.getLogger(__name__)

class CassandraClient:
    """
    Singleton Cassandra client.
    One session shared across the whole app.
    """

    _instance = None
    _session = None
    _cluster = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_session(self):
        if self._session is None:
            try:
                self._cluster = Cluster(
                    contact_points=settings.CASSANDRA_HOSTS,
                    port=settings.CASSANDRA_PORT,
                    load_balancing_policy=DCAwareRoundRobinPolicy(local_dc="datacenter1"),
                    protocol_version=4,
                )
                self._session = self._cluster.connect()
                self._setup_keyspace(),
                self._session.set_keyspace(settings.CASSANDRA_KEYSPACE)
                logger.info("Cassandra connected successfully")
            except Exception as e:
                logger.error(f"Cassandra connection failed: {e}")
                raise
            return self._session
    
    def _setup_keyspace(self):
        """
        Create keyspace if it doesn't exist.
        SimpleStrategy is fine for single node dev.
        NetworkTopologyStrategy for production.
        """
        self._session.execute(f"""
            CREATE KEYSPACE IF NOT EXISTS {settings.CASSANDRA_KEYSPACE}
            WITH replication = {{
                'class': 'SimpleStrategy',
                'replication_factor': 1
                }}
        """)

    def close(self):
        if self._cluster:
            self._cluster.shutdown()

cassandra_client = CassandraClient()
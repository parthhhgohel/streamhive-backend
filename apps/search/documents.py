"""
Elasticsearch index mappings.

Why explicit mappings:
- Control exactly how fields are analyzed and searched
- text field = full-text search (analyzed, tokenized)
- keyword field = exact match (not analyzed)
- We use both on username/display_name:
  username.text for full-text, username.keyword for exact match
"""

from django.conf import settings
from .es_client import es_client
import logging

logger = logging.getLogger(__name__)

POSTS_INDEX = settings.ELASTICSEARCH_POSTS_INDEX
USERS_INDEX = settings.ELASTICSEARCH_USERS_INDEX

POSTS_MAPPING = {
    "mappings": {
        "properties": {
            "post_id": {"type": "keyword"},
            "author_id": {"type": "keyword"},
            "author_username": {
                "type": "text",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "author_display_name": {"type": "text"},
            "content":{
                "type": "text",
                "analyzer": "standard",
                "term_vector": "with_positions_offsets"
            },
            "hashtags": {
                "type": "keyword",
                "normalizer": "lowercase_normalizer"
            },
            "like_count": {"type": "integer"},
            "comment_count": {"type": "integer"},
            "is_repost": {"type": "boolean"},
            "media_url": {"type": "keyword"},
            "created_at": {"type": "date"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0, # 0 for single node dev
        # claude given
        # "analysis": {
        #     "analyzer": {
        #         "standard": {
        #             "type": "standard"
        #         }
        #     }
        # }

        # chatgpt given
        "analysis": {
            "normalizer": {
                "lowercase_normalizer": {
                    "type": "custom",
                    "filter": ["lowercase"]
                }
            },
            "analyzer": {
                "standard": {
                    "type": "standard"
                }
            }
        }
    }
}

USERS_MAPPING = {
    "mappings": {
        "properties": {
            "user_id": {"type": "keyword"},
            "username": {
                "type": "text",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "display_name": {
                "type": "text",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "bio": {"type": "text"},
            "is_verified": {"type": "boolean"},
            "is_private": {"type": "boolean"},
            "followers_count": {"type": "integer"},
            "created_at": {"type": "date"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    }
}

def create_indexes():
    """
    Create ES indexes if they don't exist.
    Called from setup management command.
    """
    client = es_client.get_client()

    if not client.indices.exists(index=POSTS_INDEX):
        client.indices.create(index=POSTS_INDEX, mappings=POSTS_MAPPING["mappings"], settings=POSTS_MAPPING["settings"])
        logger.info(f"Created index: {POSTS_INDEX}")
    else:
        logger.info(f"Index already exists: {POSTS_INDEX}")

    if not client.indices.exists(index=USERS_INDEX):
        client.indices.create(index=USERS_INDEX, mappings=USERS_MAPPING["mappings"], settings=USERS_MAPPING["settings"])
        logger.info(f"Created index: {USERS_INDEX}")
    else:
        logger.info(f"Index already exists: {USERS_INDEX}")


def index_post(post_data: dict):
    """
    Index a single post into Elasticsearch.
    """
    client = es_client.get_client()
    client.index(
        index=POSTS_INDEX,
        id=post_data["post_id"],
        document=post_data,
    )

def index_user(user_data: dict):
    """
    Index a single user into Elasticsearch.
    """

    client = es_client.get_client()
    client.index(
        index=USERS_INDEX,
        id=user_data["user_id"],
        document=user_data,
    )


def delete_post(post_id: str):
    """
    Remove a post from the index when deleted.
    """

    client = es_client.get_client()

    try:
        client.delete(index=POSTS_INDEX, id=post_id)
    except Exception as e:
        logger.error(f"Failed to delete post from ES: {post_id} - {e}")
    
def update_post_counts(post_id: str, like_count: int, comment_count: int):
    """
    Update like/comment counts in ES index when they change.
    Called from signals.
    """
    client = es_client.get_client()
    try:
        client.update(
            index=POSTS_INDEX,
            id=post_id,
            doc={"like_count": like_count, "comment_count": comment_count}
        )
    except Exception as e:
        logger.error(f"Failed to update post counts in ES: {e}")
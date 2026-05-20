import logging
from .base import BaseConsumer
from kafka.topics import Topics

logger = logging.getLogger(__name__)

class SearchConsumer(BaseConsumer):
    """
    Listens to post.created and user.registered events.
    Indexes data into ElasticSearch for full-text search.
    """

    topic = [
        Topics.POST_CREATED,
        Topics.USER_REGISTERED,
    ]

    group_id = "search-consumer-group"

    def process_event(self, event: dict):
        topic = event.get("_meta", {}).get("topic")

        if topic == Topics.POST_CREATED:
            self._handle_post_created(event)
        elif topic == Topics.USER_REGISTERED:
            self._handle_user_registered(event)

    def _handle_post_created(self, event: dict):
        from apps.search.documents import index_post

        post_id = event.get("post_id")
        author_id = event.get("author_id")
        content = event.get("content")

        if not all([post_id, author_id, content]):
            logger.warning(f"Missing field in post.created event: {event}")
            return
        
        try:
            # fetch full author details from DB
            from apps.users.models import User
            author = User.objects.get(id=author_id)

            post_data = {
                "post_id": post_id,
                "author_id": author_id,
                "author_username": author.username,
                "author_display_name": author.display_name,
                "content": content,
                "hashtags": event.get("hashtags", []),
                "like_count": 0,
                "comment_count": 0,
                "is_repost": event.get("is_repost", False),
                "media_url": event.get("media_url"),
                "created_at": event.get("_meta", {}).get("timestamp"),
            }
            index_post(post_data)
            logger.info(f"Indexed post: {post_id}")

        except Exception as e:
            logger.error(f"Failed to index post {post_id}: {e}")

    def _handle_user_registered(self, event: dict):
        from apps.search.documents import index_user

        user_id = event.get("user_id")
        username = event.get("username")

        if not user_id or not username:
            logger.warning(f"Missing fields in user.registered event: {event}")
            return
        
        try:
            user_data = {
                "user_id": user_id,
                "username": username,
                "display_name": event.get("display_name", ""),
                "bio": event.get("bio", ""),
                "is_verified": event.get("is_verified", False),
                "is_private": False,
                "followers_count": 0,
                "created_at": event.get("_meta", {}).get("timestamp")
            }

            index_user(user_data)
            logger.info(f"Indexed user: {username}")

        except Exception as e:
            logger.error(f"Failed to index user {username}: {e}")
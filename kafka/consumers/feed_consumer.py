import logging
from uuid import UUID
from datetime import datetime
from .base import BaseConsumer
from kafka.topics import Topics

logger = logging.getLogger(__name__)

class FeedConsumer(BaseConsumer):
    """
    Listens to post.created events.
    For every new post:
    1. Writes to author's user_posts table in Cassandra
    2. Fetches all followers of the author
    3. Writes the post into each follower's user_feed in Cassandra

    This is called "fan-out on write" — expensive on write,
    but reads become O(1) regardless of follower count.
    """

    topic = Topics.POST_CREATED
    group_id = "feed-consumer-group"

    def process_event(self, event: dict):
        from apps.feed.cassandra_models import UserFeedModel, UserPostsModel
        from apps.users.models import Follow

        post_id = event.get("post_id")
        author_id = event.get("author_id")
        content = event.get("content")
        media_url = event.get("media_url")
        is_repost = event.get("is_repost", False)
        author_username = event.get("author_username", "")
        created_at_str = event.get("_meta", {}).get("timestamp")

        if not all([post_id, author_id, content]):
            logger.warning(f"Missing fields in post.created event: {event}")
            return

        try:
            created_at = datetime.fromisoformat(created_at_str)
        except Exception:
            created_at = datetime.utcnow()

        post_data = {
            "post_id": UUID(post_id),
            "author_id": UUID(author_id),
            "author_username": author_username,
            "content": content,
            "media_url": media_url,
            "is_repost": is_repost,
            "created_at": created_at,
            "like_count": 0,
            "comment_count": 0,
            "repost_count": 0,
        }

        # 1. write to user_posts
        try:
            UserPostsModel.insert(post_data)
            logger.info(f"Inserted into user_posts: post={post_id}")
        except Exception as e:
            logger.error(f"Failed to insert user_posts: {e}")

        # 2. fan-out to all followers
        try:
            follower_ids = Follow.objects.filter(
                following_id=author_id
            ).values_list("follower_id", flat=True)

            for follower_id in follower_ids:
                feed_data = {**post_data, "user_id": follower_id}
                UserFeedModel.insert(follower_id, feed_data)

            logger.info(
                f"Fan-out complete: post={post_id} "
                f"delivered to {len(follower_ids)} followers"
            )
        except Exception as e:
            logger.error(f"Fan-out failed: post={post_id} error={e}")
"""
Bulk reindex command — indexes ALL existing posts and users.
Run this once after setup to populate ES with existing data.
After this, new data flows through Kafka consumer automatically.
"""
from django.core.management.base import BaseCommand
from apps.search.documents import index_post, index_user
from apps.posts.models import Post
from apps.users.models import User
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Bulk reindex all existing posts and users into Elasticsearch"

    def handle(self, *args, **options):
        self.stdout.write("Reindexing posts...")
        self._reindex_posts()
        
        self.stdout.write("Reindexing users...")
        self._reindex_users()

        self.stdout.write(self.style.SUCCESS("Reindex complete."))

    def _reindex_posts(self):
        posts = Post.objects.select_related("author").prefetch_related("hashtags").filter(parent=None)

        count = 0

        for post in posts.iterator():
            try:
                index_post({
                    "post_id": str(post.id),
                    "author_id": str(post.author_id),
                    "author_username": post.author.username,
                    "author_display_name": post.author.display_name,
                    "content": post.content,
                    "hashtags": [h.name for h in post.hashtags.all()],
                    "like_count": post.like_count,
                    "comment_count": post.comment_count,
                    "is_repost": post.is_repost,
                    "media_url": post.media.url if post.media else None,
                    "created_at": post.created_at.isoformat(),
                })
                count += 1
            except Exception as e:
                logger.error(f"Failed to index post {post.id}: {e}")
        
        self.stdout.write(f"Indexed {count} posts.")
    
    def _reindex_users(self):
        users = User.objects.filter(is_active=True)
        print(users, "users listsssssssssss")

        count = 0
        for user in users.iterator():
            try:
                index_user({
                    "user_id": str(user.id),
                    "username": user.username,
                    "display_name": user.display_name or "",
                    "bio": user.bio or "",
                    "is_verified": user.is_verified,
                    "is_private": user.is_private,
                    "followers_count": user.follower_set.count(),
                    "created_at": user.created_at.isoformat(),
                })
                count += 1
            except Exception as e:
                logger.error(f"Failed to index user {user.id}: {e}")

        self.stdout.write(f"Indexed {count} users.")
import logging
import base64
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.feed.cassandra_models import UserFeedModel, UserPostsModel
from apps.users.models import User, Follow

logger = logging.getLogger(__name__)

class HomeTimelineFeedView(APIView):
    """
    GET /feed/
    Reads from Cassandra user_feed table.
    Falls back to PostgreSQL if Cassandra fails.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = int(request.query_params.get("limit", 20))
        paging_state_b64 = request.query_params.get("cursor")

        paging_state = None
        if paging_state_b64:
            try:
                paging_state = base64.b64decode(paging_state_b64)
            except Exception:
                pass

        try:
            result = UserFeedModel.get_feed(
                user_id=request.user.id,
                limit=limit,
                paging_state=paging_state
            )

            rows = list(result)

            # encode next page cursor
            next_cursor = None

            if result.paging_state:
                next_cursor = base64.b64encode(result.paging_state).decode("utf-8")
            
            feed_items = [self._serialize_row(row) for row in rows]

            return Response({
                "results": feed_items,
                "next_cursor": next_cursor,
                "count": len(feed_items),
            })
        
        except Exception as e:
            logger.error(f"Cassandra feed failed, falling back to PostgreSQL: {e}")
            return self._fallback_feed(request, limit)

    def _serialize_row(self, row):
        return {
            "post_id": str(row.post_id),
            "author_id": str(row.author_id),
            "author_username": row.author_username,
            "content": row.content,
            "media_url": row.media_url,
            "like_count": row.like_count,
            "comment_count": row.comment_count,
            "repost_count": row.repost_count,
            "is_repost": row.is_repost,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _fallback_feed(self, request, limit):
        """
        PostgreSQL fallback - same as Phase 1 feed.
        Used when Cassandra is unavailable.
        """
        from apps.posts.models import Post
        from apps.posts.serializers import PostSerializer

        following_ids = request.user.following_set.values_list(
            'following_id', flat=True
        )

        posts = Post.objects.filter(
            author_id__in=following_ids,
            parent=None
        ).select_related("author").prefetch_related("hashtags")[:limit]

        serializer = PostSerializer(
            posts,
            many=True,
            context={"request": request}
        )

        return Response({
            "results": serializer.data,
            "next_cursor": None,
            "count": len(serializer.data),
            "fallback": True,
        })

class UserTimelineFeedView(APIView):
    """
    GET /feed/user/<username>/
    Reads from Cassandra user_posts table.
    Used for profile page timeline.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, username):
        from apps.users.models import User
        from django.shortcuts import get_object_or_404

        user = get_object_or_404(User, username=username, is_active=True)

        if user.is_private:
            if not request.user.is_authenticated:
                return Response({"detail": "This account is private."}, status=403)
            if request.user != user and not Follow.objects.filter(follower=request.user, following=user).exists():
                return Response({"detail": "This account is private."}, status=403)

        limit = int(request.query_params.get("limit", 20))
        paging_state_b64 = request.query_params.get("cursor")

        paging_state = None
        if paging_state_b64:
            try:
                paging_state = base64.b64decode(paging_state_b64)
            except Exception:
                pass

        try:
            result = UserPostsModel.get_user_posts(
                author_id=user.id,
                limit=limit,
                paging_state=paging_state,
            )

            rows = list(result)

            next_cursor = None
            if result.paging_state:
                next_cursor = base64.b64encode(
                    result.paging_state
                ).decode("utf-8")
            
            return Response({
                "results": [self._serialize_row(row) for row in rows],
                "next_cursor": next_cursor,
                "count": len(rows),
            })

        except Exception as e:
            logger.error(f"Cassandra user_posts failed: {e}")
            return self._fallback_user_posts(request, user, limit)

    def _serialize_row(self, row):
        return {
            "post_id": str(row.post_id),
            "author_id": str(row.author_id),
            "content": row.content,
            "media_url": row.media_url,
            "like_count": row.like_count,
            "comment_count": row.comment_count,
            "repost_count": row.repost_count,
            "is_repost": row.is_repost,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _fallback_user_posts(self, request, user, limit):
        from apps.posts.models import Post
        from apps.posts.serializers import PostSerializer

        posts = Post.objects.filter(
            author=user,
            parent=None
        ).select_related("author")[:limit]

        serializer = PostSerializer(
            posts,
            many=True,
            context={"request": request}
        )

        return Response({
            "results": serializer.data,
            "next_cursor": None,
            "count": len(serializer.data),
            "fallback": True,
        })
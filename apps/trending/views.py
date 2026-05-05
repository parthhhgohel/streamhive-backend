from rest_framework.decorators import permission_classes
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.core.cache import cache
from django_redis import get_redis_connection

logger = logging.getLogger(__name__)

TRENDING_KEY = "trending:hashtags"
TRENDING_POSTS_KEY = "trending:posts"

class TrendingHashtagsView(APIView):
    """
    GET /trending/hashtags/
    Return top 10 trending hashtags from redis sorted set.
    Score = number of times used/liked 
    """

    permission_classes = [AllowAny]

    def get(self, request):
        try:
            redis_conn = get_redis_connection("default")
            # ZREVRANGE returns highest score first
            trending = redis_conn.zrevrange(
                TRENDING_KEY, 0, 9, withscores=True
            )

            results = [
                {
                    "hashtag": tag.decode("utf-8") if isinstance(tag, bytes) else tag,
                    "score": int(score),
                }
                for tag, score in trending
            ]

            return Response({"results": results})

        except Exception as e:
            logger.error(f"Trending hashtags failed: {e}")
            return Response({"results": []})
    

class TrendingPostsView(APIView):
    """
    GET /trending/posts/
    Return top 10 most liked posts in last 24h
    """

    permission_classes = [AllowAny]

    def get(self, request):
        try:
            redis_conn = get_redis_connection("default")
            trending = redis_conn.zrevrange(
                TRENDING_POSTS_KEY, 0, 9, withscore=True
            )

            if not trending:
                return Response({"results": []})

            post_ids = [
                pid.decode("utf-8") if isinstance(pid, bytes) else pid for pid, score in trending
            ]

            from apps.posts.models import Post
            from apps.posts.serializers import PostSerializer

            posts = Post.objects.filter(id__in=post_ids).select_related("author").prefetch_related("hashtags")

            serializer = PostSerializer(
                posts,
                many=True,
                context={"requests": request}
            )

            return Response({"results": serializer.data})

        except Exception as e:
            logger.error(f"Trending posts failed: {e}")
            return Response({"results": []})
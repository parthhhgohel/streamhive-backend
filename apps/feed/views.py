from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from apps.posts.models import Post
from apps.posts.serializers import PostSerializer
from core.pagination import FeedCursorPagination


class HomeTimelineFeedView(generics.ListAPIView):
    # GET /feed/ - Returns posts from users the authenticated user follows.
    # Phase 1: simple DB query - will be replaced with Cassandra in Phase 4
    serializer_class = PostSerializer
    pagination_class = FeedCursorPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        following_ids = self.request.user.following_set.values_list("following_id", flat=True)

        return Post.objects.filter(author_id__in=following_ids).select_related("author").prefetch_related("hashtags").order_by("-created_at")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context
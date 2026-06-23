from kafka.topics import Topics
from kafka.producer import kafka_producer
from rest_framework.decorators import permission_classes
from django.shortcuts import render
from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from rest_framework.views import APIView
from django.db.models import F

from .models import Post, Like, SavedPost
from .serializers import PostSerializer, PostCreateSerializer
from core.permissions import IsOwnerOrReadOnly
from core.pagination import FeedCursorPagination

class PostListCreateView(generics.ListCreateAPIView):
    # GET  /posts/       - list all posts (public timeline)
    # POST /posts/       - create a post

    pagination_class = FeedCursorPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filter_fields = ["author__username", "hashtags__name"]
    search_fields = ["content", "author__username"]
    ordering_fields = ["created_at", "like_count"]

    def get_queryset(self):
        return Post.objects.select_related("author").prefetch_related("hashtags").filter(parent=None)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PostCreateSerializer
        return PostSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class PostDetailView(generics.RetrieveUpdateDestroyAPIView):
    # GET    /posts/<id>/  - get single post
    # PUT    /posts/<id>/  - edit post (owner only)
    # DELETE /posts/<id>/  - delete post (owner only)
    queryset = Post.objects.select_related("author").prefetch_related("hashtags")
    permission_classes = [IsOwnerOrReadOnly, IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return PostCreateSerializer
        return PostSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class PostRepliesView(generics.ListAPIView):
    # GET /posts/<id>/replies/  - get all replies to a post
    serializer_class = PostSerializer
    pagination_class = FeedCursorPagination
    permission_classes = [AllowAny]

    def get_queryset(self):
        post = get_object_or_404(Post, pk=self.kwargs["pk"])
        return Post.objects.filter(parent=post).select_related("author")
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class LikeToggleView(APIView):
    # POST   /posts/<id>/like/  - like a post
    # DELETE /posts/<id>/like/  - unlike a post
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        like, created = Like.objects.get_or_create(user=request.user, post=post)

        if not created:
            return Response({"detail": "You already liked this post."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"detail": "Post liked.", "like_count": post.like_count + 1},
            status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        deleted, _ = Like.objects.filter(user=request.user, post=post).delete()

        if not deleted:
            return Response({"detail": "You have not liked this post."})

        return Response(
            {"detail": "Post unliked.", "like_count": post.like_count - 1},
            status=status.HTTP_200_OK)


class UserPostsView(generics.ListAPIView):
    # GET /users/<username>/posts/  - get all posts by a specific user
    serializer_class = PostSerializer
    pagination_class = FeedCursorPagination
    permission_classes = [AllowAny]

    def get_queryset(self):
        from apps.users.models import User, Follow
        user = get_object_or_404(User, username=self.kwargs["username"], is_active=True)

        if user.is_private:
            request = self.request

            if not request.user.is_authenticated:
                return Post.objects.none()
            if request.user != user and not Follow.objects.filter(follower=request.user, following=user).exists():
                return Post.objects.none()
        
        return Post.objects.filter(author=user).select_related("author").prefetch_related("hashtags")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def list(self, request, *args, **kwargs):
        from apps.users.models import User, Follow
        user = get_object_or_404(User, username=self.kwargs["username"], is_active=True)

        if user.is_private and user != request.user:
            if not request.user.is_authenticated or not Follow.objects.filter(follower=request.user, following=user).exists():
                return Response(
                    {"detail": "This account is private."},
                    status=status.HTTP_403_FORBIDDEN
                )

        return super().list(request, *args, **kwargs)


class RepostView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, req, pk):
        original_post = get_object_or_404(Post, pk=pk)

        if original_post.is_repost:
            original_post = original_post.parent

        already_repost = Post.objects.filter(
            author=req.user,
            parent=original_post,
            is_repost=True
        ).exists()

        if already_repost:
            return Response(
                {"detail": "You have already reposted this."},
                status=status.HTTP_400_BAD_REQUEST
            )

        repost = Post.objects.create(
            author=req.user,
            content=original_post.content,
            parent=original_post,
            is_repost=True
        )

        Post.objects.filter(pk=original_post.pk).update(
            repost_count=F("repost_count") + 1
        )

        kafka_producer.publish(
            topic=Topics.POST_REPOSTED,
            payload={
                "post_id": str(original_post.id),
                "post_author_id": str(original_post.author_id),
                "user_id": str(req.user.id),
                "repost_id": str(repost.id)
            },
            key=str(original_post.id)
        )
        
        return Response(PostSerializer(repost, context={"request": req}).data, status=status.HTTP_201_CREATED)

    def delete(self, req, pk):
        original_post = get_object_or_404(Post, pk=pk)

        if original_post.is_repost:
            original_post = original_post.parent

        repost = Post.objects.filter(
            author=req.user,
            parent=original_post,
            is_repost=True
        ).first()

        if not repost:
            return Response({"detail": "You have not reposted this."}, status=status.HTTP_400_BAD_REQUEST)

        repost.delete()

        Post.objects.filter(pk=original_post.pk).update(
            repost_count=F("repost_count") - 1
        )

        return Response({"detail": "Repost removed."}, status=status.HTTP_200_OK)


class SavedPostView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        _, created = SavedPost.objects.get_or_create(user=request.user, post=post)

        if not created:
            return Response({"detail": "Post already saved."}, status=status.HTTP_400_BAD_REQUEST)

        Post.objects.filter(pk=pk).update(saved_count=F("saved_count") + 1)
        return Response({"detail": "Post saved."}, status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        deleted, _ = SavedPost.objects.filter(user=request.user, post=post).delete()

        if not deleted:
            return Response({"detail": "Post not in saved list."},status=status.HTTP_400_BAD_REQUEST)

        Post.objects.filter(pk=pk).update(saved_count=F("saved_count") - 1)
        return Response({"detail": "Post unsaved."},status=status.HTTP_200_OK)


class SavedPostListView(generics.ListAPIView):
    serializer_class = PostSerializer
    pagination_class = FeedCursorPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Post.objects.filter(
            saves__user=self.request.user
        ).select_related("author").prefetch_related("hashtags").order_by("-saves__created_at")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context
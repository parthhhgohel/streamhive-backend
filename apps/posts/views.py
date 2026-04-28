from django.shortcuts import render
from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from rest_framework.views import APIView

from .models import Post, Like
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
        from apps.users.models import User
        user = get_object_or_404(User, username=self.kwargs["username"])
        return Post.objects.filter(author=user, parent=None).select_related("author").prefetch_related("hashtags")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context
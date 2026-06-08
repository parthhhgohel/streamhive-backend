from rest_framework import generics, status
from rest_framework.response import Response
from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from .models import Comment, CommentLike
from .serializers import CommentSerializer, CommentCreateSerializer
from apps.posts.models import Post
from core.permissions import IsOwnerOrReadOnly, IsCommentOwnerOrPostOwnerOrReadOnly
from core.pagination import StandardResultsPagination


class CommentListCreateView(generics.ListCreateAPIView):
    # GET  /comments/?post=<post_id>  - list comments for a post
    # POST /comments/                 - create a comment
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        post_id = self.request.query_params.get("post")

        qs = Comment.objects.select_related("author", "post").filter(parent=None)

        if post_id:
            qs = qs.filter(post_id=post_id)

        return qs

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CommentCreateSerializer
        return CommentSerializer
    
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    # GET    /comments/<id>/  - get a comment
    # PUT    /comments/<id>/  - edit comment (owner only)
    # DELETE /comments/<id>/  - delete comment (owner only)
    queryset = Comment.objects.select_related("author", "post")
    permission_classes = [IsAuthenticatedOrReadOnly, IsCommentOwnerOrPostOwnerOrReadOnly]

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return CommentCreateSerializer
        return CommentSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class CommentRepliesView(generics.ListAPIView):
    # GET /comments/<id>/replies/  - get replies to a comment
    serializer_class = CommentSerializer
    pagination_class = StandardResultsPagination
    permission_classes = [AllowAny]

    def get_queryset(self):
        comment = get_object_or_404(Comment, pk=self.kwargs["pk"])
        return Comment.objects.filter(
            parent=comment
        ).select_related("author")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class CommentLikeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        like, created = CommentLike.objects.get_or_create(
            user=request.user,
            comment=comment
        )

        if not created:
            return Response(
                {"detail": "You have already liked this comment."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"detail": "Comment liked successfully."},
            status=status.HTTP_201_CREATED
        )

    def delete(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        user = request.user

        like = CommentLike.objects.filter(user=user, comment=comment).first()

        if not like:
            return Response(
                {"detail": "You have not liked this comment."},
                status=status.HTTP_400_BAD_REQUEST
            )

        like.delete()

        return Response(
            {"detail": "Comment unliked successfully."},
            status=status.HTTP_200_OK
        )
from django.urls import path
from .views import (PostListCreateView, PostDetailView, PostRepliesView, LikeToggleView, UserPostsView)

urlpatterns = [
    path("", PostListCreateView.as_view(), name="post_list_create"),
    path("<uuid:pk>/", PostDetailView.as_view(), name="post_detail"),
    path("<uuid:pk>/replies/", PostRepliesView.as_view(), name="post_replies"),
    path("<uuid:pk>/like/", LikeToggleView.as_view(), name="post_like"),
    path("user/<str:username>/", UserPostsView.as_view(), name="user_posts")
]
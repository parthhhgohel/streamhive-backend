from django.urls import path
from .views import (PostListCreateView, PostDetailView, PostRepliesView, LikeToggleView, UserPostsView, RepostView, SavedPostView, SavedPostListView)

urlpatterns = [
    path("", PostListCreateView.as_view(), name="post_list_create"),
    path("saved/", SavedPostListView.as_view(), name="saved_post_list"),
    path("<uuid:pk>/", PostDetailView.as_view(), name="post_detail"),
    path("<uuid:pk>/replies/", PostRepliesView.as_view(), name="post_replies"),
    path("<uuid:pk>/like/", LikeToggleView.as_view(), name="post_like"),
    path("<uuid:pk>/repost/", RepostView.as_view(), name="post_repost"),
    path("<uuid:pk>/save/", SavedPostView.as_view(), name="post_save"),
    path("user/<str:username>/", UserPostsView.as_view(), name="user_posts")
]
from django.urls import path
from .views import (PostListCreateView, PostDetailView, PostPinView, PostRepliesView, LikeToggleView, UserPostsView, RepostView, BookmarkListView, BookmarkView, PostSaveOptionsView, CollectionListCreateView, CollectionDetailView, CollectionPostsView, CollectionPostView)

urlpatterns = [
    path("", PostListCreateView.as_view(), name="post_list_create"),
    path("saved/", BookmarkListView.as_view(), name="saved_post_list"),
    path("<uuid:pk>/", PostDetailView.as_view(), name="post_detail"),
    path("<uuid:pk>/pin/", PostPinView.as_view(), name="post_pin"),
    path("<uuid:pk>/replies/", PostRepliesView.as_view(), name="post_replies"),
    path("<uuid:pk>/like/", LikeToggleView.as_view(), name="post_like"),
    path("<uuid:pk>/repost/", RepostView.as_view(), name="post_repost"),
    path("<uuid:pk>/save/", BookmarkView.as_view(), name="post_save"),
    path("<uuid:pk>/save-options/", PostSaveOptionsView.as_view(), name="post_save_options"),
    path("user/<str:username>/", UserPostsView.as_view(), name="user_posts"),
    path("collections/", CollectionListCreateView.as_view(), name="collection_list_create"),
    path("collections/<uuid:pk>/", CollectionDetailView.as_view(), name="collection_detail"),
    path("collections/<uuid:pk>/posts/", CollectionPostsView.as_view(), name="collection_posts"),
    path("collections/<uuid:pk>/posts/<uuid:post_id>/", CollectionPostView.as_view(), name="collection_post"),
]
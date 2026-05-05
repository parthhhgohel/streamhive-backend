from django.urls import path
from .views import TrendingHashtagsView, TrendingPostsView

urlpatterns = [
    path("hashtags/", TrendingHashtagsView.as_view(), name="trending_hashtags"),
    path("posts/", TrendingPostsView.as_view(), name="trending_posts")
]
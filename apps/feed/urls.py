from django.urls import path
from .views import HomeTimelineFeedView

urlpatterns = [
    path("", HomeTimelineFeedView.as_view(), name="home_feed"),
]
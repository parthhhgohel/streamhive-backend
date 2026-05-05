from django.urls import path
from .views import HomeTimelineFeedView, UserTimelineFeedView

urlpatterns = [
    path("", HomeTimelineFeedView.as_view(), name="home_feed"),
    path("user/<str:username>/", UserTimelineFeedView.as_view(), name="user_feed"),
]
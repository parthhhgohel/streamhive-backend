from django.urls import path
from ..views.user_views import FollowerListView, FollowingListView, MeView, UserProfileView, FollowView

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("<str:username>/", UserProfileView.as_view(), name="user_profile"),
    path("<str:username>/follow/", FollowView.as_view(), name="follow"),
    path("<str:username>/followers/", FollowerListView.as_view(), name="followers"),
    path("<str:username>/following/", FollowingListView.as_view(), name="following")
]
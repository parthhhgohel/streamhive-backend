from django.urls import path
from ..views.user_views import FollowerListView, FollowingListView, MeView, UserProfileView, FollowView, FollowRequestView, FollowSuggestionsView, BlockView, BlockListView
from ..views.verification_views import VerificationRequestView, VerificationRequestStatusView

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("verification-request/", VerificationRequestView.as_view(), name="verification_request"),
    path("verification-request/status/", VerificationRequestStatusView.as_view(), name="verification_status"),
    path("follow-requests/", FollowRequestView.as_view(), name="follow_requests"),
    path("suggestions/", FollowSuggestionsView.as_view(), name="follow_suggestions"),
    path("follow-requests/<uuid:pk>/", FollowRequestView.as_view(), name="follow_request_action"),
    path("blocked/", BlockListView.as_view(), name="blocked_list"),
    path("<str:username>/", UserProfileView.as_view(), name="user_profile"),
    path("<str:username>/follow/", FollowView.as_view(), name="follow"),
    path("<str:username>/followers/", FollowerListView.as_view(), name="followers"),
    path("<str:username>/following/", FollowingListView.as_view(), name="following"),
    path("<str:username>/block/", BlockView.as_view(), name="block"),
]
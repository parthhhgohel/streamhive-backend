from django.urls import path
from .views import CommentListCreateView, CommentDetailView, CommentRepliesView

urlpatterns = [
    path("", CommentListCreateView.as_view(), name="comment_list_create"),
    path("<uuid:pk>/", CommentDetailView.as_view(), name="comment_detail"),
    path("<uuid:pk>/replies/", CommentRepliesView.as_view(), name="comment_replies"),
]
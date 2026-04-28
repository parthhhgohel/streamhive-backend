from django.urls import path
from .views import (NotificationListView, MarkAllReadView, MarkReadView, UnreadCountView)

urlpatterns = [
    path("", NotificationListView.as_view(), name="notifications"),
    path("unread-count/", UnreadCountView.as_view(), name="unread_count"),
    path("mark-all-read/", MarkAllReadView.as_view(), name="mark_all_read"),
    path("<uuid:pk>/read/", MarkReadView.as_view(), name="mark_read"),
]
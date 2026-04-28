from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Notification
from .serializers import NotificationSerializer
from core.pagination import StandardResultsPagination

class NotificationListView(generics.ListAPIView):
    # GET /notifications/ - list notifications for the authenticated user
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related("sender", "post").order_by("-created_at")


class MarkAllReadView(APIView):
    # POST /notifications/mark-all-read/

    def post(self, request):
        updated = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True)
        return Response({"detail": f"{updated} notifications marked as read."})

class MarkReadView(APIView):
    # POST /notifications/<id>/read/

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notification = generics.get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response({"detail": "Marked as read."})

class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({"unread_count": count})
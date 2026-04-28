from rest_framework import serializers
from .models import Notification
from apps.users.serializers import UserMinimalSerializer

class NotificationSerializer(serializers.ModelSerializer):
    sender = UserMinimalSerializer(read_only=True)
    post_preview = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id", "sender", "notification_type",
            "post_preview", "is_read", "created_at"
        ]

    def get_post_preview(self, obj):
        if obj.post:
            return {
                "id": str(obj.post.id),
                "content": obj.post.content[:100]
            }

        return None
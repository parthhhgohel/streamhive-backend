from rest_framework import serializers
from .models import Comment
from apps.users.serializers import UserMinimalSerializer

class CommentSerializer(serializers.ModelSerializer):
    author = UserMinimalSerializer(read_only=True)
    replies_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id", "post", "author", "parent", "content", "like_count", "replies_count", "created_at", "updated_at"
        ]

        read_only_fields = [
            "id", "author", "like_count", "created_at", "updated_at"
        ]

    def get_replies_count(self, obj):
        return obj.replies.count()


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ["post", "parent", "content"]

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Comment cannot be empty.")
        return value

    def validate(self, attrs):
        parent = attrs.get("parent")
        post = attrs.get("post")

        if parent and parent.post != post:
            raise serializers.ValidationError(
                {"parent": "parent comment does not belong to this post."}
            )
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        comment = Comment.objects.create(author=user, **validated_data)

        # if comment.post.author != user:
        #     from apps.notifications.tasks import create_notification
        #     create_notification.delay(
        #         recipient_id=str(comment.post.author_id),
        #         sender_id=str(user.id),
        #         notification_type="comment",
        #         post_id=str(comment.post_id)
        #     )

        return comment
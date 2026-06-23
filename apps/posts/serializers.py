from rest_framework import serializers
from .models import Post, Like, Hashtag, SavedPost
from apps.users.serializers import UserMinimalSerializer
from core.utils import extract_hashtags, extract_mentions
from kafka.producer import kafka_producer
from kafka.topics import Topics

class HashtagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hashtag
        fields = ["id", "name"]


class PostSerializer(serializers.ModelSerializer):
    author = UserMinimalSerializer(read_only=True)
    hashtags = HashtagSerializer(many=True, read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_reposted = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()

    # for replies - show minimal parent info
    parent = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id", "author", "content", "media",
            "parent", "is_repost",
            "like_count", "comment_count", "repost_count", "saved_count",
            "hashtags", "is_liked", "is_reposted", "is_saved",
            "created_at", "updated_at"
        ]
        read_only_fields = [
            "id", "author", "like_count",
            "comment_count", "repost_count", "created_at", "updated_at"
        ]

    def get_is_liked(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Like.objects.filter(user=request.user, post=obj).exists()
        return False

    def get_is_reposted(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            original_post = obj.parent if obj.is_repost else obj
            return Post.objects.filter(
                author=request.user,
                parent=original_post,
                is_repost=True
            ).exists()
        return False

    def get_parent(self, obj):
        if obj.parent:
            return {
                "id": str(obj.parent.id),
                "author": obj.parent.author.username,
                "content": obj.parent.content[:100],
                "repost_count": obj.parent.repost_count,
            }
        return None

    def get_is_saved(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return SavedPost.objects.filter(user=request.user, post=obj).exists()
        return False

class PostCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ["content", "media", "parent", "is_repost"]

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Post content cannot be empty.")
        return value

    def validate(self, attrs):
        # if its a repost, parent is required
        if attrs.get("is_repost") and not attrs.get("parent"):
            raise serializers.ValidationError({"parent": "Parent post is required for a repost"})
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        post = Post.objects.create(author=user, **validated_data)

        tags = extract_hashtags(post.content)

        hashtag_objs = []
        for tag_name in tags:
            hashtag, _ = Hashtag.objects.get_or_create(name=tag_name)
            hashtag_objs.append(hashtag)

        if hashtag_objs:
            post.hashtags.add(*hashtag_objs)

        mentions = extract_mentions(post.content)
        if mentions:
            kafka_producer.publish(
                topic=Topics.USER_MENTIONED,
                payload={
                    "post_id": str(post.id),
                    "user_id": str(user.id),
                    "mentions": mentions,
                },
                key=str(user.id)
            )
        
        kafka_producer.publish(
            topic=Topics.POST_CREATED,
            payload={
                "post_id": str(post.id),
                "author_id": str(post.author_id),
                "author_username": post.author.username,
                "content": post.content,
                "media_url": post.media.url if post.media else None,
                "hashtags": tags,
                "is_repost": post.is_repost,
            },
            key=str(post.author_id)
        )

        return post


class LikeSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)

    class Meta:
        model = Like
        fields = ["id", "user", "post", "created_at"]


class RepostSerializer(serializers.Serializer):
    parent = serializers.UUIDField(required=True)
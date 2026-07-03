from django.db import models
from django.conf import settings
import uuid


class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='posts'
    )

    content = models.TextField(max_length=280)
    media = models.ImageField(upload_to='posts/media', blank=True, null=True)

    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='replies',
        blank=True,
        null=True
    )

    is_repost = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    like_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    repost_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "posts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["author", "-created_at"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"Post({self.author}, {self.content[:30]})"


class Like(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes"
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "likes"
        unique_together = ("user", "post")
        indexes = [
            models.Index(fields=["post"]),
            models.Index(fields=["user"]),
        ]


class Hashtag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    posts = models.ManyToManyField(Post, related_name="hashtags", blank=True)

    class Meta:
        db_table = "hashtags"

    def __str__(self):
        return f"#{self.name}"


class Collection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="collections")
    name = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)
    posts = models.ManyToManyField(
        Post,
        through="CollectionPost",
        related_name="collections",
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "collections"
        unique_together = ("author", "name")
        indexes = [
            models.Index(fields=["author"]),
        ]


class CollectionPost(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name="items")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="collection_items")
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "collection_posts"
        unique_together = ("collection", "post")
        indexes = [
            models.Index(fields=["collection"]),
            models.Index(fields=["post"]),
        ]
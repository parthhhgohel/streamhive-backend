from django.contrib import admin
from .models import Post, Like, Hashtag


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["author", "content_preview", "like_count", "comment_count", "created_at"]
    list_filter = ["is_repost", "created_at"]
    search_fields = ["content", "author__username"]
    readonly_fields = ["like_count", "comment_count", "repost_count"]

    def content_preview(self, obj):
        return obj.content[:60]
    content_preview.short_description = "Content"


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ["user", "post", "created_at"]


@admin.register(Hashtag)
class HashtagAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
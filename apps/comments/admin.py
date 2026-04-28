from django.contrib import admin
from .models import Comment

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["author", "post", "content_preview", "created_at"]
    search_fields = ["content", "author__username"]

    def content_preview(self, obj):
        return obj.content[:60]
    content_preview.short_description = "Content"
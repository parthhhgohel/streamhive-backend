from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Follow, VerificationRequest, PasswordResetOTP

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "is_verified", "is_active", "created_at"]
    list_filter = ["username", "email"]
    ordering = ["-created_at"]

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Profile", {"fields": ("display_name", "bio", "avatar", "website")}),
        ("OAuth", {"fields": ("auth_provider", "auth_provider_id")}),    # ADD
        ("Flags", {"fields": ("is_verified", "is_private", "is_active", "is_staff")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "password1", "password2"),
        }),
    )


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ["follower", "following", "created_at"]
    search_fields = ["follower__username", "following__username"]

@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = ["user", "status", "reviewed_by", "created_at", "updated_at"]
    list_filter = ["status"]
    search_fields = ["user__username"]
    readonly_fields = ["created_at", "updated_at"]

@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ["user", "created_at", "expires_at", "attempts", "is_used"]
    list_filter = ["is_used"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["otp", "created_at", "expires_at"]
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, Follow, VerificationRequest, FollowRequest

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )

    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ["email", "username", "password", "password2", "display_name"]

    def validate_username(self, value):
        if not value.isalnum() and "_" not in value:
            raise serializers.ValidationError("Username can only contain letters, numbers, underscores.")
        return value.lower()

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"Password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        user = User.objects.create_user(**validated_data)
        return user

    
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"],
            password=attrs["password"]
        )

        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")
        attrs["user"] = user
        return attrs


class UserMinimalSerializer(serializers.ModelSerializer):
    # Used wherever we embed user info inside another serializer
    # e.g. post.author, comment.author
    # Keeps responses lean
    class Meta:
        model = User
        fields = ["id", "username", "display_name", "avatar", "is_verified"]


class UserListSerializer(UserMinimalSerializer):
    is_following = serializers.SerializerMethodField()

    class Meta(UserMinimalSerializer.Meta):
        fields = UserMinimalSerializer.Meta.fields + ["is_following"]

    def get_is_following(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Follow.objects.filter(
                follower=request.user,
                following=obj
            ).exists()
        return False


class UserProfileSerializer(serializers.ModelSerializer):
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()
    is_follow_requested = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "display_name", "bio",
            "avatar", "website", "is_verified", "is_private",
            "followers_count", "following_count", "is_following",
            "is_follow_requested", "is_admin", "created_at"
        ]
        read_only_fields = ["id", "is_verified", "created_at"]

    def get_followers_count(self, obj):
        return obj.follower_set.count()

    def get_following_count(self, obj):
        return obj.following_set.count()

    def get_is_following(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Follow.objects.filter(
                follower=request.user,
                following=obj
            ).exists()

        return False

    def get_is_admin(self, obj):
        return obj.is_staff

    def get_is_follow_requested(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from .models import FollowRequest
            return FollowRequest.objects.filter(
                sender=request.user,
                receiver=obj,
                status=FollowRequest.Status.PENDING
            ).exists()
        return False


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["display_name", "bio", "avatar", "website", "is_private"]


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True,
        validators=[validate_password]
    )
    new_password2 = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password2"]:
            raise serializers.ValidationError({"new_password": "Passwords do not match."})
        return attrs

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


# Password reset
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate_otp(self, value):
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("OTP must be 6 digits.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        validators=[validate_password]
    )
    new_password2 = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password2"]:
            raise serializers.ValidationError(
                {"new_password": "Passwords do not match."}
            )
        return attrs

class FollowSerializer(serializers.ModelSerializer):
    follower = UserMinimalSerializer(read_only=True)
    following = UserMinimalSerializer(read_only=True)

    class Meta:
        model = Follow
        fields = ["id", "follower", "following", "created_at"]


class FollowRequestSerializer(serializers.ModelSerializer):
    sender = UserMinimalSerializer(read_only=True)

    class Meta:
        model = FollowRequest
        fields = ["id", "sender", "status", "created_at"]


class VerificationRequestSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)

    class Meta:
        model = VerificationRequest
        fields = [
            "id", "user", "reason", "status",
            "admin_note", "created_at", "updated_at"
        ]
        read_only_fields = [
            "id", "user", "status",
            "admin_note", "created_at", "updated_at"
        ]


class VerificationRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationRequest
        fields = ["reason"]

    def validate_reason(self, value):
        if len(value.strip()) < 20:
            raise serializers.ValidationError(
                "Reason must be at least 20 characters."
            )
        return value


class AdminRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True)
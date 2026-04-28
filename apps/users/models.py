import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

# Create your models here.

class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, username, password, **extra_fields)

    
class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=30, unique=True)
    display_name = models.CharField(max_length=60, blank=True)
    bio = models.TextField(max_length=160, blank=True)
    avatar = models.ImageField(upload_to='avatar', blank=True, null=True)
    website = models.URLField(blank=True)
    is_verified = models.BooleanField(default=False)    # blue tick
    is_private = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["email"])
        ]

    def __str__(self):
        return f"@{self.username}"

class Follow(models.Model):
    # follower → follows → following
    # e.g. "Alice follows Bob": follower=Alice, following=Bob
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following_set')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='follower_set')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "follows"
        unique_together = ('follower', "following")
        indexes = [
            models.Index(fields=["follower"]),
            models.Index(fields=["following"])
        ]

    def __str__(self):
        return f"{self.follower} follows {self.following}"

class Block(models.Model):
    # Block user
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocking_set')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_set')
    create_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "blocks"
        unique_together = ('blocker', "blocked")
        indexes = [
            models.Index(fields=["blocker"]),
            models.Index(fields=["blocked"])
        ]

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked}"
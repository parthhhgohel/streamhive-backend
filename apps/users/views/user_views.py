from rest_framework import status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets
from django.shortcuts import get_object_or_404
from django.core.cache import cache

from ..models import User, Follow
from ..serializers import UserProfileSerializer, UpdateProfileSerializer, UserMinimalSerializer, FollowSerializer, UserListSerializer
from core.permissions import IsOwner
from core.pagination import StandardResultsPagination
from kafka.producer import kafka_producer
from kafka.topics import Topics


class UserProfileView(generics.RetrieveUpdateAPIView):
    # GET  /users/<username>/ - view any user's profile
    # PUT  /users/<username>/ - update only if it's your own profile
    lookup_field = "username"
    queryset = User.objects.filter(is_active=True)

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return UpdateProfileSerializer
        return UserProfileSerializer
    
    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH"]:
            return [IsAuthenticated(), IsOwner()]
        return [AllowAny()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def retrieve(self, request, *args, **kwargs):
        username = kwargs.get("username")
        cache_key = f"user_profile_{username}"
        cached = cache.get(cache_key)

        if cached:
            return Response(cached)

        response = super().retrieve(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=300)
        return response
    
    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        cache.delete(f"user_profile_{kwargs['username']}")
        return response


class MeView(generics.RetrieveAPIView):
    # GET /users/me/ - get the currently authenticated user's profile
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user


class FollowView(APIView):
    # POST   /users/<username>/follow/    - follow a user
    # DELETE /users/<username>/follow/    - unfollow a user
    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        target_user = get_object_or_404(User, username=username, is_active=True)

        if target_user == request.user:
            return Response({"detail": "You can't follow yourself."}, status=status.HTTP_400_BAD_REQUEST)

        follow, created = Follow.objects.get_or_create(
            follower=request.user,
            following=target_user
        )

        if not created:
            return Response({"detail": "You are already following this user."}, status=status.HTTP_400_BAD_REQUEST)

        # celery reference
        # from apps.notifications.tasks import create_notification
        # create_notification.delay(
        #     recipient_id=str(target_user.id),
        #     sender_id=str(request.user.id),
        #     notification_type="follow"
        # )
        kafka_producer.publish(
            topic=Topics.USER_FOLLOWED,
            payload={
                "follower_id": str(request.user.id),
                "following_id": str(target_user.id),
            },
            key=str(request.user.id)
        )

        cache.delete(f"user_profile_{username}")
        return Response({"detail": "Followed successfully."}, status=status.HTTP_201_CREATED)

    def delete(self, request, username):
        target_user = get_object_or_404(User, username=username, is_active=True)

        deleted, _ = Follow.objects.filter(
            follower=request.user,
            following=target_user
        ).delete()

        if not deleted:
            return Response({"detail": "You are not following this user"}, status=status.HTTP_400_BAD_REQUEST)
        
        cache.delete(f"user_profile_{username}")
        kafka_producer.publish(
            topic=Topics.USER_UNFOLLOWED,
            payload={
                "follower_id": str(request.user.id),
                "following_id": str(target_user.id),
            },
            key=str(request.user.id)
        )

        return Response({"detail": "Unfollowed successfully."})


class FollowerListView(generics.ListAPIView):
    # GET /users/<username>/followers/

    serializer_class = UserListSerializer
    pagination_class = StandardResultsPagination
    permission_classes = [AllowAny]

    def get_queryset(self):
        user = get_object_or_404(User, username=self.kwargs['username'])
        return User.objects.filter(following_set__following=user) # Alternatively: Follow.objects.filter(following=user).values_list("follower", flat=True)


class FollowingListView(generics.ListAPIView):
    # GET /users/<username>/following/
    serializer_class = UserListSerializer
    pagination_class = StandardResultsPagination
    permission_classes = [AllowAny]

    def get_queryset(self):
        user = get_object_or_404(User, username=self.kwargs["username"])
        return User.objects.filter(follower_set__follower=user) # Alternatively: Follow.objects.filter(follower=user).values_list("following", flat=True)



# Extra later implementation for me

# class SuggestUserView(generics.ListAPIView):
#     """
#     GET /users/suggest/  — get suggested users
#     """
#     permission_classes = [IsAuthenticated]
#     serializer_class = UserMinimalSerializer
#     pagination_class = StandardResultsPagination

#     def get_queryset(self):
#         user = self.request.user
#         # Users who are not the current user and are not already followed
#         suggested = User.objects.filter(
#             is_active=True,
#             is_private=False
#         ).exclude(id=user.id).exclude(
#             id__in=user.following.values_list("id", flat=True)
#         )

#         return suggested.order_by("-followers_count")[:50]
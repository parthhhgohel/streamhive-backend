from rest_framework import status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets
from django.shortcuts import get_object_or_404
from django.core.cache import cache

from ..models import User, Follow, FollowRequest
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

        if target_user.is_private:
            follow_request, created = FollowRequest.objects.get_or_create(
                sender=request.user,
                receiver=target_user,
                defaults={"status": FollowRequest.Status.PENDING}
            )

            if not created:
                if follow_request.status == FollowRequest.Status.PENDING:
                    return Response({"detail": "Follow request already sent."}, status=status.HTTP_400_BAD_REQUEST)
                elif follow_request.status == FollowRequest.Status.REJECTED:
                    # Allow re-sending after rejection
                    follow_request.status = FollowRequest.Status.PENDING
                    follow_request.save()
                    return Response({"detail": "Follow request sent."}, status=status.HTTP_201_CREATED)

            return Response({"detail": "Follow request sent."}, status=status.HTTP_201_CREATED)

        # Public account — create follow directly
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

        follow_request_deleted, _ = FollowRequest.objects.filter(
            sender=request.user,
            receiver=target_user,
            status=FollowRequest.Status.PENDING
        ).delete()

        follow_deleted, _ = Follow.objects.filter(
            follower=request.user,
            following=target_user
        ).delete()

        if not follow_deleted and not follow_request_deleted:
            return Response(
                {"detail": "You are not following this user."},
                status=status.HTTP_400_BAD_REQUEST
            )

        cache.delete(f"user_profile_{username}")

        if follow_deleted:
            kafka_producer.publish(
                topic=Topics.USER_UNFOLLOWED,
                payload={
                    "follower_id": str(request.user.id),
                    "following_id": str(target_user.id),
                },
                key=str(request.user.id)
            )

        return Response({"detail": "Unfollowed successfully."})


class FollowRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        requests = FollowRequest.objects.filter(
            receiver=request.user,
            status=FollowRequest.Status.PENDING
        ).select_related("sender")

        from ..serializers import FollowRequestSerializer
        return Response(FollowRequestSerializer(requests, many=True).data)


    def post(self, request, pk):
        action = request.data.get("action")

        follow_request = get_object_or_404(
            FollowRequest,
            pk=pk,
            receiver=request.user,
            status=FollowRequest.Status.PENDING
        )

        if action == "accept":
            follow_request.status = FollowRequest.Status.ACCEPTED
            follow_request.save()

            Follow.objects.get_or_create(
                follower=follow_request.sender,
                following=follow_request.receiver
            )

            kafka_producer.publish(
                topic=Topics.USER_FOLLOWED,
                payload={
                    "follower_id": str(follow_request.sender_id),
                    "following_id": str(follow_request.receiver_id),
                },
                key=str(follow_request.sender_id)
            )

            cache.delete(f"user_profile_{request.user.username}")
            return Response({"detail": "Follow request accepted."})

        elif action == "reject":
            follow_request.status = FollowRequest.Status.REJECTED
            follow_request.save()
            return Response({"detail": "Follow request rejected."})

        return Response({"detail": "Invalid action. Use 'accept' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)


class FollowerListView(generics.ListAPIView):
    # GET /users/<username>/followers/

    serializer_class = UserListSerializer
    pagination_class = StandardResultsPagination
    permission_classes = [AllowAny]

    def get_queryset(self):
        user = get_object_or_404(User, username=self.kwargs['username'])
        return User.objects.filter(following_set__following=user) # Alternatively: Follow.objects.filter(following=user).values_list("follower", flat=True)

    def list(self, request, *args, **kwargs):
        from apps.users.models import Follow
        user = get_object_or_404(User, username=self.kwargs["username"])

        if user.is_private and user != request.user:
            if not request.user.is_authenticated or not Follow.objects.filter(follower=request.user, following=user).exists():
                return Response(
                    {"detail": "This account is private."},
                    status=status.HTTP_403_FORBIDDEN
                )

        return super().list(request, *args, **kwargs)


class FollowingListView(generics.ListAPIView):
    # GET /users/<username>/following/
    serializer_class = UserListSerializer
    pagination_class = StandardResultsPagination
    permission_classes = [AllowAny]

    def get_queryset(self):
        user = get_object_or_404(User, username=self.kwargs["username"])
        return User.objects.filter(follower_set__follower=user) # Alternatively: Follow.objects.filter(follower=user).values_list("following", flat=True)

    def list(self, request, *args, **kwargs):
        from apps.users.models import Follow
        user = get_object_or_404(User, username=self.kwargs["username"])

        if user.is_private and user != request.user:
            if not request.user.is_authenticated or not Follow.objects.filter(follower=request.user, following=user).exists():
                return Response(
                    {"detail": "This account is private."},
                    status=status.HTTP_403_FORBIDDEN
                )

        return super().list(request, *args, **kwargs)



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
from django.db.models import Count, Q
from django.db import transaction
from rest_framework import status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets
from django.shortcuts import get_object_or_404
from django.core.cache import cache

from ..models import User, Follow, FollowRequest, Block
from apps.posts.models import Like
from apps.comments.models import Comment
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
                elif follow_request.status  in [ FollowRequest.Status.REJECTED, FollowRequest.Status.ACCEPTED ]:
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
        cache.delete(f"user_profile_{request.user.username}")
        return Response({"detail": "Followed successfully."}, status=status.HTTP_201_CREATED)

    def delete(self, request, username):
        target_user = get_object_or_404(User, username=username, is_active=True)

        follow_request_deleted, _ = FollowRequest.objects.filter(
            sender=request.user,
            receiver=target_user,
            status__in=[
                FollowRequest.Status.PENDING,
                FollowRequest.Status.ACCEPTED
            ]
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
        cache.delete(f"user_profile_{request.user.username}")

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


class FollowSuggestionsView(APIView):
    """
    GET /users/suggestions/?limit=10
    Returns suggested users to follow:
    1. Mutual-connection based (people followed by people you follow)
    2. Backfilled with popular accounts if not enough mutuals
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = int(request.query_params.get("limit", 10))
        user = request.user

        following_ids = set(
            user.following_set.values_list("following_id", flat=True)
        )
        following_ids.add(user.id)

        blocked_ids = set(
            Block.objects.filter(
                Q(blocker=user) | Q(blocked=user)
            ).values_list("blocker_id", "blocked_id")
        )

        blocked_id_set = set()
        for a, b in blocked_ids:
            blocked_id_set.add(a)
            blocked_id_set.add(b)
        blocked_id_set.discard(user.id)

        exclude_ids = following_ids | blocked_id_set

        # 1.
        mutual_candidates = (
            Follow.objects
            .filter(follower_id__in=user.following_set.values_list("following_id", flat=True))
            .exclude(following_id__in=exclude_ids)
            .values("following_id")
            .annotate(mutual_count=Count("follower_id"))
            .order_by("-mutual_count")[:limit]
        )

        suggested_ids = [row["following_id"] for row in mutual_candidates]
        
        # 2.
        if len(suggested_ids) < limit:
            remaining = limit - len(suggested_ids)
            exclude_ids_with_suggested = exclude_ids | set(suggested_ids)

            popular_users = (
                User.objects
                .filter(is_active=True)
                .exclude(id__in=exclude_ids_with_suggested)
                .annotate(followers_count=Count("follower_set"))
                .order_by("-followers_count", "-is_verified")[:remaining]
            )

            suggested_ids += [u.id for u in popular_users]

        users_by_id = User.objects.filter(id__in=suggested_ids).in_bulk()
        ordered_users = [users_by_id[uid] for uid in suggested_ids if uid in users_by_id]

        serializer = UserListSerializer(
            ordered_users, many=True, context={"request": request}
        )

        return Response({"results": serializer.data})


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


class BlockView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        target_user = User.objects.filter(username=username, is_active=True).first()

        if not target_user:
            return Response({"detail": "User does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        if request.user == target_user:
            return Response({"detail": "You can't block yourself."}, status=status.status.HTTP_400_BAD_REQUEST)

        is_blocked = Blocker.objects.filter(blocker=request.user, blocked=target_user).first()

        if is_blocked:
            return Response({"detail": "You have already blocked this user."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            blocked = Block.objects.create(blocker=request.user, blocked=target_user)

            if not blocked:
                return Response({"detail": "Failed to block user."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            Follow.objects.filter(follower=request.user, following=target_user).delete()
            Follow.objects.filter(follower=target_user, following=request.user).delete()

            FollowRequest.objects.filter(
                sender=request.user, receiver=target_user
            ).delete()
            FollowRequest.objects.filter(
                sender=target_user, receiver=request.user
            ).delete()

            Like.objects.filter(user=request.user, post__author=target_user).delete()
            Comment.objects.filter(author=request.user, post__author=target_user).delete()

        cache.delete(f"user_profile_{username}")
        cache.delete(f"user_profile_{request.user.username}")
        
        return Response({"detail": "User blocked successfully."}, status=status.HTTP_200_OK)

    def delete(self, request, username):
        target_user = User.objects.filter(username=username)

        if not target_user:
            return Response({"detail": "User does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        if request.user == target_user:
            return Response({"detail": "You can't unblock yourself."}, status=status.HTTP_403_FORBIDDEN)

        is_blocked = Block.objects.filter(blocker=request.user, blocked=target_user).first()

        if not is_blocked:
            return Response({"detail": "You have not blocked this user."}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            is_blocked.delete()

        return Response({"detail":"User unblocked successfully."}, status=status.HTTP_200_OK)


class BlockListView(generics.ListAPIView):
    """
    GET /users/blocked/  — get list of blocked users
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserMinimalSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        blocked_ids = Block.objects.filter(blocker=self.request.user).values_list("blocked_id", flat=True)
        return User.objects.filter(id__in=blocked_ids, is_active=True)


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
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..models import VerificationRequest, User
from ..serializers import (
    VerificationRequestSerializer,
    VerificationRequestCreateSerializer,
    AdminRejectSerializer,
)
from core.permissions import IsAdminUser
from core.pagination import StandardResultsPagination
from kafka.producer import kafka_producer
from kafka.topics import Topics
import logging

logger = logging.getLogger(__name__)


class VerificationRequestView(APIView):
    # POST /users/verification-request/
    # Submit or resubmit a verification request.
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.is_verified:
            return Response(
                {"detail": "Your account is already verified."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = VerificationRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        existing = VerificationRequest.objects.filter(
            user=request.user
        ).first()

        if existing:
            if existing.status == VerificationRequest.Status.PENDING:
                return Response(
                    {"detail": "You already have a pending verification request."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if existing.status == VerificationRequest.Status.APPROVED:
                return Response(
                    {"detail": "Your account is already verified."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            existing.reason = serializer.validated_data["reason"]
            existing.status = VerificationRequest.Status.PENDING
            existing.admin_note = None
            existing.reviewed_by = None
            existing.save()

            return Response(
                VerificationRequestSerializer(existing).data,
                status=status.HTTP_200_OK
            )

        verification_request = VerificationRequest.objects.create(
            user=request.user,
            reason=serializer.validated_data["reason"]
        )

        return Response(
            VerificationRequestSerializer(verification_request).data,
            status=status.HTTP_201_CREATED
        )


class VerificationRequestStatusView(APIView):
    # GET /users/verification-request/status/
    # User checks their own request status.
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            verification_request = VerificationRequest.objects.get(
                user=request.user
            )
            return Response(
                VerificationRequestSerializer(verification_request).data
            )
        except VerificationRequest.DoesNotExist:
            return Response(
                {"detail": "No verification request found."},
                status=status.HTTP_404_NOT_FOUND
            )


class AdminVerificationListView(generics.ListAPIView):
    # GET /admin/verification-requests/
    # Admin lists all verification requests.
    serializer_class = VerificationRequestSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        status_filter = self.request.query_params.get("status")
        qs = VerificationRequest.objects.select_related("user", "reviewed_by")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class AdminVerificationApproveView(APIView):
    # POST /admin/verification-requests/<id>/approve/
    # Admin approves a verification request.
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        try:
            verification_request = VerificationRequest.objects.select_related(
                "user"
            ).get(pk=pk)
        except VerificationRequest.DoesNotExist:
            return Response(
                {"detail": "Request not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if verification_request.status != VerificationRequest.Status.PENDING:
            return Response(
                {"detail": "Only pending requests can be approved."},
                status=status.HTTP_400_BAD_REQUEST
            )

        verification_request.status = VerificationRequest.Status.APPROVED
        verification_request.reviewed_by = request.user
        verification_request.save()

        User.objects.filter(pk=verification_request.user_id).update(
            is_verified=True
        )

        kafka_producer.publish(
            topic=Topics.VERIFICATION_APPROVED,
            payload={
                "user_id": str(verification_request.user_id),
                "username": verification_request.user.username,
            },
            key=str(verification_request.user_id)
        )

        logger.info(
            f"Verification approved: user={verification_request.user.username} "
            f"by admin={request.user.username}"
        )

        return Response(
            VerificationRequestSerializer(verification_request).data
        )


class AdminVerificationRejectView(APIView):
    # POST /admin/verification-requests/<id>/reject/
    # Admin rejects a verification request with a reason.
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        try:
            verification_request = VerificationRequest.objects.select_related(
                "user"
            ).get(pk=pk)
        except VerificationRequest.DoesNotExist:
            return Response(
                {"detail": "Request not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if verification_request.status != VerificationRequest.Status.PENDING:
            return Response(
                {"detail": "Only pending requests can be rejected."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = AdminRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        verification_request.status = VerificationRequest.Status.REJECTED
        verification_request.admin_note = serializer.validated_data["reason"]
        verification_request.reviewed_by = request.user
        verification_request.save()

        kafka_producer.publish(
            topic=Topics.VERIFICATION_REJECTED,
            payload={
                "user_id": str(verification_request.user_id),
                "username": verification_request.user.username,
                "admin_note": verification_request.admin_note,
            },
            key=str(verification_request.user_id)
        )

        logger.info(
            f"Verification rejected: user={verification_request.user.username} "
            f"by admin={request.user.username}"
        )

        return Response(
            VerificationRequestSerializer(verification_request).data
        )
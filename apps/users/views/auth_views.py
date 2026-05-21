from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from ..serializers import RegisterSerializer, LoginSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        from kafka.producer import kafka_producer
        from kafka.topics import Topics

        kafka_producer.publish(
            topic=Topics.USER_REGISTERED,
            payload={
                "user_id": str(user.id),
                "username": user.username,
                "display_name": user.display_name,
                "bio": user.bio or "",
                "is_verified": user.is_verified,
            },
            key=str(user.id)
        )

        try:
            from apps.users.tasks import send_welcome_email_direct
            send_welcome_email_direct(
                user_email=user.email,
                display_name=user.display_name,
                username=user.username
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Welcome email failed: {e}")

        refresh = RefreshToken.for_user(user)
        return Response({
            "user": {
                "id": str(user.id),
                "email": user.email,
                "username": user.username
            },
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request}
        )

        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        return Response({
            "user": {
                "id": str(user.id),
                "email": user.email,
                "username": user.username
            },
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            if not refresh_token:
                return Response({"detail": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"detail": "Logged out successfully."})
        except TokenError:
            return Response({"detail": "Invalid or expired token."},status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        from ..serializers import ChangePasswordSerializer
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password updated successfully."})
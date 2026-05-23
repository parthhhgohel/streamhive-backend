from django.utils import timezone
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django_redis import get_redis_connection
from django.conf import settings

from ..models import User, PasswordResetOTP
from ..serializers import RegisterSerializer, LoginSerializer, ForgotPasswordSerializer, VerifyOTPSerializer, ResetPasswordSerializer


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
        email = request.data.get("email", "").lower().strip()

        # brute force protection — track failed attempts per email
        redis_conn = get_redis_connection("default")
        fail_key = f"login_fail:{email}"
        fail_count = redis_conn.get(fail_key)
        fail_count = int(fail_count) if fail_count else 0

        # lock account after 10 failed attempts for 15 minutes
        if fail_count >= 10:
            ttl = redis_conn.ttl(fail_key)
            return Response(
                {
                    "detail": f"Too many failed login attempts. Try again in {ttl} seconds.",
                    "retry_after": ttl,
                    "locked": True,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        serializer = LoginSerializer(
            data=request.data,
            context={"request": request}
        )

        if not serializer.is_valid():
            # increment fail counter on bad credentials
            pipe = redis_conn.pipeline()
            pipe.incr(fail_key)
            pipe.expire(fail_key, 900)
            pipe.execute()

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        user = serializer.validated_data["user"]

        # clear fail counter on successful login
        redis_conn.delete(fail_key)

        refresh = RefreshToken.for_user(user)

        return Response({
            "user": {
                "id": str(user.id),
                "email": user.email,
                "username": user.username,
                "display_name": user.display_name,
                "avatar": user.avatar.url if user.avatar else None,
                "is_verified": user.is_verified,
                "is_staff": user.is_staff,
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


# Including Redis
# class ForgotPasswordView(APIView):
#     """
#     POST /auth/forgot-password/
#     {"email", "user@example.com"}

#     Always returns 200 even if email not found
#     to prevent user enumeration attacks.
#     """
#     permission_classes = [AllowAny]
#     throttle_scope = "forgot_password"

#     def post(self, request):
#         serializer = ForgotPasswordSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         email = serializer.validated_data["email"]

#         redis_conn = get_redis_connection("default")
#         cooldown_key = f"otp_cooldown:{email}"

#         if redis_conn.exists(cooldown_key):
#             ttl = redis_conn.ttl(cooldown_key)
#             return Response(
#                 {
#                     "detail": f"Please wait {ttl} seconds before requesting another OTP.",
#                     "retry_after": ttl,
#                 },
#                 status=status.HTTP_429_TOO_MANY_REQUESTS
#             )

#         try:
#             user = User.objects.get(email=email, is_active=True)

#             otp_obj = PasswordResetOTP.create_for_user(user)

#             from apps.users.tasks import send_otp_email_direct
#             send_otp_email_direct(
#                 user_email=user.email,
#                 display_name=user.display_name or user.username,
#                 otp=otp_obj.otp,
#             )

#             cooldown = getattr(settings, "OTP_COOLDOWN_SECONDS", 60)
#             redis_conn.setex(cooldown_key, cooldown, "1")

#         except User.DoesNotExist:
#             pass
#         except Exception as e:
#             import logging
#             logging.getLogger(__name__).error(f"Forgot password error: {e}")
#             return Response(
#                 {"detail": "Failed to send OTP. Please try again."},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

#         return Response({
#             "detail": "If this email exists, an OTP has been sent.",
#             "expiry_minutes": getattr(settings, "OTP_EXPIRY_MINUTES", 15),
#         })

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email, is_active=True)
            otp_obj = PasswordResetOTP.create_for_user(user)

            from apps.users.tasks import send_otp_email_direct
            send_otp_email_direct(
                user_email=user.email,
                display_name=user.display_name or user.username,
                otp=otp_obj.otp,
            )

        except User.DoesNotExist:
            pass
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Forgot password error: {e}")
            return Response(
                {"detail": "Failed to send OTP. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            "detail": "If this email exists, an OTP has been sent.",
            "expiry_minutes": getattr(settings, "OTP_EXPIRY_MINUTES", 15),
        })

# class VerifyOTPView(APIView):
#     """
#     POST /auth/verify-otp/
#     { "email": "user@example.com", "otp": "123456" }

#     Just verifies the OTP is correct without resetting.
#     Frontend uses this to show the "set new password" step.
#     Returns a short-lived reset token stored in Redis.
#     """

#     permission_classes = [AllowAny]

#     def post(self, request):
#         serializer = VerifyOTPSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         email = serializer.validated_data["email"]
#         otp = serializer.validated_data["otp"]

#         try:
#             from apps.users.models import User
#             user = User.objects.get(email=email, is_active=True)
#         except User.DoesNotExist:
#             return Response(
#                 {"detail": "Invalid OTP or email."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         try:
#             otp_obj = PasswordResetOTP.objects.get(user=user)
#         except PasswordResetOTP.DoesNotExist:
#             return Response(
#                 {"detail": "No OTP found. Please request a new one."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         max_attempts = getattr(settings, "OTP_MAX_ATTEMPTS", 5)
#         if otp_obj.attempts >= max_attempts:
#             otp_obj.delete()
#             return Response(
#                 {"detail": "Too many failed attempts. Please request a new OTP."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         if otp_obj.is_expired():
#             otp_obj.delete()
#             return Response(
#                 {"detail": "OTP has expired. Please request a new one."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         if otp_obj.is_used:
#             return Response(
#                 {"detail": "OTP already used. Please request a new one."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         if otp_obj.otp != otp:
#             otp_obj.attempts += 1
#             otp_obj.save(update_fields=["attempts"])
#             remaining = max_attempts - otp_obj.attempts
#             return Response(
#                 {
#                     "detail": f"Incorrect OTP. {remaining} attempts remaining.",
#                     "attempts_remaining": remaining,
#                 },
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         import secrets
#         reset_token = secrets.token_urlsafe(32)
#         redis_conn = get_redis_connection("default")
#         redis_conn.setex(
#             f"reset_token:{reset_token}",
#             600,
#             str(user.id)
#         )

#         otp_obj.is_used = True
#         otp_obj.save(update_fields=["is_used"])

#         return Response({
#             "detail": "OTP verified successfully.",
#             "reset_token": reset_token,
#         })

class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid OTP or email."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            otp_obj = PasswordResetOTP.objects.get(user=user)
        except PasswordResetOTP.DoesNotExist:
            return Response(
                {"detail": "No OTP found. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )

        max_attempts = getattr(settings, "OTP_MAX_ATTEMPTS", 5)
        if otp_obj.attempts >= max_attempts:
            otp_obj.delete()
            return Response(
                {"detail": "Too many failed attempts. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if otp_obj.is_expired():
            otp_obj.delete()
            return Response(
                {"detail": "OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if otp_obj.is_used:
            return Response(
                {"detail": "OTP already used. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if otp_obj.otp != otp:
            otp_obj.attempts += 1
            otp_obj.save(update_fields=["attempts"])
            remaining = max_attempts - otp_obj.attempts
            return Response(
                {
                    "detail": f"Incorrect OTP. {remaining} attempts remaining.",
                    "attempts_remaining": remaining,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # OTP is correct - generate reset token and store in DB
        import secrets
        from datetime import timedelta

        reset_token = secrets.token_urlsafe(32)
        otp_obj.is_used = True
        otp_obj.reset_token = reset_token
        otp_obj.reset_token_expires_at = timezone.now() + timedelta(minutes=10)
        otp_obj.save(update_fields=["is_used", "reset_token", "reset_token_expires_at"])

        return Response({
            "detail": "OTP verified successfully.",
            "reset_token": reset_token,
        })


# class ResetPasswordView(APIView):
#     """
#     POST /auth/reset-password/
#     {
#         "reset_token": "...",
#         "new_password": "...",
#         "new_password2": "..."
#     }

#     Uses the reset_token from VerifyOTPView.
#     Token is single-use and expires in 10 minutes.
#     """
#     permission_classes = [AllowAny]

#     def post(self, request):
#         reset_token = request.data.get("reset_token", "").strip()
#         new_password = request.data.get("new_password", "")
#         new_password2 = request.data.get("new_password2", "")

#         if not reset_token:
#             return Response(
#                 {"detail": "Reset token is required."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         if not new_password or not new_password2:
#             return Response(
#                 {"detail": "Both password fields are required."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         if new_password != new_password2:
#             return Response(
#                 {"detail": "Passwords do not match."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         if len(new_password) < 8:
#             return Response(
#                 {"detail": "Password must be at least 8 characters."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         redis_conn = get_redis_connection("default")
#         token_key = f"reset_token:{reset_token}"
#         user_id = redis_conn.get(token_key)

#         if not user_id:
#             return Response(
#                 {"detail": "Invalid or expired reset token. Please start over."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         if isinstance(user_id, bytes):
#             user_id = user_id.decode("utf-8")

#         try:
#             from apps.users.models import User
#             user = User.objects.get(id=user_id, is_active=True)
#         except User.DoesNotExist:
#             redis_conn.delete(token_key)
#             return Response(
#                 {"detail": "User not found."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         try:
#             from django.contrib.auth.password_validation import validate_password
#             validate_password(new_password, user)
#         except Exception as e:
#             return Response(
#                 {"detail": list(e.messages)},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         user.set_password(new_password)
#         user.save(update_fields=["password"])

#         # delete reset token — single use
#         redis_conn.delete(token_key)

#         # blacklist all existing JWT tokens for this user
#         # by rotating the user's password, existing tokens become invalid
#         # optionally also clear any OTP leftover
#         PasswordResetOTP.objects.filter(user=user).delete()

#         try:
#             from apps.users.tasks import send_password_changed_email_direct
#             send_password_changed_email_direct(
#                 user_email=user.email,
#                 display_name=user.display_name or user.username,
#             )
#         except Exception:
#             pass

#         return Response({
#             "detail": "Password reset successfully. Please login with your new password."
#         })

class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        reset_token = request.data.get("reset_token", "").strip()
        new_password = request.data.get("new_password", "")
        new_password2 = request.data.get("new_password2", "")

        if not reset_token:
            return Response(
                {"detail": "Reset token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not new_password or not new_password2:
            return Response(
                {"detail": "Both password fields are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_password != new_password2:
            return Response(
                {"detail": "Passwords do not match."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(new_password) < 8:
            return Response(
                {"detail": "Password must be at least 8 characters."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # look up token in DB
        try:
            otp_obj = PasswordResetOTP.objects.select_related("user").get(
                reset_token=reset_token,
                is_used=True,
            )
        except PasswordResetOTP.DoesNotExist:
            return Response(
                {"detail": "Invalid or expired reset token. Please start over."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if otp_obj.reset_token_expires_at and timezone.now() > otp_obj.reset_token_expires_at:
            otp_obj.delete()
            return Response(
                {"detail": "Reset token has expired. Please start over."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = otp_obj.user

        if not user.is_active:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from django.contrib.auth.password_validation import validate_password
            validate_password(new_password, user)
        except Exception as e:
            return Response(
                {"detail": list(e.messages)},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        # delete OTP row - single use, cleans up everything
        otp_obj.delete()

        try:
            from apps.users.tasks import send_password_changed_email_direct
            send_password_changed_email_direct(
                user_email=user.email,
                display_name=user.display_name or user.username,
            )
        except Exception:
            pass

        return Response({
            "detail": "Password reset successfully. Please login with your new password."
        })
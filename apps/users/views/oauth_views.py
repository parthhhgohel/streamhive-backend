import secrets
import logging
from urllib.parse import urlencode
from django.shortcuts import redirect
from django.conf import settings
from django.core import signing
from django.core.signing import BadSignature, SignatureExpired
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from ..oauth_utils import GoogleOAuth, GitHubOAuth
from ..oauth_service import get_or_create_google_user, get_or_create_github_user
from ..tasks import send_welcome_email_direct

logger = logging.getLogger(__name__)


def build_frontend_redirect(user, is_new_user: bool) -> str:
    refresh = RefreshToken.for_user(user)
    params = {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "is_new": "1" if is_new_user else "0",
    }
    return f"{settings.FRONTEND_URL}/oauth/callback?{urlencode(params)}"


def build_frontend_error_redirect(message: str) -> str:
    params = {"error": message}
    return f"{settings.FRONTEND_URL}/login?{urlencode(params)}"


def generate_signed_state(provider: str) -> str:
    """
    Generate a signed state string using Django's signing module.
    No Redis or DB needed — the signature itself proves authenticity.
    Expires in 10 minutes.
    """
    return signing.dumps(
        {"provider": provider, "nonce": secrets.token_hex(16)},
        salt="oauth_state",
        compress=True,
    )


def verify_signed_state(state: str, expected_provider: str) -> bool:
    """
    Verify the signed state string.
    Returns True if valid and matches expected provider.
    Returns False if expired, tampered, or wrong provider.
    """
    try:
        data = signing.loads(
            state,
            salt="oauth_state",
            max_age=600,
        )
        return data.get("provider") == expected_provider
    except SignatureExpired:
        logger.warning("OAuth state expired")
        return False
    except BadSignature:
        logger.warning("OAuth state signature invalid — possible CSRF attempt")
        return False
    except Exception as e:
        logger.error(f"OAuth state verification failed: {e}")
        return False


def _post_registration_tasks(user, is_new: bool):
    """
    Send welcome email and publish Kafka event for new OAuth users.
    Errors here never block the login flow.
    """
    if not is_new:
        return
    try:
        send_welcome_email_direct(
            user_email=user.email,
            display_name=user.display_name or user.username,
            username=user.username,
        )
    except Exception as e:
        logger.error(f"Welcome email failed: {e}")

    try:
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
    except Exception as e:
        logger.error(f"Kafka publish failed for OAuth user: {e}")


class GoogleLoginView(APIView):
    """
    GET /auth/google/
    Redirects user to Google consent screen.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        state = generate_signed_state("google")
        auth_url = GoogleOAuth.get_auth_url(state=state)
        return redirect(auth_url)


class GoogleCallbackView(APIView):
    """
    GET /auth/google/callback/
    Google redirects here after user consents.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        error = request.query_params.get("error")

        if error:
            logger.warning(f"Google OAuth error: {error}")
            return redirect(build_frontend_error_redirect(
                "Google login was cancelled."
            ))

        if not code or not state:
            return redirect(build_frontend_error_redirect(
                "Invalid OAuth response."
            ))

        if not verify_signed_state(state, "google"):
            return redirect(build_frontend_error_redirect(
                "OAuth session expired or invalid. Please try again."
            ))

        try:
            token_data = GoogleOAuth.exchange_code_for_token(code)
            access_token = token_data.get("access_token")

            if not access_token:
                raise ValueError("No access token received from Google")

            user_info = GoogleOAuth.get_user_info(access_token)
            user, is_new = get_or_create_google_user(user_info)
            _post_registration_tasks(user, is_new)

            return redirect(build_frontend_redirect(user, is_new))

        except ValueError as e:
            logger.warning(f"Google OAuth value error: {e}")
            return redirect(build_frontend_error_redirect(str(e)))
        except Exception as e:
            logger.error(f"Google OAuth failed: {e}")
            return redirect(build_frontend_error_redirect(
                "Google login failed. Please try again."
            ))


class GitHubLoginView(APIView):
    """
    GET /auth/github/
    Redirects user to GitHub consent screen.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        state = generate_signed_state("github")
        auth_url = GitHubOAuth.get_auth_url(state=state)
        return redirect(auth_url)


class GitHubCallbackView(APIView):
    """
    GET /auth/github/callback/
    GitHub redirects here after user consents.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        error = request.query_params.get("error")

        if error:
            logger.warning(f"GitHub OAuth error: {error}")
            return redirect(build_frontend_error_redirect(
                "GitHub login was cancelled."
            ))

        if not code or not state:
            return redirect(build_frontend_error_redirect(
                "Invalid OAuth response."
            ))

        if not verify_signed_state(state, "github"):
            return redirect(build_frontend_error_redirect(
                "OAuth session expired or invalid. Please try again."
            ))

        try:
            token_data = GitHubOAuth.exchange_code_for_token(code)
            access_token = token_data.get("access_token")

            if not access_token:
                raise ValueError("No access token received from GitHub")

            user_info = GitHubOAuth.get_user_info(access_token)
            user, is_new = get_or_create_github_user(user_info)
            _post_registration_tasks(user, is_new)

            return redirect(build_frontend_redirect(user, is_new))

        except ValueError as e:
            logger.warning(f"GitHub OAuth value error: {e}")
            return redirect(build_frontend_error_redirect(str(e)))
        except Exception as e:
            logger.error(f"GitHub OAuth failed: {e}")
            return redirect(build_frontend_error_redirect(
                "GitHub login failed. Please try again."
            ))
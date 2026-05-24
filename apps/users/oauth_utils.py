import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class GoogleOAuth:
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USER_INFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    @classmethod
    def get_auth_url(cls, state: str) -> str:
        """
        Build the Google consent screen URL.
        state is a random string to prevent CSRF.
        """
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "state": state,
            "prompt": "select_account",
        }

        from urllib.parse import urlencode
        return f"{cls.AUTH_URL}?{urlencode(params)}"

    @classmethod
    def exchange_code_for_token(cls, code: str) -> dict:
        """
        Exchange authorization code for access token.
        """
        response = requests.post(cls.TOKEN_URL, data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        }, timeout=10)

        response.raise_for_status()
        return response.json()

    @classmethod
    def get_user_info(cls, access_token: str) -> dict:
        """
        Get user profile from Google.
        Returns: { id, email, name, picture, verified_email }
        """
        response = requests.get(
            cls.USER_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        response.raise_for_status()
        return response.json()


class GitHubOAuth:
    AUTH_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USER_INFO_URL = "https://api.github.com/user"
    USER_EMAIL_URL = "https://api.github.com/user/emails"

    @classmethod
    def get_auth_url(cls, state: str) -> str:
        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": settings.GITHUB_REDIRECT_URI,
            "scope": "user:email",
            "state": state,
        }
        from urllib.parse import urlencode
        return f"{cls.AUTH_URL}?{urlencode(params)}"

    @classmethod
    def exchange_code_for_token(cls, code: str) -> dict:
        response = requests.post(
            cls.TOKEN_URL,
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_REDIRECT_URI,
            },
            headers={"Accept": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        return response.json()

    @classmethod
    def get_user_info(cls, access_token: str) -> dict:
        """
        Get user profile from GitHub.
        GitHub may return null email if user has private email setting.
        So we fetch emails separately.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        user_response = requests.get(
            cls.USER_INFO_URL,
            headers=headers,
            timeout=10
        )

        user_response.raise_for_status()
        user_data = user_response.json()

        if not user_data.get("email"):
            email_response = requests.get(
                cls.USER_EMAIL_URL,
                headers=headers,
                timeout=10
            )
            if email_response.status_code == 200:
                emails = email_response.json()
                primary = next(
                    (e for e in emails if e.get("primary") and e.get("verified")),
                    None
                )
                if primary:
                    user_data["email"] = primary["email"]

        return user_data
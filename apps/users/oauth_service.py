import logging
import secrets
import string
from django.db import transaction
from .models import User

logger = logging.getLogger(__name__)

def generate_unique_username(base: str) -> str:
    """
    Generate a unique username from a base string.
    Cleans the base, checks DB, appends random suffix if taken.
    """

    import re
    base = re.sub(r"[^a-zA-Z0-9_]", "", base).lower()
    base = base[:20] if len(base) > 20 else base
    base = base or "user"

    username = base
    if not User.objects.filter(username=username).exists():
        return username

    for _ in range(10):
        suffix = "".join(secrets.choice(string.digits) for _ in range(4))
        candidate = f"{base}_{suffix}"
        if not User.objects.filter(username=candidate).exists():
            return candidate

    return f"user_{''.join(secrets.choice(string.digits) for _ in range(8))}"


def generate_random_password() -> str:
    """
    OAuth users don't use passwords but Django requires one.
    Generate a strong random one they'll never use.
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(40))


@transaction.atomic
def get_or_create_google_user(google_user_info: dict) -> tuple:
    """
    Find or create a user from Google OAuth data.
    Returns (user, created) tuple.

    google_user_info shape:
    {
        "id": "...",
        "email": "user@gmail.com",
        "name": "John Doe",
        "given_name": "John",
        "picture": "https://...",
        "verified_email": True
    }
    """
    google_id = str(google_user_info.get("id", ""))
    email = google_user_info.get("email", "").lower().strip()
    name = google_user_info.get("name", "")
    picture = google_user_info.get("picture", "")

    if not email:
        raise ValueError("Google account has no email address")

    user = User.objects.filter(
        auth_provider="google",
        auth_provider_id=google_id
    ).first()

    if user:
        return user, False

    existing_user = User.objects.filter(email=email).first()
    if existing_user:
        if existing_user.auth_provider == "email":
            existing_user.auth_provider = "google"
            existing_user.auth_provider_id = google_id
            existing_user.save(update_fields=["auth_provider", "auth_provider_id"])
            logger.info(f"Linked Google to existing account: {email}")
            return existing_user, False
        else:
            existing_user.auth_provider_id = google_id
            existing_user.save(update_fields=["auth_provider_id"])
            return existing_user, False

    username = generate_unique_username(
        name.replace(" ", "_") if name else email.split("@")[0]
    )
    display_name = name or username

    user = User.objects.create(
        email=email,
        username=username,
        display_name=display_name,
        auth_provider="google",
        auth_provider_id=google_id,
        is_active=True,
    )
    user.set_password(generate_random_password())
    user.save()

    logger.info(f"Created new user via Google OAuth: {username}")
    return user, True


@transaction.atomic
def get_or_create_github_user(github_user_info: dict) -> tuple:
    """
    Find or create a user from GitHub OAuth data.
    Returns (user, created) tuple.

    github_user_info shape:
    {
        "id": 12345,
        "login": "johndoe",
        "name": "John Doe",
        "email": "user@example.com",
        "avatar_url": "https://...",
        "bio": "..."
    }
    """
    github_id = str(github_user_info.get("id", ""))
    email = (github_user_info.get("email") or "").lower().strip()
    login = github_user_info.get("login", "")
    name = github_user_info.get("name") or login
    bio = github_user_info.get("bio") or ""

    if not email:
        raise ValueError(
            "GitHub account has no public email. "
            "Please set a public email in GitHub settings or use a different login method."
        )

    user = User.objects.filter(
        auth_provider="github",
        auth_provider_id=github_id
    ).first()

    if user:
        return user, False

    existing_user = User.objects.filter(email=email).first()
    if existing_user:
        existing_user.auth_provider = "github"
        existing_user.auth_provider_id = github_id
        existing_user.save(update_fields=["auth_provider", "auth_provider_id"])
        logger.info(f"Linked GitHub to existing account: {email}")
        return existing_user, False

    username = generate_unique_username(login or email.split("@")[0])
    display_name = name or username

    user = User.objects.create(
        email=email,
        username=username,
        display_name=display_name,
        bio=bio[:160] if bio else "",
        auth_provider="github",
        auth_provider_id=github_id,
        is_active=True,
    )
    user.set_password(generate_random_password())
    user.save()

    logger.info(f"Created new user via GitHub OAuth: {username}")
    return user, True
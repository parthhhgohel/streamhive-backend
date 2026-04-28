import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from apps.users.models import User
from apps.posts.models import Post
from apps.notifications.models import Notification

@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="test@example.com",
        username="testuser",
        password="StrongPass123!"
    )

@pytest.fixture
def auth_client(client, user):
    url = reverse("login")
    response = client.post(url, {
        "email": user.email,
        "password": "StrongPass123!"
    }, format="json")
    token = response.data["tokens"]["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client

@pytest.mark.django_db
def test_notifications_list(auth_client, user):
    Notification.objects.create(
        recipient=user,
        sender=user,
        notification_type="follow"
    )

    url = reverse("notifications")
    response = auth_client.get(url)

    assert response.status_code == 200
    assert len(response.data["results"]) == 1


@pytest.mark.django_db
def test_unread_count(auth_client, user):
    Notification.objects.create(
        recipient=user,
        sender=user,
        notification_type="follow",
        is_read=False
    )

    url = reverse("unread_count")
    response = auth_client.get(url)

    assert response.data["unread_count"] == 1

@pytest.mark.django_db
def test_mark_all_read(auth_client, user):
    Notification.objects.create(
        recipient=user,
        sender=user,
        notification_type="follow",
        is_read=False
    )

    url = reverse("mark_all_read")
    response = auth_client.post(url)

    assert response.status_code == 200
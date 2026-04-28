import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from apps.users.models import User
from apps.posts.models import Post


@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def user_data():
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "StrongPass123!",
        "password2": "StrongPass123!",
        "display_name": "Test User"
    }

@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="user@test.com",
        username="user1",
        password="StrongPass123!"
    )

@pytest.fixture
def user2(db):
    return User.objects.create_user(
        email="user2@test.com",
        username="user2",
        password="StrongPass123!"
    )

@pytest.fixture
def created_user(db, user_data):
    return User.objects.create_user(
        email=user_data["email"],
        username=user_data["username"],
        password=user_data["password"]
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
def test_register(client, user_data):
    url = reverse("register")
    response = client.post(url, user_data, format="json")

    assert response.status_code == 201
    assert "tokens" in response.data
    assert User.objects.filter(email=user_data["email"]).exists()

@pytest.mark.django_db
def test_login(client, created_user, user_data):
    url = reverse("login")
    response = client.post(url, {
        "email": user_data["email"],
        "password": user_data["password"]
    }, format="json")

    assert response.status_code == 200
    assert "tokens" in response.data

@pytest.mark.django_db
def test_login_wrong_password(client, created_user, user_data):
    url = reverse("login")
    response = client.post(url, {
        "email": user_data["email"],
        "password": "wrongpassword"
    }, format="json")

    assert response.status_code == 400
    assert "error" in response.data or "detail" in response.data

@pytest.mark.django_db
def test_follow_user(auth_client, user2):
    url = reverse("follow", args=[user2.username])
    response = auth_client.post(url)

    assert response.status_code == 201


@pytest.mark.django_db
def test_follow_self(auth_client, user):
    url = reverse("follow", args=[user.username])
    response = auth_client.post(url)

    assert response.status_code == 400

@pytest.mark.django_db
def test_follow_duplicate(auth_client, user2):
    url = reverse("follow", args=[user2.username])

    auth_client.post(url)
    response = auth_client.post(url)

    assert response.status_code == 400

@pytest.mark.django_db
def test_unfollow(auth_client, user2):
    url = reverse("follow", args=[user2.username])

    auth_client.post(url)
    response = auth_client.delete(url)

    assert response.status_code == 200

@pytest.mark.django_db
def test_feed(auth_client, user2):
    follow_url = reverse("follow", args=[user2.username])
    auth_client.post(follow_url)

    Post.objects.create(author=user2, content="Post following")

    feed_url = reverse("home_feed")
    res = auth_client.get(feed_url)

    assert res.status_code == 200

    contents = [p["content"] for p in res.data["results"]]

    assert "Post following" in contents
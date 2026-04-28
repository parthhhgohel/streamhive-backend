import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from apps.users.models import User
from apps.posts.models import Post


@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="poster@example.com",
        username="poster",
        password="StrongPass123!"
    )

@pytest.fixture
def user2(db):
    return User.objects.create_user(
        email="user2@test.com",
        username="user2",
        password="pass1234"
    )

@pytest.fixture
def post(user):
    return Post.objects.create(author=user, content="Post 1")

@pytest.fixture
def auth_client(client, user):
    url = reverse("login")
    response = client.post(url, {
        "email": "poster@example.com",
        "password": "StrongPass123!"
    }, format="json")
    token = response.data["tokens"]["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client

@pytest.mark.django_db
def test_create_post(auth_client):
    url = reverse("post_list_create")
    response = auth_client.post(url, {"content": "Hello #world"}, format="json")
    assert response.status_code == 201
    assert Post.objects.filter(content="Hello #world").exists()

@pytest.mark.django_db
def test_create_post_unauthenticated(client):
    url = reverse("post_list_create")
    response = client.post(url, {"content": "Hello"}, format="json")
    assert response.status_code == 401

@pytest.mark.django_db
def test_list_posts(auth_client, user):
    Post.objects.create(author=user, content="Post 1")
    Post.objects.create(author=user, content="Post 2")
    url = reverse("post_list_create")
    response = auth_client.get(url)
    assert response.status_code == 200

@pytest.mark.django_db
def test_delete_post(auth_client, user):
    post = Post.objects.create(author=user, content="Post 1")
    url = reverse("post_detail", args=[post.id])
    response = auth_client.delete(url)
    assert response.status_code == 204
    assert not Post.objects.filter(id=post.id).exists()

@pytest.mark.django_db
def test_like_post(auth_client, post):
    url = reverse("post_like", args=[post.id])
    response = auth_client.post(url)

    assert response.status_code == 201

@pytest.mark.django_db
def test_unlike_post(auth_client, post):
    url = reverse("post_like", args=[post.id])

    auth_client.post(url)
    response = auth_client.delete(url)

    assert response.status_code == 200

@pytest.mark.django_db
def test_like_twice(auth_client, post):
    url = reverse("post_like", args=[post.id])

    auth_client.post(url)
    response = auth_client.post(url)

    assert response.status_code == 400

@pytest.mark.django_db
def test_edit_other_user_post(auth_client, user2):
    post = Post.objects.create(author=user2, content="Hello")

    url = reverse("post_detail", args=[post.id])
    response = auth_client.put(url, {"content": "Hack"})

    assert response.status_code in [403, 401]

@pytest.mark.django_db
def test_empty_post(auth_client):
    url = reverse("post_list_create")
    response = auth_client.post(url, {"content": ""})

    assert response.status_code == 400
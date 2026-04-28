import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from apps.posts.models import Post
from apps.comments.models import Comment
from apps.users.models import User

@pytest.fixture
def client():
    return APIClient()

@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="commenter@gmail.com",
        username="commenter",
        password="StrongPass123!"
    )

@pytest.fixture()
def auth_client(user):
    url = reverse("login")
    client = APIClient()
    res = client.post(url, {
        "email": "commenter@gmail.com",
        "password": "StrongPass123!",
    }, format="json")
    token = res.data["tokens"]["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client

@pytest.fixture
def post(user):
    return Post.objects.create(
        author=user,
        content="This is a post"
    )

@pytest.mark.django_db
def test_create_comment(auth_client, post):
    url = reverse("comment_list_create")
    res = auth_client.post(url, {
        "post": str(post.id),
        "content": "Nice post"
    })
    assert res.status_code == 201
    assert Comment.objects.filter(content="Nice post").exists()

@pytest.mark.django_db
def test_comment_unauthenticated(client, post):
    url = reverse("comment_list_create")
    res = client.post(url, {
        "post": str(post.id),
        "content": "Nice post"
    }, format="json")
    assert res.status_code == 401

@pytest.mark.django_db
def test_list_comments(auth_client, post, user):
    Comment.objects.create(post=post, author=user, content="C1")
    Comment.objects.create(post=post, author=user, content="C2")
    
    url = reverse("comment_list_create") + f"?post={post.id}"
    res = auth_client.get(url)

    assert res.status_code == 200
    assert len(res.data["results"]) == 2


@pytest.mark.django_db
def test_delete_comment(auth_client, post, user):
    comment = Comment.objects.create(post=post, author=user, content="C1")
    url = reverse("comment_detail", args=[comment.id])
    res = auth_client.delete(url)
    assert res.status_code == 204
    assert not Comment.objects.filter(id=comment.id).exists()
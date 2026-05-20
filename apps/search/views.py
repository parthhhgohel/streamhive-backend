import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings
from .es_client import es_client

logger = logging.getLogger(__name__)

POSTS_INDEX = settings.ELASTICSEARCH_POSTS_INDEX
USERS_INDEX = settings.ELASTICSEARCH_USERS_INDEX

class SearchView(APIView):
    """
    GET /search/?q=<query>&type=posts|users|all&page=1&size=20

    Searches Elasticsearch for posts and/or users.
    Falls back to PostgreSQL if ES is unavailable.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        search_type = request.query_params.get("type", "all")
        page = int(request.query_params.get("page", 1))
        size = int(request.query_params.get("size", 20))

        if not query:
            return Response({
                "posts": [],
                "users": [],
                "query": query,
            })
        
        if len(query) > 200:
            return Response({"detail": "Query too long."}, status=400)

        if not es_client.is_healthy():
            logger.warning("Elasticsearch unavailable, falling back to PostgreSQL")
            return self._fallback_search(query, search_type)
        
        results = {}
        from_offset = (page - 1) * size

        try:
            if search_type in ("posts", "all"):
                results["posts"] = self._search_posts(
                    query, size, from_offset
                )
            if search_type in ("users", "all"):
                results["users"] = self._search_users(
                    query, size, from_offset
                )
            
            results["query"] = query
            results["page"] = page
            return Response(results)

        except Exception as e:
            logger.error(f"Elasticsearch search failed: {e}")
            return self._fallback_search(query, search_type)


    def _search_posts(self, query: str, size: int, from_offset: int):
        client = es_client.get_client()

        body = {
            "from": from_offset,
            "size": size,
            "query": {
                "bool": {
                    "should": [
                        # full-text match on content - highest priority
                        {
                            "match": {
                                "content": {
                                    "query": query,
                                    "boost": 3,
                                    "fuzziness": "AUTO",
                                }
                            }
                        },
                        # match on hashtags
                        {
                            "term": {
                                "hashtags": {
                                    "value": query.lower().lstrip("#"),
                                    "boost": 2,
                                }
                            }
                        },
                        # match on author username
                        {
                            "match": {
                                "author_username": {
                                    "query": query,
                                    "boost": 1
                                }
                            }
                        }
                    ],
                    "minimum_should_match": 1,
                }
            },
            # boost popular posts
            "sort": [
                "_score",
                {"like_count": {"order": "desc"}},
                {"created_at": {"order": "desc"}},
            ],
            # highlight matching terms in content
            "highlight": {
                "fields": {
                    "content": {
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"],
                        "fragment_size": 150,
                    }
                }
            }
        }

        response = client.search(index=POSTS_INDEX, query=body["query"], sort=body["sort"], highlight=body["highlight"], from_=from_offset, size=size)
        return self._format_post_results(response)

    def _search_users(self, query: str, size: int, from_offset: int):
        client = es_client.get_client()

        body = {
            "from": from_offset,
            "size": size,
            "query": {
                "bool": {
                    "should": [
                        # exact username match - highest priority
                        {
                            "term": {
                                "username.keyword": {
                                    "value": query.lower(),
                                    "boost": 4,
                                }
                            }
                        },
                        # prefix match on username (for autocomplete)
                        {
                            "prefix": {
                                "username": {
                                    "value": query.lower(),
                                    "boost": 3,
                                    # "fuzziness": "AUTO",
                                }
                            }
                        },
                        # full-text on display name
                        {
                            "match": {
                                "display_name": {
                                    "query": query,
                                    "boost": 2,
                                    "fuzziness": "AUTO",
                                }
                            }
                        },
                        # full-text on bio
                        {
                            "match": {
                                "bio": {
                                    "query": query,
                                    "boost": 1,
                                    "fuzziness": "AUTO",
                                }
                            }
                        }
                    ],
                    "minimum_should_match": 1,
                    # exclude private accounts from search
                    # "filter": [
                    #     {"term": {"is_private": False}}
                    # ]
                }
            },
            "sort": [
                "_score",
                {"followers_count": {"order": "desc"}},
            ],
        }

        response = client.search(index=USERS_INDEX, query=body["query"], sort=body["sort"], from_=from_offset, size=size)
        return self._format_user_results(response)

    def _format_post_results(self, response):
        results = []

        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            highlight = hit.get("highlight", {})
            results.append({
                "post_id": source.get("post_id"),
                "author_id": source.get("author_id"),
                "author_username": source.get("author_username"),
                "author_display_name": source.get("author_display_name"),
                "content": source.get("content"),
                "content_highlight": highlight.get("content", [source.get("content", "")[:150]])[0],
                "hashtags": source.get("hashtags", []),
                "like_count": source.get("like_count", 0),
                "comment_count": source.get("comment_count", 0),
                "media_url": source.get("media_url"),
                "created_at": source.get("created_at"),
                "score": hit["_score"],
            })
        return {
            "results": results,
            "total": response["hits"]["total"]["value"],
        }

    def _format_user_results(self, response):
            results = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                results.append({
                    "user_id": source.get("user_id"),
                    "username": source.get("username"),
                    "display_name": source.get("display_name"),
                    "bio": source.get("bio"),
                    "is_verified": source.get("is_verified", False),
                    "followers_count": source.get("followers_count", 0),
                    "score": hit["_score"],
                })
            return {
                "results": results,
                "total": response["hits"]["total"]["value"],
            }


    def _fallback_search(self, query: str, search_type: str):
            """
            PostgreSQL fallback using icontains.
            Much slower than ES but works when ES is down.
            """
            results = {"query": query, "fallback": True}

            if search_type in ("posts", "all"):
                from apps.posts.models import Post
                from apps.posts.serializers import PostSerializer

                posts = Post.objects.filter(
                    content__icontains=query
                ).select_related("author").prefetch_related("hashtags")[:20]

                results["posts"] = {
                    "results": PostSerializer(posts, many=True).data,
                    "total": posts.count(),
                }

            if search_type in ("users", "all"):
                from apps.users.models import User
                from apps.users.serializers import UserMinimalSerializer

                users = User.objects.filter(
                    username__icontains=query,
                    is_active=True,
                    is_private=False,
                )[:20]

                results["users"] = {
                    "results": UserMinimalSerializer(users, many=True).data,
                    "total": users.count(),
                }

            return Response(results)



# ELasticSearch response demo here
"""
{
  "took": 12,
  "timed_out": false,
  "_shards": {
    "total": 1,
    "successful": 1,
    "skipped": 0,
    "failed": 0
  },
  "hits": {
    "total": {
      "value": 2,
      "relation": "eq"
    },
    "max_score": 1.85,
    "hits": [
      {
        "_index": "posts",
        "_id": "101",
        "_score": 1.85,
        "_source": {
          "id": 101,
          "user": {
            "id": 5,
            "username": "parth_dev",
            "profile_picture": "https://example.com/profile.jpg"
          },
          "caption": "Building real-time social media app using Django, Kafka, Redis and Elasticsearch 🚀",
          "hashtags": [
            "django",
            "kafka",
            "elasticsearch"
          ],
          "likes_count": 245,
          "comments_count": 18,
          "created_at": "2026-05-19T10:30:00Z"
        }
      },
      {
        "_index": "posts",
        "_id": "102",
        "_score": 1.42,
        "_source": {
          "id": 102,
          "user": {
            "id": 8,
            "username": "backend_master",
            "profile_picture": "https://example.com/user2.jpg"
          },
          "caption": "Elasticsearch full-text search is insanely fast for hashtags and captions.",
          "hashtags": [
            "search",
            "backend"
          ],
          "likes_count": 120,
          "comments_count": 9,
          "created_at": "2026-05-18T14:15:00Z"
        }
      }
    ]
  }
}
"""
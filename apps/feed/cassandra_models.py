"""
just for overview

Cassadra is Not like postgreSQL
No JOINS, no ofreign keys, no indexes like SQL.
You design tables around your QUERIES, not your entities.

Our queries:
1. "Give me feed for user X, ordered by time" → user_feed table
2. "Give me all posts by user X, ordered by time" → user_posts table

Why Cassandra for feed:
- Writes are extremely fast (append only, sorted by time automatically)
- Reads for a specific user's feed are 0(1) - direct partition lookup
- Scales horizontally without slowing down
"""

from apps.feed.cassandra_client import cassandra_client

def create_tables():
    """
    Call this once on startup or via management command.
    """
    session = cassandra_client.get_session()

    # user_feed: stores the home timeline for each user
    # partition key = user_id (all feed items for a user on same node)
    # clustering key = created_at DESC (auto sorted newest first)
    session.execute("""
        CREATE TABLE IF NOT EXISTS user_feed (
            user_id UUID,
            created_at TIMESTAMP,
            post_id UUID,
            author_id UUID,
            author_username TEXT,
            content TEXT,
            media_url TEXT,
            like_count INT,
            comment_count INT,
            repost_count INT,
            is_repost BOOLEAN,
            PRIMARY KEY (user_id, created_at, post_id) 
        ) WITH CLUSTERING ORDER BY (created_at DESC, post_id ASC)
          AND default_time_to_live = 604800
    """)

    # default_time_to_live = 604800 seconds = 7 days
    # old feed items auto-deleted - saves storage

    # user_posts: stores all posts by a specific user
    # used for profile page timeline

    session.execute("""
        CREATE TABLE IF NOT EXISTS user_posts (
            author_id UUID,
            created_at TIMESTAMP,
            post_id UUID,
            content TEXT,
            media_url TEXT,
            like_count INT,
            comment_count INT,
            repost_count INT,
            is_repost BOOLEAN,
            PRIMARY KEY (author_id, created_at, post_id)
        ) WITH CLUSTERING ORDER BY (created_at DESC, post_id ASC)
          AND default_time_to_live = 2592000
    """)
    # user_posts TTL = 30 days

class UserFeedModel:
    """
    All Cassandra operations for user_feed table.
    """

    @staticmethod
    def insert(user_id, post_data: dict):
        session = cassandra_client.get_session()
        session.execute("""
            INSERT INTO user_feed (
                user_id, created_at, post_id, author_id,
                author_username, content, media_url,
                like_count, comment_count, repost_count, is_repost
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            post_data["created_at"],
            post_data["post_id"],
            post_data["author_id"],
            post_data["author_username"],
            post_data["content"],
            post_data.get("media_url"),
            post_data.get("like_count", 0),
            post_data.get("comment_count", 0),
            post_data.get("repost_count", 0),
            post_data.get("is_repost", False),
        ))

    @staticmethod
    def get_feed(user_id, limit=20, paging_state=None):
        """
        Returns feed for a user with pagination.
        paging_state is Cassandra's native pagination token.
        """
        session = cassandra_client.get_session()
        query = session.prepare("""
            SELECT * FROM user_feed
            WHERE user_id = ?
            LIMIT ?
        """)
        statement = query.bind((user_id, limit))

        if paging_state:
            statement.paging_state = paging_state
        
        statement.fetch_size = limit
        result = session.execute(statement)
        return result

    @staticmethod
    def delete_post_from_feed(user_id, created_at, post_id):
        """
        When a post is deleted , remove from feed.
        """

        session = cassandra_client.get_session()
        session.execute("""
            DELETE FROM user_feed
            WHERE user_id = %s
            AND created_at = %s
            AND post_id = %s
        """, (user_id, created_at, post_id))

class UserPostsModel:
    """
    All Cassandra operations for user_posts table.
    """

    @staticmethod
    def insert(post_data: dict):
        session = cassandra_client.get_session()
        session.execute("""
            INSERT INTO user_posts (
                author_id, created_at, post_id, content,
                media_url, like_count, comment_count,
                repost_count, is_repost
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            post_data["author_id"],
            post_data["created_at"],
            post_data["post_id"],
            post_data["content"],
            post_data.get("media_url"),
            post_data.get("like_count", 0),
            post_data.get("comment_count", 0),
            post_data.get("repost_count", 0),
            post_data.get("is_repost", False),
        ))

    @staticmethod
    def get_user_posts(author_id, limit=20, paging_state=None):
        session = cassandra_client.get_session()
        query = session.prepare("""
            SELECT * FROM user_posts
            WHERE author_id = ?
            LIMIT ?
        """)
        statement = query.bind((author_id, limit))

        if paging_state:
            statement.paging_state = paging_state

        statement.fetch_size = limit
        result = session.execute(statement)
        return result
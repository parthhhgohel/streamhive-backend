from rest_framework.pagination import CursorPagination

class StandardResultsPagination(CursorPagination):
    page_size = 20
    ordering = "-created_at"

class FeedCursorPagination(CursorPagination):
    page_size = 20
    ordering = "-created_at"
    cursor_query_param = "cursor"
    cursor_strict = False
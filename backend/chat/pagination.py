from rest_framework.pagination import CursorPagination

class MessageCursorPagination(CursorPagination):
    page_size = 20
    ordering = "-id"
    page_size_query_param = "page_size"
    max_page_size = 50
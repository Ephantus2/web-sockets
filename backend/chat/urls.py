from django.urls import path
from .views import (
    ConversationListCreateView,
    ConversationDetailView,
    MessageListCreateView,
    MessageSearchView,
    UnreadCountView
)

urlpatterns = [
    path("conversation/", ConversationListCreateView.as_view(), name="conversation-list-create"),
    path("conversations/<int:pk>/", ConversationDetailView.as_view(), name="conversation-detail"),
    path("conversations/<int:conversation_id>/messages/", MessageListCreateView.as_view(), name="message-list-create"),
    path("conversations/<int:conversation_id>/messages/search/", MessageSearchView.as_view(), name="message_search"),
    path("conversations/unread-counts/", UnreadCountView.as_view(), name="unread-counts"),
]
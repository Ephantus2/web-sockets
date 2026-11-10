from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_list_or_404, get_object_or_404
from .models import Conversation, Message
from .serializers import (
    ConversationSerializer,
    MessageSerializer
)
from .pagination import MessageCursorPagination

from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from rest_framework.exceptions import ValidationError

from django.db.models import Count, OuterRef, Subquery, IntegerField, Value
from django.db.models.functions import Coalesce

class ConversationListCreateView(APIView):
    permission_classes=[IsAuthenticated]

    def get(self, request):
        conversation = (
            Conversation.objects.filter(participants=request.user)
            .prefetch_related("participants")
            .distinct()
            .order_by("-updated_at")
        )

        serializer = ConversationSerializer(
            conversation,
            many=True
        )
        return Response(serializer.data)

    def post(self, request):
        serializer = ConversationSerializer(
            data=request.data
        )

        if serializer.is_valid():
            conversation = serializer.save()

            # Ensure the creator is a participant

            conversation.participants.add(request.user)
            return Response(
                ConversationSerializer(conversation).data,
                status=status.HTTP_201_CREATED
            )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        conversation = get_object_or_404(
            Conversation.objects.prefetch_related("participants"),
            pk=pk,
            participants=request.user
        )

        serializer = ConversationSerializer(conversation)
        return Response(serializer.data)

class MessageListCreateView(APIView):
    permission_classes=[IsAuthenticated]

    def get(self, request, conversation_id):
        #check wheather the user belongs to this conversation

        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=request.user
        )

        # Retrieve messages efficiently

        messages = Message.objects.filter(
            conversation=conversation
        ).select_related("sender").order_by("-id")

        #create paginator
        paginator = MessageCursorPagination()

        #Retrieve only requested page

        page = paginator.paginate_queryset(
            messages,
            request,
            view=self
        )

        #serialize message

        serializer = MessageSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, conversation_id):
        conversation = get_object_or_404(
            Conversation,
            pk=conversation_id,
            participants=request.user
        )

        serializer = MessageSerializer(
            data=request.data
        )

        if serializer.is_valid():
            message = serializer.save(
                conversation=conversation,
                sender=request.user
            )

            return Response(
                MessageSerializer(message).data,
                status=status.HTTP_201_CREATED
            )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

class MessageSearchView(APIView):
    permission_classes=[IsAuthenticated]

    def get(self, request, conversation_id):
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=request.user
        )

        search_text = request.query_params.get("q", "").strip()

        if not search_text:
            raise ValidationError({
                "error": "Search query is required"
            })

        if len(search_text) > 200:
            raise ValidationError({
                "error": "Search query cannot exceed 200 characters"
            })
        search_vector = SearchVector(
            "content",
            config="english"
        )

        search_query = SearchQuery(
            search_text,
            config="english"
        )

        messages = Message.objects.filter(
            conversation=conversation
        ).annotate(
            search=search_vector,
            rank=SearchRank(search_vector, search_query)
        ).filter(
            search=search_query
        ).select_related(
            "sender"
        ).order_by(
            "-rank",
            "-id"
        )

        serializer = MessageSerializer(messages, many=True)

        return Response(serializer.data)

class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread_messages = (
            Message.objects.filter(conversation_id=OuterRef("pk"))
            .exclude(sender=request.user)
            .exclude(read_receipts__user=request.user)
            .order_by()
            .values("conversation_id")
            .annotate(total=Count("id", distinct=True))
            .values("total")
        )

        conversations = (
            Conversation.objects.filter(participants=request.user)
            .annotate(
                unread_count=Coalesce(
                    Subquery(
                        unread_messages,
                        output_field=IntegerField()
                    ),
                    Value(0)
                )
            )
            .values("id", "name", "unread_count")
        )
        return Response(list(conversations))
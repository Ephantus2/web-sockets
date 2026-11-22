from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_list_or_404, get_object_or_404
from .models import Conversation, Message, MessageReaction
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    MessageReactionSerializer
)
from .pagination import MessageCursorPagination

from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from rest_framework.exceptions import ValidationError

from django.db.models import Count, OuterRef, Subquery, IntegerField, Value
from django.db.models.functions import Coalesce

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from notifications.tasks import create_message_notifications

from django.db import transaction

import logging

from notifications.models import NotificationOutbox
from notifications.tasks import dispatch_pending_notification_outbox

from django.utils import timezone

logger = logging.getLogger(__name__)

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
        ).select_related("sender").prefetch_related(
            "read_receipts__user",
            "reactions__user"
        ).order_by("-id")

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

        serializer = MessageSerializer(data=request.data)

        if serializer.is_valid():

            # 1. Save message and outbox event atomically
            with transaction.atomic():

                message = serializer.save(
                    conversation=conversation,
                    sender=request.user
                )

                conversation.save(update_fields=["updated_at"])

                # 2. Identify recipients
                recipient_ids = list(
                    conversation.participants
                    .exclude(id=request.user.id)
                    .values_list("id", flat=True)
                )

                # 3. Create persistent notification event
                if recipient_ids:

                    outbox = NotificationOutbox.objects.create(
                        message=message,
                        recipient_ids=recipient_ids
                    )

                    logger.info(
                        "Created outbox event %s for message %s",
                        outbox.id,
                        message.id
                    )

                # 4. Serialize message before leaving transaction
                message_data = MessageSerializer(message).data

                # 5. Schedule real-time operations after commit
                def after_commit():

                    channel_layer = get_channel_layer()

                    if channel_layer is None:
                        logger.error(
                            "Channel layer unavailable. "
                            "Could not broadcast message %s",
                            message.id
                        )

                    else:

                        # Broadcast message to conversation participants
                        try:
                            async_to_sync(channel_layer.group_send)(
                                f"chat_{conversation_id}",
                                {
                                    "type": "chat_message",
                                    "message": message_data
                                }
                            )
    
                        except Exception as error:
                            logger.exception(
                                "Failed to broadcast message %s",
                                message.id,
                                conversation_id
                            )

                    # Trigger outbox dispatcher
                    if recipient_ids:
                        try:
                            dispatch_pending_notification_outbox.delay()

                            logger.info(
                                "Notification outbox dispatcher triggered "
                                "after message %s was committed",
                                message.id
                            )

                        except Exception as error:
                            logger.exception(
                                "Failed to trigger notification outbox dispatcher "
                                "for message %s",
                                message.id
                            )

                transaction.on_commit(after_commit)

            return Response(
                message_data,
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
        ).prefetch_related(
            "read_receipts__user"
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

class MessageUpdateDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def get_message(self, request, conversation_id, message_id):
        # Confirm that the user belongs to this conversation.

        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=request.user
        )

        # Retrieve the message from chat conversation

        message = get_object_or_404(
            Message,
            id=message_id,
            conversation=conversation
        )

        # only the original sender can modify the message.

        if message.sender_id != request.user.id:
            return None, Response({
                "error": "You can only modify your own messages."
            }, status=status.HTTP_403_FORBIDDEN)
        return message, None

    def patch(self, request, conversation_id, message_id):
        message, error = self.get_message(
            request,
            conversation_id,
            message_id
        )

        if error:
            return error

        if message.is_deleted:
            return Response({
                "error": "Deleted messages cannot be edited."
            }, status=status.HTTP_400_BAD_REQUEST)

        content = request.data.get("content")

        if not isinstance(content, str) or not content.strip():
            return Response({
                "error": "Message content cannot be empty."
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = MessageSerializer(
            message,
            data={"content": content.strip()},
            partial=True
        )

        if serializer.is_valid():
            message = serializer.save(
                is_edited=True,
                edited_at=timezone.now()
            )

            message_data = MessageSerializer(message).data

            # Broadcast the edit after the database transaction commits

            def broadcast_edit():
                channel_layer = get_channel_layer()

                if channel_layer is not None:
                    async_to_sync(channel_layer.group_send)(
                        f"chat_{conversation_id}",
                        {
                            "type": "message_edited",
                            "message": message_data
                        }
                    )
            transaction.on_commit(broadcast_edit)

            return Response(
                message_data,
                status=status.HTTP_200_OK
            )
        
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, conversation_id, message_id):
        message, error = self.get_message(
            request,
            conversation_id,
            message_id
        )

        if error:
            return error

        if message.is_deleted:
            return Response(
                {"error": "Message has already been deleted."},
                status=status.HTTP_400_BAD_REQUEST
            )

        message.is_deleted = True
        message.deleted_at = timezone.now()

        message.save(
            update_fields = ["is_deleted", "deleted_at"]
        )

        message_data = MessageSerializer(message).data

        # Broadcast the deletion after the database transaction commits

        def broadcast_delete():
            channel_layer = get_channel_layer()

            if channel_layer is not None:
                async_to_sync(channel_layer.group_send)(
                    f"chat_{conversation_id}",
                    {
                        "type": "message_deleted",
                        "message_id": message.id,
                        "conversation_id": conversation_id
                    }
                )

        transaction.on_commit(broadcast_delete)

        return Response(
            message_data,
            status=status.HTTP_200_OK
        )

class MessageReactionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id, message_id):
        # 1. verify conversation membership

        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants=request.user
        )

        # 2. Retrieve the message
        message = get_object_or_404(
            Message,
            id=message_id,
            conversation=conversation
        )

        # 3. Prevent reactions to deleted messages

        if message.is_deleted:
            return Response(
                {
                    "error": "Cannot react to a deleted message."
                },

                status=status.HTTP_400_BAD_REQUEST
            )

        # validate the emoji

        emoji = request.data.get("emoji")

        if not isinstance(emoji, str) or not emoji.strip():
            return Response(
                {
                    "error": "A valid emoji is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        emoji = emoji.strip()

        if len(emoji) > 32:
            return Response(
                {"error": "Emoji cannot exceed 32 characters."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 5. Toogle the reaction

        reaction, created = MessageReaction.objects.get_or_create(
            message=message,
            user=request.user,
            emoji=emoji
        )

        if not created:
            reaction.delete()

        #6. Retrieve updated reactions

        reactions = (
            MessageReaction.objects
            .filter(message=message)
            .select_related("user")
            .order_by("created_at")
        )

        reaction_data = MessageReactionSerializer(
            reactions,
            many=True
        ).data

        # 7. Broadcast updated reactions after databese commit

        def broadcast_reaction():
            channel_layer = get_channel_layer()

            if channel_layer is None:
                logger.error(
                    "Channel layer unavailable. "
                    "Could not broadcast reactions for message %s",
                    message.id
                )
                return

            try:
                async_to_sync(channel_layer.group_send)(
                    f"chat_{conversation_id}",
                    {
                        "type": "reaction_updated",
                        "message_id": message.id,
                        "conversation_id": conversation_id,
                        "reactions": reaction_data
                    }
                )

            except Exception:
                logger.exception(
                    "Failed to broadcast reactions for message %s",
                    message.id
                )
        transaction.on_commit(broadcast_reaction)

        return Response(
            {
                "message_id": message.id,
                "conversation_id": conversation.id,
                "action": "added" if created else "removed",
                "reactions": reaction_data
            },
            status=status.HTTP_200_OK
        )

class MessagePinView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, conversation_id, message_id):
        # 1. Verify conversation membership.

        conversation = get_object_or_404(
            Conversation.objects.select_for_update(),
            id=conversation_id,
            participants=request.user
        )

        # 2. Retrieve the message

        message = get_object_or_404(
            Message,
            id=message_id,
            conversation=conversation
        )

        # 3. Prevent pinning deleted messages

        if message.is_deleted:
            return Response(
                {
                    "error": "Cannot pin a deleted message."
                }, status=status.HTTP_400_BAD_REQUEST
            )

        # 4. Toggle pinning

        if message.is_pinned:
            message.is_pinned = False
            message.pinned_at = None
            message.pinned_by = None
            action = "unpinned"

        else:
            # Unpin the previously pinned message.

            Message.objects.filter(
                conversation=conversation,
                is_pinned=True
            ).update(
                is_pinned=False,
                pinned_at=None,
                pinned_by=None
            )

            # pin the selected message

            message.is_pinned = True
            message.pinned_at = timezone.now()
            message.pinned_by = request.user
            action="pinned"

        message.save(
            update_fields=[
                "is_pinned",
                "pinned_at",
                "pinned_by"
            ]
        )

        # Broadcast the updated pinned message state.

        def broadcast_pin_update():
            channel_layer = get_channel_layer()

            if channel_layer is None:
                logger.error(
                    "Channel layer unavailable. "
                    "Could not broadcast pin update for message %s",
                    message.id
                )
                return
            try:
                async_to_sync(channel_layer.group_send)(
                    f"chat_{conversation_id}",
                    {
                        "type": "pin_updated",
                        "conversation_id": conversation.id,
                        "message_id": (
                            message.id if message.is_pinned else None
                        ),
                        "is_pinned": message.is_pinned,
                        "pinned_at": (
                            message.pinned_at.isoformat()
                            if message.pinned_at else None
                        ),
                        "pinned_by": (
                            str(message.pinned_by)
                            if message.pinned_by else None
                        )
                    }
                )

            except Exception:
                logger.exception(
                    "Failed to broadcast pin update for message %s",
                    message.id
                )
                
        transaction.on_commit(broadcast_pin_update)

        return Response(
            {
                "message_id": message.id,
                "conversation_id": conversation.id,
                "action": action,
                "is_pinned": message.is_pinned,
                "pinned_at": message.pinned_at,
                "pinned_by": (
                    str(message.pinned_by)
                    if message.pinned_by else None
                )
            },
            status=status.HTTP_200_OK
        )
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from django.contrib.auth.models import AnonymousUser
from django.shortcuts import get_object_or_404

from .models import Conversation, Message, MessageRead
from .serializers import MessageSerializer
from django.utils import timezone

from django.db import transaction

from notifications.models import NotificationOutbox
from notifications.tasks import dispatch_pending_notification_outbox

import logging

logger = logging.getLogger(__name__)

@database_sync_to_async
def is_conversation_participant(conversation_id, user):
    return Conversation.objects.filter(
        id=conversation_id,
        participants=user
    ).exists()

@database_sync_to_async
def save_message(converation_id, user, content):
    with transaction.atomic():
        conversation = get_object_or_404(
            Conversation,
            id=converation_id
        )

        message = Message.objects.create(
            conversation=conversation,
            sender=user,
            content=content
        )

        # update conversation activity timestamp

        conversation.save(update_fields=["updated_at"])

        # find everyone else in this conversation
        recipient_ids = list(
            conversation.participants
            .exclude(id=user.id)
            .values_list("id", flat=True)
        )

        if recipient_ids:
            outbox = NotificationOutbox.objects.create(
                message=message,
                recipient_ids=recipient_ids
            )

            logger.info(
                "Created outbox event %s for WebSocket message %s",
                outbox.id,
                message.id
            )

        message_data = {
            "id": message.id,
            "conversation": conversation.id,
            "sender": str(message.sender),
            "content": message.content,
            "created_at": message.created_at.isoformat()
            }
        return {
            "message": message_data,
            "recipient_ids": recipient_ids
        }

@database_sync_to_async
def mark_messages_as_read(conversation_id, user):
    unread_messages = Message.objects.filter(
        conversation_id=conversation_id
    ).exclude(
        sender=user
    ).exclude(
        read_receipts__user=user
    )

    message_ids = list(
        unread_messages.values_list("id", flat=True)
    )

    read_records = [
        MessageRead(
            message_id=message_id,
            user=user
        )
        for message_id in message_ids
    ]

    MessageRead.objects.bulk_create(
        read_records,
        ignore_conflicts=True
    )

    return message_ids

@database_sync_to_async
def get_unread_message_count(conversation_id, user):
    return Message.objects.filter(
        conversation_id=conversation_id
    ).exclude(
        sender=user
    ).exclude(
        read_receipts__user=user
    ).count()

@database_sync_to_async
def get_missed_messages(conversation_id, user, last_message_id):
    # Confirm that the user belongs to this conversation.

    is_member = Conversation.objects.filter(
        id=conversation_id,
        participants=user
    ).exists()

    if not is_member:
        return None

    # Retrieve messages created after the client's last received message.

    messages = list(Message.objects.filter(
        conversation_id=conversation_id,
        id__gt=last_message_id
    ).select_related(
        "sender",
    ).order_by("id")[:101]
    )

    has_more = len(messages) > 100
    messages = messages[:100]

    serialized_messages = [
        {
            "id": message.id,
            "conversation": message.conversation_id,
            "sender": str(message.sender),
            "content": message.content,
            "created_at": message.created_at.isoformat()
        }
        for message in messages
    ]

    return {
        "messages": serialized_messages,
        "has_more": has_more
    }

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
    
    # Keep the rest of your existing code.
        self.user = self.scope["user"]
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"

        # reject unauthenticated users
        if isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        is_member = await is_conversation_participant(
            self.conversation_id,
            self.user
        )

        if not is_member:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        logger.info(
            "WebSocket connected: user=%s conversation=%s",
            self.user.id,
            self.conversation_id
        )

        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "conversation_id": self.conversation_id,
            "message": "Successfully connected to conversation"
        }))

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Invalid JSON format."
            }))
            return
        message_type = data.get("type", "message")

        if message_type == "sync":
            last_message_id = data.get("last_message_id", 0)

            if (
                not isinstance(last_message_id, int)
                or isinstance(last_message_id, bool)
                or last_message_id < 0
            ):
                await self.send(text_data=json.dumps({
                    "type": "error",
                    "message": "Invalid last_massage_id."
                }))

                return
            await self.sync_messages(last_message_id)
            return

        if message_type == "read":
            await self.mark_as_read()
            return

        if message_type == "typing":
            print("TYPING EVENT RECEIVED")
            is_typing = data.get("is_typing", False)

            if not isinstance(is_typing, bool):
                await self.send(text_data = json.dumps({
                    "type": "error",
                    "message": "Invalid typing status."
                }))

                return
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "typing_indicator",
                    "user": str(self.user),
                    "is_typing": is_typing
                }
            )

            return
        
        content = data.get("message", "")
        if not isinstance(content, str) or not content.strip():
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Message cannot be empty."
            }))
            return
        if len(content) > 5000:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Message exceeds 5000 characters."
            }))
            return
        # verify membership again before saving
        is_member = await is_conversation_participant(
            self.conversation_id,
            self.user
        )
        if not is_member:
            await self.close(code=4403)
            return

        saved = await save_message(
            self.conversation_id,
            self.user,
            content.strip()
        )

        #Broadcast the message to conversation participants
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": saved["message"]
            }
        )

        if saved["recipient_ids"]:
            try:
                dispatch_pending_notification_outbox.delay()
                logger.info(
                    "Notification outbox dispatcher triggered "
                    "for WebSocket message in conversation %s",
                    self.conversation_id
                )
            except Exception:
                logger.exception(
                    "Failed to trigger notification outbox dispatcher "
                    "for conversation %s",
                    self.conversation_id
                )

    async def sync_messages(self, last_message_id):
        result = await get_missed_messages(
            self.conversation_id,
            self.user,
            last_message_id
        )

        if result is None:
            await self.close(code=4403)
            return

        messages = result["messages"]

        next_cursor = (
            messages[-1]["id"]
            if messages
            else last_message_id
        )

        await self.send(text_data=json.dumps({
            "type": "sync_batch",
            "conversation_id": self.conversation_id,
            "messages": messages,
            "next_cursor": next_cursor,
            "has_more": result["has_more"]
        }))

    async def typing_indicator(self, event):
        print("BROADCASTING TYPING EVENT:", event)
        # dont send the typing indicator back to the sender
        if event["user"] == str(self.user):
            return
        
        await self.send(text_data=json.dumps({
            "type": "typing",
            "user": event["user"],
            "is_typing": event["is_typing"]
        }))

    async def chat_message(self, event):
        await self.send(text_data = json.dumps({
            "type": "chat_message",
            "message": event["message"]
        }))

    async def message_edited(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "message_edited",
                "message": event["message"]
            })
        )

    async def message_deleted(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "message_deleted",
                "message_id": event["message_id"],
                "conversation_id": self.conversation_id
            })
        )

    async def reaction_updated(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "reaction_updated",
                "message_id": event["message_id"],
                "conversation_id": event["conversation_id"],
                "reactions": event["reactions"]
            })
        )

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

            logger.info(
                "WebSocket disconnected: user=%s conversation=%s close_code=%s",
                self.user.id if hasattr(self, "user") else None,
                getattr(self, "conversation_id", None),
                close_code
            )

    async def mark_as_read(self):
        message_ids = await mark_messages_as_read(
            self.conversation_id,
            self.user
        )

        unread_count = await get_unread_message_count(
            self.conversation_id,
            self.user
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "read_receipt",
                "user": str(self.user),
                "conversation_id": self.conversation_id,
                "message_ids": message_ids,
                "count": len(message_ids),
                "unread_count": unread_count
            }
        )

    async def read_receipt(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "read_receipt",
                "user": event["user"],
                "conversation_id": event["conversation_id"],
                "message_ids": event["message_ids"],
                "count": event["count"],
                "unread_count": event["unread_count"]
            })
        )


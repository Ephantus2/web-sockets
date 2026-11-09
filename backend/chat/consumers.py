import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from django.contrib.auth.models import AnonymousUser
from django.shortcuts import get_object_or_404

from .models import Conversation, Message, MessageRead
from .serializers import MessageSerializer
from django.utils import timezone

from notifications.models import Notification
from django.db import transaction

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

        # create a notification for each recipient
        notifications = [
            Notification(
                recipient_id=recipient_id,
                sender=user,
                notification_type="MESSAGE",
                title=f"{user} sent you a message",
                message=content[:200],
                conversation=conversation
            )
            for recipient_id in recipient_ids
        ]

        Notification.objects.bulk_create(notifications)
    

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

    now = timezone.now()

    read_records = [
        MessageRead(
            message_id=message_id,
            user=user,
            read_at=now
        )
        for message_id in unread_messages.values_list(
            "id",
            flat=True
        )
    ]

    MessageRead.objects.bulk_create(
        read_records,
        ignore_conflicts=True
    )

    return len(read_records)

@database_sync_to_async
def get_unread_message_count(conversation_id, user):
    return Message.objects.filter(
        conversation_id=conversation_id
    ).exclude(
        sender=user
    ).exclude(
        read_receipts__user=user
    ).count()
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        print("\n========== WEBSOCKET DEBUG ==========")
        print("WEBSOCKET CONNECT CALLED")
        print("USER:", self.user)
        print("AUTHENTICATED:", self.user.is_authenticated)
        print("ORIGIN:", self.scope.get("headers"))
    
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
    
        print("CONVERSATION ID:", self.conversation_id)
        print("=====================================\n")

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

        if message_type == "read":
            await self.mark_as_read()
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
        message = await save_message(
            self.conversation_id,
            self.user,
            content.strip()
        )
        # broadcast the saved message to the group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message
            }
        )

    async def chat_message(self, event):
        await self.send(text_data = json.dumps({
            "type": "chat_message",
            "message": event["message"]
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

        print(f"WebSocket disconnected: {close_code}")

    async def mark_as_read(self):
        count = await mark_messages_as_read(
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
                "count": count,
                "unread_count": unread_count
            }
        )

    async def read_receipt(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "read_receipt",
                "user": event["user"],
                "conversation_id": event["conversation_id"],
                "count": event["count"],
                "unread_count": event["unread_count"]
            })
        )
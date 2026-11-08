import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from django.contrib.auth.models import AnonymousUser
from django.shortcuts import get_object_or_404

from .models import Conversation, Message
from .serializers import MessageSerializer

@database_sync_to_async
def is_conversation_participant(conversation_id, user):
    return Conversation.objects.filter(
        id=conversation_id,
        participants=user
    ).exists()

@database_sync_to_async
def save_message(converation_id, user, content):
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

    return {
        "id": message.id,
        "conversation": conversation.id,
        "sender": str(message.sender),
        "content": message.content,
        "created_at": message.created_at.isoformat()
        }

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
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
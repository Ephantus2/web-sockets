from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async

from channels.testing import WebsocketCommunicator

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings

from rest_framework_simplejwt.tokens import RefreshToken

from chat.models import Conversation, Message
from config.asgi import application

User = get_user_model()

@override_settings(
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    },
    ALLOWED_HOSTS=[
        "testserver",
        "localhost",
        "127.0.0.1"
    ]
)
class ChatConsumerTests(TransactionTestCase):

    def setUp(self):

        self.alice = User.objects.create_user(
            username="alice",
            password="testpassword123"
        )

        self.bob = User.objects.create_user(
            username="bob",
            password="testpassword123"
        )

        self.charlie = User.objects.create_user(
            username="charlie",
            password="testpassword123"
        )

        self.conversation = Conversation.objects.create(
            name="WebSocket Testing"
        )

        self.conversation.participants.add(
            self.alice,
            self.bob
        )

    def get_token(self, user):

        return str(
            RefreshToken.for_user(user).access_token
        )

    def test_authenticated_user_can_connect(self):
        token = self.get_token(self.alice)

        communicator = WebsocketCommunicator(
            application,
            f"/ws/chat/{self.conversation.id}/?token={token}",
            headers=[
                (b"origin", b"http://testserver")
            ]
        )

        async def run_test():
            connected, close_code = await communicator.connect()

            self.assertTrue(
                connected,
                f"Connection rejected. Close code: {close_code}"
            )

            response = await communicator.receive_json_from()

            self.assertEqual(
                response["type"],
                "connection_established"
            )

            self.assertEqual(
                int(response["conversation_id"]),
                self.conversation.id
            )

            await communicator.disconnect()

        async_to_sync(run_test)()

    def test_user_without_token_cannot_connect(self):
        communicator = WebsocketCommunicator(
            application,
            f"/ws/chat/{self.conversation.id}/",
            headers=[
                (b"origin", b"http://testserver")
            ]
        )

        async def run_test():
            connected, _ = await communicator.connect()

            self.assertFalse(connected)

        async_to_sync(run_test)()

    def test_non_participant_cannot_connect(self):
        token = self.get_token(self.charlie)

        communicator = WebsocketCommunicator(
            application,
            f"/ws/chat/{self.conversation.id}/?token={token}",
            headers=[
                (b"origin", b"http://testserver")
            ]
        )

        async def run_test():
            connected, _ = await communicator.connect()

            self.assertFalse(connected)

        async_to_sync(run_test)()

    @patch("chat.consumers.create_message_notifications.delay")
    def test_user_can_send_message(self, mock_notification_task):
        token = self.get_token(self.alice)

        communicator = WebsocketCommunicator(
            application,
            f"/ws/chat/{self.conversation.id}/?token={token}",
            headers=[
                (b"origin", b"http://testserver")
            ]
        )

        async def run_test():
            connected, close_code = await communicator.connect()

            self.assertTrue(
                connected,
                f"Connection rejected. Close code: {close_code}"
            )

            welcome = await communicator.receive_json_from()

            self.assertEqual(
                welcome["type"],
                "connection_established"
            )

            await communicator.send_json_to({
                "message": "Automated WebSocket test"
            })

            response = await communicator.receive_json_from()

            self.assertEqual(response["type"], "chat_message")

            self.assertEqual(
                response["message"]["content"],
                "Automated WebSocket test"
            )

            self.assertTrue(
                await self.message_exists()
            )

            mock_notification_task.assert_called_once()

            await communicator.disconnect()

        async_to_sync(run_test)()

    @database_sync_to_async
    def message_exists(self):
        return Message.objects.filter(
            conversation=self.conversation,
            content="Automated WebSocket test"
        ).exists()

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from rest_framework.test import APIClient

from chat.models import Conversation, Message
from notifications.models import Notification

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class ChatAPITests(TestCase):

    def setUp(self):
        # Create test users
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

        # Create a conversation
        self.conversation = Conversation.objects.create(
            name="Testing Conversation"
        )

        self.conversation.participants.add(
            self.alice,
            self.bob
        )

        # Initialize REST Framework API client
        self.client = APIClient()

    def test_authenticated_user_can_list_conversations(self):
        self.client.force_authenticate(user=self.alice)

        response = self.client.get("/api/conversation/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_non_participant_cannot_access_conversation(self):
        self.client.force_authenticate(user=self.charlie)

        response = self.client.get(
            f"/api/conversations/{self.conversation.id}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_user_can_retrieve_messages(self):
        Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Hello Bob"
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.get(
            f"/api/conversations/{self.conversation.id}/messages/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_non_participant_cannot_retrieve_messages(self):
        self.client.force_authenticate(user=self.charlie)

        response = self.client.get(
            f"/api/conversations/{self.conversation.id}/messages/"
        )

        self.assertEqual(response.status_code, 404)

    def test_message_history_is_paginated(self):
        for i in range(25):
            Message.objects.create(
                conversation=self.conversation,
                sender=self.alice,
                content=f"Test message {i}"
            )

        self.client.force_authenticate(user=self.alice)

        response = self.client.get(
            f"/api/conversations/{self.conversation.id}/messages/"
        )

        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])

    def test_unread_count_is_calculated_correctly(self):
        for i in range(3):
            Message.objects.create(
                conversation=self.conversation,
                sender=self.bob,
                content=f"Message {i}"
            )

        self.client.force_authenticate(user=self.alice)

        response = self.client.get(
            "/api/conversations/unread-counts/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["unread_count"], 3)

    def test_user_only_sees_their_own_notifications(self):
        Notification.objects.create(
            recipient=self.bob,
            sender=self.alice,
            notification_type="MESSAGE",
            title="Hello Bob",
            message="Testing notification privacy",
            conversation=self.conversation
        )

        self.client.force_authenticate(user=self.alice)

        response = self.client.get("/api/notifications/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_user_can_mark_own_notification_as_read(self):
        notification = Notification.objects.create(
            recipient=self.bob,
            sender=self.alice,
            notification_type="MESSAGE",
            title="Hello Bob",
            message="Testing read status",
            conversation=self.conversation
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.patch(
            f"/api/notifications/{notification.id}/read/",
            {},
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

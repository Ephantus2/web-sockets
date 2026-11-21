
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from rest_framework.test import APIClient

from chat.models import Conversation, Message, MessageReaction
from notifications.models import Notification, NotificationOutbox

from unittest.mock import mock_open, patch
from channels.layers import InMemoryChannelLayer

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

    def test_sending_message_creates_outbox_event(self):

        self.client.force_authenticate(user=self.alice)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/",
            {
                "content": "Testing transactional outbox"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 201)

        # verify message was created.

        message = Message.objects.get(
            content="Testing transactional outbox"
        )

        self.assertEqual(message.sender, self.alice)
        self.assertEqual(message.conversation, self.conversation)

        # verify corresponding outbox event was created.
        outbox = NotificationOutbox.objects.get(
            message=message
        )

        self.assertIsNone(outbox.dispatched_at)

        self.assertIsNone(outbox.completed_at)
        self.assertIsNone(outbox.failed_at)

    def test_non_participant_cannot_create_message(self):
        self.client.force_authenticate(user=self.charlie)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/",
            {
                "content": "Unauthorized"
            },
            format = "json"
        )

        self.assertEqual(response.status_code, 404)

        self.assertFalse(
            Message.objects.filter(
                content="Unautorized message"
            ).exists()
        )

        self.assertEqual(
            NotificationOutbox.objects.count(),
            0
        )

    def test_outbox_includes_all_recipients_except_sender(self):
        # Add charlie to the conversation

        self.conversation.participants.add(self.charlie)

        self.client.force_authenticate(user=self.alice)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/",
            {
                "content": "Hello everyone!"
            },
            format = "json"
        )

        self.assertEqual(response.status_code, 201)

        message = Message.objects.get(
            content="Hello everyone!"
        )

        outbox = NotificationOutbox.objects.get(message=message)

        self.assertCountEqual(
            outbox.recipient_ids,
            [self.bob.id, self.charlie.id]
        )

        self.assertNotIn(
            self.alice.id,
            outbox.recipient_ids
        )

    def test_invalid_message_does_not_create_outbox_event(self):
        self.client.force_authenticate(user=self.alice)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/",
            {
                "content": ""
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(NotificationOutbox.objects.count(), 0)

    def test_outbox_dispatcher_runs_after_transaction_commit(self):

        self.client.force_authenticate(user=self.alice)

        with patch(
            "chat.views.get_channel_layer",
            return_value=InMemoryChannelLayer()
        ), patch(
            "chat.views.dispatch_pending_notification_outbox.delay"
        ) as mock_dispatch:

            with self.captureOnCommitCallbacks(
                execute=True
            ) as callbacks:

                response = self.client.post(
                    f"/api/conversations/{self.conversation.id}/messages/",
                    {
                        "content": "Testing on_commit callback"
                    },
                    format="json"
                )

            self.assertEqual(response.status_code, 201)

            # Confirm that an on_commit callback was registered.
            self.assertEqual(len(callbacks), 1)

            # Confirm that the callback triggered the dispatcher.
            mock_dispatch.assert_called_once_with()

    def test_user_can_edit_own_message(self):
        # create a message owned by Alice.
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Original message"
        )

        self.client.force_authenticate(user=self.alice)

        # Edit the message.

        response = self.client.patch(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/",
            {
                "content": "Updated message"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        # Verify the response.

        self.assertEqual(response.data["content"], "Updated message")
        self.assertTrue(response.data["is_edited"])

        self.assertIsNotNone(response.data["edited_at"])

        # verify the database was updated.
        message.refresh_from_db()

        self.assertEqual(message.content, "Updated message")
        self.assertTrue(message.is_edited)
        self.assertIsNotNone(message.edited_at)

    def test_user_cannot_edit_another_users_message(self):
        message = Message.objects.create(
            conversation = self.conversation,
            sender = self.alice,
            content = "Alice's private message"
        )

        # Bob belongs to the conversation but does not own the message

        self.client.force_authenticate(user=self.bob)

        response = self.client.patch(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/",
            {
                "content": "Unauthorized edit"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 403)

        # Confirm the original message remains unchanged.

        message.refresh_from_db()

        self.assertEqual(message.content, "Alice's private message")
        self.assertFalse(message.is_edited)

    def test_user_can_delete_own_message(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Message to delete"
        )

        self.client.force_authenticate(user=self.alice)

        response = self.client.delete(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/"
        )

        self.assertEqual(response.status_code, 200)

        # verify the response

        self.assertTrue(response.data["is_deleted"])
        self.assertIsNotNone(response.data["deleted_at"])

        # verify soft deletion in the database

        message.refresh_from_db()

        self.assertTrue(message.is_deleted)
        self.assertIsNotNone(message.deleted_at)

        # The database row and original content should remain.
        self.assertEqual(message.content, "Message to delete")
        self.assertTrue(
            Message.objects.filter(id=message.id).exists()
        )

    def test_user_cannot_delete_another_users_message(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Alice's message"
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.delete(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/"

        )

        self.assertEqual(response.status_code, 403)

        # Verify the message was not deleted

        message.refresh_from_db()

        self.assertFalse(message.is_deleted)
        self.assertIsNone(message.deleted_at)
        self.assertEqual(message.content, "Alice's message")

    def test_deleted_message_cannot_be_edited(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Already deleted"
        )

        # Soft-delete the message.

        message.is_deleted = True

        from django.utils import timezone
        message.deleted_at = timezone.now()
        message.save()

        self.client.force_authenticate(user=self.alice)

        response = self.client.patch(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/",
            {
                "content": "Trying to edit deleted message"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)
        message.refresh_from_db()

        self.assertEqual(message.content, "Already deleted")
        self.assertTrue(message.is_deleted)

    def test_deleted_message_cannot_be_deleted_again(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Message to delete"
        )

        self.client.force_authenticate(user=self.alice)

        # first deletion shoud be successful

        first_response = self.client.delete(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/"
        )

        self.assertEqual(first_response.status_code, 200)

        # Second deletion should be rejected.

        second_response = self.client.delete(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/"
        )

        self.assertEqual(second_response.status_code, 400)
        message.refresh_from_db()

        self.assertTrue(message.is_deleted)

    def test_user_cannot_edit_message_with_empty_content(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Original message"
        )

        self.client.force_authenticate(user=self.alice)

        response = self.client.patch(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/",
            {
                "content": "   "
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)
        message.refresh_from_db()

        self.assertEqual(message.content, "Original message")
        self.assertFalse(message.is_edited)

    def test_non_participant_cannot_edit_or_delete_message(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Protected message"
        )

        self.client.force_authenticate(user=self.charlie)

        url = (
            f"/api/conversations/{self.conversation.id}"
            f"/messages/{message.id}/"
        )

        # charlie attempts to edit.

        edit_response = self.client.patch(
            url,
            {
                "content": "Unauthorized"
            },
            format="json"
        )

        self.assertEqual(edit_response.status_code, 404)

        # charlie attempts to delete

        delete_response = self.client.delete(url)

        self.assertEqual(delete_response.status_code, 404)

        # verify the message remains unchanged.

        message.refresh_from_db()

        self.assertEqual(message.content, "Protected message")
        self.assertFalse(message.is_edited)
        self.assertFalse(message.is_deleted)

    def test_unauthenticated_user_cannot_edit_or_delete_message(self):
        message = Message.objects.create(
            conversation = self.conversation,
            sender=self.alice,
            content="Protected message"
        )

        url = (
            f"/api/conversations/{self.conversation.id}"
            f"/messages/{message.id}/"
        )

        # Attempt to edit without authentication.

        edit_response = self.client.patch(
            url,
            {"content": "Unauthorized edit"},
            format= "json"
        )

        self.assertEqual(edit_response.status_code, 401)

        # Attempt to delete without authentication

        delete_response = self.client.delete(url)

        self.assertEqual(delete_response.status_code, 401)

        message.refresh_from_db()

        self.assertEqual(message.content, "Protected message")
        self.assertFalse(message.is_edited)
        self.assertFalse(message.is_deleted)

    def test_edit_message_broadcasts_websocket_event(self):
        message = Message.objects.create(
            conversation = self.conversation,
            sender=self.alice,
            content="Original message"
        )

        self.client.force_authenticate(user=self.alice)

        with patch(
            "chat.views.get_channel_layer",
            return_value=InMemoryChannelLayer()
        ), patch("chat.views.async_to_sync") as mock_async_to_sync:
            with self.captureOnCommitCallbacks(
                execute=True
            ) as callbacks:
                response = self.client.patch(
                    f"/api/conversations/{self.conversation.id}/messages/{message.id}/",
                    {
                        "content": "Edited message"
                    },
                    format = "json"
                )

        self.assertEqual(response.status_code, 200)

        # verify that the on_commit callback was registered

        self.assertEqual(len(callbacks), 1)

        # verify that the broadcast function was invoked

        mock_async_to_sync.assert_called_once()

        group_send = mock_async_to_sync.return_value

        group_send.assert_called_once()

        # Inspect the broadcast arguments

        args, kwargs = group_send.call_args

        self.assertEqual(
            args[0],
            f"chat_{self.conversation.id}"
        )

        self.assertEqual(
            args[1]["type"],
            "message_edited"
        )

        self.assertEqual(
            args[1]["message"]["content"],
            "Edited message"
        )

    def test_delete_message_broadcasts_websocket_event(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender = self.alice,
            content="Message to delete"
        )

        self.client.force_authenticate(user=self.alice)

        with patch(
            "chat.views.get_channel_layer",
            return_value=InMemoryChannelLayer()
        ), patch("chat.views.async_to_sync") as mock_async_to_sync:
            with  self.captureOnCommitCallbacks(
                execute=True
            ) as callbacks:
                response = self.client.delete(
                    f"/api/conversations/{self.conversation.id}/messages/{message.id}/"
                )

        self.assertEqual(response.status_code, 200)

        # verify transaction callback registration.

        self.assertEqual(len(callbacks), 1)

        # verify groupsend was called once

        mock_async_to_sync.assert_called_once()

        group_send = mock_async_to_sync.return_value

        group_send.assert_called_once()

        args, kwargs = group_send.call_args

        self.assertEqual(
            args[1]["type"], "message_deleted"
        )

        self.assertEqual(
            args[1]["message_id"],
            message.id
        )

    def test_user_can_react_to_message(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Hello Bob"
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/reactions/",
            {
                "emoji": "🔥"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data["action"], "added")

        # verify the reaction existts in the database

        reaction = MessageReaction.objects.get(
            message=message,
            user=self.bob,
            emoji="🔥"
        )

        self.assertEqual(reaction.user, self.bob)

        # verify the API returned the reaction.

        self.assertEqual(len(response.data["reactions"]), 1)

        self.assertEqual(response.data["reactions"][0]["emoji"], "🔥")

    def test_user_can_remove_own_reaction(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Hello Bob"
        )

        self.client.force_authenticate(user=self.bob)

        url = (
            f"/api/conversations/{self.conversation.id}"
            f"/messages/{message.id}/reactions/"
        )

        # first request: Add reaction.

        first_response = self.client.post(
            url,
            {"emoji": "🔥"},
            format="json"
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.data["action"], "added")

        # Second Request: Remove te same reaction

        second_response = self.client.post(
            url,
            {"emoji": "🔥"},
            format="json"
        )

        self.assertEqual(second_response.status_code, 200)

        self.assertEqual(second_response.data["action"], "removed")

        # verify reaction was removed from the database.

        self.assertFalse(
            MessageReaction.objects.filter(
                message=message,
                user=self.bob,
                emoji="🔥"
            ).exists()
        )
        self.assertEqual(len(second_response.data["reactions"]), 0)

    def test_non_participant_cannot_react_to_message(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Protected message"
        )

        self.client.force_authenticate(user=self.charlie)

        response = self.client.post(
            f"/api/conversation/{self.conversation.id}/messages/{message.id}/reactions/",
            {
                "emoji": "🔥"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 404)

        # verify no reaction was created.

        self.assertEqual(
            MessageReaction.objects.filter(
                message=message
            ).count(),
            0
        )

    def test_deleted_message_cannot_receive_reactions(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Deleted message",
            is_deleted=True
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/reactions/",
            {
                "emoji": "🔥"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(MessageReaction.objects.filter(
            message=message
        ).count(), 0)

    def test_invalid_reaction_emoji_is_rejected(self):
        message = Message.objects.create(
            conversation = self.conversation,
            sender=self.alice,
            content="Hello Bob"
        )

        self.client.force_authenticate(user=self.bob)

        url = (
            f"/api/conversations/{self.conversation.id}"
            f"/messages/{message.id}/reactions/"
        )

        invalid_values = [
            {},
            {"emoji": ""},
            {"emoji": "  "},
            {"emoji": "🔥" * 33},
        ]

        for payload in invalid_values:
            response = self.client.post(
                url,
                payload,
                format="json"
            )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            MessageReaction.objects.filter(
                message=message
            ).count(), 0
        )

    def test_reaction_broadcasts_websocket_event(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Hello Bob"
        )

        self.client.force_authenticate(user=self.bob)

        with patch(
            "chat.views.get_channel_layer",
            return_value = InMemoryChannelLayer()
        ), patch(
            "chat.views.async_to_sync"
        ) as mock_async_to_sync:
            with self.captureOnCommitCallbacks(
                execute=True
            ) as callbacks:
                response = self.client.post(
                    f"/api/conversations/{self.conversation.id}/messages/{message.id}/reactions/",
                    {"emoji": "🔥"},
                    format="json"
                )

        self.assertEqual(len(callbacks), 1)

        self.assertEqual(response.status_code, 200)

        # verify the broadcast function was called

        mock_async_to_sync.assert_called_once()

        group_send = mock_async_to_sync.return_value

        group_send.assert_called_once()

        args, kwargs = group_send.call_args

        # verify the destination conversation group

        self.assertEqual(
            args[0],
            f"chat_{self.conversation.id}"
        )

        # verify the event type.

        self.assertEqual(
            args[1]["type"],
            "reaction_updated"
        )

        # verify the message ID

        self.assertEqual(
            args[1]["message_id"],
            message.id
        )

        # Verify the reaction payload.

        self.assertEqual(
            args[1]["reactions"][0]["emoji"], "🔥"
        )
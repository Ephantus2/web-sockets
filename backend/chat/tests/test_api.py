
from turtle import forward

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from rest_framework.test import APIClient

from chat.models import Conversation, Message, MessageEditHistory, MessageReaction, MessageBookmark
from notifications.models import Notification, NotificationOutbox

from unittest.mock import mock_open, patch
from channels.layers import InMemoryChannelLayer
from django.utils import timezone


from asgiref.sync import async_to_sync

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

    def test_user_can_pin_message(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Important announcement"
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/pin/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["action"], "pinned")
        self.assertTrue(response.data["is_pinned"])

        # verify database persistence

        message.refresh_from_db()

        self.assertTrue(message.is_pinned)
        self.assertEqual(message.pinned_by, self.bob)
        self.assertIsNotNone(message.pinned_at)

    def test_user_can_unpin_message(self):
        message = Message.objects.create(
            conversation = self.conversation,
            sender=self.alice,
            content="Important announcement",
            is_pinned=True,
            pinned_by=self.bob,
            pinned_at=timezone.now()
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/pin/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["action"], "unpinned")
        self.assertFalse(response.data["is_pinned"])

        message.refresh_from_db()

        self.assertFalse(message.is_pinned)

        self.assertIsNone(message.pinned_by)
        self.assertIsNone(message.pinned_at)

    def test_pinning_another_message_replaces_previous_pin(self):
        first_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="First message",
            is_pinned=True,
            pinned_by=self.bob,
            pinned_at=timezone.now()
        )

        second_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Second message"
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{second_message.id}/pin/"
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data["action"], "pinned")

        first_message.refresh_from_db()
        second_message.refresh_from_db()

        self.assertFalse(first_message.is_pinned)
        self.assertTrue(second_message.is_pinned)

        self.assertEqual(
            Message.objects.filter(
                conversation=self.conversation,
                is_pinned=True
            ).count(),
            1
        )

    def test_non_participant_cannot_pin_message(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Protected message"
        )

        self.client.force_authenticate(user=self.charlie)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/pin/"
        )

        self.assertEqual(response.status_code, 404)

        message.refresh_from_db()

        self.assertFalse(message.is_pinned)

    def test_deleted_message_cannot_be_pinned(self):
        message = Message.objects.create(
            conversation = self.conversation,
            sender=self.alice,
            content="Deleted message",
            is_deleted=True
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/pin/"
        )

        self.assertEqual(response.status_code, 400)

        message.refresh_from_db()

        self.assertFalse(message.is_pinned)

    def test_pin_broadcasts_websocket_event(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Important announcement"
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
                    f"/api/conversations/{self.conversation.id}/messages/{message.id}/pin/"
                )

        self.assertEqual(len(callbacks), 1)
        self.assertEqual(response.status_code, 200)

        # verify broadcast was triggered

        mock_async_to_sync.assert_called_once()

        group_send = mock_async_to_sync.return_value

        group_send.assert_called_once()

        args, kwargs = group_send.call_args

        # verify destination

        self.assertEqual(
            args[0],
            f"chat_{self.conversation.id}"
        )

        # verify event type

        self.assertEqual(
            args[1]["type"],
            "pin_updated"
        )

        # verify pinned message ID

        self.assertEqual(
            args[1]["message_id"],
            message.id
        )

        self.assertTrue(args[1]["is_pinned"])

    def test_user_can_forward_message_to_another_conversation(self):
        # Create the original message in the source conversation

        original_message = Message.objects.create(
            conversation = self.conversation,
            sender = self.alice,
            content = "Important project announcement"
        )

        # create a destination conversation

        destination = Conversation.objects.create(
            name="Destination Conversation"
        )

        destination.participants.add(
            self.bob,
            self.charlie
        )

        # Bob forwards Alice's message

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{original_message.id}/forward/",
            {
                "destination_conversation_ids": [destination.id]
            },
            format="json"
        )

        # Verify the API response
        print("\nSTATUS:", response.status_code)
        print("\nRESPONSE DATA:", response.data)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["forwarded_count"], 1)

        forwarded_data = response.data["messages"][0]

        self.assertEqual(
            forwarded_data["content"],
            "Important project announcement"
        )

        self.assertEqual(
            forwarded_data["sender"],
            str(self.bob)
        )

        self.assertEqual(
            forwarded_data["forwarded_from"],
            original_message.id
        )

        self.assertEqual(
            forwarded_data["forwarded_by"],
            str(self.bob)
        )

        self.assertEqual(
            forwarded_data["forwarded_sender"],
            str(self.alice)
        )



    def test_non_participant_cannot_forward_message(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Private message"
        )

        destination = Conversation.objects.create(
            name="Destination"
        )

        destination.participants.add(self.charlie)

        self.client.force_authenticate(user=self.charlie)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/forward/",
            {"destination_conversation_id": destination.id},
            format="json"
        )

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_forward_to_non_member_conversation(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Important message"
        )

        destination = Conversation.objects.create(
            name="Private destination"
        )

        destination.participants.add(self.charlie)

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/forward/",
            {"destination_conversation_ids": [destination.id]},
            format="json"
        )

        self.assertEqual(response.status_code, 404)


    def test_deleted_message_cannot_be_forwaded(self):
        message = Message.objects.create(
            conversation = self.conversation,
            sender=self.alice,
            content="Deleted message",
            is_deleted=True
        )

        destination = Conversation.objects.create(
            name="Destination"
        )

        destination.participants.add(self.bob)

        self.client.force_authenticate(user=self.bob)

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/forward/",
            {
                "destination_conversation_id": destination.id
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_forward_message_requires_destination(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Important message"
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/forward/",
            {},
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_user_can_forward_message_to_multiple_conversations(self):

        # create original message

        original_message = Message.objects.create(
            conversation = self.conversation,
            sender=self.alice,
            content="Important project announcement"
        )

        # Create first destination

        destination_one = Conversation.objects.create(
            name="Destination One"
        )

        destination_one.participants.add(
        self.bob
        )

        # Create second destination

        destination_two = Conversation.objects.create(
            name="Destination Two"
        )

        destination_two.participants.add(self.bob)

        # Authenticate Bob

        self.client.force_authenticate(user=self.bob)

        # Forward to both conversations

        response = self.client.post(
            f"/api/conversations/{self.conversation.pk}/messages/{original_message.pk}/forward/",
            {
                "destination_conversation_ids":
                [
                    destination_one.id,
                    destination_two.id
                ]
            },
            format="json"
        )

        # verify response

        self.assertEqual(response.status_code, 201)

        self.assertEqual(response.data["forwarded_count"], 2)
        self.assertEqual(len(response.data["messages"]), 2)

        # verify both messages were created

        self.assertEqual(
            Message.objects.filter(
                forwarded_from=original_message,
                forwarded_by=self.bob
            ).count(), 2
        )

        # verify each destination received a copy

        self.assertEqual(
            Message.objects.filter(
                conversation=destination_two,
                forwarded_from=original_message
            ).count(),
            1
        )

    def test_duplicate_destination_ids_are_rejected(self):
        original_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Important project announcement"
        )

        destination = Conversation.objects.create(
            name="Destination"
        )

        destination.participants.add(self.bob)

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{original_message.id}/forward/",
            {
                "destination_conversation_ids": [
                    destination.id,
                    destination.id
                ]
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["error"],
            "Duplicate destination IDs are not allowed."
        )

        self.assertEqual(
            Message.objects.filter(
                forwarded_from=original_message
            ).count(), 0
        )

    def test_user_cannot_forward_to_unauthorized_destinations(self):
        original_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Important project announcement"
        )

        # Bob is not a participant in this conversation

        destination = Conversation.objects.create(
            name="Private Conversation"
        )

        destination.participants.add(self.alice, self.charlie)

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{original_message.id}/forward/",
            {
                "destination_conversation_ids": [destination.id]
            },
            format="json"
        )

        self.assertEqual(response.status_code, 404)

        self.assertEqual(
            response.data["error"],
            "One or more destination conversations were not found."
        )

        self.assertEqual(
            Message.objects.filter(
                forwarded_from=original_message
            ).count(),
            0
        )

    def test_empty_destination_list_is_rejected(self):
        original_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Important project announcement"
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(
            f"/api/conversations/{self.conversation.pk}/messages/{original_message.pk}/forward/",
            {
                "destination_conversation_ids": []
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["error"],
            "Provide at least one destination conversation ID."
        )

    def test_non_integer_destination_id_is_rejected(self):
        original_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Important project announcement"
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/{original_message.id}/forward/",

            {
                "destination_conversation_ids": ["invalid"]
            },
            format="json"
        )


        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            response.data["error"],
            "All destination IDs must be integers."
        )
    
    def test_forwarded_message_broadcasts_websocket_event(self):
    
        # Create original message
        original_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Important announcement"
        )
    
        # Create destination conversation
        destination = Conversation.objects.create(
            name="destination"
        )
        destination.participants.add(self.bob, self.charlie)
    
        # Authenticate Bob
        self.client.force_authenticate(user=self.bob)
    
        with patch(
            "chat.views.get_channel_layer",
            return_value=InMemoryChannelLayer()
        ), patch(
            "chat.views.async_to_sync"
        ) as mock_async_to_sync:
    
            with self.captureOnCommitCallbacks(
                execute=True
            ) as callbacks:
    
                response = self.client.post(
                    f"/api/conversations/{self.conversation.id}/messages/{original_message.id}/forward/",
                    {
                        "destination_conversation_ids": [destination.id]
                    },
                    format="json"
                )
    
            # The callback has now executed
    
            self.assertEqual(len(callbacks), 1)
    
            # Verify API response
            self.assertEqual(response.status_code, 201)
    
            # Verify broadcast was triggered
            mock_async_to_sync.assert_called_once()
    
            group_send = mock_async_to_sync.return_value
            group_send.assert_called_once()
    
            args, kwargs = group_send.call_args
    
            # Verify destination conversation
            self.assertEqual(
                args[0],
                f"chat_{destination.id}"
            )
    
            # Verify event type
            self.assertEqual(
                args[1]["type"],
                "chat_message"
            )
    
            # Verify forwarded message content
            self.assertEqual(
                args[1]["message"]["content"],
                "Important announcement"
            )
    
            # Verify forwarding attribution
            self.assertEqual(
                args[1]["message"]["forwarded_from"],
                original_message.id
            )
    def test_user_can_reply_to_message(self):
        original = Message.objects.create(
            conversation=self.conversation,
            sender=self.bob,
            content="Original message"
        )

        self.client.force_authenticate(user=self.alice)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/",
            {
                "content": "This is a reply",
                "reply_to": original.id
            },
            format="json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["reply_to"], original.id)
        self.assertEqual(response.data["reply_sender"], self.bob.username)
        self.assertEqual(response.data["reply_content"], "Original message")

        reply = Message.objects.get(id=response.data["id"])

        self.assertEqual(reply.reply_to, original)
        self.assertEqual(reply.sender, self.alice)

    def test_user_cannot_reply_to_message_in_another_conversation(self):
        other_conversation = Conversation.objects.create()

        other_conversation.participants.add(
            self.alice,
            self.bob
        )

        original = Message.objects.create(
            conversation=other_conversation,
            sender=self.bob,
            content="Message from another conversation"
        )

        self.client.force_authenticate(user=self.alice)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/",
            {
                "content": "Invalid reply",
                "reply_to": original.id
            },
            format="json"
        )

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_reply_to_deleted_message(self):
        original = Message.objects.create(
            conversation=self.conversation,
            sender=self.bob,
            content="Deleted message",
            is_deleted=True
        )

        self.client.force_authenticate(user=self.alice)

        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/",
            {
                "content": "Reply to deleted message",
                "reply_to": original.id
            },
            format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_user_can_edit_own_message_and_save_history(self):
        original = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Original message"
        )

        self.client.force_authenticate(user=self.alice)

        response = self.client.patch(
            f"/api/conversations/{self.conversation.id}/messages/{original.id}/",
            {
                "content": "Updated message"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["content"], "Updated message")
        self.assertTrue(response.data["is_edited"])

        original.refresh_from_db()

        self.assertEqual(original.content, "Updated message")
        self.assertTrue(original.is_edited)
        self.assertIsNotNone(original.edited_at)

        history = MessageEditHistory.objects.get(message=original)

        self.assertEqual(history.previous_content, "Original message")
        self.assertEqual(history.edited_by, self.alice)

    def test_editing_message_without_changes_does_not_create_history(self):
        original = Message.objects.create(
            conversation=self.conversation,
            sender = self.alice,
            content = "Same message"
        )

        self.client.force_authenticate(user=self.alice)

        response = self.client.patch(
            f"/api/conversations/{self.conversation.id}/messages/{original.id}/",
            {
                "content": "Same message"
            },
            format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(MessageEditHistory.objects.filter(message=original).count(), 0)

        original.refresh_from_db()
        self.assertFalse(original.is_edited)

    def test_user_can_delete_message_for_themselves(self):
        self.client.force_authenticate(user=self.alice)

        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.bob,
            content="A message to hide"
        )

        response = self.client.delete(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/",
            {"delete_for": "me"},
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        message.refresh_from_db()

        self.assertFalse(message.is_deleted)
        self.assertTrue(
            message.deleted_for.filter(id=self.alice.id)
        )

    def test_sender_can_delete_message_for_everyone(self):
        self.client.force_authenticate(user=self.alice)

        message = Message.objects.create(
            conversation = self.conversation,
            sender=self.alice,
            content="This message will be deleted for everyone"
        )

        response = self.client.delete(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/",
            {"deleted_for": "everyone"},
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        message.refresh_from_db()
        self.assertTrue(message.is_deleted)
        self.assertIsNotNone(message.deleted_at)

    def test_user_cannot_delete_another_users_message_for_everyone(self):
        self.client.force_authenticate(user=self.alice)

        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.bob,
            content="This belongs to another user"
        )

        response = self.client.delete(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/",
            {"delete_for": "everyone"},
            format="json"
        )

        self.assertEqual(response.status_code, 403)

        message.refresh_from_db()

        self.assertFalse(message.is_deleted)

    def test_delete_for_me_does_not_affect_other_participants(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.bob,
            content="Only one user should hide this"
        )

        self.client.force_authenticate(user=self.alice)

        response = self.client.delete(
            f"/api/conversations/{self.conversation.id}/messages/{message.id}/",
            {"delete_for": "me"},
            format="json"
        )

        self.assertEqual(response.status_code, 200)

        message.refresh_from_db()

        # Alice has hidden the message.

        self.assertTrue(
            message.deleted_for.filter(id=self.alice.id).exists()
        )

        # Bob has not hidden the message.

        self.assertFalse(
            message.deleted_for.filter(id=self.bob.id).exists()
        )

        # the message remains globally available

        self.assertFalse(message.is_deleted)

    def test_search_messages_by_date_range(self):
        from django.utils import timezone
        from datetime import timedelta

        old_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Project meeting"
        )

        Message.objects.filter(id=old_message.id).update(
            created_at=timezone.now() - timedelta(days=30)
        )

        recent_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Project meeting"
        )

        self.client.force_authenticate(user=self.alice)

        response = self.client.get(
            f"/api/conversations/{self.conversation.id}/messages/search/",
            {
                "q": "meeting",
                "date_from": (timezone.now() - timedelta(days=7)).date().isoformat()
            }
        )

        self.assertEqual(response.status_code, 200)
        returned_ids = [item["id"] for item in response.data["results"]]

        self.assertIn(recent_message.id, returned_ids)
        self.assertNotIn(old_message.id, returned_ids)

    def test_search_excludes_deleted_messages(self):
        message = Message.objects.create(
                conversation=self.conversation,
                sender=self.alice,
                content="Important project meeting"
        )

        message.is_deleted = True
        
        message.save(update_fields=["is_deleted"])

        self.client.force_authenticate(user=self.alice)

        response = self.client.get(
            f"/api/conversations/{self.conversation.id}/messages/search/",
            {"q": "meeting"}
        )

        self.assertEqual(response.status_code, 200)

        returned_ids = [item["id"] for item in response.data["results"]]

        self.assertNotIn(message.id, returned_ids)

    def test_user_can_bookmark_a_message(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Message to bookmark"
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.post(f"/api/messages/{message.id}/bookmark/")

        self.assertEqual(response.status_code, 201)

        # verify the bookmark was saved for Bob.

        bookmark = MessageBookmark.objects.get(
            user=self.bob,
            message=message
        )

        self.assertEqual(bookmark.user, self.bob)
        self.assertEqual(bookmark.message, message)

    def test_user_cannot_create_duplicate_bookmarks(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Message to bookmark"
        )

        self.client.force_authenticate(user=self.bob)

        url = f"/api/messages/{message.id}/bookmark/"

        first_response = self.client.post(url)
        second_response = self.client.post(url)

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)

        self.assertEqual(
            MessageBookmark.objects.filter(
                user=self.bob,
                message=message
            ).count(),
            1
        )

    def test_user_only_sees_own_bookmarks(self):
        message1 = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="First bookmarked message"
        )

        message2 = Message.objects.create(
            conversation=self.conversation,
            sender=self.bob,
            content="Second bookmarked message"
        )

        MessageBookmark.objects.create(
            user=self.bob,
            message=message1
        )

        MessageBookmark.objects.create(
            user=self.alice,
            message=message2
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.get("/api/bookmarks/")

        self.assertEqual(response.status_code, 200)

        returned_ids = [
            message["id"] for message in response.data
        ]

        self.assertIn(message1.id, returned_ids)
        self.assertNotIn(message2.id, returned_ids)

    def test_user_can_remove_bookmark(self):
        message = Message.objects.create(
            conversation = self.conversation,
            sender = self.alice,
            content = "Message to remove from bookmarks"
        )

        MessageBookmark.objects.create(
            user=self.bob,
            message=message
        )

        self.client.force_authenticate(user=self.bob)

        response = self.client.delete(
            f"/api/messages/{message.id}/bookmark/"
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            MessageBookmark.objects.filter(
                user=self.bob,
                message=message
            ).exists()
        )

    def test_unauthenticated_user_cannot_access_bookmarks(self):
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/bookmarks/")

        self.assertEqual(response.status_code, 401)
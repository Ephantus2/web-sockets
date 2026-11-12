from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from config.settings import CHANNEL_LAYERS
from chat.models import Conversation, Message
from notifications.models import Notification, NotificationOutbox
from notifications.tasks import create_message_notifications, dispatch_pending_notification_outbox

from unittest.mock import patch
from notifications.tasks import dispatch_pending_notification_outbox

from datetime import timedelta
from django.utils import timezone

User = get_user_model()

@override_settings(
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }
)
class NotificationOutboxTests(TestCase):
    def setUp(self):
        #create users
        self.alice = User.objects.create_user(
            username="alice",
            password="testpassword123"
        )
        self.bob = User.objects.create_user(
            username="bob",
            password="testpassword123"
        )

        # create conversation
        self.conversation = Conversation.objects.create(
            name="Notification Testing"
        )
        self.conversation.participants.add(
            self.alice,
            self.bob
        )
        #create message
        self.message = Message.objects.create(
            conversation=self.conversation,
            sender=self.alice,
            content="Hello Bob, testing notifications!"
        )

        # create outbox event
        self.outbox = NotificationOutbox.objects.create(
            message=self.message,
            recipient_ids=[self.bob.id]
        )

    def test_notification_is_created_successfully(self):
        result = create_message_notifications(
            self.message.id,
            [self.bob.id],
            self.outbox.id
        )
        self.assertEqual(result, 1)

        notification = Notification.objects.get(
            recipient=self.bob,
            source_message=self.message
        )

        self.assertEqual(notification.sender, self.alice)
        self.assertEqual(notification.notification_type, "MESSAGE")

        self.outbox.refresh_from_db()

        self.assertIsNotNone(self.outbox.completed_at)
        self.assertIsNone(self.outbox.failed_at)

    def test_duplicate_task_does_not_create_duplicate_notifications(self):
        #first execution
        create_message_notifications(
            self.message.id,
            [self.bob.id],
            self.outbox.id
        )

        # second execution with the same message

        create_message_notifications(
            self.message.id,
            [self.bob.id],
            self.outbox.id
        )

        notification_count = Notification.objects.filter(
            recipient=self.bob,
            source_message=self.message
        ).count()

        self.assertEqual(notification_count, 1)

    @patch(
        "notifications.tasks.create_message_notifications.delay"
    )
    def test_pending_outbox_event_is_dispatched(self, mock_delay):
        result = dispatch_pending_notification_outbox()
        self.assertEqual(result, 1)

        mock_delay.assert_called_once_with(
            self.message.id,
            [self.bob.id],
            self.outbox.id
        )

        self.outbox.refresh_from_db()

        self.assertEqual(self.outbox.attempts, 1)
        self.assertIsNotNone(self.outbox.dispatched_at)
        self.assertIsNone(self.outbox.completed_at)
        self.assertEqual(self.outbox.last_error, "")

    @patch(
        "notifications.tasks.create_message_notifications.delay"
    )
    def test_dispatch_failure_is_recorded(self, mock_delay):
        # simulate broker failure
        mock_delay.side_effect = Exception(
            "Redis broker unavailable"
        )

        result = dispatch_pending_notification_outbox()

        self.assertEqual(result, 0)
        self.outbox.refresh_from_db()

        self.assertEqual(self.outbox.attempts, 1)
        self.assertIsNone(self.outbox.dispatched_at)
        self.assertIsNone(self.outbox.completed_at)
        self.assertIn(
            "Redis broker unavailable",
            self.outbox.last_error
        )
    @patch(
        "notifications.tasks.create_message_notifications.delay"
    )
    def test_exhausted_event_is_moved_to_dead_letter(self, mock_delay):
        #simulate an event that has exhausted all attempts.

        self.outbox.attempts = 10
        self.outbox.dispatched_at = (
            timezone.now() - timedelta(minutes=3)
        )

        self.outbox.save(
            update_fields=["attempts", "dispatched_at"]
        )

        result = dispatch_pending_notification_outbox()
        self.assertEqual(result, 0)
        self.outbox.refresh_from_db()

        self.assertIsNotNone(self.outbox.failed_at)

        self.assertIsNone(self.outbox.completed_at)
        self.assertEqual(self.outbox.attempts, 10)

        self.assertIn(
            "Maximum dispatch attempts (10) reached",
            self.outbox.last_error
        )

        mock_delay.assert_not_called()

    @patch(
        "notifications.tasks.create_message_notifications.delay"
    )
    def test_completed_event_is_not_dispatched(self, mock_delay):
        self.outbox.completed_at = timezone.now()

        self.outbox.save(
            update_fields=["completed_at"]
        )
        result = dispatch_pending_notification_outbox()

        self.assertEqual(result, 0)
        mock_delay.assert_not_called()
        self.outbox.refresh_from_db()

        self.assertIsNotNone(self.outbox.completed_at)
        self.assertEqual(self.outbox.attempts, 0)

    @patch(
        "notifications.tasks.create_message_notifications.delay"
    )
    def test_dispatcher_respects_batch_size(self, mock_delay):

        # Create two additional messages and outbox events.
        for i in range(2):
            message = Message.objects.create(
                conversation=self.conversation,
                sender=self.alice,
                content=f"Batch testing message {i}"
            )

            NotificationOutbox.objects.create(
                message=message,
                recipient_ids=[self.bob.id]
            )

        result = dispatch_pending_notification_outbox(
            batch_size=2
        )

        self.assertEqual(result, 2)

        self.assertEqual(mock_delay.call_count, 2)

    @patch(
        "notifications.tasks.create_message_notifications.delay"
    )
    def test_stale_dispatched_event_is_retried(self, mock_delay):
        # simulate a task dispatched three minutes age

        self.outbox.dispatched_at = (
            timezone.now() - timedelta(minutes=3)
        )

        self.outbox.attempts = 1

        self.outbox.save(
            update_fields=["dispatched_at", "attempts"]
        )

        result = dispatch_pending_notification_outbox()

        self.assertEqual(result, 1)
        mock_delay.assert_called_once_with(
            self.message.id,
            [self.bob.id],
            self.outbox.id
        )

        self.outbox.refresh_from_db()

        self.assertEqual(self.outbox.attempts, 2)
        self.assertIsNotNone(self.outbox.dispatched_at)
        self.assertIsNone(self.outbox.completed_at)
        self.assertIsNone(self.outbox.failed_at)

    @patch(
        "notifications.tasks.get_channel_layer",
        return_value=None
    )
    def test_outbox_is_not_completed_when_channel_layer_fails(self, mock_channel_layer):
        with self.assertRaises(RuntimeError):
            create_message_notifications(
                self.message.id,
                [self.bob.id],
                self.outbox.id
            )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.bob,
                source_message=self.message
            ).exists()
        )

        self.outbox.refresh_from_db()

        self.assertIsNone(self.outbox.completed_at)
        self.assertIsNone(self.outbox.failed_at)
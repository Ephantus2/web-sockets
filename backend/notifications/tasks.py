from celery import shared_task
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from chat.models import Message
from .models import Notification

User = get_user_model()

@shared_task
def create_message_notifications(message_id, recipient_ids):
    message = Message.objects.select_related(
        "sender",
        "conversation"
    ).get(id=message_id)

    recipients = User.objects.filter(
        id__in=recipient_ids
    )

    notifications = []

    for recipient in recipients:
        notification = Notification(
            recipient=recipient,
            sender=message.sender,
            notification_type="MESSAGE",
            title=f"{message.sender} sent you a message",
            message=message.content[:200],
            conversation=message.conversation
        )
        notifications.append(notification)
        created_notifications = Notification.objects.bulk_create(
            notifications
        )

        channel_layer = get_channel_layer()

    for notification in created_notifications:
        event = {
            "id": notification.id,
            "sender": str(message.sender),
            "notification_type": notification.notification_type,
            "title": notification.title,
            "message": notification.message,
            "conversation": message.conversation_id,
            "is_read": notification.is_read,
            "created_at": notification.created_at.isoformat()
        }

    async_to_sync(channel_layer.group_send)(
        f"user_{notification.recipient_id}_notifications",
        {
            "type": "notification_message",
            "notification": event
        }
    )

    return len(created_notifications)
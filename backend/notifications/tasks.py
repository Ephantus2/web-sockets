from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from chat.models import Message
from .models import Notification, NotificationOutbox

import logging

logger = logging.getLogger(__name__)

User = get_user_model()

@shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_backoff=True,
        retry_backoff_max=600,
        retry_jitter=True,
        max_retries=5,
)
def create_message_notifications(self, message_id, recipient_ids, outbox_id=None):
    message = Message.objects.select_related(
        "sender",
        "conversation"
    ).get(id=message_id)

    notifications = []

    with transaction.atomic():
        for recipient in User.objects.filter(id__in=recipient_ids):
            notification, created = Notification.objects.get_or_create(
                recipient=recipient,
                source_message=message,
                defaults={
                    "sender": message.sender,
                    "notification_type": "MESSAGE",
                    "title": f"{message.sender} sent you a message",
                    "message": message.content[:200],
                    "conversation": message.conversation,

                }

            )
            notifications.append(notification)


    channel_layer = get_channel_layer()

    if channel_layer is None:
        raise RuntimeError("Could not connect to the channel layer.")

    for notification in notifications:
        event = {
            "id": notification.id,
            "sender": str(notification.sender),
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

    if outbox_id is not None:
        NotificationOutbox.objects.filter(
            id=outbox_id,
            completed_at__isnull=True,
            failed_at__isnull=True
        ).update(
            completed_at=timezone.now()
        )

        logger.info(
            "Outbox event %s completed successfully.",
            outbox_id
        )

    return len(notifications)

@shared_task
def dispatch_pending_notification_outbox(batch_size=50):

    retry_before = timezone.now() - timedelta(minutes=2)

    # STEP 1: Move exhausted events into the dead-letter state.
    failed_count = (
        NotificationOutbox.objects
        .filter(
            completed_at__isnull=True,
            failed_at__isnull=True,
            attempts__gte=10
        )
        .filter(
            Q(dispatched_at__isnull=True) |
            Q(dispatched_at__lt=retry_before)
        )
        .update(
            failed_at=timezone.now(),
            last_error=(
                "Maximum dispatch attempts (10) reached "
                "without completion."
            )
        )
    )

    if failed_count:
        logger.warning(
            "%s outbox events moved to dead-letter state",
            failed_count
        )

    # STEP 2: Find eligible pending events.
    pending_ids = list(
        NotificationOutbox.objects
        .filter(
            completed_at__isnull=True,
            failed_at__isnull=True
        )
        .filter(
            Q(dispatched_at__isnull=True) |
            Q(dispatched_at__lt=retry_before)
        )
        .filter(attempts__lt=10)
        .order_by("created_at")
        .values_list("id", flat=True)[:batch_size]
    )

    dispatched_count = 0

    # STEP 3: Dispatch eligible events.
    for outbox_id in pending_ids:

        with transaction.atomic():

            try:
                outbox = (
                    NotificationOutbox.objects
                    .select_for_update()
                    .get(
                        id=outbox_id,
                        completed_at__isnull=True,
                        failed_at__isnull=True
                    )
                )

                if (
                    outbox.dispatched_at is not None
                    and outbox.dispatched_at >= retry_before
                ):
                    continue

                if outbox.attempts >= 10:
                    continue

            except NotificationOutbox.DoesNotExist:
                continue

            try:
                create_message_notifications.delay(
                    outbox.message_id,
                    outbox.recipient_ids,
                    outbox.id
                )

            except Exception as error:

                outbox.attempts += 1
                outbox.last_error = str(error)[:2000]

                outbox.save(update_fields=[
                    "attempts",
                    "last_error"
                ])

                logger.exception(
                    "Failed to dispatch outbox event %s",
                    outbox.id
                )

            else:

                outbox.dispatched_at = timezone.now()
                outbox.attempts += 1
                outbox.last_error = ""

                outbox.save(update_fields=[
                    "dispatched_at",
                    "attempts",
                    "last_error"
                ])

                dispatched_count += 1

                logger.info(
                    "Outbox event %s dispatched successfully",
                    outbox.id
                )

    return dispatched_count
from django.db import models
from django.conf import settings
from django.db.models import constraints

# Create your models here.

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("MESSAGE", "New Message"),
        ("GROUP", "Group Activity"),
        ("SYSTEM", "System Notification"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification"
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications"
    )

    source_message = models.ForeignKey(
        "chat.Message",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications"
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default="MESSAGE"
    )

    title = models.CharField(max_length=255)
    message = models.TextField()
    conversation = models.ForeignKey(
        "chat.Conversation",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications"
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["recipient", "is_read", "-created_at"],
                name="notif_rec_read_date_idx"
            )
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "source_message"],
                name="unique_message_notification_per_recipient"
            )
        ]

    def __str__(self):
        return f"{self.title} -> {self.recipient}"

class NotificationOutbox(models.Model):

    message = models.OneToOneField(
        "chat.Message",
        on_delete=models.CASCADE,
        related_name="notification_outbox"
    )

    recipient_ids = models.JSONField(
        default=list
    )
    created_at = models.DateField(
        auto_now_add=True
    )

    dispatched_at = models.DateTimeField(
        null=True,
        blank=True
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    failed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    attempts = models.PositiveIntegerField(
        default=0
    )

    last_error = models.TextField(
        blank=True
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["dispatched_at", "created_at"],
                name="notif_outbox_pending_idx"
            )
        ]

    def __str__(self):
        return f"Outbox event for message {self.message_id}"
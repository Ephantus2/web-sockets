from django.db import models
from django.conf import settings

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

    def __str__(self):
        return f"{self.title} -> {self.recipient}"

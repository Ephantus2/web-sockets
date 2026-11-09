from django.db import models
from django.conf import settings
from django.db.migrations import autodetector
from django.db.models import constraints

class Conversation(models.Model):
    name = models.CharField(max_length=225, blank=True, null=True)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="coversation"
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.name or f"Conversation {self.id}"

class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete = models.CASCADE,
        related_name = "messages"
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )

    content = models.TextField(
        max_length=5000
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["created_at"]

        indexes = [
            models.Index(
                fields=["conversation", "created_at"],
                name="chat_conv_created_idx"
            )
        ]

    def __str__(self):
        return f"{self.sender} - {self.conversation_id}"
    
class MessageRead(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="read_receipts"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_reads"
    )

    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["message", "user"],
                name="unique_message_user_read"
            )
        ]

        indexes = [
            models.Index(
                fields=["user", "message"],
                name="chat_user_message_read_idx"
            )
        ]

        def __str__(self):
            return f"{self.user} read message {self.message_id}"
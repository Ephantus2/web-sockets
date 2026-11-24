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

    is_edited = models.BooleanField(
        default=False
    )

    edited_at = models.DateTimeField(
        null=True,
        blank=True
    )

    is_deleted = models.BooleanField(
        default=False
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True
    )

    deleted_for = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="hidden_messages"
    )

    is_pinned = models.BooleanField(
        default=False
    )
    pinned_at = models.DateTimeField(
        null=True,
        blank=True
    )
    pinned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pinned_messages"
    )

    forwarded_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="forwarded_messages"
    )

    forwarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="forwarded_messages"
    )

    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies"
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

class MessageReaction(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="reactions"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_reactions"
    )

    emoji = models.CharField(max_length=32)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["message", "user", "emoji"],
                name="unique_user_message_reaction"
            )
        ]

        indexes = [
            models.Index(
                fields = ["message", "emoji"],

                name="chat_message_emoji_idx"
            )
        ]

        def __str__(self):
            return f"{self.user} reacted {self.emoji} to message {self.message_id}"


class MessageEditHistory(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="edit_history"
    )

    previous_content = models.TextField(
        max_length=5000
    )

    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="message_edits"
    )

    edited_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-edited_at"]

        indexes = [
            models.Index(
                fields=["message", "edited_at"],
                name="chat_msg_edit_history_idx"
            )
        ]

    def __str__(self):
        return f"Edit: history for message {self.message_id}"
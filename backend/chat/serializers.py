from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Conversation, Message, MessageReaction

User = get_user_model()

class ConversationSerializer(serializers.ModelSerializer):
    participants = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all()
    )
    class Meta:
        model = Conversation

        fields = [
            "id",
            "name",
            "participants",
            "created_at",
            "updated_at"
        ]

        read_only_fields = [
            "id",
            "created_at",
            "uploaded_at"
        ]
class MessageReactionSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = MessageReaction
        fields = [
            "id",
            "message",
            "user",
            "emoji",
            "created_at"
        ]

        read_only_fields = [
            "id",
            "message",
            "user",
            "created_at"
        ]

class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.StringRelatedField(read_only=True)
    read_by=serializers.SerializerMethodField()
    reactions = MessageReactionSerializer(
        many=True,
        read_only=True
    )
    is_pinned = serializers.BooleanField(read_only=True)
    pinned_at = serializers.DateTimeField(read_only=True)
    pinned_by = serializers.StringRelatedField(read_only=True)

    forwarded_from = serializers.PrimaryKeyRelatedField(
        read_only=True
    )

    forwarded_by = serializers.StringRelatedField(
        read_only=True
    )

    forwarded_sender = serializers.CharField(
        source="forwarded_from.sender.username",
        read_only=True,
        allow_null=True
    )

    reply_to = serializers.PrimaryKeyRelatedField(
        read_only=True
    )
    reply_sender = serializers.CharField(
        source="reply_to.sender.username",
        read_only=True,
        allow_null=True
    )
    reply_content = serializers.CharField(
        source="reply_to.content",
        read_only=True,
        allow_null=True
    )


    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "sender",
            "content",
            "created_at",
            "read_by",
            "is_edited",
            "edited_at",
            "is_deleted",
            "deleted_at",
            "reactions",
            "is_pinned",
            "pinned_at",
            "pinned_by",
            "forwarded_from",
            "forwarded_by",
            "forwarded_sender",
            "reply_to",
            "reply_sender",
            "reply_content"
        ]

        read_only_fields = [
            "id",
            "conversation",
            "sender",
            "created_at",
            "read_by",
            "is_edited",
            "edited_at",
            "is_deleted",
            "deleted_at",
            "forwarded_from",
            "forwarded_by",
            "forwarded_sender",
            "reply_to",
            "reply_sender",
            "reply_content"
        ]
    def get_read_by(self, obj):
        return [
            receipt.user.username for receipt in obj.read_receipts.all()
        ]


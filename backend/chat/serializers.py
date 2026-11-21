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
            "reactions"
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
            "deleted_at"
        ]
    def get_read_by(self, obj):
        return [
            receipt.user.username for receipt in obj.read_receipts.all()
        ]


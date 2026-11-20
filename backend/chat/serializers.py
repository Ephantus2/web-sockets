from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Conversation, Message

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

class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.StringRelatedField(read_only=True)
    read_by=serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "sender",
            "content",
            "created_at",
            "read_by"
        ]

        read_only_fields = [
            "id",
            "conversation",
            "sender",
            "created_at",
            "read_by",
        ]
    def get_read_by(self, obj):
        return list(
            obj.read_receipts.select_related("user").values_list(
                "user__username",
                flat=True
            )
        )
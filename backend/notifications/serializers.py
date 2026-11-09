from rest_framework import serializers
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    sender = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Notification

        fields = [
            "id",
            "sender",
            "notification_type",
            "title",
            "message",
            "conversation",
            "is_read",
            "created_at"
        ]

        read_only_fields = fields
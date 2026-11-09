from django.contrib import admin
from .models import Notification

# Register your models here.
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "recipient",
        "sender",
        "notification_type",
        "title",
        "is_read",
        "created_at"
    )

    list_filter = (
        "notification_type",
        "is_read",
        "created_at"
    )

    search_fields = (
        "recipient__username",
        "sender__username",
        "title",
        "message"
    )
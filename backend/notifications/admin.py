from django.contrib import admin
from .models import Notification, NotificationOutbox

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

@admin.register(NotificationOutbox)
class NotificationOutboxAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "message",
        "attempts",
        "dispatched_at",
        "completed_at",
        "failed_at",
        "created_at"
    )

    list_filter = (
        "failed_at",
        "completed_at",
        "dispatched_at",
    )

    search_fields = (
        "message__id",
        "last_error"
    )
    readonly_fields = (
        "message",
        "recipient_ids",
        "created_at",
        "dispatched_at",
        "completed_at",
        "failed_at",
        "attempts",
        "last_error",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    @admin.action(description="Requeue selected failed events")
    def requeue_failed_events(self, request, queryset):
        failed_events = queryset.filter(
            failed_at__isnull=False,
            completed_at__isnull=True
        )

        count = failed_events.update(
            failed_at=None,
            dispatched_at=None,
            attempts=0
        )

        self.message_user(
            request,
            f"{count} failed events successfully requeued."
        )

    actions=["requeue_failed_events"]
from django.contrib import admin
from .models import Conversation, Message, MessageRead

# Register your models here.
@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):

    list_display = [
        "id",
        "name",
        "created_at",
        "updated_at"
    ]

    search_fields = ["name"]
    filter_horizontal = ("participants",)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "conversation",
        "sender",
        "created_at"
    ]

    search_fields = ["content"]

    list_filter = ["created_at"]

admin.site.register(MessageRead)
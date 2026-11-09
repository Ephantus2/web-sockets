import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close(code=4401)
            return

        self.notification_group = (
            f"user_{self.user.id}_notifications"
        )

        await self.channel_layer.group_add(
            self.notification_group,
            self.channel_name
        )

        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "notification_connection",
            "message": "Notification connection established"
        }))

    async def notification_message(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "notification",
                "notification": event["notification"]
            })
        )

    async def disconnect(self, close_code):
        if hasattr(self, "notification_group"):
            await self.channel_layer.group_discard(
                self.notification_group,
                self.channel_name
            )
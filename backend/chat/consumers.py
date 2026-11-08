import json

from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):

        # define the group name
        self.room_group_name = "chat_lobby"

        # add this websocket connection to the group

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # accept the web socket connection

        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "message": "Welcome to the chat lobby!"
        }))

    async def receive(self, text_data):
        # convert incoming JSON into a python dictionary
        data = json.loads(text_data)
        message = data.get("message", "")
        # Broadcast the message to the entire group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message
            }
        )

    async def chat_message(self, event):

        #Extract the message from the event

        message = event["message"]

        # send the message to this websocket client

        await self.send(text_data=json.dumps({
            "type": "chat_message",
            "message": message
        }))

    async def disconnect(self, close_code):
        # remove this connection from the group

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        print(f"Disconnected with code: {close_code}")

        
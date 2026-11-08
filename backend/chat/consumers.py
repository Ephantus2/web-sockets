import json

from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # accept the websocket connection
        await self.accept()

        # send a welcome message to the client
        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "message": "Welcome! You are connected to the chat server."
        }))

        async def receive(self, text_data):
            #convert incoming JSON string into Python dictionary
            data = json.loads(text_data)

            # Extract the message

            message = data.get("message", "")

            # send a response back to the same client

            await self.send(text_data=json.dumps({
                "type": "chat_message",
                "message": message
            }))

        async def disconnect(self, close_code):
            print(f"Websocket disconnected. Code: {close_code}")
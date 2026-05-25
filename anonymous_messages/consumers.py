# backend/anonymous_messages/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class MessageConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.username = self.scope['url_route']['kwargs']['username']
        self.room_group_name = f'user_{self.username}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'new_message',
                'message': data['message'],
                'message_id': data['message_id'],
            }
        )
    
    async def new_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event['message'],
            'message_id': event['message_id'],
        }))
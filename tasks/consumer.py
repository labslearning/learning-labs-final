import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User
from .models import ActiveUser
from datetime import datetime

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        # Agregar usuario al grupo
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Registrar usuario como activo
        user = self.scope['user']
        ActiveUser.objects.update_or_create(user=user, defaults={'last_activity': datetime.now()})

        # Enviar lista de usuarios activos al unirse
        active_users = ActiveUser.objects.filter(user__is_active=True)
        await self.send(text_data=json.dumps({
            'type': 'active_users',
            'users': [user.user.username for user in active_users]
        }))

        await self.accept()

    async def disconnect(self, close_code):
        # Eliminar usuario del grupo
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        # Marcar usuario como inactivo
        user = self.scope['user']
        ActiveUser.objects.filter(user=user).delete()

        # Enviar lista de usuarios activos al desconectarse
        active_users = ActiveUser.objects.filter(user__is_active=True)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'active_users',
                'users': [user.user.username for user in active_users]
            }
        )

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            text_data_json = json.loads(text_data)
            message = text_data_json['message']
            username = text_data_json['username']

            # Enviar mensaje al grupo
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'username': username
                }
            )

    async def chat_message(self, event):
        message = event['message']
        username = event['username']
        await self.send(text_data=json.dumps({
            'message': message,
            'username': username
        }))

    async def active_users(self, event):
        users = event['users']
        await self.send(text_data=json.dumps({
            'active_users': users
        }))



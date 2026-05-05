import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)

class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Websocket consumer for real-time notifications.
    Each user connects to thier own groupt: notifications_<user_id>
    """

    async def connect(self):
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.close()
            return
        
        self.user_id = str(user.id)
        self.group_name = f"notifications_{self.user_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"WebSocket connected: user={self.user_id}")

        #send unread count immediately on connect
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            "type": "unread_count",
            "count": unread_count,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        logger.info(f"WebSocket disconnected: user={self.user_id}")

    async def receive(self, text_data):
        """
        Handle message from the client.
        Right now only supports mark_read.
        """
        try:
            data = json.loads(text_data)
            if data.get("type") == "mark_read":
                notification_id = data.get("notification_id")
                if notification_id:
                    await self.mark_notification_read(notification_id)
        
        except json.JSONDecodeError:
            pass

    # this method is called when group_send is called with type=notification.new
    async def notification_new(self, event):
        """
        Push new notification to connected Websocket client.
        """

        await self.send(text_data=json.dumps({
            "type": "new_notification",
            "notification": event["notification"],
        }))

    @database_sync_to_async
    def get_unread_count(self):
        from apps.notifications.models import Notification
        return Notification.objects.filter(
            recipient_id=self.user_id,
            is_read=False
        ).count()

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        from apps.notifications.models import Notification
        Notification.objects.filter(
            id=notification_id,
            recipient_id=self.user_id
        ).update(is_read=True)
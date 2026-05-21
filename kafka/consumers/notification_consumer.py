import logging
from .base import BaseConsumer
from kafka.topics import Topics

logger = logging.getLogger(__name__)


class NotificationConsumer(BaseConsumer):
    topic = [
        Topics.POST_LIKED,
        Topics.POST_UNLIKED,
        Topics.POST_COMMENTED,
        Topics.POST_REPOSTED,
        Topics.USER_FOLLOWED,
        Topics.USER_UNFOLLOWED,
        Topics.USER_MENTIONED,
        Topics.VERIFICATION_APPROVED,
        Topics.VERIFICATION_REJECTED,
    ]
    group_id = "notification-consumer-group"

    def process_event(self, event: dict):
        topic = event.get("_meta", {}).get("topic")

        if topic == Topics.POST_LIKED:
            self._handle_like(event)
        elif topic == Topics.POST_UNLIKED:
            self._handle_unlike(event)
        elif topic == Topics.POST_COMMENTED:
            self._handle_comment(event)
        elif topic == Topics.POST_REPOSTED:
            self._handle_repost(event)
        elif topic == Topics.USER_FOLLOWED:
            self._handle_follow(event)
        elif topic == Topics.USER_UNFOLLOWED:
            self._handle_unfollow(event)
        elif topic == Topics.USER_MENTIONED:
            self._handle_mention(event)
        elif topic == Topics.VERIFICATION_APPROVED:
            self._handle_verification_approved(event)
        elif topic == Topics.VERIFICATION_REJECTED:
            self._handle_verification_rejected(event)
            
    def _handle_like(self, event: dict):
        from apps.notifications.models import Notification

        recipient_id = event.get("post_author_id")
        sender_id = event.get("user_id")
        post_id = event.get("post_id")

        if not recipient_id or not sender_id or not post_id:
            logger.warning(f"Missing fields in like event: {event}")
            return

        if recipient_id == sender_id:
            return

        notification = Notification.objects.create(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type=Notification.NotificationType.LIKE,
            post_id=post_id,
        )
        self._push_websocket_notification(notification)

    def _handle_unlike(self, event: dict):
        from apps.notifications.models import Notification

        sender_id = event.get("user_id")
        post_id = event.get("post_id")

        if not sender_id or not post_id:
            logger.warning(f"Missing fields in unlike event: {event}")
            return

        deleted_count, _ = Notification.objects.filter(
            sender_id=sender_id,
            notification_type=Notification.NotificationType.LIKE,
            post_id=post_id,
        ).delete()

        logger.info(
            f"Unlike handler: deleted {deleted_count} notification(s) "
            f"for sender={sender_id} post={post_id}"
        )

    def _handle_repost(self, event: dict):
        from apps.notifications.models import Notification

        recipient_id = event.get("post_author_id")
        sender_id = event.get("user_id")
        post_id = event.get("post_id")

        if not recipient_id or not sender_id or not post_id:
            logger.warning(f"Missing fields in repost event: {event}")
            return

        if recipient_id == sender_id:
            return

        notification = Notification.objects.create(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type=Notification.NotificationType.REPOST,
            post_id=post_id,
        )
        self._push_websocket_notification(notification)

    def _handle_comment(self, event: dict):
        from apps.notifications.models import Notification

        recipient_id = event.get("post_author_id")
        sender_id = event.get("user_id")
        post_id = event.get("post_id")

        if not recipient_id or not sender_id or not post_id:
            logger.warning(f"Missing fields in comment event: {event}")
            return

        if recipient_id == sender_id:
            return

        notification = Notification.objects.create(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type=Notification.NotificationType.COMMENT,
            post_id=post_id,
        )
        self._push_websocket_notification(notification)

    def _handle_follow(self, event: dict):
        from apps.notifications.models import Notification

        recipient_id = event.get("following_id")
        sender_id = event.get("follower_id")

        if not recipient_id or not sender_id:
            logger.warning(f"Missing fields in follow event: {event}")
            return

        notification = Notification.objects.create(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type=Notification.NotificationType.FOLLOW,
        )
        self._push_websocket_notification(notification)

    def _handle_unfollow(self, event: dict):
        from apps.notifications.models import Notification

        recipient_id = event.get("following_id")
        sender_id = event.get("follower_id")

        if not recipient_id or not sender_id:
            logger.warning(f"Missing fields in unfollow event: {event}")
            return

        Notification.objects.filter(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type=Notification.NotificationType.FOLLOW,
        ).delete()

    def _handle_mention(self, event: dict):
        from apps.notifications.models import Notification
        from apps.users.models import User

        mentions = event.get("mentions", [])
        sender_id = event.get("user_id")
        post_id = event.get("post_id")

        if not mentions or not sender_id or not post_id:
            logger.warning(f"Missing fields in mention event: {event}")
            return

        mentioned_users = User.objects.filter(
            username__in=mentions,
            is_active=True
        ).exclude(id=sender_id)

        for user in mentioned_users:
            notification = Notification.objects.create(
                recipient=user,
                sender_id=sender_id,
                notification_type=Notification.NotificationType.MENTION,
                post_id=post_id,
            )
            self._push_websocket_notification(notification)

    def _push_websocket_notification(self, notification):
        """
        Push real-time notification via Django Channels.
        Uses async_to_sync since consumer.run() is synchronous.
        """
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        group_name = f"notifications_{notification.recipient_id}"

        notification_data = {
            "id": str(notification.id),
            "type": notification.notification_type,
            "sender": notification.sender.username if notification.sender else None,
            "post_id": str(notification.post_id) if notification.post_id else None,
            "created_at": notification.created_at.isoformat(),
            "is_read": False,
        }

        try:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "notification.new",
                    "notification": notification_data,
                }
            )
            logger.info(f"WebSocket push sent to group: {group_name}")
        except Exception as e:
            logger.error(f"WebSocket push failed: {e}")

    
    def _handle_verification_approved(self, event: dict):
        from apps.notifications.models import Notification

        user_id = event.get("user_id")
        if not user_id:
            return

        notification = Notification.objects.create(
            recipient_id=user_id,
            sender=None,
            notification_type=Notification.NotificationType.VERIFIED,
        )
        self._push_websocket_notification(notification)

    def _handle_verification_rejected(self, event: dict):
        from apps.notifications.models import Notification

        user_id = event.get("user_id")
        if not user_id:
            return

        notification = Notification.objects.create(
            recipient_id=user_id,
            sender=None,
            notification_type=Notification.NotificationType.REJECTED
        )
        self._push_websocket_notification(notification)
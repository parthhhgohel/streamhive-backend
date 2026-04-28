import logging
from .base import BaseConsumer
from kafka.topics import Topics

logger = logging.getLogger(__name__)


class NotificationConsumer(BaseConsumer):
    topic = [
        Topics.POST_LIKED,
        Topics.POST_UNLIKED,
        Topics.POST_COMMENTED,
        Topics.USER_FOLLOWED,
        Topics.USER_UNFOLLOWED,
        Topics.USER_MENTIONED,
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
        elif topic == Topics.USER_FOLLOWED:
            self._handle_follow(event)
        elif topic == Topics.USER_UNFOLLOWED:
            self._handle_unfollow(event)
        elif topic == Topics.USER_MENTIONED:
            self._handle_mention(event)

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

        Notification.objects.create(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type=Notification.NotificationType.LIKE,
            post_id=post_id,
        )

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

        logger.info(f"Unlike handler: deleted {deleted_count} notification(s) for sender={sender_id} post={post_id}")


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

        Notification.objects.create(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type=Notification.NotificationType.COMMENT,
            post_id=post_id,
        )

    def _handle_follow(self, event: dict):
        from apps.notifications.models import Notification

        recipient_id = event.get("following_id")
        sender_id = event.get("follower_id")

        if not recipient_id or not sender_id:
            logger.warning(f"Missing fields in follow event: {event}")
            return

        Notification.objects.create(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type=Notification.NotificationType.FOLLOW,
        )

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

        recipient_id = event.get("mentioned_user_id")
        sender_id = event.get("user_id")
        post_id = event.get("post_id")

        if not recipient_id or not sender_id or not post_id:
            logger.warning(f"Missing fields in mention event: {event}")
            return

        if recipient_id == sender_id:
            return

        Notification.objects.create(
            recipient_id=recipient_id,
            sender_id=sender_id,
            notification_type=Notification.NotificationType.MENTION,
            post_id=post_id,
        )
# ------------------------------ CELERY (REFENCE ONLY) --------------------------

# from celery import shared_task

# @shared_task
# def create_notification(recipient_id, sender_id, notification_type, post_id=None):
#     from apps.notifications.models import Notification
#     Notification.objects.create(
#         recipient_id=recipient_id,
#         sender_id=sender_id,
#         notification_type=notification_type,
#         post_id=post_id
#     )

# @shared_task
# def create_mention_notifications(post_id, sender_id, mentions):
#     """
#     mentions is a list of usernames extracted from post content
#     """

#     from apps.users.models import User
#     from .models import Notification

#     mentioned_users = User.objects.filter(username__in=mentions, is_active=True).exclude(id=sender_id)

#     notifications = [
#         Notification(
#             recipient=user,
#             sender_id=sender_id,
#             notification_type=Notification.NotificationType.MENTION,
#             post_id=post_id
#         )
#         for user in mentioned_users
#     ]

#     Notification.objects.bulk_create(notifications)



# # For Test Only
# @shared_task
# def add(x, y):
#     return x + y

from kafka.producer import kafka_producer
from kafka.topics import Topics
import logging

logger = logging.getLogger(__name__)

def create_mention_notifications(post_id, sender_id, mentions):
    # mentions is a list of usernames extracted from post content

    from apps.users.models import User
    from .models import Notification

    mentioned_users = User.objects.filter(username__in=mentions, is_active=True).exclude(id=sender_id)

    for user in mentioned_users:
        kafka_producer.publish(
            topic=Topics.USER_MENTIONED,
            payload={
                "post_id": str(post_id),
                "user_id": str(sender_id),
                "mentioned_user_id": str(user.id),
            },
            key=str(post_id)
        )
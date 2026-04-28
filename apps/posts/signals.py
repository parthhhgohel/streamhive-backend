# CELERY

# from django.db.models.signals import post_save, post_delete
# from django.dispatch import receiver
# from django.db.models import F
# from .models import Like, Post
# from apps.comments.models import Comment
# from apps.notifications.models import Notification
# from apps.notifications.tasks import create_notification

# @receiver(post_save, sender=Like)
# def increment_like_count(sender, instance, created, **kwargs):
#     if created:
#         Post.objects.filter(pk=instance.post_id).update(like_count=F("like_count") + 1)

#         if instance.post.author != instance.user:
#             create_notification.delay(
#                 recipient_id=str(instance.post.author_id),
#                 sender_id=str(instance.user_id),
#                 notification_type="like",
#                 post_id=str(instance.post_id)
#             )

# @receiver(post_delete, sender=Like)
# def decrement_like_count(sender, instance, **kwargs):
#     Post.objects.filter(pk=instance.post_id).update(like_count=F("like_count") - 1)

# @receiver(post_save, sender=Comment)
# def increment_comment_count(sender, instance, created, **kwargs):
#     if created:
#         Post.objects.filter(pk=instance.post_id).update(comment_count=F("comment_count") + 1)

# @receiver(post_delete, sender=Comment)
# def decrement_comment_count(sender, instance, **kwargs):
#     Post.objects.filter(pk=instance.post_id).update(comment_count=F("comment_count") - 1)


####-------------------------------------------- KAFKA ----------------------------------------------###
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import F
from .models import Like, Post
from apps.comments.models import Comment
from kafka.producer import kafka_producer
from kafka.topics import Topics
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Like)
def on_like_created(sender, instance, created, **kwargs):
    if created:
        # update counter
        Post.objects.filter(pk=instance.post_id).update(
            like_count=F("like_count") + 1
        )

        # publish to Kafka - notification consumer handles the rest
        kafka_producer.publish(
            topic=Topics.POST_LIKED,
            payload={
                "post_id": str(instance.post_id),
                "post_author_id": str(instance.post.author_id),
                "user_id": str(instance.user_id),
            },
            key=str(instance.post_id)
        )


@receiver(post_delete, sender=Like)
def on_like_deleted(sender, instance, **kwargs):
    Post.objects.filter(pk=instance.post_id).update(
        like_count=F("like_count") - 1
    )

    kafka_producer.publish(
        topic=Topics.POST_UNLIKED,
        payload={
            "post_id": str(instance.post_id),
            "user_id": str(instance.user_id),
        },
        key=str(instance.post_id)
    )


@receiver(post_save, sender=Comment)
def on_comment_created(sender, instance, created, **kwargs):
    if created:
        Post.objects.filter(pk=instance.post_id).update(
            comment_count=F("comment_count") + 1
        )

        kafka_producer.publish(
            topic=Topics.POST_COMMENTED,
            payload={
                "post_id": str(instance.post_id),
                "post_author_id": str(instance.post.author_id),
                "user_id": str(instance.author_id),
                "comment_id": str(instance.id),
            },
            key=str(instance.post_id)
        )


@receiver(post_delete, sender=Comment)
def on_comment_deleted(sender, instance, **kwargs):
    Post.objects.filter(pk=instance.post_id).update(
        comment_count=F("comment_count") - 1
    )
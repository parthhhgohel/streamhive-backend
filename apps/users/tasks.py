# apps/users/tasks.py — refactor to share HTML builder

import logging
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _build_welcome_email_html(display_name: str, username: str) -> str:
    """Shared HTML builder used by both Celery task and direct send."""
    return f"""
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title>Welcome to StreamHive</title>
      </head>
      <body style="margin:0;padding:0;background-color:#000000;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#000000;padding:40px 0;">
          <tr>
            <td align="center">
              <table width="600" cellpadding="0" cellspacing="0" style="background-color:#111111;border:1px solid #1f2937;border-radius:16px;overflow:hidden;max-width:600px;width:100%;">
                <tr>
                  <td style="background:linear-gradient(135deg,#1d4ed8,#1e40af);padding:40px 40px 30px;text-align:center;">
                    <h1 style="margin:0;color:#ffffff;font-size:32px;font-weight:800;">StreamHive</h1>
                    <p style="margin:8px 0 0;color:#bfdbfe;font-size:14px;">Your voice. Your stream.</p>
                  </td>
                </tr>
                <tr>
                  <td style="padding:40px;">
                    <h2 style="margin:0 0 8px;color:#ffffff;font-size:22px;font-weight:700;">Welcome, {display_name} 👋</h2>
                    <p style="margin:0 0 24px;color:#9ca3af;font-size:14px;">@{username}</p>
                    <p style="margin:0 0 20px;color:#e5e7eb;font-size:15px;line-height:1.6;">
                      You're now part of StreamHive — a place to share your thoughts, follow people you care about, and join conversations that matter.
                    </p>
                    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
                      <tr>
                        <td align="center">
                          <a href="{settings.FRONTEND_URL}" style="display:inline-block;background-color:#2563eb;color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;padding:14px 36px;border-radius:50px;">
                            Go to StreamHive →
                          </a>
                        </td>
                      </tr>
                    </table>
                    <hr style="border:none;border-top:1px solid #1f2937;margin:0 0 24px;" />
                    <p style="margin:0;color:#6b7280;font-size:13px;">
                      If you didn't create this account, you can safely ignore this email.
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="padding:20px 40px;background-color:#0a0a0a;border-top:1px solid #1f2937;text-align:center;">
                    <p style="margin:0;color:#4b5563;font-size:12px;">© 2025 StreamHive. All rights reserved.</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
      </html>
      """


@shared_task
def send_welcome_email(user_email: str, display_name: str, username: str):
    """Celery task version — used when celery_worker is running."""
    try:
        from django.core.mail import send_mail
        html_content = _build_welcome_email_html(display_name, username)
        send_mail(
            subject=f"Welcome to StreamHive, {display_name}!",
            message=f"Welcome to StreamHive, {display_name}! Visit us at {settings.FRONTEND_URL}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_content,
            fail_silently=False,
        )
        logger.info(f"Welcome email sent to {user_email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user_email}: {e}")


def send_welcome_email_direct(user_email: str, display_name: str, username: str):
    """Direct version — used in production without celery_worker."""
    try:
        from django.core.mail import send_mail
        html_content = _build_welcome_email_html(display_name, username)
        send_mail(
            subject=f"Welcome to StreamHive, {display_name}!",
            message=f"Welcome to StreamHive, {display_name}! Visit us at {settings.FRONTEND_URL}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_content,
            fail_silently=True,
        )
        logger.info(f"Welcome email sent directly to {user_email}")
    except Exception as e:
        logger.error(f"Direct welcome email failed: {e}")
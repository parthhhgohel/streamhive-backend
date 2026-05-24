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


# BREVO
def send_welcome_email_direct(user_email: str, display_name: str, username: str):
    try:
        import sib_api_v3_sdk
        from django.conf import settings

        html_content = _build_welcome_email_html(display_name, username)

        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key["api-key"] = settings.BREVO_API_KEY

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": user_email}],
            sender={"email": "parthgohel806@gmail.com", "name": "StreamHive"},
            subject=f"Welcome to StreamHive, {display_name}!",
            html_content=html_content,
        )
        api_instance.send_transac_email(send_smtp_email)
        logger.info(f"Welcome email sent to {user_email}")
    except Exception as e:
        logger.error(f"Direct welcome email failed: {e}")


def _build_otp_email_html(display_name: str, otp: str, expiry_minutes: int = 15) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Reset your StreamHive password</title>
</head>
<body style="margin:0;padding:0;background-color:#000000;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#000000;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color:#111111;border:1px solid #1f2937;border-radius:16px;overflow:hidden;max-width:600px;width:100%;">

          <tr>
            <td style="background:linear-gradient(135deg,#1d4ed8,#1e40af);padding:40px 40px 30px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:32px;font-weight:800;">StreamHive</h1>
              <p style="margin:8px 0 0;color:#bfdbfe;font-size:14px;">Password Reset</p>
            </td>
          </tr>

          <tr>
            <td style="padding:40px;">
              <h2 style="margin:0 0 16px;color:#ffffff;font-size:20px;font-weight:700;">
                Hi {display_name},
              </h2>
              <p style="margin:0 0 24px;color:#e5e7eb;font-size:15px;line-height:1.6;">
                We received a request to reset your StreamHive password. Use the OTP below to continue. It expires in <strong style="color:#ffffff;">{expiry_minutes} minutes</strong>.
              </p>

              <!-- OTP Block -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
                <tr>
                  <td align="center" style="padding:28px;background-color:#1a1a2e;border:1px solid #1f2937;border-radius:12px;">
                    <p style="margin:0 0 8px;color:#9ca3af;font-size:13px;text-transform:uppercase;letter-spacing:2px;">Your OTP Code</p>
                    <p style="margin:0;color:#ffffff;font-size:42px;font-weight:800;letter-spacing:12px;">{otp}</p>
                  </td>
                </tr>
              </table>

              <!-- Security notes -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
                <tr>
                  <td style="padding:16px;background-color:#1a1a0a;border:1px solid #713f12;border-radius:10px;">
                    <p style="margin:0 0 8px;color:#fbbf24;font-size:13px;font-weight:600;">⚠️ Security Notice</p>
                    <ul style="margin:0;padding-left:16px;color:#9ca3af;font-size:13px;line-height:1.8;">
                      <li>This OTP is valid for {expiry_minutes} minutes only</li>
                      <li>Never share this code with anyone</li>
                      <li>StreamHive will never ask for your OTP</li>
                      <li>If you didn't request this, change your password immediately</li>
                    </ul>
                  </td>
                </tr>
              </table>

              <hr style="border:none;border-top:1px solid #1f2937;margin:0 0 24px;" />
              <p style="margin:0;color:#6b7280;font-size:13px;">
                If you didn't request a password reset, you can safely ignore this email. Your password will not be changed.
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


# BREVO emailing
def send_otp_email_direct(user_email: str, display_name: str, otp: str):
    try:
        import sib_api_v3_sdk
        from sib_api_v3_sdk.rest import ApiException
        from django.conf import settings

        expiry = getattr(settings, "OTP_EXPIRY_MINUTES", 15)
        html_content = _build_otp_email_html(display_name, otp, expiry)

        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key["api-key"] = settings.BREVO_API_KEY

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": user_email}],
            sender={"email": "parthgohel806@gmail.com", "name": "StreamHive"},
            subject="Your StreamHive password reset OTP",
            html_content=html_content,
        )
        api_instance.send_transac_email(send_smtp_email)
        logger.info(f"OTP email sent to {user_email}")
    except Exception as e:
        logger.error(f"OTP email failed for {user_email}: {e}")
        raise

# BREVO
def send_password_changed_email_direct(user_email: str, display_name: str):
    try:
        import sib_api_v3_sdk
        from django.conf import settings
        from django.utils import timezone

        html_content = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background-color:#000000;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#000000;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color:#111111;border:1px solid #1f2937;border-radius:16px;overflow:hidden;max-width:600px;width:100%;">
          <tr>
            <td style="background:linear-gradient(135deg,#1d4ed8,#1e40af);padding:40px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:32px;font-weight:800;">StreamHive</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:40px;">
              <h2 style="margin:0 0 16px;color:#ffffff;font-size:20px;">Password Changed Successfully ✅</h2>
              <p style="margin:0 0 20px;color:#e5e7eb;font-size:15px;line-height:1.6;">
                Hi {display_name}, your StreamHive password was successfully changed on {timezone.now().strftime("%B %d, %Y at %H:%M UTC")}.
              </p>
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
                <tr>
                  <td style="padding:16px;background-color:#1a0a0a;border:1px solid #7f1d1d;border-radius:10px;">
                    <p style="margin:0;color:#fca5a5;font-size:13px;">
                      🚨 <strong>If you didn't do this</strong>, your account may be compromised. Please contact support immediately.
                    </p>
                  </td>
                </tr>
              </table>
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td align="center">
                    <a href="{settings.FRONTEND_URL}/login" style="display:inline-block;background-color:#2563eb;color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;padding:14px 36px;border-radius:50px;">
                      Login to StreamHive
                    </a>
                  </td>
                </tr>
              </table>
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

        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key["api-key"] = settings.BREVO_API_KEY

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": user_email}],
            sender={"email": "parthgohel806@gmail.com", "name": "StreamHive"},
            subject="Your StreamHive password was changed",
            html_content=html_content,
        )
        api_instance.send_transac_email(send_smtp_email)
        logger.info(f"Password changed confirmation sent to {user_email}")
    except Exception as e:
        logger.error(f"Password changed email failed: {e}")
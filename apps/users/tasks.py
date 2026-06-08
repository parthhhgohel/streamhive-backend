import logging
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


def _build_welcome_email_html(display_name: str, username: str) -> str:
    return f"""<!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8"/>
      <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
      <title>Welcome to StreamHive</title>
    </head>
    <body style="margin:0;padding:0;background-color:#131316;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#131316;padding:48px 0;">
        <tr>
          <td align="center">
            <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background-color:#1f1f22;border:1px solid #464554;border-radius:24px;overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="padding:40px;background:linear-gradient(135deg,#4f4fd6,#3b3bbf);text-align:center;">
                  <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:800;letter-spacing:-0.03em;">StreamHive</h1>
                  <p style="margin:10px 0 0;color:#c0c1ff;font-size:13px;font-weight:500;letter-spacing:0.07em;text-transform:uppercase;">Premium Creator Space</p>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:40px;">
                  <h2 style="margin:0 0 6px;color:#e4e1e6;font-size:22px;font-weight:700;letter-spacing:-0.02em;">Welcome, {display_name} 👋</h2>
                  <p style="margin:0 0 28px;color:#c7c4d7;font-size:13px;">@{username}</p>

                  <p style="margin:0 0 32px;color:#c7c4d7;font-size:15px;line-height:1.7;">
                    You're now part of StreamHive — a place to share your thoughts, follow people you care about, and join conversations that matter.
                  </p>

                  <!-- CTA Button -->
                  <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:36px;">
                    <tr>
                      <td align="center">
                        <a href="{settings.FRONTEND_URL}"
                          style="display:inline-block;background-color:#4f52c9;color:#e1e0ff;text-decoration:none;font-size:15px;font-weight:700;padding:14px 40px;border-radius:9999px;letter-spacing:-0.01em;">
                          Go to StreamHive →
                        </a>
                      </td>
                    </tr>
                  </table>

                  <hr style="border:none;border-top:1px solid #464554;margin:0 0 28px;"/>

                  <p style="margin:0;color:#5a5870;font-size:13px;line-height:1.6;">
                    If you didn't create this account, you can safely ignore this email.
                  </p>
                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td style="padding:20px 40px;background-color:#0e0e11;border-top:1px solid #464554;text-align:center;">
                  <p style="margin:0;color:#464554;font-size:12px;">© 2025 StreamHive. All rights reserved.</p>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>"""


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
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Reset your StreamHive password</title>
</head>
<body style="margin:0;padding:0;background-color:#131316;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#131316;padding:48px 0;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background-color:#1f1f22;border:1px solid #464554;border-radius:24px;overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="padding:40px;background:linear-gradient(135deg,#4f4fd6,#3b3bbf);text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:800;letter-spacing:-0.03em;">StreamHive</h1>
              <p style="margin:10px 0 0;color:#c0c1ff;font-size:13px;font-weight:500;letter-spacing:0.07em;text-transform:uppercase;">Password Reset</p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:40px;">
              <h2 style="margin:0 0 16px;color:#e4e1e6;font-size:20px;font-weight:700;letter-spacing:-0.02em;">Hi {display_name},</h2>
              <p style="margin:0 0 28px;color:#c7c4d7;font-size:15px;line-height:1.7;">
                We received a request to reset your StreamHive password. Use the code below to continue — it expires in
                <strong style="color:#e4e1e6;">{expiry_minutes} minutes</strong>.
              </p>

              <!-- OTP Block -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
                <tr>
                  <td align="center" style="padding:32px 24px;background-color:#2a2a2d;border:1px solid #464554;border-radius:20px;">
                    <p style="margin:0 0 10px;color:#c7c4d7;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.15em;">Your OTP Code</p>
                    <p style="margin:0;color:#c0c1ff;font-size:44px;font-weight:800;letter-spacing:14px;">{otp}</p>
                  </td>
                </tr>
              </table>

              <!-- Security Notice -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
                <tr>
                  <td style="padding:18px 20px;background-color:#1b1b1e;border:1px solid #464554;border-left:3px solid #c0c1ff;border-radius:14px;">
                    <p style="margin:0 0 10px;color:#c0c1ff;font-size:13px;font-weight:600;">⚠️ Security Notice</p>
                    <ul style="margin:0;padding-left:18px;color:#c7c4d7;font-size:13px;line-height:2;">
                      <li>This OTP is valid for {expiry_minutes} minutes only</li>
                      <li>Never share this code with anyone</li>
                      <li>StreamHive will never ask for your OTP</li>
                      <li>If you didn't request this, change your password immediately</li>
                    </ul>
                  </td>
                </tr>
              </table>

              <hr style="border:none;border-top:1px solid #464554;margin:0 0 28px;"/>

              <p style="margin:0;color:#5a5870;font-size:13px;line-height:1.6;">
                If you didn't request a password reset, you can safely ignore this email. Your password will not be changed.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:20px 40px;background-color:#0e0e11;border-top:1px solid #464554;text-align:center;">
              <p style="margin:0;color:#464554;font-size:12px;">© 2025 StreamHive. All rights reserved.</p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


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

        html_content = f"""<!DOCTYPE html>
          <html>
          <head>
            <meta charset="UTF-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
          </head>
          <body style="margin:0;padding:0;background-color:#131316;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
            <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#131316;padding:48px 0;">
              <tr>
                <td align="center">
                  <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background-color:#1f1f22;border:1px solid #464554;border-radius:24px;overflow:hidden;">

                    <!-- Header -->
                    <tr>
                      <td style="padding:40px;background:linear-gradient(135deg,#4f4fd6,#3b3bbf);text-align:center;">
                        <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:800;letter-spacing:-0.03em;">StreamHive</h1>
                        <p style="margin:10px 0 0;color:#c0c1ff;font-size:13px;font-weight:500;letter-spacing:0.07em;text-transform:uppercase;">Account Security</p>
                      </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                      <td style="padding:40px;">
                        <h2 style="margin:0 0 16px;color:#e4e1e6;font-size:20px;font-weight:700;letter-spacing:-0.02em;">Password Changed ✅</h2>
                        <p style="margin:0 0 28px;color:#c7c4d7;font-size:15px;line-height:1.7;">
                          Hi {display_name}, your StreamHive password was successfully changed on
                          <strong style="color:#e4e1e6;">{timezone.now().strftime("%B %d, %Y at %H:%M UTC")}</strong>.
                        </p>

                        <!-- Warning block -->
                        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
                          <tr>
                            <td style="padding:18px 20px;background-color:#1b1b1e;border:1px solid #464554;border-left:3px solid #ffb4ab;border-radius:14px;">
                              <p style="margin:0;color:#ffb4ab;font-size:13px;line-height:1.7;">
                                🚨 <strong>If you didn't do this</strong>, your account may be compromised. Please contact support immediately and reset your password.
                              </p>
                            </td>
                          </tr>
                        </table>

                        <!-- CTA -->
                        <table width="100%" cellpadding="0" cellspacing="0">
                          <tr>
                            <td align="center">
                              <a href="{settings.FRONTEND_URL}/login"
                                style="display:inline-block;background-color:#4f52c9;color:#e1e0ff;text-decoration:none;font-size:15px;font-weight:700;padding:14px 40px;border-radius:9999px;letter-spacing:-0.01em;">
                                Login to StreamHive
                              </a>
                            </td>
                          </tr>
                        </table>
                      </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                      <td style="padding:20px 40px;background-color:#0e0e11;border-top:1px solid #464554;text-align:center;">
                        <p style="margin:0;color:#464554;font-size:12px;">© 2025 StreamHive. All rights reserved.</p>
                      </td>
                    </tr>

                  </table>
                </td>
              </tr>
            </table>
          </body>
          </html>"""

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
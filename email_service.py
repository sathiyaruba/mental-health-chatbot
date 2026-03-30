import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr, formatdate
from app.config import settings


def _send_email(to: str, subject: str, html_body: str, plain_body: str = "") -> bool:
    """Core SMTP email sender with UTF-8 support."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"[Email] SMTP not configured. Would send to {to}: {subject}")
        return True  # dev mode

    try:
        msg = MIMEMultipart("alternative")

        # ✅ These headers help land in Primary inbox
        msg["Subject"]           = Header(subject, "utf-8")
        msg["From"]              = formataddr(("Solace Support", settings.SMTP_USER))
        msg["To"]                = to
        msg["Date"]              = formatdate(localtime=True)
        msg["X-Priority"]        = "1"
        msg["X-MSMail-Priority"] = "High"
        msg["Importance"]        = "High"

        # ✅ Plain text version (helps avoid spam)
        if not plain_body:
            plain_body = "Please view this email in an HTML-compatible email client."
        msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, to, msg.as_string())

        print(f"[Email] Sent to {to}: {subject}")
        return True

    except Exception as e:
        print(f"[Email Error] {e}")
        return False


def send_crisis_alert(contact_name: str, contact_email: str, user_display_name: str) -> bool:
    """Send crisis alert email to a trusted contact."""
    subject = f"urgent: {user_display_name} needs your support right now"

    plain = f"""Hi {contact_name},

{user_display_name} has been using Solace, a mental health support platform, and may be experiencing significant distress right now.

Please consider reaching out to them with a kind message or a call. Let them know you are there for them.

If you believe they are in immediate danger, please call 112.

- Solace Support Team
"""

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:540px;margin:auto;padding:24px">
      <div style="background:#0a0f1e;border-radius:16px;padding:28px;color:#e2e8f0">
        <h1 style="font-size:24px;margin-bottom:4px">Solace</h1>
        <p style="color:#718096;font-size:13px;margin-top:0">Mental Health Support Platform</p>
        <h2 style="color:#fc8181;margin-bottom:16px">Someone you care about needs support</h2>
        <p style="color:#a0aec0;line-height:1.7">
          Hi <strong style="color:#e2e8f0">{contact_name}</strong>,<br><br>
          <strong style="color:#e2e8f0">{user_display_name}</strong> has been using Solace
          and their session indicated they may be experiencing significant distress right now.
        </p>
        <div style="background:#1a2236;border-radius:12px;padding:16px;margin:20px 0;border-left:3px solid #fc8181">
          <p style="color:#e2e8f0;margin:0">
            Please consider reaching out to them with a kind message or a call.
            Let them know you are there for them.
          </p>
        </div>
        <p style="color:#718096;font-size:12px;margin-top:24px">
          This alert was sent by Solace. Their conversation details remain private.<br>
          If you believe they are in immediate danger, please call <strong>112</strong>.
        </p>
      </div>
    </div>
    """
    return _send_email(contact_email, subject, html, plain)


def send_password_reset(email: str, reset_token: str, user_name: str) -> bool:
    """Send password reset email."""
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    subject   = "Reset your Solace password"

    plain = f"""Hi {user_name},

Click the link below to reset your Solace password. This link expires in 1 hour.

{reset_url}

If you did not request this, ignore this email.

- Solace Support Team
"""

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:540px;margin:auto;padding:24px">
      <div style="background:#0a0f1e;border-radius:16px;padding:28px;color:#e2e8f0">
        <h1 style="font-size:24px;margin-bottom:4px">Solace</h1>
        <h2 style="margin-bottom:16px">Reset your password</h2>
        <p style="color:#a0aec0">Hi {user_name}, click below to reset your password. Expires in 1 hour.</p>
        <a href="{reset_url}"
           style="display:inline-block;margin:20px 0;padding:12px 28px;background:#63b3ed;color:#0a0f1e;border-radius:10px;text-decoration:none;font-weight:600">
          Reset Password
        </a>
        <p style="color:#718096;font-size:12px">If you did not request this, ignore this email.</p>
      </div>
    </div>
    """
    return _send_email(email, subject, html, plain)


def send_welcome_email(email: str, display_name: str) -> bool:
    """Send welcome email on signup."""
    subject = "Welcome to Solace - Your safe space"

    plain = f"""Hi {display_name},

Welcome to Solace! You have taken a brave step.

What you can do:
- Chat with our AI companion anytime
- Track your mood and see your patterns
- Join anonymous support rooms
- Connect with licensed therapists

You are not alone. We are here every step of the way.

- Solace Support Team
"""

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:540px;margin:auto;padding:24px">
      <div style="background:#0a0f1e;border-radius:16px;padding:28px;color:#e2e8f0">
        <h1 style="font-size:24px;margin-bottom:4px">Solace</h1>
        <h2 style="margin-bottom:12px">Welcome, {display_name}!</h2>
        <p style="color:#a0aec0;line-height:1.7">
          You have taken a brave step by joining Solace. This is your safe, anonymous space
          to express yourself, track your mood, and find support - 24/7, judgment-free.
        </p>
        <div style="background:#1a2236;border-radius:12px;padding:16px;margin:20px 0">
          <p style="color:#68d391;margin:0 0 8px;font-weight:600">What you can do here:</p>
          <p style="color:#a0aec0;margin:4px 0">- Chat with our AI companion anytime</p>
          <p style="color:#a0aec0;margin:4px 0">- Track your mood and see your patterns</p>
          <p style="color:#a0aec0;margin:4px 0">- Join anonymous support rooms</p>
          <p style="color:#a0aec0;margin:4px 0">- Connect with licensed therapists</p>
        </div>
        <p style="color:#718096;font-size:12px">
          You are not alone. We are here every step of the way.
        </p>
      </div>
    </div>
    """
    return _send_email(email, subject, html, plain)
# backend/accounts/utils.py
import logging
import secrets
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def generate_token():
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)


def get_frontend_url():
    """Get clean frontend base URL with fallback to production"""
    raw_url = getattr(settings, 'FRONTEND_URL', '').strip()
    if not raw_url:
        raw_url = 'https://use-anonymsg.vercel.app' if not getattr(settings, 'DEBUG', False) else 'http://localhost:3000'
    raw_url = raw_url.rstrip('/')
    if not raw_url.startswith(('http://', 'https://')):
        raw_url = f"https://{raw_url}"
    return raw_url


def dispatch_email(subject: str, plain_message: str, html_message: str, recipient_email: str) -> bool:
    """
    Robust multi-provider email dispatcher:
    1. First tries Resend API if RESEND_API_KEY is configured (best for Render & cloud PaaS)
    2. Falls back to Django SMTP (Gmail, Sendgrid SMTP, etc.)
    3. Comprehensive error and status logging for debugging production issues
    """
    recipient_email = recipient_email.strip()
    if not recipient_email:
        logger.error("❌ Cannot send email: recipient email is empty")
        return False

    resend_api_key = getattr(settings, 'RESEND_API_KEY', '').strip()
    
    # 1. Try Resend API (HTTP-based, resilient to cloud port blocking)
    if resend_api_key:
        try:
            import resend
            resend.api_key = resend_api_key
            
            from_addr = getattr(settings, 'RESEND_FROM_EMAIL', '').strip()
            if not from_addr:
                from_addr = getattr(settings, 'DEFAULT_FROM_EMAIL', '').strip()
            
            # Clean up invalid "AnonQ <None>" or empty from address
            if not from_addr or 'None' in from_addr or '@' not in from_addr:
                from_addr = 'AnonQ <onboarding@resend.dev>'
                
            logger.info(f"📧 Sending email to {recipient_email} via Resend API (from: {from_addr})...")
            
            response = resend.Emails.send({
                "from": from_addr,
                "to": [recipient_email],
                "subject": subject,
                "html": html_message,
                "text": plain_message,
            })
            
            logger.info(f"✅ Email successfully delivered via Resend to {recipient_email}: {response}")
            return True
        except Exception as e:
            logger.error(f"⚠️ Resend email delivery failed: {e}. Falling back to SMTP if available.")
            
    # 2. Try Django SMTP
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '').strip()
        if not from_email or 'None' in from_email or '@' not in from_email:
            host_user = getattr(settings, 'EMAIL_HOST_USER', '').strip()
            from_email = f"AnonQ <{host_user}>" if host_user else "AnonQ <noreply@anonq.me>"
            
        logger.info(f"📧 Sending email to {recipient_email} via Django SMTP (from: {from_email})...")
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=[recipient_email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"✅ Email successfully delivered via SMTP to {recipient_email}")
        return True
    except Exception as e:
        logger.error(f"❌ SMTP email delivery failed for {recipient_email}: {e}")
        
    # If neither succeeded
    logger.error(
        f"❌ All email dispatch methods failed for {recipient_email}. "
        f"Please verify EMAIL_HOST_USER/EMAIL_HOST_PASSWORD or RESEND_API_KEY in your environment variables."
    )
    return False


def send_verification_email(user):
    """Send email verification link to user"""
    token = generate_token()
    user.verification_token = token
    user.verification_token_created_at = timezone.now()
    user.save()
    
    frontend_url = get_frontend_url()
    verification_link = f"{frontend_url}/verify-email?token={token}&email={user.email}"
    
    subject = "Verify your email - AnonQ"
    
    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Verify Your Email</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #0b0f19;">
        <div style="max-width: 600px; margin: 20px auto; padding: 20px;">
            <div style="text-align: center; padding: 24px; background: linear-gradient(135deg, #2563eb, #4f46e5); border-radius: 16px;">
                <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 800;">Anon<span style="color: #93c5fd;">Q</span></h1>
            </div>
            
            <div style="padding: 30px; background: #ffffff; border-radius: 16px; margin-top: 20px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
                <h2 style="color: #111827; margin-top: 0;">Welcome, {user.username}! 👋</h2>
                <p style="color: #4b5563;">Thanks for joining AnonQ. Please verify your email address to start receiving anonymous messages, confessions, and tips.</p>
                
                <div style="text-align: center; margin: 32px 0;">
                    <a href="{verification_link}" 
                       style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 15px;">
                        Verify Email Address
                    </a>
                </div>
                
                <p style="font-size: 13px; color: #6b7280; margin-bottom: 6px;">Or copy this link into your browser:</p>
                <p style="font-size: 12px; color: #2563eb; word-break: break-all; background: #f3f4f6; padding: 10px; border-radius: 8px;">{verification_link}</p>
                
                <hr style="margin: 24px 0; border: none; border-top: 1px solid #e5e7eb;">
                <p style="font-size: 12px; color: #9ca3af; margin: 0;">This link will expire in 24 hours.</p>
                <p style="font-size: 12px; color: #9ca3af; margin-top: 4px;">If you didn't create an account, please ignore this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_message = f"""
    Welcome to AnonQ, {user.username}!
    
    Thanks for signing up! Please verify your email address by clicking the link below:
    
    {verification_link}
    
    This link will expire in 24 hours.
    
    If you didn't create an account, please ignore this email.
    
    - AnonQ Team
    """
    
    return dispatch_email(subject, plain_message, html_message, user.email)


def send_password_reset_email(user):
    """Send password reset link to user"""
    token = generate_token()
    user.reset_password_token = token
    user.reset_password_token_created_at = timezone.now()
    user.save()
    
    frontend_url = get_frontend_url()
    reset_link = f"{frontend_url}/reset-password?token={token}&email={user.email}"
    
    subject = "Reset your password - AnonQ"
    
    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Reset Your Password</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #0b0f19;">
        <div style="max-width: 600px; margin: 20px auto; padding: 20px;">
            <div style="text-align: center; padding: 24px; background: linear-gradient(135deg, #2563eb, #4f46e5); border-radius: 16px;">
                <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 800;">Anon<span style="color: #93c5fd;">Q</span></h1>
            </div>
            
            <div style="padding: 30px; background: #ffffff; border-radius: 16px; margin-top: 20px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
                <h2 style="color: #111827; margin-top: 0;">Reset Your Password</h2>
                <p style="color: #4b5563;">We received a request to reset your password for your AnonQ account. Click the button below to choose a new password.</p>
                
                <div style="text-align: center; margin: 32px 0;">
                    <a href="{reset_link}" 
                       style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 15px;">
                        Reset Password
                    </a>
                </div>
                
                <p style="font-size: 13px; color: #6b7280; margin-bottom: 6px;">Or copy this link into your browser:</p>
                <p style="font-size: 12px; color: #2563eb; word-break: break-all; background: #f3f4f6; padding: 10px; border-radius: 8px;">{reset_link}</p>
                
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 8px; margin: 20px 0;">
                    <p style="color: #92400e; font-size: 13px; margin: 0; font-weight: 500;">⚠️ This link will expire in 1 hour for security reasons.</p>
                </div>
                
                <hr style="margin: 24px 0; border: none; border-top: 1px solid #e5e7eb;">
                <p style="font-size: 12px; color: #9ca3af; margin: 0;">If you didn't request a password reset, you can safely ignore this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_message = f"""
    Reset Your Password - AnonQ
    
    We received a request to reset your password. Click the link below to create a new password:
    
    {reset_link}
    
    This link will expire in 1 hour for security reasons.
    
    If you didn't request this, please ignore this email.
    
    - AnonQ Team
    """
    
    return dispatch_email(subject, plain_message, html_message, user.email)
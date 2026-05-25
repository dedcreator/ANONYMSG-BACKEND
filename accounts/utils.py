# backend/accounts/utils.py
import secrets
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

def generate_token():
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)

def send_verification_email(user):
    """Send email verification link to user"""
    token = generate_token()
    user.verification_token = token
    user.verification_token_created_at = timezone.now()
    user.save()
    
    verification_link = f"{settings.FRONTEND_URL}/verify-email?token={token}&email={user.email}"
    
    subject = "Verify your email - AnonMsg"
    
    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Verify Your Email</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #2563eb, #1d4ed8); border-radius: 12px;">
                <h1 style="color: white; margin: 0;">AnonMsg</h1>
            </div>
            
            <div style="padding: 30px; background: #f9fafb; border-radius: 12px; margin-top: 20px;">
                <h2>Welcome, {user.username}! 👋</h2>
                <p>Thanks for signing up! Please verify your email address to start receiving anonymous messages.</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_link}" 
                       style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                        Verify Email Address
                    </a>
                </div>
                
                <p style="font-size: 12px; color: #666;">Or copy this link into your browser:</p>
                <p style="font-size: 12px; color: #3b82f6; word-break: break-all;">{verification_link}</p>
                
                <hr style="margin: 20px 0;">
                <p style="font-size: 12px; color: #999;">This link will expire in 24 hours.</p>
                <p style="font-size: 12px; color: #999;">If you didn't create an account, please ignore this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_message = f"""
    Welcome to AnonMsg, {user.username}!
    
    Thanks for signing up! Please verify your email address by clicking the link below:
    
    {verification_link}
    
    This link will expire in 24 hours.
    
    If you didn't create an account, please ignore this email.
    
    - AnonMsg Team
    """
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        print(f"✅ Verification email sent to {user.email}")
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False


def send_password_reset_email(user):
    """Send password reset link to user"""
    token = generate_token()
    user.reset_password_token = token
    user.reset_password_token_created_at = timezone.now()
    user.save()
    
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}&email={user.email}"
    
    subject = "Reset your password - AnonMsg"
    
    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Reset Your Password</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #2563eb, #1d4ed8); border-radius: 12px;">
                <h1 style="color: white; margin: 0;">AnonMsg</h1>
            </div>
            
            <div style="padding: 30px; background: #f9fafb; border-radius: 12px; margin-top: 20px;">
                <h2>Reset Your Password</h2>
                <p>We received a request to reset your password. Click the button below to create a new password.</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" 
                       style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                        Reset Password
                    </a>
                </div>
                
                <p style="font-size: 12px; color: #666;">Or copy this link into your browser:</p>
                <p style="font-size: 12px; color: #3b82f6; word-break: break-all;">{reset_link}</p>
                
                <div style="background: #fef3c7; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <p style="color: #92400e; font-size: 13px; margin: 0;">⚠️ This link will expire in 1 hour for security reasons.</p>
                </div>
                
                <hr style="margin: 20px 0;">
                <p style="font-size: 12px; color: #999;">If you didn't request this, please ignore this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    plain_message = f"""
    Reset Your Password - AnonMsg
    
    We received a request to reset your password. Click the link below to create a new password:
    
    {reset_link}
    
    This link will expire in 1 hour for security reasons.
    
    If you didn't request this, please ignore this email.
    
    - AnonMsg Team
    """
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        print(f"✅ Password reset email sent to {user.email}")
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False
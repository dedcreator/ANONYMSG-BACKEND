from django.core.management.base import BaseCommand
from django.conf import settings
from accounts.utils import dispatch_email


class Command(BaseCommand):
    help = 'Send a test email to verify email settings (Resend API / SMTP) on Render or local environment'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Recipient email address')

    def handle(self, *args, **options):
        recipient = options['email'].strip()
        self.stdout.write(self.style.NOTICE(f"🔍 Testing email dispatch to: {recipient}"))
        
        # Display current configuration
        resend_key = getattr(settings, 'RESEND_API_KEY', '')
        self.stdout.write(f"- RESEND_API_KEY present: {bool(resend_key)}")
        self.stdout.write(f"- EMAIL_HOST: {getattr(settings, 'EMAIL_HOST', '')}")
        self.stdout.write(f"- EMAIL_PORT: {getattr(settings, 'EMAIL_PORT', '')}")
        self.stdout.write(f"- EMAIL_USE_TLS: {getattr(settings, 'EMAIL_USE_TLS', '')}")
        self.stdout.write(f"- EMAIL_USE_SSL: {getattr(settings, 'EMAIL_USE_SSL', '')}")
        self.stdout.write(f"- EMAIL_HOST_USER present: {bool(getattr(settings, 'EMAIL_HOST_USER', ''))}")
        self.stdout.write(f"- DEFAULT_FROM_EMAIL: {getattr(settings, 'DEFAULT_FROM_EMAIL', '')}")
        self.stdout.write(f"- FRONTEND_URL: {getattr(settings, 'FRONTEND_URL', '')}")

        subject = "Test Email from AnonQ"
        plain_message = "This is a test email sent from AnonQ backend to verify email configuration."
        html_message = """
        <div style="font-family: Arial, sans-serif; padding: 20px; background-color: #0b0f19; color: #ffffff; border-radius: 12px;">
            <h1 style="color: #3b82f6;">AnonQ Email Verification Test</h1>
            <p>Your email service (Resend API / SMTP) is working properly on production!</p>
        </div>
        """

        success = dispatch_email(subject, plain_message, html_message, recipient)

        if success:
            self.stdout.write(self.style.SUCCESS(f"✅ Successfully sent test email to {recipient}!"))
        else:
            self.stdout.write(self.style.ERROR(f"❌ Failed to send test email to {recipient}. Check logs for details."))

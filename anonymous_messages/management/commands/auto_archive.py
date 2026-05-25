# backend/anonymous_messages/management/commands/auto_archive.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from anonymous_messages.models import AnonymousMessage

class Command(BaseCommand):
    help = 'Archive messages older than 10 days'

    def handle(self, *args, **options):
        cutoff_date = timezone.now() - timedelta(days=10)
        old_messages = AnonymousMessage.objects.filter(
            created_at__lt=cutoff_date,
            is_archived=False
        )
        
        count = old_messages.update(is_archived=True, archived_at=timezone.now())
        self.stdout.write(f'Archived {count} messages')
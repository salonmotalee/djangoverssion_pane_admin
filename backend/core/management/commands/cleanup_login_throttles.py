from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from core.models import LoginThrottle


class Command(BaseCommand):
    help = "Remove inactive login throttle records older than one day. Schedule daily if needed."

    def handle(self, *args, **options):
        now = timezone.now()
        deleted, _ = (
            LoginThrottle.objects.filter(window_started_at__lt=now - timedelta(days=1))
            .filter(Q(locked_until__isnull=True) | Q(locked_until__lte=now))
            .delete()
        )
        self.stdout.write(f"Removed {deleted} inactive login counters.")

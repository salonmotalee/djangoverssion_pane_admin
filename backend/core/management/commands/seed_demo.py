"""Optional data only. Never creates users or credentials."""

import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Customer


class Command(BaseCommand):
    help = "افزودن داده‌های نمونه مشتری؛ بدون ایجاد حساب کاربری"

    def add_arguments(self, parser):
        parser.add_argument("--customers", type=int, default=24)

    def handle(self, *args, **options):
        count = options["customers"]
        if not 1 <= count <= 200:
            raise CommandError("تعداد مشتری باید بین ۱ تا ۲۰۰ باشد.")
        names = [
            "خانه کتاب روشن",
            "سالن مطالعه سپید",
            "آکادمی مسیر",
            "مطالعه‌سرای آبان",
            "خانه دانش سرو",
            "مرکز مطالعه پارسا",
            "سالن مطالعه رویا",
            "کتابخانه نارون",
        ]
        managers = ["مریم کریمی", "علی رضایی", "نگار محمدی", "محمد حسینی", "سارا احمدی", "رضا موسوی"]
        rng = random.Random(42)
        today = timezone.localdate()
        with transaction.atomic():
            for i in range(count):
                start = (
                    today + timedelta(days=14) if i % 8 == 0 else today - timedelta(days=rng.randint(30, 240))
                )
                end = (
                    start + timedelta(days=120)
                    if start > today
                    else today + timedelta(days=[-10, 3, 7, 21, 30, 60, 90][i % 7])
                )
                customer = Customer.objects.create(
                    name=f"{names[i % len(names)]} {i + 1}",
                    manager_name=managers[i % len(managers)],
                    phone=f"0912{rng.randint(0, 9999999):07d}",
                    start_date=start,
                    expiration_date=end,
                )
                Customer.objects.filter(pk=customer.pk).update(
                    created_at=timezone.now() - timedelta(days=rng.randint(0, 150))
                )
        self.stdout.write(self.style.SUCCESS(f"{count} مشتری نمونه ایجاد شد. حساب کاربری ایجاد نشد."))

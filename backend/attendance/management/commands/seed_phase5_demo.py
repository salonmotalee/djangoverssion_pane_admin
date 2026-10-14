"""Explicit, additive sample data; never creates credentials or changes capacity."""

from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from attendance.models import AttendanceRecord, PresenceEvent
from attendance.services import TEHRAN, create_decision
from core.models import Customer
from operations.models import Hall, HallSession, Student, StudySession, SupervisorHall
from scheduling.models import ScheduleAssignment, ScheduleAudit, WorkShift
from staff.models import SupervisorAccount

MARKER = "DAMAVAND_PHASE5_DEMO"


class Command(BaseCommand):
    help = "ایجاد دادهٔ نمونهٔ افزایشی فاز ۵ برای یک حساب مراقب موجود؛ بدون ایجاد رمز یا افزایش ظرفیت"

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True, help="نشانی مجموعهٔ موجود")
        parser.add_argument("--account", required=True, type=int, help="شناسهٔ حساب فعال مراقب همین مجموعه")

    @transaction.atomic
    def handle(self, *args, **options):
        organization = (
            Customer.objects.select_for_update()
            .filter(slug=options["organization"], deleted_at__isnull=True)
            .first()
        )
        if not organization:
            raise CommandError("مجموعهٔ فعال یافت نشد.")
        account = (
            SupervisorAccount.objects.select_related("supervisor", "organization")
            .filter(pk=options["account"], organization=organization)
            .first()
        )
        if account is None or not account.access_is_valid:
            raise CommandError("حساب مراقب باید فعال، معتبر و متعلق به همین مجموعه باشد.")
        manager = organization.portal_owner
        if manager is None:
            raise CommandError("حساب مدیر مجموعه یافت نشد.")
        identifiers = [f"DEMO-P5-{organization.pk}-{index}" for index in range(1, 4)]
        missing = sum(
            not Student.objects.filter(organization=organization, identifier=value).exists()
            for value in identifiers
        )
        enrolled = Student.objects.filter(organization=organization, is_active=True).count()
        if organization.capacity is None or enrolled + missing > organization.capacity:
            raise CommandError("برای دادهٔ نمونه به ظرفیت خالی کافی نیاز است؛ ظرفیت مجموعه تغییر نکرد.")
        hall, _ = Hall.objects.get_or_create(
            organization=organization,
            name="نمونهٔ فاز ۵ — افق",
            description=MARKER,
            defaults={"is_active": True},
        )
        if not hall.is_active:
            raise CommandError("سالن نمونه بایگانی شده است؛ ابتدا خودتان آن را بازیابی کنید.")
        SupervisorHall.objects.get_or_create(supervisor=account.supervisor, hall=hall)
        session, _ = StudySession.objects.get_or_create(
            organization=organization,
            title="نمونهٔ فاز ۵ — مطالعهٔ صبح",
            start_time="08:00",
            end_time="10:00",
            is_active=True,
        )
        HallSession.objects.get_or_create(hall=hall, session=session)
        shift, _ = WorkShift.objects.get_or_create(
            organization=organization,
            name="نمونهٔ فاز ۵ — صبح",
            start_time="08:00",
            end_time="12:00",
            is_active=True,
        )
        names = [("سارا", "نمونهٔ حاضر"), ("سینا", "نمونهٔ تأخیر"), ("رها", "نمونهٔ غایب")]
        students = []
        for identifier, (first, last) in zip(identifiers, names, strict=True):
            student, created = Student.objects.get_or_create(
                organization=organization,
                identifier=identifier,
                defaults={
                    "hall": hall,
                    "first_name": first,
                    "last_name": last,
                    "primary_phone": "09120000000",
                    "grade": 12,
                    "major": "experimental",
                },
            )
            if not created and (
                student.hall_id != hall.pk or student.first_name != first or student.last_name != last
            ):
                raise CommandError("شناسهٔ نمونه با دادهٔ موجود تداخل دارد؛ هیچ داده‌ای بازنویسی نشد.")
            students.append(student)
        day = timezone.localdate() - timedelta(days=1)
        start = datetime.combine(day, datetime.min.time(), tzinfo=TEHRAN) + timedelta(hours=8)
        end = start + timedelta(hours=2)
        for index, student in enumerate(students):
            if AttendanceRecord.objects.filter(
                organization=organization, hall=hall, session=session, date=day, student=student
            ).exists():
                continue
            if PresenceEvent.objects.filter(student=student).exists():
                self.stdout.write(
                    f"تاریخچهٔ موجود دانش‌آموز {student.identifier} حفظ شد؛ نمونهٔ حضور افزوده نشد."
                )
                continue
            status = ["present", "late", "absent"][index]
            departure = end - timedelta(minutes=15) if index == 0 else end
            if index < 2:
                entry = start - timedelta(minutes=10) if index == 0 else start + timedelta(minutes=20)
                for sequence, (kind, instant) in enumerate((("entry", entry), ("exit", departure)), 1):
                    PresenceEvent.objects.create(
                        organization=organization,
                        student=student,
                        hall=hall,
                        hall_name=hall.name,
                        actor=account,
                        kind=kind,
                        sequence=sequence,
                        occurred_at=instant,
                    )
            record = create_decision(
                organization,
                account,
                hall,
                session,
                day,
                start,
                end,
                student,
                {
                    "status": status,
                    "early_departure": index == 0,
                    "departed_at": departure if index == 0 else None,
                },
                "automatic",
            )
            record.roster_context = {"demo": MARKER}
            record.save(update_fields=["roster_context"])
        today = timezone.localdate()
        created_schedule = 0
        for offset in range(7):
            scheduled_date = today + timedelta(days=offset)
            existing = ScheduleAssignment.objects.filter(
                organization=organization,
                supervisor=account.supervisor,
                date=scheduled_date,
            )
            if existing.filter(hall=hall, shift=shift).exists():
                continue
            if existing.filter(start_time__lt=shift.end_time, end_time__gt=shift.start_time).exists():
                self.stdout.write(
                    f"شیفت نمونهٔ {scheduled_date} به علت تداخل افزوده نشد؛ برنامهٔ موجود حفظ شد."
                )
                continue
            ScheduleAssignment.objects.create(
                organization=organization,
                date=scheduled_date,
                hall=hall,
                shift=shift,
                supervisor=account.supervisor,
                start_time=shift.start_time,
                end_time=shift.end_time,
                shift_name=shift.name,
                created_by=manager,
            )
            created_schedule += 1
        if created_schedule:
            ScheduleAudit.objects.create(
                organization=organization,
                actor=manager,
                action="demo_seed",
                changes={"created": created_schedule, "marker": MARKER},
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"نمونهٔ فاز ۵ آماده شد؛ سالن {hall.pk}، حساب {account.pk}، تاریخ حضور {day}، شیفت تازه {created_schedule}. "
                "دادهٔ قبلی، ظرفیت و رمزهای ورود حفظ شدند."
            )
        )

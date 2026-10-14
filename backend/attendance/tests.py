"""API isolation, historical interval calculations and immutable record ownership."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Customer
from operations.models import Hall, HallSession, Student, StudySession, Supervisor, SupervisorHall
from portal.services import provision_portal
from staff.models import SupervisorAccount

from .models import AttendanceAudit, AttendanceRecord, PresenceEvent
from .services import TEHRAN, calculate_status


class IntervalTests(SimpleTestCase):
    start = datetime(2026, 10, 1, 8, tzinfo=TEHRAN)
    end = start + timedelta(hours=2)

    def calculate(self, pairs):
        events = [
            SimpleNamespace(kind=kind, occurred_at=self.start + timedelta(minutes=minute), hall_id=hall)
            for kind, minute, hall in pairs
        ]
        return calculate_status(events, 1, self.start, self.end)

    def test_inside_at_start_is_present(self):
        self.assertEqual(self.calculate([("entry", -30, 1), ("exit", 120, 1)])["status"], "present")

    def test_entry_at_start_is_present(self):
        self.assertEqual(self.calculate([("entry", 0, 1)])["status"], "present")

    def test_entry_at_end_is_absent(self):
        self.assertEqual(self.calculate([("entry", 120, 1)])["status"], "absent")

    def test_exit_at_start_and_later_return_is_late(self):
        result = self.calculate([("entry", -30, 1), ("exit", 0, 1), ("entry", 45, 1)])
        self.assertEqual(result["status"], "late")
        self.assertFalse(result["early_departure"])

    def test_no_overlap_and_other_hall_are_absent(self):
        for pairs in ([], [("entry", -60, 1), ("exit", -1, 1)], [("entry", -30, 2)]):
            self.assertEqual(self.calculate(pairs)["status"], "absent")

    def test_present_departure_is_additional_indicator(self):
        result = self.calculate([("entry", -10, 1), ("exit", 45, 1)])
        self.assertEqual(result["status"], "present")
        self.assertTrue(result["early_departure"])
        self.assertEqual(result["departed_at"], self.start + timedelta(minutes=45))

    def test_late_departure_keeps_late(self):
        result = self.calculate([("entry", 20, 1), ("exit", 80, 1)])
        self.assertEqual(result["status"], "late")
        self.assertTrue(result["early_departure"])

    def test_reentry_before_end_clears_early_departure(self):
        result = self.calculate([("entry", -10, 1), ("exit", 45, 1), ("entry", 90, 1)])
        self.assertEqual(result["status"], "present")
        self.assertFalse(result["early_departure"])

    def test_multiple_intervals_keep_last_actual_departure(self):
        result = self.calculate([("entry", 10, 1), ("exit", 45, 1), ("entry", 70, 1), ("exit", 100, 1)])
        self.assertEqual(result["status"], "late")
        self.assertEqual(result["departed_at"], self.start + timedelta(minutes=100))

    def test_zero_length_visit_is_not_presence(self):
        self.assertEqual(self.calculate([("entry", 10, 1), ("exit", 10, 1)])["status"], "absent")


class AttendanceAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Customer.objects.create(
            name="آفتاب",
            manager_name="مدیر",
            phone="09123456789",
            slug="aftab",
            capacity=20,
            start_date="2020-01-01",
            expiration_date="2020-12-31",
        )
        cls.foreign_org = Customer.objects.create(
            name="دریا",
            manager_name="مدیر",
            phone="09123456789",
            slug="darya",
            capacity=20,
            start_date="2020-01-01",
            expiration_date="2020-12-31",
        )
        cls.owner = provision_portal(
            cls.org, {"login_username": "manager", "login_password": "Testing$Only2026!"}
        )
        cls.foreign_owner = provision_portal(
            cls.foreign_org, {"login_username": "manager", "login_password": "Testing$Only2026!"}
        )
        cls.hall = Hall.objects.create(organization=cls.org, name="سالن روشن")
        cls.second = Hall.objects.create(organization=cls.org, name="سالن آرام")
        cls.foreign_hall = Hall.objects.create(organization=cls.foreign_org, name="سالن دریا")
        cls.session = StudySession.objects.create(
            organization=cls.org, title="صبح", start_time="08:00", end_time="10:00"
        )
        HallSession.objects.create(hall=cls.hall, session=cls.session)
        HallSession.objects.create(hall=cls.second, session=cls.session)
        cls.person = Supervisor.objects.create(
            organization=cls.org, first_name="سارا", last_name="رضایی", phone="09123456789"
        )
        cls.other_person = Supervisor.objects.create(
            organization=cls.org, first_name="مریم", last_name="احمدی", phone="09123456788"
        )
        SupervisorHall.objects.create(supervisor=cls.person, hall=cls.hall)
        SupervisorHall.objects.create(supervisor=cls.other_person, hall=cls.hall)
        cls.account = SupervisorAccount.objects.create_user(cls.person, password="Testing$Only2026!")
        cls.other_account = SupervisorAccount.objects.create_user(
            cls.other_person, password="Testing$Only2026!"
        )
        cls.student = cls.make_student("A-001", cls.hall)
        cls.student2 = cls.make_student("A-002", cls.hall)
        cls.outside = cls.make_student("B-001", cls.second)
        cls.foreign_student = cls.make_student("F-001", cls.foreign_hall)

    @classmethod
    def make_student(cls, identifier, hall):
        return Student.objects.create(
            organization=hall.organization,
            hall=hall,
            identifier=identifier,
            first_name="سینا",
            last_name=identifier,
            primary_phone="09123456789",
            grade=12,
            major="mathematics",
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.account)
        self.base = "/api/organizations/aftab/supervisor/"
        self.day = timezone.localdate() - timedelta(days=1)
        self.start = datetime.combine(self.day, datetime.min.time(), tzinfo=TEHRAN) + timedelta(hours=8)
        self.end = self.start + timedelta(hours=2)

    def post(self, path, data):
        return self.client.post(self.base + path, data, format="json")

    def selection(self, **changes):
        return {"hall": self.hall.pk, "date": self.day.isoformat(), "session": self.session.pk, **changes}

    def manual(self, student=None, status="present", revision=None):
        item = {"student": (student or self.student).pk, "status": status}
        if revision is not None:
            item["revision"] = revision
        return self.post("attendance/bulk/", {**self.selection(), "records": [item]})

    def event(self, kind, minute, student=None, hall=None):
        student = student or self.student
        hall = hall or self.hall
        return PresenceEvent.objects.create(
            organization=self.org,
            student=student,
            hall=hall,
            hall_name=hall.name,
            actor=self.account,
            kind=kind,
            sequence=PresenceEvent.objects.filter(student=student).count() + 1,
            occurred_at=self.start + timedelta(minutes=minute),
        )

    def preview(self):
        response = self.post("attendance/preview/", self.selection())
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def finalize(self, preview, students=None):
        return self.post(
            "attendance/automatic/",
            {"preview_token": preview["preview_token"], "students": students or [self.student.pk]},
        )

    def test_shift_hours_do_not_restrict_supervisor(self):
        self.assertEqual(self.client.get(self.base + "dashboard/").status_code, 200)
        self.assertEqual(self.client.get(self.base + "students/").data["count"], 2)
        self.assertEqual(
            self.post("presence/", {"student": self.student.pk, "kind": "entry"}).status_code, 201
        )

    def test_presence_entry_exit_server_timestamp_and_duplicates(self):
        before = timezone.now()
        first = self.post(
            "presence/", {"student": self.student.pk, "kind": "entry", "occurred_at": "2000-01-01T00:00:00Z"}
        )
        self.assertEqual(first.status_code, 201)
        self.assertGreaterEqual(PresenceEvent.objects.get(pk=first.data["id"]).occurred_at, before)
        self.assertEqual(
            self.post("presence/", {"student": self.student.pk, "kind": "entry"}).status_code, 400
        )
        self.assertTrue(self.client.get(self.base + "students/").data["results"][0]["inside"])
        self.assertEqual(
            self.post("presence/", {"student": self.student.pk, "kind": "exit"}).status_code, 201
        )
        self.assertEqual(
            self.post("presence/", {"student": self.student.pk, "kind": "exit"}).status_code, 400
        )
        history = self.client.get(self.base + "presence/").data["results"]
        self.assertEqual([event["kind"] for event in history], ["entry", "exit"])
        self.assertFalse(self.client.get(self.base + "students/").data["results"][0]["inside"])

    def test_exit_without_entry_rejected(self):
        self.assertEqual(
            self.post("presence/", {"student": self.student.pk, "kind": "exit"}).status_code, 400
        )

    def test_presence_isolation_and_disabled_access(self):
        for student in (self.outside, self.foreign_student):
            self.assertEqual(
                self.post("presence/", {"student": student.pk, "kind": "entry"}).status_code, 404
            )
        self.assertEqual(self.client.get(self.base.replace("aftab", "darya") + "students/").status_code, 403)
        SupervisorHall.objects.filter(supervisor=self.person, hall=self.hall).delete()
        self.assertEqual(
            self.post("presence/", {"student": self.student.pk, "kind": "entry"}).status_code, 404
        )

    def test_transfer_preserves_historical_hall_and_closes_inherited_entry(self):
        entered = self.post("presence/", {"student": self.student.pk, "kind": "entry"})
        self.student.hall = self.second
        self.student.save()
        SupervisorHall.objects.create(supervisor=self.person, hall=self.second)
        SupervisorHall.objects.filter(supervisor=self.person, hall=self.hall).delete()
        self.assertEqual(
            self.post("presence/", {"student": self.student.pk, "kind": "entry"}).status_code, 400
        )
        exited = self.post("presence/", {"student": self.student.pk, "kind": "exit"})
        self.assertEqual(exited.status_code, 201, exited.data)
        self.assertEqual(exited.data["hall"], self.hall.pk)
        self.assertEqual(PresenceEvent.objects.get(pk=entered.data["id"]).hall_id, self.hall.pk)
        self.assertEqual(self.client.get(self.base + "presence/").data["count"], 0)
        self.assertEqual(
            self.post("presence/", {"student": self.student.pk, "kind": "entry"}).data["hall"], self.second.pk
        )

    def test_manual_creates_owned_unique_record_and_rejects_duplicate_targets(self):
        self.assertEqual(self.manual().status_code, 200)
        record = AttendanceRecord.objects.get()
        self.assertEqual(record.original_recorder_id, self.account.pk)
        self.assertEqual(record.source, "manual")
        created = record.created_at
        self.assertEqual(self.manual(status="late", revision=1).status_code, 200)
        record.refresh_from_db()
        self.assertEqual(record.revision, 2)
        self.assertEqual(record.created_at, created)
        self.assertEqual(self.manual(status="absent", revision=1).status_code, 409)
        duplicate = self.post(
            "attendance/bulk/",
            {
                **self.selection(),
                "records": [
                    {"student": self.student.pk, "status": "present"},
                    {"student": self.student.pk, "status": "absent"},
                ],
            },
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    def test_manual_bulk_is_atomic_and_scoped(self):
        response = self.post(
            "attendance/bulk/",
            {
                **self.selection(),
                "records": [
                    {"student": self.student.pk, "status": "present"},
                    {"student": self.outside.pk, "status": "present"},
                ],
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AttendanceRecord.objects.exists())
        self.assertEqual(
            self.post(
                "attendance/bulk/",
                {
                    **self.selection(hall=self.second.pk),
                    "records": [{"student": self.outside.pk, "status": "present"}],
                },
            ).status_code,
            404,
        )

    def test_future_manual_and_missing_session_rejected(self):
        self.assertEqual(
            self.post(
                "attendance/bulk/",
                {
                    **self.selection(date=(timezone.localdate() + timedelta(days=1)).isoformat()),
                    "records": [{"student": self.student.pk, "status": "present"}],
                },
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post(
                "attendance/preview/", {"hall": self.hall.pk, "date": self.day.isoformat()}
            ).status_code,
            400,
        )

    def test_other_supervisor_views_but_cannot_edit(self):
        self.manual()
        self.client.force_authenticate(self.other_account)
        result = self.client.get(self.base + "attendance/", self.selection())
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.data["students"][0]["record"]["can_edit"])
        self.assertEqual(self.manual(status="absent", revision=1).status_code, 403)

    def test_owner_edit_deadline_does_not_restart(self):
        self.manual()
        record = AttendanceRecord.objects.get()
        initial = timezone.now() - timedelta(hours=47)
        AttendanceRecord.objects.filter(pk=record.pk).update(created_at=initial)
        self.assertEqual(self.manual(status="late", revision=1).status_code, 200)
        with patch("attendance.views.timezone.now", return_value=initial + timedelta(hours=48, seconds=1)):
            self.assertEqual(self.manual(status="absent", revision=2).status_code, 403)
        record.refresh_from_db()
        self.assertEqual(record.created_at, initial)
        self.assertEqual(record.status, "late")

    def test_manager_override_requires_reason_and_audits_original_owner(self):
        self.manual()
        record = AttendanceRecord.objects.get()
        initial = timezone.now() - timedelta(days=4)
        AttendanceRecord.objects.filter(pk=record.pk).update(created_at=initial)
        self.client.force_authenticate(self.owner)
        url = "/api/organizations/aftab/attendance/corrections/"
        payload = {"records": [{"id": record.pk, "status": "absent", "revision": 1}]}
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 400)
        response = self.client.post(url, {**payload, "reason": "اصلاح پس از بررسی گزارش"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        record.refresh_from_db()
        self.assertEqual(record.created_at, initial)
        self.assertEqual(record.original_recorder_id, self.account.pk)
        audit = AttendanceAudit.objects.get()
        self.assertEqual(audit.acting_manager_id, self.owner.pk)
        self.assertEqual(audit.original_recorder_id, self.account.pk)
        self.assertEqual(audit.previous["status"], "present")
        self.assertEqual(audit.new["status"], "absent")
        self.assertEqual(
            self.client.post(url, {**payload, "reason": "دوباره"}, format="json").status_code, 409
        )

    def test_foreign_manager_cannot_correct(self):
        self.manual()
        record = AttendanceRecord.objects.get()
        self.client.force_authenticate(self.foreign_owner)
        response = self.client.post(
            "/api/organizations/darya/attendance/corrections/",
            {"records": [{"id": record.pk, "status": "absent", "revision": 1}], "reason": "اصلاح گزارش"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AttendanceAudit.objects.exists())

    def test_manager_correction_marks_automatic_record_manual_and_prevents_auto_overwrite(self):
        self.assertEqual(self.finalize(self.preview()).status_code, 200)
        record = AttendanceRecord.objects.get()
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            "/api/organizations/aftab/attendance/corrections/",
            {
                "records": [{"id": record.pk, "status": "present", "revision": 1}],
                "reason": "اصلاح وضعیت توسط مدیر",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(self.account)
        preview = self.preview()
        self.assertEqual(preview["students"][0]["record"]["source"], "manual")
        self.assertEqual(self.finalize(preview).status_code, 403)

    def test_automatic_uses_historical_intervals_and_preserves_early_departure(self):
        self.event("entry", -10)
        self.event("exit", 40)
        self.event("entry", 15, student=self.student2)
        self.event("exit", 90, student=self.student2)
        preview = self.preview()
        self.assertEqual([s["calculated_status"] for s in preview["students"]], ["present", "late"])
        self.assertTrue(preview["students"][0]["early_departure"])
        self.assertEqual(self.finalize(preview, [self.student.pk, self.student2.pk]).status_code, 200)
        rows = AttendanceRecord.objects.order_by("student_id")
        self.assertEqual([r.status for r in rows], ["present", "late"])
        self.assertTrue(all(r.early_departure for r in rows))
        self.assertTrue(all(r.original_recorder_id == self.account.pk for r in rows))

    def test_ongoing_preview_is_provisional_and_cannot_finalize(self):
        self.event("entry", -10)
        with patch("attendance.views.timezone.now", return_value=self.start + timedelta(minutes=30)):
            preview = self.preview()
            self.assertTrue(preview["provisional"])
            self.assertEqual(self.finalize(preview).status_code, 400)
        self.assertEqual(self.finalize(preview).status_code, 400)
        self.assertEqual(self.finalize(self.preview()).status_code, 200)

    def test_preview_before_session_starts_rejected(self):
        with patch("attendance.views.timezone.now", return_value=self.start - timedelta(seconds=1)):
            self.assertEqual(self.post("attendance/preview/", self.selection()).status_code, 400)

    def test_automatic_manual_records_never_overwritten(self):
        self.manual(status="late")
        preview = self.preview()
        self.assertFalse(preview["students"][0]["selectable"])
        self.assertEqual(self.finalize(preview).status_code, 403)
        self.assertEqual(self.finalize(preview, [self.student2.pk]).status_code, 200)
        self.assertEqual(AttendanceRecord.objects.get(student=self.student).status, "late")

    def test_automatic_only_owner_can_edit_existing_automatic(self):
        self.assertEqual(self.finalize(self.preview()).status_code, 200)
        self.client.force_authenticate(self.other_account)
        preview = self.preview()
        self.assertFalse(preview["students"][0]["selectable"])
        self.assertEqual(self.finalize(preview).status_code, 403)
        self.client.force_authenticate(self.account)
        self.assertEqual(self.finalize(self.preview()).status_code, 200)
        self.assertEqual(AttendanceRecord.objects.get().revision, 2)

    def test_stale_preview_is_rejected_after_events_or_records_change(self):
        preview = self.preview()
        self.event("entry", 15)
        self.assertEqual(self.finalize(preview).status_code, 409)
        preview = self.preview()
        self.manual(status="late")
        self.assertEqual(self.finalize(preview).status_code, 409)

    def test_preview_account_binding_and_tampering_rejected(self):
        preview = self.preview()
        self.client.force_authenticate(self.other_account)
        self.assertEqual(self.finalize(preview).status_code, 403)
        self.client.force_authenticate(self.account)
        preview["preview_token"] += "tampered"
        self.assertEqual(self.finalize(preview).status_code, 409)

    def test_records_survive_transfer_and_session_time_changes(self):
        self.event("entry", -10)
        self.event("exit", 40)
        self.manual()
        record = AttendanceRecord.objects.get()
        self.student.hall = self.second
        self.student.save()
        self.session.start_time = "11:00"
        self.session.end_time = "12:00"
        self.session.save()
        response = self.client.get(self.base + "attendance/", self.selection())
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.student.pk, [s["id"] for s in response.data["students"]])
        self.assertEqual(response.data["starts_at"].hour, 8)
        self.assertEqual(AttendanceRecord.objects.get(pk=record.pk).hall_id, self.hall.pk)

    def test_db_constraints_prevent_duplicate_and_invalid_decisions(self):
        self.manual()
        existing = AttendanceRecord.objects.get()
        existing.pk = None
        with self.assertRaises(IntegrityError), transaction.atomic():
            existing.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            AttendanceRecord.objects.filter(pk=AttendanceRecord.objects.get().pk).update(status="unknown")

    def test_presence_history_cannot_be_rewritten(self):
        from django.core.exceptions import ValidationError as ModelValidationError

        event = self.event("entry", -10)
        event.hall = self.second
        with self.assertRaises(ModelValidationError):
            event.save()

    def test_optional_demo_seed_is_additive_idempotent_and_preserves_credentials(self):
        from io import StringIO

        from django.core.management import call_command

        from scheduling.models import ScheduleAssignment

        before_password = self.account.password
        for _ in range(2):
            call_command("seed_phase5_demo", organization="aftab", account=self.account.pk, stdout=StringIO())
        self.assertEqual(
            Student.objects.filter(organization=self.org, identifier__startswith="DEMO-P5-").count(), 3
        )
        self.assertEqual(AttendanceRecord.objects.count(), 3)
        self.assertEqual(ScheduleAssignment.objects.count(), 7)
        self.account.refresh_from_db()
        self.org.refresh_from_db()
        self.assertEqual(self.account.password, before_password)
        self.assertEqual(self.org.capacity, 20)
        self.assertEqual(AttendanceRecord.objects.filter(early_departure=True).count(), 1)

    def test_optional_demo_seed_insufficient_capacity_rolls_back_everything(self):
        from io import StringIO

        from django.core.management import call_command
        from django.core.management.base import CommandError

        self.org.capacity = 3
        self.org.save()
        with self.assertRaises(CommandError):
            call_command("seed_phase5_demo", organization="aftab", account=self.account.pk, stdout=StringIO())
        self.assertEqual(Hall.objects.filter(organization=self.org).count(), 2)
        self.assertFalse(Student.objects.filter(identifier__startswith="DEMO-P5-").exists())
        self.assertFalse(PresenceEvent.objects.exists())


class ConcurrentAttendanceTests(SimpleTestCase):
    def test_real_writers_serialize_presence_and_new_attendance(self):
        """Two independent processes compete against actual SQLite file locks."""
        import json
        import os
        import subprocess
        import sys
        import tempfile
        import time
        from pathlib import Path

        from django.conf import settings

        bootstrap = """
import django
django.setup()
from django.core.management import call_command
from core.models import Customer
from operations.models import Hall,StudySession,HallSession,Student,Supervisor,SupervisorHall
from staff.models import SupervisorAccount
call_command('migrate',verbosity=0,interactive=False)
o=Customer.objects.create(name='Concurrency',manager_name='Manager',phone='09123456789',slug='attendance-race',capacity=5,start_date='2020-01-01',expiration_date='2020-12-31')
h=Hall.objects.create(organization=o,name='Hall')
s=StudySession.objects.create(organization=o,title='Morning',start_time='08:00',end_time='10:00')
HallSession.objects.create(hall=h,session=s)
p=Supervisor.objects.create(organization=o,first_name='Supervisor',last_name='Test',phone='09123456789')
SupervisorHall.objects.create(supervisor=p,hall=h)
a=SupervisorAccount.objects.create_user(p,password='Testing$Only2026!')
Student.objects.create(organization=o,hall=h,identifier='RACE',first_name='Student',last_name='Test',primary_phone='09123456789',grade=12,major='other')
"""
        worker = """
import django,os,time,json
from pathlib import Path
from datetime import timedelta
django.setup()
from django.utils import timezone
from attendance.models import PresenceEvent,AttendanceRecord
from staff.models import SupervisorAccount
from rest_framework.test import APIClient
import attendance.views as views
original=views.record_presence if os.environ['MODE']=='presence' else views.create_decision
def slow(*args,**kwargs):
    time.sleep(.15)
    return original(*args,**kwargs)
if os.environ['MODE']=='presence': views.record_presence=slow
else: views.create_decision=slow
client=APIClient()
client.force_authenticate(SupervisorAccount.objects.get())
Path(os.environ['READY']).touch()
while not Path(os.environ['RELEASE']).exists(): time.sleep(.01)
if os.environ['MODE']=='presence':
    response=client.post('/api/organizations/attendance-race/supervisor/presence/',{'student':1,'kind':'entry'},format='json')
    count=PresenceEvent.objects.count()
else:
    response=client.post('/api/organizations/attendance-race/supervisor/attendance/bulk/',{'hall':1,'session':1,'date':(timezone.localdate()-timedelta(days=1)).isoformat(),'records':[{'student':1,'status':'present'}]},format='json')
    count=AttendanceRecord.objects.count()
print(json.dumps({'status':response.status_code,'count':count}))
"""
        with tempfile.TemporaryDirectory(prefix="damavand-presence-race-") as tmp:
            task_env = {
                **os.environ,
                "DATABASE_URL": "sqlite:///" + str(Path(tmp) / "test.sqlite3"),
                "DJANGO_SETTINGS_MODULE": "config.settings",
                "DEBUG": "true",
                "ALLOWED_HOSTS": "testserver",
            }
            subprocess.run(
                [sys.executable, "-c", bootstrap],
                cwd=settings.BASE_DIR,
                env=task_env,
                check=True,
                capture_output=True,
                timeout=30,
            )
            for mode, expected in [("presence", [201, 400]), ("attendance", [200, 409])]:
                processes = []
                try:
                    release = Path(tmp) / (mode + "-release")
                    for index in range(2):
                        child_env = {
                            **task_env,
                            "MODE": mode,
                            "READY": str(Path(tmp) / f"{mode}-{index}"),
                            "RELEASE": str(release),
                        }
                        processes.append(
                            subprocess.Popen(
                                [sys.executable, "-c", worker],
                                cwd=settings.BASE_DIR,
                                env=child_env,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                            )
                        )
                    deadline = time.monotonic() + 15
                    while not all((Path(tmp) / f"{mode}-{index}").exists() for index in range(2)):
                        self.assertLess(time.monotonic(), deadline, "Concurrent workers did not become ready")
                        time.sleep(0.02)
                    release.touch()
                    results = []
                    for process in processes:
                        output, error = process.communicate(timeout=20)
                        self.assertEqual(process.returncode, 0, error)
                        results.append(json.loads(output))
                    self.assertEqual(sorted(item["status"] for item in results), sorted(expected))
                    self.assertTrue(all(item["count"] == 1 for item in results))
                finally:
                    for process in processes:
                        if process.poll() is None:
                            process.kill()
                        process.wait()

"""Independent security regression checks for authentication realms and bulk writes."""

import json
import os
import subprocess
import sys
import tempfile
import time as clock_time
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from attendance.models import AttendanceAudit, AttendanceRecord, PresenceEvent
from core.models import AuditLog, Customer, User
from operations.models import Hall, HallSession, Student, StudySession, Supervisor
from operations.services import assign_supervisor_halls, change_supervisor_status
from portal.services import provision_portal
from staff.models import SupervisorAccount
from staff.services import provision_supervisor

PASSWORD = "Independent$Security2026!"


class Phase5RealmSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Customer.objects.create(
            name="امنیت آفتاب",
            manager_name="مدیر",
            slug="phase5-security",
            phone="09123456789",
            capacity=40,
            start_date=date(2025, 1, 1),
            expiration_date=date(2025, 12, 31),
        )
        cls.other_organization = Customer.objects.create(
            name="امنیت دریا",
            manager_name="مدیر دیگر",
            slug="phase5-other",
            phone="09123456789",
            capacity=40,
            start_date=date(2025, 1, 1),
            expiration_date=date(2025, 12, 31),
        )
        cls.owner = provision_portal(
            cls.organization, {"login_username": "manager", "login_password": PASSWORD}
        )
        cls.other_owner = provision_portal(
            cls.other_organization, {"login_username": "manager", "login_password": PASSWORD}
        )
        cls.central = User.objects.create_user(
            username="phase5-central", password=PASSWORD, role=User.Role.SUPER_ADMIN
        )
        cls.hall = Hall.objects.create(organization=cls.organization, name="سالن مجاز")
        cls.other_hall = Hall.objects.create(organization=cls.organization, name="سالن دیگر")
        cls.personnel = Supervisor.objects.create(
            organization=cls.organization,
            first_name="سارا",
            last_name="احمدی",
            phone="09123456789",
        )
        cls.foreign_personnel = Supervisor.objects.create(
            organization=cls.other_organization,
            first_name="سارا",
            last_name="احمدی",
            phone="09123456789",
        )
        assign_supervisor_halls(cls.personnel, [cls.hall])
        provision_supervisor(cls.organization, cls.personnel.pk, cls.owner, True, PASSWORD)
        provision_supervisor(
            cls.other_organization, cls.foreign_personnel.pk, cls.other_owner, True, PASSWORD
        )
        cls.account = SupervisorAccount.objects.get(supervisor=cls.personnel)

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.base = "/api/organizations/phase5-security/"

    def csrf(self):
        response = self.client.get("/api/auth/csrf/")
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["csrfToken"]

    def post(self, path, payload):
        return self.client.post(path, payload, format="json", HTTP_X_CSRFTOKEN=self.csrf())

    def login_staff(self, username="۰۹۱۲۳۴۵۶۷۸۹"):
        response = self.post(self.base + "supervisor/login/", {"username": username, "password": PASSWORD})
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def login_manager(self):
        response = self.post(self.base + "login/", {"username": "manager", "password": PASSWORD})
        self.assertEqual(response.status_code, 200, response.data)

    def login_central(self):
        response = self.post("/api/auth/login/", {"username": "phase5-central", "password": PASSWORD})
        self.assertEqual(response.status_code, 200, response.data)

    def test_three_sessions_coexist_and_staff_logout_is_scoped(self):
        self.login_central()
        self.login_manager()
        response = self.login_staff()
        names = (
            settings.SESSION_COOKIE_NAME,
            settings.PORTAL_SESSION_COOKIE_NAME,
            settings.SUPERVISOR_SESSION_COOKIE_NAME,
        )
        self.assertEqual(len({self.client.cookies[name].value for name in names}), 3)
        self.assertEqual(set(response.cookies), {settings.SUPERVISOR_SESSION_COOKIE_NAME, "csrftoken"})
        self.assertTrue(response.cookies[settings.SUPERVISOR_SESSION_COOKIE_NAME]["httponly"])
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)
        self.assertEqual(self.client.get(self.base + "dashboard/").status_code, 200)
        self.assertEqual(self.client.get(self.base + "supervisor/me/").status_code, 200)
        self.assertEqual(self.post(self.base + "supervisor/logout/", {}).status_code, 204)
        self.assertEqual(self.client.get(self.base + "supervisor/me/").status_code, 401)
        self.assertEqual(self.client.get(self.base + "dashboard/").status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)

    def test_replayed_staff_cookie_cannot_become_manager_or_central(self):
        self.login_staff()
        key = self.client.cookies[settings.SUPERVISOR_SESSION_COOKIE_NAME].value
        self.client.cookies[settings.PORTAL_SESSION_COOKIE_NAME] = key
        self.client.cookies[settings.SESSION_COOKIE_NAME] = key
        for path in (self.base + "dashboard/", "/api/auth/me/", "/api/customers/", "/api/users/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        response = self.post(self.base + f"supervisor-access/{self.personnel.pk}/", {})
        self.assertIn(response.status_code, (403, 405))

    def test_replayed_manager_and_central_cookies_cannot_become_staff(self):
        for login, name in (
            (self.login_manager, settings.PORTAL_SESSION_COOKIE_NAME),
            (self.login_central, settings.SESSION_COOKIE_NAME),
        ):
            with self.subTest(name=name):
                self.client = APIClient(enforce_csrf_checks=True)
                login()
                self.client.cookies[settings.SUPERVISOR_SESSION_COOKIE_NAME] = self.client.cookies[name].value
                self.assertEqual(self.client.get(self.base + "supervisor/me/").status_code, 403)

    def test_csrf_required_for_login_and_authenticated_logout(self):
        response = self.client.post(
            self.base + "supervisor/login/",
            {"username": self.personnel.phone, "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.login_staff()
        self.assertEqual(
            self.client.post(self.base + "supervisor/logout/", {}, format="json").status_code, 403
        )
        self.assertEqual(self.client.get(self.base + "supervisor/me/").status_code, 200)

    def test_tenant_scope_and_expired_subscription_are_independent(self):
        self.assertLess(self.organization.expiration_date, timezone.localdate())
        self.login_staff()
        self.assertEqual(self.client.get(self.base + "supervisor/me/").status_code, 200)
        response = self.client.get("/api/organizations/phase5-other/supervisor/me/")
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(self.other_organization.name, str(response.data))
        self.assertEqual(self.post("/api/organizations/phase5-other/supervisor/logout/", {}).status_code, 403)
        self.assertEqual(self.client.get(self.base + "supervisor/me/").status_code, 200)

    def test_access_disable_enable_never_restores_an_old_cookie(self):
        self.login_staff()
        old_key = self.client.cookies[settings.SUPERVISOR_SESSION_COOKIE_NAME].value
        provision_supervisor(self.organization, self.personnel.pk, self.owner, False)
        provision_supervisor(self.organization, self.personnel.pk, self.owner, True)
        self.client.cookies[settings.SUPERVISOR_SESSION_COOKIE_NAME] = old_key
        self.assertEqual(self.client.get(self.base + "supervisor/me/").status_code, 401)
        self.login_staff()

    def test_personnel_archive_restore_and_phone_round_trip_revoke_old_cookie(self):
        self.login_staff()
        old_key = self.client.cookies[settings.SUPERVISOR_SESSION_COOKIE_NAME].value
        change_supervisor_status(self.personnel, "archive")
        change_supervisor_status(self.personnel, "restore")
        self.client.cookies[settings.SUPERVISOR_SESSION_COOKIE_NAME] = old_key
        self.assertEqual(self.client.get(self.base + "supervisor/me/").status_code, 401)
        self.login_staff()
        old_key = self.client.cookies[settings.SUPERVISOR_SESSION_COOKIE_NAME].value
        self.personnel.refresh_from_db()
        self.personnel.phone = "09123456780"
        self.personnel.save()
        self.personnel.phone = "09123456789"
        self.personnel.save()
        self.client.cookies[settings.SUPERVISOR_SESSION_COOKIE_NAME] = old_key
        self.assertEqual(self.client.get(self.base + "supervisor/me/").status_code, 401)

    def test_organization_archive_restore_revoke_old_cookie(self):
        self.login_staff()
        old_key = self.client.cookies[settings.SUPERVISOR_SESSION_COOKIE_NAME].value
        self.organization.deleted_at = timezone.now()
        self.organization.save(update_fields=["deleted_at", "updated_at"])
        self.organization.deleted_at = None
        self.organization.save(update_fields=["deleted_at", "updated_at"])
        self.client.cookies[settings.SUPERVISOR_SESSION_COOKIE_NAME] = old_key
        self.assertEqual(self.client.get(self.base + "supervisor/me/").status_code, 401)

    def test_hall_revocation_is_visible_to_an_existing_session(self):
        self.login_staff()
        self.assertEqual(
            [row["id"] for row in self.client.get(self.base + "supervisor/me/").data["halls"]], [self.hall.pk]
        )
        assign_supervisor_halls(self.personnel, [self.other_hall])
        response = self.client.get(self.base + "supervisor/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data["halls"]], [self.other_hall.pk])

    def test_password_reset_revokes_old_session_and_audit_contains_no_secret(self):
        self.login_staff()
        old_hash = self.account.password
        new_password = PASSWORD + "Reset"
        provision_supervisor(self.organization, self.personnel.pk, self.owner, True, new_password)
        self.assertEqual(self.client.get(self.base + "supervisor/me/").status_code, 401)
        self.account.refresh_from_db()
        self.assertTrue(self.account.check_password(new_password))
        raw = str(list(AuditLog.objects.values("changes", "description")))
        for secret in (PASSWORD, new_password, old_hash, self.account.password):
            self.assertNotIn(secret, raw)

    def test_staff_session_fixation_is_rotated_and_private_response_is_not_cached(self):
        session = SessionStore()
        session["anonymous"] = True
        session.save()
        self.client.cookies[settings.SUPERVISOR_SESSION_COOKIE_NAME] = session.session_key
        response = self.login_staff()
        self.assertNotEqual(
            response.cookies[settings.SUPERVISOR_SESSION_COOKIE_NAME].value, session.session_key
        )
        self.assertFalse(SessionStore().exists(session.session_key))
        response = self.client.get(self.base + "supervisor/me/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])


class Phase5AttendanceSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Phase5RealmSecurityTests.setUpTestData.__func__(cls)
        cls.day = timezone.localdate(timezone=ZoneInfo("Asia/Tehran")) - timedelta(days=1)
        cls.session = StudySession.objects.create(
            organization=cls.organization, title="صبح", start_time=time(8), end_time=time(10)
        )
        HallSession.objects.create(hall=cls.hall, session=cls.session)
        cls.student = cls.make_student("OWN-1", cls.hall)
        cls.second_student = cls.make_student("OWN-2", cls.hall)
        cls.unauthorized_student = cls.make_student("OTHER-HALL", cls.other_hall)
        cls.peer = Supervisor.objects.create(
            organization=cls.organization, first_name="مینا", last_name="رضایی", phone="09123456788"
        )
        assign_supervisor_halls(cls.peer, [cls.hall])
        provision_supervisor(cls.organization, cls.peer.pk, cls.owner, True, PASSWORD)
        cls.peer_account = SupervisorAccount.objects.get(supervisor=cls.peer)
        cls.foreign_hall = Hall.objects.create(organization=cls.other_organization, name="سالن مجموعه دیگر")
        cls.foreign_student = cls.make_student("FOREIGN-1", cls.foreign_hall)
        cls.foreign_session = StudySession.objects.create(
            organization=cls.other_organization, title="صبح", start_time=time(8), end_time=time(10)
        )
        HallSession.objects.create(hall=cls.foreign_hall, session=cls.foreign_session)
        cls.foreign_account = SupervisorAccount.objects.get(supervisor=cls.foreign_personnel)

    @classmethod
    def make_student(cls, identifier, hall):
        return Student.objects.create(
            organization=hall.organization,
            identifier=identifier,
            first_name="دانش‌آموز",
            last_name=identifier,
            primary_phone="09123456781",
            grade=12,
            major="mathematics",
            hall=hall,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.account)
        self.base = "/api/organizations/phase5-security/"
        self.staff_base = self.base + "supervisor/"
        self.selection = {"hall": self.hall.pk, "date": self.day.isoformat(), "session": self.session.pk}

    def manual(self, records):
        return self.client.post(
            self.staff_base + "attendance/bulk/", {**self.selection, "records": records}, format="json"
        )

    def preview(self):
        response = self.client.post(self.staff_base + "attendance/preview/", self.selection, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["provisional"])
        return response.data

    def automatic(self, preview, students=None):
        return self.client.post(
            self.staff_base + "attendance/automatic/",
            {"preview_token": preview["preview_token"], "students": students or [self.student.pk]},
            format="json",
        )

    def create_record(self, student, recorder, hall=None, session=None, created_at=None):
        hall, session = hall or self.hall, session or self.session
        return AttendanceRecord.objects.create(
            organization=hall.organization,
            student=student,
            hall=hall,
            session=session,
            date=self.day,
            status="present",
            source="manual",
            original_recorder=recorder,
            hall_name=hall.name,
            session_title=session.title,
            session_start_time=session.start_time,
            session_end_time=session.end_time,
            created_at=created_at or timezone.now(),
        )

    def test_presence_timestamp_actor_tenant_and_hall_are_server_authoritative(self):
        before = timezone.now()
        response = self.client.post(
            self.staff_base + "presence/",
            {
                "student": self.student.pk,
                "kind": "entry",
                "occurred_at": "2000-01-01T00:00:00Z",
                "actor": self.peer_account.pk,
                "organization": self.other_organization.pk,
                "hall": self.other_hall.pk,
                "sequence": 999,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        event = PresenceEvent.objects.get()
        self.assertGreaterEqual(event.occurred_at, before)
        self.assertLessEqual(event.occurred_at, timezone.now())
        self.assertEqual(event.actor_id, self.account.pk)
        self.assertEqual(event.organization_id, self.organization.pk)
        self.assertEqual(event.hall_id, self.hall.pk)
        self.assertEqual(event.sequence, 1)
        self.assertEqual(
            self.client.post(
                self.staff_base + "presence/", {"student": self.student.pk, "kind": "entry"}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(PresenceEvent.objects.count(), 1)

    def test_bulk_cross_hall_and_cross_tenant_injection_is_atomic(self):
        for unauthorized in (self.unauthorized_student, self.foreign_student):
            with self.subTest(student=unauthorized.identifier):
                response = self.manual(
                    [
                        {"student": self.student.pk, "status": "present"},
                        {"student": unauthorized.pk, "status": "late"},
                    ]
                )
                self.assertEqual(response.status_code, 403, response.data)
                self.assertFalse(AttendanceRecord.objects.exists())
                self.assertFalse(AttendanceAudit.objects.exists())

    def test_bulk_non_owner_edit_cannot_partially_create_other_rows(self):
        existing = self.create_record(self.student, self.peer_account)
        response = self.manual(
            [
                {"student": self.second_student.pk, "status": "absent"},
                {"student": self.student.pk, "status": "late", "revision": existing.revision},
            ]
        )
        self.assertEqual(response.status_code, 403, response.data)
        existing.refresh_from_db()
        self.assertEqual(existing.status, "present")
        self.assertEqual(existing.revision, 1)
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        self.assertFalse(AttendanceAudit.objects.exists())

    def test_preview_cannot_finalize_after_access_disable(self):
        preview = self.preview()
        provision_supervisor(self.organization, self.personnel.pk, self.owner, False)
        response = self.automatic(preview)
        self.assertIn(response.status_code, (401, 403), response.data)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_preview_cannot_finalize_after_hall_revocation(self):
        preview = self.preview()
        assign_supervisor_halls(self.personnel, [self.other_hall])
        response = self.automatic(preview)
        self.assertIn(response.status_code, (403, 404, 409), response.data)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_preview_rejects_roster_change_after_student_transfer(self):
        preview = self.preview()
        self.student.hall = self.other_hall
        self.student.save(update_fields=["hall", "updated_at"])
        response = self.automatic(preview)
        self.assertEqual(response.status_code, 409, response.data)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_preview_rejects_new_historical_presence_before_registration(self):
        preview = self.preview()
        PresenceEvent.objects.create(
            organization=self.organization,
            student=self.student,
            hall=self.hall,
            hall_name=self.hall.name,
            actor=self.account,
            kind="entry",
            sequence=1,
            occurred_at=datetime.combine(self.day, time(7), tzinfo=ZoneInfo("Asia/Tehran")),
        )
        response = self.automatic(preview)
        self.assertEqual(response.status_code, 409, response.data)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_preview_is_bound_to_original_supervisor_even_in_same_hall(self):
        preview = self.preview()
        self.client.force_authenticate(self.peer_account)
        response = self.automatic(preview)
        self.assertEqual(response.status_code, 403, response.data)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_manual_record_cannot_be_overwritten_by_forged_automatic_selection(self):
        existing = self.create_record(self.student, self.account)
        preview = self.preview()
        row = next(row for row in preview["students"] if row["id"] == self.student.pk)
        self.assertFalse(row["selectable"])
        response = self.automatic(preview, [self.second_student.pk, self.student.pk])
        self.assertEqual(response.status_code, 403, response.data)
        existing.refresh_from_db()
        self.assertEqual(existing.status, "present")
        self.assertEqual(existing.source, "manual")
        self.assertEqual(existing.revision, 1)
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    def test_manager_cross_tenant_correction_is_atomic_and_creates_no_audit(self):
        own = self.create_record(self.student, self.account)
        foreign = self.create_record(
            self.foreign_student, self.foreign_account, self.foreign_hall, self.foreign_session
        )
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.base + "attendance/corrections/",
            {
                "reason": "اصلاح با بررسی",
                "records": [
                    {"id": own.pk, "status": "late", "revision": 1},
                    {"id": foreign.pk, "status": "absent", "revision": 1},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.data)
        own.refresh_from_db()
        foreign.refresh_from_db()
        self.assertEqual(own.status, "present")
        self.assertEqual(foreign.status, "present")
        self.assertFalse(AttendanceAudit.objects.exists())

    def test_manager_correction_preserves_expired_ownership_and_records_exact_audit(self):
        created = timezone.now() - timedelta(days=3)
        record = self.create_record(self.student, self.account, created_at=created)
        denied = self.manual([{"student": self.student.pk, "status": "late", "revision": 1}])
        self.assertEqual(denied.status_code, 403, denied.data)
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.base + "attendance/corrections/",
            {"reason": "تطبیق با دفتر سالن", "records": [{"id": record.pk, "status": "late", "revision": 1}]},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        record.refresh_from_db()
        self.assertEqual(record.original_recorder_id, self.account.pk)
        self.assertEqual(record.created_at, created)
        self.assertEqual(record.status, "late")
        audit = AttendanceAudit.objects.get(record=record)
        self.assertEqual(audit.acting_manager_id, self.owner.pk)
        self.assertIsNone(audit.acting_supervisor_id)
        self.assertEqual(audit.original_recorder_id, self.account.pk)
        self.assertEqual(audit.previous["status"], "present")
        self.assertEqual(audit.new["status"], "late")
        self.assertEqual(audit.reason, "تطبیق با دفتر سالن")
        self.assertGreater(audit.created_at, created)


class Phase5RealAttendanceConcurrencyTests(SimpleTestCase):
    """Two independent processes exercise SQLite's real IMMEDIATE write lock."""

    def run_race(self, mode):
        bootstrap = """
import django, json, os
from pathlib import Path
from datetime import timedelta
django.setup()
from django.core.management import call_command
from django.utils import timezone
from core.models import Customer, User
from operations.models import Hall, Student, StudySession, Supervisor, HallSession
from staff.models import SupervisorAccount
from attendance.models import AttendanceRecord
from rest_framework.test import APIClient
call_command('migrate', verbosity=0, interactive=False)
org = Customer.objects.create(name='Concurrent', manager_name='Test', phone='09123456789', slug='phase5-race', capacity=10, start_date='2025-01-01', expiration_date='2025-12-31')
hall = Hall.objects.create(organization=org, name='Hall')
personnel = Supervisor.objects.create(organization=org, first_name='Test', last_name='Supervisor', phone='09123456789')
personnel.halls.add(hall)
account = SupervisorAccount.objects.create_user(supervisor=personnel, password='Independent$Security2026!')
student = Student.objects.create(organization=org, identifier='TEST-RACE', first_name='Test', last_name='Student', primary_phone='09123456780', grade=12, major='mathematics', hall=hall)
session = StudySession.objects.create(organization=org, title='Session', start_time='08:00', end_time='10:00')
HallSession.objects.create(hall=hall, session=session)
day = timezone.localdate() - timedelta(days=1)
data = {'student': student.pk, 'hall': hall.pk, 'session': session.pk, 'date': str(day)}
if os.environ['RACE_MODE'] == 'automatic':
    client = APIClient()
    client.force_authenticate(account)
    response = client.post('/api/organizations/phase5-race/supervisor/attendance/preview/', {'hall': hall.pk, 'session': session.pk, 'date': str(day)}, format='json')
    assert response.status_code == 200, response.data
    data['preview_token'] = response.data['preview_token']
else:
    record = AttendanceRecord.objects.create(organization=org, student=student, hall=hall, session=session, date=day, status='absent', source='manual', original_recorder=account, hall_name='Hall', session_title='Session', session_start_time='08:00', session_end_time='10:00')
    data['record'] = record.pk
Path(os.environ['RACE_DATA']).write_text(json.dumps(data))
"""
        worker = """
import django, json, os, time
from pathlib import Path
django.setup()
from staff.models import SupervisorAccount
from attendance.models import AttendanceAudit, AttendanceRecord
from rest_framework.test import APIClient
import attendance.views as views
original = views.actor_context
def slow_context(*args, **kwargs):
    result = original(*args, **kwargs)
    if kwargs.get('lock'):
        time.sleep(.2)
    return result
views.actor_context = slow_context
client = APIClient()
client.force_authenticate(SupervisorAccount.objects.get())
data = json.loads(Path(os.environ['RACE_DATA']).read_text())
Path(os.environ['RACE_READY']).touch()
while not Path(os.environ['RACE_RELEASE']).exists():
    time.sleep(.01)
if os.environ['RACE_MODE'] == 'automatic':
    response = client.post('/api/organizations/phase5-race/supervisor/attendance/automatic/', {'preview_token': data['preview_token'], 'students': [data['student']]}, format='json')
else:
    response = client.post('/api/organizations/phase5-race/supervisor/attendance/bulk/', {'hall': data['hall'], 'session': data['session'], 'date': data['date'], 'records': [{'student': data['student'], 'status': 'present' if os.environ['RACE_WORKER'] == '0' else 'late', 'revision': 1}]}, format='json')
record = AttendanceRecord.objects.get()
print(json.dumps({'status': response.status_code, 'records': AttendanceRecord.objects.count(), 'audits': AttendanceAudit.objects.count(), 'revision': record.revision, 'source': record.source, 'original_recorder': record.original_recorder_id}))
"""
        with tempfile.TemporaryDirectory(prefix="damavand-independent-attendance-race-") as temporary:
            directory = Path(temporary)
            environment = {
                **os.environ,
                "DATABASE_URL": "sqlite:///" + (directory / "race.sqlite3").as_posix(),
                "DJANGO_SETTINGS_MODULE": "config.settings",
                "DEBUG": "true",
                "ALLOWED_HOSTS": "testserver",
                "RACE_MODE": mode,
                "RACE_DATA": str(directory / "data.json"),
                "RACE_RELEASE": str(directory / "release"),
            }
            result = subprocess.run(
                [sys.executable, "-c", bootstrap],
                cwd=settings.BASE_DIR,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            processes = []
            try:
                for index in range(2):
                    processes.append(
                        subprocess.Popen(
                            [sys.executable, "-c", worker],
                            cwd=settings.BASE_DIR,
                            env={
                                **environment,
                                "RACE_WORKER": str(index),
                                "RACE_READY": str(directory / f"ready-{index}"),
                            },
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                    )
                deadline = clock_time.monotonic() + 15
                while not all((directory / f"ready-{index}").exists() for index in range(2)):
                    self.assertLess(
                        clock_time.monotonic(), deadline, "Workers did not reach the race barrier"
                    )
                    clock_time.sleep(0.02)
                (directory / "release").touch()
                results = []
                for process in processes:
                    output, errors = process.communicate(timeout=20)
                    self.assertEqual(process.returncode, 0, errors)
                    results.append(json.loads(output))
                return results
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                    process.wait()

    def test_concurrent_automatic_registration_one_preview_cannot_be_replayed(self):
        results = self.run_race("automatic")
        self.assertEqual(sorted(result["status"] for result in results), [200, 409])
        self.assertTrue(all(result["records"] == 1 for result in results))
        self.assertTrue(all(result["revision"] == 1 for result in results))
        self.assertTrue(all(result["source"] == "automatic" for result in results))
        self.assertTrue(all(result["audits"] == 0 for result in results))

    def test_concurrent_owned_record_updates_require_the_same_original_revision(self):
        results = self.run_race("manual")
        self.assertEqual(sorted(result["status"] for result in results), [200, 409])
        self.assertTrue(all(result["records"] == 1 for result in results))
        self.assertTrue(all(result["revision"] == 2 for result in results))
        self.assertTrue(all(result["source"] == "manual" for result in results))
        self.assertTrue(all(result["audits"] == 1 for result in results))

"""Real API boundaries, relational constraints, capacity and archiving behavior."""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Customer, User
from portal.services import provision_portal

from .models import Hall, HallSession, Student, StudySession


class OperationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Customer.objects.create(
            name="آفتاب",
            manager_name="مدیر",
            phone="09123456789",
            slug="aftab",
            capacity=3,
            start_date="2020-01-01",
            expiration_date="2020-12-31",
        )
        cls.b = Customer.objects.create(
            name="دریا",
            manager_name="مدیر",
            phone="09123456789",
            slug="darya",
            capacity=3,
            start_date="2020-01-01",
            expiration_date="2020-12-31",
        )
        cls.owner = provision_portal(
            cls.a, {"login_username": "manager", "login_password": "Testing$Only2026!"}
        )
        cls.other = provision_portal(
            cls.b, {"login_username": "manager", "login_password": "Testing$Only2026!"}
        )
        cls.hall = Hall.objects.create(organization=cls.a, name="سالن روشن")
        cls.second = Hall.objects.create(organization=cls.a, name="سالن آرام")
        cls.foreign = Hall.objects.create(organization=cls.b, name="سالن دیگر")
        cls.late = StudySession.objects.create(organization=cls.a, start_time="14:00", end_time="16:00")
        cls.early = StudySession.objects.create(organization=cls.a, start_time="08:00", end_time="10:00")
        cls.foreign_session = StudySession.objects.create(
            organization=cls.b, start_time="07:00", end_time="09:00"
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.base = "/api/organizations/aftab/"

    def post(self, path, data):
        return self.client.post(self.base + path, data, format="json")

    def patch(self, path, data):
        return self.client.patch(self.base + path, data, format="json")

    def student(self, identifier="ST-001", **overrides):
        return {
            "identifier": identifier,
            "desk_number": "12",
            "first_name": "سارا",
            "last_name": "احمدی",
            "primary_phone": "09123456789",
            "grade": 12,
            "major": "experimental",
            "hall": self.hall.pk,
            **overrides,
        }

    def register(self, identifier="ST-001", **overrides):
        response = self.post("students/", self.student(identifier, **overrides))
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_hall_crud_and_archive_restore_preserves_rows(self):
        created = self.post("halls/", {"name": "سالن بنفش", "description": "آرام و روشن"})
        self.assertEqual(created.status_code, 201)
        pk = created.data["id"]
        self.assertEqual(self.patch(f"halls/{pk}/", {"name": "سالن مطالعه"}).status_code, 200)
        self.assertEqual(self.client.delete(self.base + f"halls/{pk}/").status_code, 204)
        self.assertFalse(Hall.objects.get(pk=pk).is_active)
        self.assertEqual(self.client.get(self.base + "halls/?status=archived").data["count"], 1)
        self.assertEqual(self.post(f"halls/{pk}/restore/", {}).status_code, 200)

    def test_session_crud_and_chronology_even_if_client_requests_reverse_order(self):
        response = self.post(
            "study-sessions/", {"start_time": "06:30", "end_time": "07:45", "title": "سپیده"}
        )
        self.assertEqual(response.status_code, 201)
        pk = response.data["id"]
        for query in ("", "?ordering=-start_time"):
            rows = self.client.get(self.base + "study-sessions/" + query).data["results"]
            self.assertEqual([row["start_time"] for row in rows], ["06:30:00", "08:00:00", "14:00:00"])
        self.assertEqual(self.patch(f"study-sessions/{pk}/", {"end_time": "07:30"}).status_code, 200)
        self.assertEqual(self.client.delete(self.base + f"study-sessions/{pk}/").status_code, 204)
        self.assertEqual(self.post(f"study-sessions/{pk}/restore/", {}).status_code, 200)

    def test_invalid_times_and_partial_updates_are_rejected(self):
        for start, end in [("08:00", "08:00"), ("23:00", "01:00"), ("25:00", "26:00")]:
            with self.subTest(start=start):
                self.assertEqual(
                    self.post("study-sessions/", {"start_time": start, "end_time": end}).status_code, 400
                )
        self.assertEqual(self.post("study-sessions/", {"title": "بدون ساعت"}).status_code, 400)
        self.assertEqual(
            self.patch(f"study-sessions/{self.early.pk}/", {"start_time": "11:00"}).status_code, 400
        )

    def test_database_enforces_same_day_session_order(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            StudySession.objects.create(organization=self.a, start_time="23:00", end_time="02:00")

    def test_many_to_many_matrix_persists_and_clears_in_chronological_order(self):
        pairs = [
            {"hall": self.hall.pk, "session": self.late.pk},
            {"hall": self.hall.pk, "session": self.early.pk},
            {"hall": self.second.pk, "session": self.early.pk},
        ]
        response = self.client.put(self.base + "assignments/", {"assignments": pairs}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(HallSession.objects.count(), 3)
        self.assertEqual([s["id"] for s in response.data["sessions"]], [self.early.pk, self.late.pk])
        self.assertEqual(list(self.hall.sessions.values_list("pk", flat=True)), [self.early.pk, self.late.pk])
        self.client.put(self.base + "assignments/", {"assignments": []}, format="json")
        self.assertFalse(HallSession.objects.exists())

    def test_matrix_rejects_foreign_archived_and_duplicate_pairs_atomically(self):
        HallSession.objects.create(hall=self.hall, session=self.early)
        archived = StudySession.objects.create(
            organization=self.a, start_time="05:00", end_time="06:00", is_active=False
        )
        pair = {"hall": self.hall.pk, "session": self.early.pk}
        for pairs in (
            [pair, pair],
            [{"hall": self.foreign.pk, "session": self.early.pk}],
            [{"hall": self.hall.pk, "session": self.foreign_session.pk}],
            [{"hall": self.hall.pk, "session": archived.pk}],
            [{"hall": 99999, "session": self.early.pk}],
        ):
            response = self.client.put(self.base + "assignments/", {"assignments": pairs}, format="json")
            self.assertEqual(response.status_code, 400, response.data)
            self.assertEqual(HallSession.objects.count(), 1)
        self.patch(f"study-sessions/{self.early.pk}/", {"is_active": False})
        self.assertFalse(HallSession.objects.exists())

    def test_assignment_model_and_database_guards(self):
        with self.assertRaises(ModelValidationError):
            HallSession.objects.create(hall=self.hall, session=self.foreign_session)
        HallSession.objects.create(hall=self.hall, session=self.early)
        with self.assertRaises(IntegrityError), transaction.atomic():
            HallSession.objects.bulk_create([HallSession(hall=self.hall, session=self.early)])

    def test_hall_archiving_removes_links_and_restore_requires_reassignment(self):
        HallSession.objects.create(hall=self.hall, session=self.early)
        self.assertEqual(self.client.delete(self.base + f"halls/{self.hall.pk}/").status_code, 204)
        self.assertFalse(HallSession.objects.exists())
        self.post(f"halls/{self.hall.pk}/restore/", {})
        self.assertFalse(HallSession.objects.exists())

    def test_student_crud_normalizes_phone_and_digits_and_retains_archived_identity(self):
        created = self.register("۰۰۱", primary_phone="+98 912-345-6789", secondary_phone="۰۹۳۵۱۲۳۴۵۶۷")
        pk = created["id"]
        self.assertEqual((created["identifier"], created["primary_phone"]), ("001", "09123456789"))
        self.assertEqual(
            self.client.get(self.base + f"students/{pk}/").data["secondary_phone"], "09351234567"
        )
        self.assertEqual(self.patch(f"students/{pk}/", {"first_name": "نگار"}).status_code, 200)
        self.assertEqual(self.client.delete(self.base + f"students/{pk}/").status_code, 204)
        self.assertTrue(Student.objects.filter(pk=pk, is_active=False).exists())
        self.assertEqual(self.post("students/", self.student("001")).status_code, 400)
        self.assertEqual(self.post(f"students/{pk}/restore/", {}).status_code, 200)

    def test_identifiers_unique_per_organization_and_desk_numbers_repeat(self):
        self.register("SAME")
        self.register("OTHER", desk_number="12")
        self.assertEqual(self.post("students/", self.student("SAME")).status_code, 400)
        self.client.force_authenticate(self.other)
        self.base = "/api/organizations/darya/"
        self.register("SAME", hall=self.foreign.pk)
        self.assertEqual(Student.objects.filter(identifier="SAME").count(), 2)

    def test_database_identifier_constraint_and_model_hall_validation(self):
        row = self.register()
        original = Student.objects.get(pk=row["id"])
        original.pk = None
        with self.assertRaises(IntegrityError), transaction.atomic():
            original.save()
        original.hall = self.foreign
        with self.assertRaises(ModelValidationError):
            original.clean()

    def test_student_validation_and_unknown_fields(self):
        for override in (
            {"primary_phone": "123"},
            {"secondary_phone": "not-a-phone"},
            {"grade": 6},
            {"major": "invalid"},
            {"identifier": ""},
            {"first_name": ""},
            {"last_name": ""},
            {"hall": self.foreign.pk},
            {"organization": self.b.pk},
            {"organization_id": self.b.pk},
            {"id": 999},
        ):
            with self.subTest(override=override):
                self.assertEqual(self.post("students/", self.student(**override)).status_code, 400)
        self.register(desk_number="", secondary_phone="")

    def test_capacity_creation_edit_transfer_archive_and_restore(self):
        rows = [self.register(str(index)) for index in range(3)]
        self.assertEqual(self.post("students/", self.student("extra")).status_code, 400)
        pk = rows[0]["id"]
        self.assertEqual(
            self.patch(f"students/{pk}/", {"hall": self.second.pk, "last_name": "تغییر"}).status_code, 200
        )
        self.assertEqual(Student.objects.filter(organization=self.a, is_active=True).count(), 3)
        self.client.delete(self.base + f"students/{pk}/")
        self.register("replacement")
        self.assertEqual(self.post(f"students/{pk}/restore/", {}).status_code, 400)
        self.assertEqual(self.patch(f"students/{pk}/", {"is_active": True}).status_code, 400)
        self.assertEqual(Student.objects.filter(organization=self.a, is_active=True).count(), 3)

    def test_direct_model_save_cannot_bypass_capacity_or_change_organization(self):
        rows = [self.register(str(index)) for index in range(3)]
        with self.assertRaises(ModelValidationError):
            Student.objects.create(organization=self.a, **{**self.student("direct"), "hall": self.hall})
        student = Student.objects.get(pk=rows[0]["id"])
        student.organization = self.b
        student.hall = self.foreign
        with self.assertRaises(ModelValidationError):
            student.save()

    def test_capacity_reduction_preserves_enrollment_and_warning_until_below_limit(self):
        rows = [self.register(str(i)) for i in range(3)]
        admin = User.objects.create_superuser(username="central", password="Testing$Only2026!")
        central = APIClient()
        central.force_authenticate(admin)
        response = central.patch(f"/api/customers/{self.a.pk}/", {"capacity": 2}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        stats = self.client.get(self.base + "dashboard/").data["operations"]
        self.assertTrue(stats["over_capacity"])
        self.assertEqual(stats["utilization_percent"], 150)
        self.assertEqual(stats["remaining_capacity"], 0)
        self.assertEqual(self.patch(f"students/{rows[0]['id']}/", {"hall": self.second.pk}).status_code, 200)
        self.assertEqual(self.post("students/", self.student("blocked")).status_code, 400)
        for row in rows[:2]:
            self.client.delete(self.base + f"students/{row['id']}/")
        self.register("now-allowed")

    def test_hall_with_active_students_cannot_archive_then_can_after_transfer(self):
        row = self.register()
        self.assertEqual(self.client.delete(self.base + f"halls/{self.hall.pk}/").status_code, 400)
        self.assertEqual(self.patch(f"halls/{self.hall.pk}/", {"is_active": False}).status_code, 400)
        self.patch(f"students/{row['id']}/", {"hall": self.second.pk})
        self.assertEqual(self.client.delete(self.base + f"halls/{self.hall.pk}/").status_code, 204)
        self.assertEqual(self.patch(f"students/{row['id']}/", {"hall": self.hall.pk}).status_code, 400)

    def test_archived_students_cannot_restore_into_archived_hall(self):
        row = self.register(is_active=False)
        self.client.delete(self.base + f"halls/{self.hall.pk}/")
        self.assertEqual(self.post(f"students/{row['id']}/restore/", {}).status_code, 400)
        self.assertEqual(
            self.patch(f"students/{row['id']}/", {"hall": self.second.pk, "is_active": True}).status_code, 200
        )

    def test_search_filter_sort_and_pagination(self):
        self.register("XYZ", first_name="کیانا", desk_number="45", grade=10)
        self.register("ABC", hall=self.second.pk, grade=11, major="humanities")
        for search in ["XYZ", "کیانا", "کیانا احمدی", "۰۹۱۲۳۴۵۶۷۸۹", "۴۵"]:
            result = self.client.get(self.base + "students/", {"search": search}).data
            self.assertGreaterEqual(result["count"], 1, search)
        for params in [{"hall": self.second.pk}, {"grade": 10}, {"major": "humanities"}]:
            self.assertEqual(self.client.get(self.base + "students/", params).data["count"], 1)
        response = self.client.get(self.base + "students/?ordering=identifier&page_size=1")
        self.assertEqual(response.data["results"][0]["identifier"], "ABC")
        self.assertIsNotNone(response.data["next"])
        for params in [
            {"hall": self.foreign.pk},
            {"hall": "bad"},
            {"grade": 1},
            {"major": "bad"},
            {"ordering": "organization"},
        ]:
            self.assertEqual(self.client.get(self.base + "students/", params).status_code, 400)

    def test_bulk_transfer_archive_and_atomic_restore_at_capacity(self):
        ids = [self.register(str(i))["id"] for i in range(3)]
        self.assertEqual(
            self.post(
                "students/bulk/", {"ids": ids, "action": "transfer", "hall": self.second.pk}
            ).status_code,
            200,
        )
        self.assertEqual(Student.objects.filter(hall=self.second).count(), 3)
        self.assertEqual(self.post("students/bulk/", {"ids": ids, "action": "archive"}).status_code, 200)
        self.register("takes-one-slot")
        self.assertEqual(self.post("students/bulk/", {"ids": ids, "action": "restore"}).status_code, 400)
        self.assertEqual(Student.objects.filter(pk__in=ids, is_active=True).count(), 0)
        self.assertEqual(self.post("students/bulk/", {"ids": ids[:2], "action": "restore"}).status_code, 200)

    def test_bulk_rejects_foreign_students_halls_duplicates_and_missing_target(self):
        row = self.register()
        foreign = Student.objects.create(
            organization=self.b, **{**self.student("foreign"), "hall": self.foreign}
        )
        for payload in (
            {"ids": [row["id"], foreign.pk], "action": "archive"},
            {"ids": [row["id"], row["id"]], "action": "archive"},
            {"ids": [row["id"]], "action": "transfer", "hall": self.foreign.pk},
            {"ids": [row["id"]], "action": "transfer"},
        ):
            self.assertEqual(self.post("students/bulk/", payload).status_code, 400)
        self.assertTrue(Student.objects.get(pk=row["id"]).is_active)

    def test_dashboard_uses_registered_students_and_expiry_does_not_block_operations(self):
        self.register()
        self.register("inactive", is_active=False)
        response = self.client.get(self.base + "dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["organization"]["subscription"]["status"], "expired")
        stats = response.data["operations"]
        self.assertEqual(
            (stats["active_students"], stats["active_halls"], stats["active_sessions"]), (1, 2, 2)
        )
        self.assertEqual(stats["remaining_capacity"], 2)
        self.assertEqual(sum(row["active_students"] for row in stats["students_per_hall"]), 1)
        self.assertNotIn("attendance", stats)

    def test_scoping_all_endpoints_and_mutations(self):
        row = self.register()
        for suffix in ["halls/", "study-sessions/", "students/", "assignments/"]:
            self.assertEqual(self.client.get("/api/organizations/darya/" + suffix).status_code, 403)
        self.assertEqual(self.client.get(self.base + f"halls/{self.foreign.pk}/").status_code, 404)
        self.assertEqual(self.patch(f"halls/{self.foreign.pk}/", {"name": "نفوذ"}).status_code, 404)
        self.assertEqual(
            self.client.delete(self.base + f"study-sessions/{self.foreign_session.pk}/").status_code, 404
        )
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/organizations/darya/students/{row['id']}/").status_code, 404)
        self.assertEqual(
            self.client.post(f"/api/organizations/darya/students/{row['id']}/restore/").status_code, 404
        )

    def test_anonymous_central_inactive_and_deleted_organization_sessions_denied(self):
        for user in [None, User.objects.create_user(username="central")]:
            self.client.force_authenticate(user)
            self.assertIn(self.client.get(self.base + "students/").status_code, [401, 403])
        self.owner.is_active = False
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(self.base + "students/").status_code, 403)

    def test_deleted_organization_cannot_read_or_mutate_operations(self):
        Customer.objects.filter(pk=self.a.pk).update(deleted_at=timezone.now())
        self.assertEqual(self.client.get(self.base + "students/").status_code, 403)
        self.assertEqual(self.post("halls/", {"name": "مجاز نیست"}).status_code, 403)

    def test_real_session_operations_require_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get("/api/auth/csrf/").data["csrfToken"]
        response = client.post(
            self.base + "login/",
            {"username": "manager", "password": "Testing$Only2026!"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            client.post(self.base + "halls/", {"name": "بدون توکن"}, format="json").status_code, 403
        )
        token = client.get("/api/auth/csrf/").data["csrfToken"]
        self.assertEqual(
            client.post(
                self.base + "halls/", {"name": "با توکن"}, format="json", HTTP_X_CSRFTOKEN=token
            ).status_code,
            201,
        )


class OperationsMigrationTests(TransactionTestCase):
    def test_additive_migration_preserves_customers_and_portal_accounts(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [("operations", None), ("core", "0003_organization_portal")]
        executor.migrate(previous)
        try:
            old = executor.loader.project_state([("core", "0003_organization_portal")]).apps
            customer = old.get_model("core", "Customer").objects.create(
                name="موجود",
                manager_name="مدیر",
                phone="09123456789",
                slug="existing",
                capacity=40,
                identifier="EXISTING001",
                start_date="2026-01-01",
                expiration_date="2026-12-31",
            )
            account = old.get_model("core", "User").objects.create(
                username="existing-owner",
                role="tenant",
                organization_id=customer.pk,
                portal_username="manager",
                is_portal_owner=True,
                password="existing-password-hash",
            )
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            new = executor.loader.project_state(latest).apps
            self.assertEqual(new.get_model("core", "Customer").objects.get(pk=customer.pk).capacity, 40)
            self.assertEqual(
                new.get_model("core", "User").objects.get(pk=account.pk).password, "existing-password-hash"
            )
            self.assertEqual(new.get_model("operations", "Hall").objects.count(), 0)
            self.assertEqual(new.get_model("operations", "Student").objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(latest)


class ConcurrentRegistrationTests(SimpleTestCase):
    def test_real_processes_cannot_create_or_restore_beyond_capacity(self):
        """A disposable file-backed SQLite DB tests real competing writers.

        Django's shared in-memory test DB reports SQLITE_LOCKED without a busy
        timeout and cannot demonstrate file-lock contention correctly.
        """
        root = Path(settings.BASE_DIR)
        bootstrap = """
import django
django.setup()
from core.models import Customer, User
from operations.models import Hall, Student
from django.core.management import call_command
call_command('migrate', verbosity=0, interactive=False)
o = Customer.objects.create(name='Concurrency', manager_name='Test', phone='09123456789', slug='concurrent', capacity=1, start_date='2026-01-01', expiration_date='2026-12-31')
User.objects.create(username='concurrent', role='tenant', organization=o, portal_username='manager')
h = Hall.objects.create(organization=o, name='Hall')
Student.objects.create(organization=o, hall=h, identifier='restore', first_name='Test', last_name='Student', primary_phone='09123456789', grade=12, major='other', is_active=False)
"""
        worker = """
import django, os, time, json
from pathlib import Path
django.setup()
from core.models import User
from operations.models import Student, Hall
from operations.serializers import StudentSerializer
from rest_framework.test import APIClient
original = StudentSerializer.validate
def slow(self, attrs):
    time.sleep(.3)
    return original(self, attrs)
StudentSerializer.validate = slow
c = APIClient()
c.force_authenticate(User.objects.get(username='concurrent'))
Path(os.environ['READY']).touch()
while not Path(os.environ['RELEASE']).exists(): time.sleep(.01)
if os.environ['MODE'] == 'restore':
    response = c.post('/api/organizations/concurrent/students/1/restore/', {}, format='json')
else:
    response = c.post('/api/organizations/concurrent/students/', {'identifier': os.environ['MODE'], 'first_name': 'Test', 'last_name': 'Student', 'primary_phone': '09123456789', 'grade': 12, 'major': 'other', 'hall': Hall.objects.get().pk}, format='json')
print(json.dumps({'status': response.status_code, 'active': Student.objects.filter(is_active=True).count()}))
"""
        for modes in [("one", "two"), ("new", "restore")]:
            with (
                self.subTest(modes=modes),
                tempfile.TemporaryDirectory(prefix="damavand-concurrency-") as tmp,
            ):
                env = {
                    **os.environ,
                    "DATABASE_URL": "sqlite:///" + str(Path(tmp) / "test.sqlite3"),
                    "DJANGO_SETTINGS_MODULE": "config.settings",
                    "DEBUG": "true",
                    "ALLOWED_HOSTS": "testserver",
                }
                subprocess.run(
                    [sys.executable, "-c", bootstrap],
                    env=env,
                    cwd=root,
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
                processes = []
                try:
                    for index, mode in enumerate(modes):
                        child_env = {
                            **env,
                            "MODE": mode,
                            "READY": str(Path(tmp) / f"ready-{index}"),
                            "RELEASE": str(Path(tmp) / "release"),
                        }
                        processes.append(
                            subprocess.Popen(
                                [sys.executable, "-c", worker],
                                env=child_env,
                                cwd=root,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                            )
                        )
                    deadline = time.monotonic() + 15
                    while not all((Path(tmp) / f"ready-{i}").exists() for i in range(2)):
                        self.assertLess(
                            time.monotonic(), deadline, "Workers did not reach the concurrent barrier"
                        )
                        time.sleep(0.02)
                    (Path(tmp) / "release").touch()
                    results = []
                    for process in processes:
                        output, error = process.communicate(timeout=20)
                        self.assertEqual(process.returncode, 0, error)
                        results.append(json.loads(output))
                    codes = sorted(item["status"] for item in results)
                    self.assertEqual(codes[1], 400)
                    self.assertIn(codes[0], [200, 201] if "restore" in modes else [201])
                    self.assertTrue(all(item["active"] == 1 for item in results))
                finally:
                    for process in processes:
                        if process.poll() is None:
                            process.kill()
                        process.wait()

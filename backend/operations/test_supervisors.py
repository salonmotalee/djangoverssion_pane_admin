"""Supervisor tenant boundaries, state transitions, ORM writes and additive migration."""

from django.core.exceptions import ValidationError as ModelValidationError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from core.models import Customer, User
from portal.services import provision_portal

from .models import Hall, Supervisor, SupervisorHall
from .services import assign_supervisor_halls, capacity_summary


class SupervisorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Customer.objects.create(
            name="آفتاب",
            manager_name="مدیر",
            phone="09123456789",
            slug="sup-aftab",
            capacity=20,
            start_date="2026-01-01",
            expiration_date="2026-12-31",
        )
        cls.other_organization = Customer.objects.create(
            name="دریا",
            manager_name="مدیر",
            phone="09123456789",
            slug="sup-darya",
            capacity=20,
            start_date="2026-01-01",
            expiration_date="2026-12-31",
        )
        cls.owner = provision_portal(
            cls.organization, {"login_username": "manager", "login_password": "Testing$Only2026!"}
        )
        cls.other_owner = provision_portal(
            cls.other_organization, {"login_username": "manager", "login_password": "Testing$Only2026!"}
        )
        cls.hall = Hall.objects.create(organization=cls.organization, name="روشن")
        cls.second_hall = Hall.objects.create(organization=cls.organization, name="آرام")
        cls.foreign_hall = Hall.objects.create(organization=cls.other_organization, name="دیگر")
        cls.archived_hall = Hall.objects.create(organization=cls.organization, name="قدیمی", is_active=False)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.base = "/api/organizations/sup-aftab/supervisors/"

    def payload(self, **overrides):
        return {"first_name": "سارا", "last_name": "احمدی", "phone": "09123456789", **overrides}

    def create(self, **overrides):
        response = self.client.post(self.base, self.payload(**overrides), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def action(self, pk, name):
        return self.client.post(f"{self.base}{pk}/{name}/", {}, format="json")

    def patch(self, pk, payload):
        return self.client.patch(f"{self.base}{pk}/", payload, format="json")

    def test_crud_required_fields_and_complete_response(self):
        for missing in ("first_name", "last_name", "phone"):
            payload = self.payload()
            del payload[missing]
            response = self.client.post(self.base, payload, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertIn(missing, response.data)
        for field in ("first_name", "last_name", "phone"):
            self.assertEqual(
                self.client.post(self.base, self.payload(**{field: "   "}), format="json").status_code, 400
            )
        row = self.create(halls=[self.hall.pk, self.second_hall.pk])
        self.assertEqual(
            set(row),
            {
                "id",
                "first_name",
                "last_name",
                "phone",
                "is_active",
                "archived_at",
                "halls",
                "hall_details",
                "created_at",
                "updated_at",
            },
        )
        self.assertCountEqual(row["halls"], [self.hall.pk, self.second_hall.pk])
        self.assertEqual({item["name"] for item in row["hall_details"]}, {"روشن", "آرام"})
        updated = self.patch(row["id"], {"last_name": "رضایی"})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["last_name"], "رضایی")
        self.assertCountEqual(updated.data["halls"], row["halls"])
        self.assertEqual(self.client.get(f"{self.base}{row['id']}/").status_code, 200)

    def test_phone_normalization_and_duplicates_in_both_tenants(self):
        for phone in ("۰۹۱۲۳۴۵۶۷۸۹", "٠٩١٢٣٤٥٦٧٨٩", "+98 912-345-6789", "00989123456789"):
            self.assertEqual(self.create(phone=phone)["phone"], "09123456789")
        self.client.force_authenticate(self.other_owner)
        response = self.client.post(
            "/api/organizations/sup-darya/supervisors/", self.payload(), format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Supervisor.objects.filter(phone="09123456789").count(), 5)

    def test_phone_validation_and_forbidden_account_fields(self):
        for phone in ("9123456789", "0912", "+979123456789", "0912345678a"):
            response = self.client.post(self.base, self.payload(phone=phone), format="json")
            self.assertEqual(response.status_code, 400)
            self.assertIn("phone", response.data)
        for field, value in (
            ("password", "secret"),
            ("organization", self.other_organization.pk),
            ("username", "login"),
            ("archived_at", timezone.now().isoformat()),
        ):
            response = self.client.post(self.base, self.payload(**{field: value}), format="json")
            self.assertEqual(response.status_code, 400)
            self.assertIn(field, response.data)
        self.assertEqual(User.objects.count(), 2)

    def test_replace_and_clear_multiple_active_assignments(self):
        row = self.create(halls=[self.hall.pk, self.second_hall.pk])
        response = self.patch(row["id"], {"halls": [self.second_hall.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["halls"], [self.second_hall.pk])
        response = self.patch(row["id"], {"halls": []})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["halls"], [])
        self.assertFalse(SupervisorHall.objects.exists())

    def test_assignment_rejects_foreign_archived_duplicate_and_unknown_ids_atomically(self):
        row = self.create(halls=[self.hall.pk])
        for ids in ([self.foreign_hall.pk], [self.archived_hall.pk], [999999], [self.hall.pk, self.hall.pk]):
            response = self.patch(row["id"], {"first_name": "نباید ذخیره شود", "halls": ids})
            self.assertEqual(response.status_code, 400, response.data)
            supervisor = Supervisor.objects.get(pk=row["id"])
            self.assertEqual(supervisor.first_name, "سارا")
            self.assertEqual(list(supervisor.halls.values_list("pk", flat=True)), [self.hall.pk])
        response = self.client.post(self.base, self.payload(halls=[self.foreign_hall.pk]), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Supervisor.objects.count(), 1)

    def test_deactivation_archive_and_restore_preserve_state_and_assignments(self):
        row = self.create(halls=[self.hall.pk])
        deactivated = self.action(row["id"], "deactivate")
        self.assertEqual(deactivated.status_code, 200)
        self.assertFalse(deactivated.data["is_active"])
        self.assertIsNone(deactivated.data["archived_at"])
        self.assertEqual(self.client.get(self.base + "?status=inactive").data["count"], 1)
        archived = self.action(row["id"], "archive")
        self.assertEqual(archived.status_code, 200)
        self.assertIsNotNone(archived.data["archived_at"])
        self.assertFalse(archived.data["is_active"])
        self.assertEqual(self.action(row["id"], "archive").data["archived_at"], archived.data["archived_at"])
        for payload in ({"first_name": "تغییر"}, {"is_active": True}, {"halls": []}):
            self.assertEqual(self.patch(row["id"], payload).status_code, 400)
        for action in ("activate", "deactivate"):
            self.assertEqual(self.action(row["id"], action).status_code, 400)
        restored = self.action(row["id"], "restore")
        self.assertEqual(restored.status_code, 200)
        self.assertIsNone(restored.data["archived_at"])
        self.assertFalse(restored.data["is_active"])
        self.assertEqual(restored.data["halls"], [self.hall.pk])
        self.assertTrue(self.action(row["id"], "activate").data["is_active"])

    def test_delete_archives_instead_of_deleting_and_restore_active_record(self):
        row = self.create(halls=[self.hall.pk])
        response = self.client.delete(f"{self.base}{row['id']}/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["archived_at"])
        self.assertTrue(Supervisor.objects.filter(pk=row["id"]).exists())
        self.assertEqual(SupervisorHall.objects.count(), 1)
        self.assertEqual(self.client.get(self.base).data["count"], 0)
        restored = self.action(row["id"], "restore")
        self.assertTrue(restored.data["is_active"])
        self.assertIsNone(restored.data["archived_at"])

    def test_filters_search_pagination_and_dashboard_counts(self):
        active = self.create(halls=[self.hall.pk])
        self.create(first_name="مینا", last_name="کریمی", is_active=False, halls=[self.second_hall.pk])
        archived = self.create(first_name="رضا", last_name="جعفری")
        self.action(archived["id"], "archive")
        for value, count in (("active", 1), ("inactive", 1), ("archived", 1), ("all", 3)):
            response = self.client.get(self.base, {"status": value})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], count)
        for search in ("سارا", "احمدی", "سارا احمدی", "۰۹۱۲"):
            response = self.client.get(self.base, {"search": search})
            self.assertEqual([item["id"] for item in response.data["results"]], [active["id"]])
        self.assertEqual(
            self.client.get(self.base, {"status": "all", "hall": self.second_hall.pk}).data["count"], 1
        )
        for params in (
            {"status": "bogus"},
            {"hall": "abc"},
            {"hall": self.foreign_hall.pk},
            {"hall": 999999},
            {"ordering": "phone"},
        ):
            self.assertEqual(self.client.get(self.base, params).status_code, 400)
        self.assertEqual(capacity_summary(self.organization)["active_supervisors"], 1)
        self.assertEqual(
            self.client.get("/api/organizations/sup-aftab/dashboard/").data["operations"][
                "active_supervisors"
            ],
            1,
        )

    def test_archived_hall_assignments_remain_history(self):
        row = self.create(halls=[self.hall.pk, self.second_hall.pk])
        Hall.objects.filter(pk=self.hall.pk).update(is_active=False)
        response = self.patch(row["id"], {"halls": []})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["halls"], [self.hall.pk])
        self.assertEqual(
            response.data["hall_details"], [{"id": self.hall.pk, "name": "روشن", "is_active": False}]
        )
        self.assertEqual(self.client.get(self.base, {"hall": self.hall.pk}).data["count"], 1)
        self.assertEqual(self.patch(row["id"], {"halls": [self.hall.pk]}).status_code, 400)
        self.action(row["id"], "archive")
        self.assertEqual(self.action(row["id"], "restore").data["halls"], [self.hall.pk])

    def test_tenant_isolation_for_all_endpoints(self):
        row = self.create(halls=[self.hall.pk])
        self.client.force_authenticate(self.other_owner)
        foreign_base = "/api/organizations/sup-darya/supervisors/"
        self.assertEqual(self.client.get(foreign_base).data["count"], 0)
        self.assertEqual(self.client.get(self.base).status_code, 403)
        self.assertEqual(self.client.get(f"{foreign_base}{row['id']}/").status_code, 404)
        self.assertEqual(
            self.client.patch(f"{foreign_base}{row['id']}/", {"phone": "09111111111"}).status_code, 404
        )
        self.assertEqual(self.client.delete(f"{foreign_base}{row['id']}/").status_code, 404)
        for action in ("archive", "restore", "activate", "deactivate"):
            self.assertEqual(self.client.post(f"{foreign_base}{row['id']}/{action}/", {}).status_code, 404)

    def test_anonymous_internal_inactive_and_deleted_organization_denied(self):
        for user in (None, User.objects.create_user(username="central-supervisor-test", role="super_admin")):
            self.client.force_authenticate(user)
            self.assertIn(self.client.get(self.base).status_code, (401, 403))
        self.owner.is_active = False
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(self.base).status_code, 403)
        self.owner.is_active = True
        Customer.objects.filter(pk=self.organization.pk).update(deleted_at=timezone.now())
        self.assertEqual(self.client.get(self.base).status_code, 403)

    def test_real_session_mutations_require_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get("/api/auth/csrf/").data["csrfToken"]
        response = client.post(
            "/api/organizations/sup-aftab/login/",
            {"username": "manager", "password": "Testing$Only2026!"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.post(self.base, self.payload(), format="json").status_code, 403)
        token = client.get("/api/auth/csrf/").data["csrfToken"]
        self.assertEqual(
            client.post(self.base, self.payload(), format="json", HTTP_X_CSRFTOKEN=token).status_code, 201
        )

    def test_direct_model_creation_normalizes_phone_and_protects_organization(self):
        supervisor = Supervisor.objects.create(
            organization=self.organization, **self.payload(phone="+98 912-345-6789")
        )
        self.assertEqual(supervisor.phone, "09123456789")
        with self.assertRaises(ModelValidationError):
            Supervisor.objects.create(organization=self.organization, **self.payload(phone="0912"))
        supervisor.organization = self.other_organization
        with self.assertRaises(ModelValidationError):
            supervisor.save()
        with self.assertRaises(ModelValidationError):
            Supervisor.objects.filter(pk=supervisor.pk).update(organization=self.other_organization)
        Supervisor.objects.bulk_create(
            [
                Supervisor(organization=self.organization, **self.payload()),
                Supervisor(organization=self.organization, **self.payload()),
            ]
        )
        self.assertEqual(Supervisor.objects.filter(phone="09123456789").count(), 3)

    def test_direct_and_bulk_relation_creation_and_both_m2m_directions_enforce_tenant(self):
        supervisor = Supervisor.objects.get(pk=self.create()["id"])
        for operation in (
            lambda: SupervisorHall.objects.create(supervisor=supervisor, hall=self.foreign_hall),
            lambda: SupervisorHall.objects.bulk_create(
                [
                    SupervisorHall(supervisor=supervisor, hall=self.hall),
                    SupervisorHall(supervisor=supervisor, hall=self.foreign_hall),
                ]
            ),
            lambda: supervisor.halls.add(self.foreign_hall),
            lambda: self.foreign_hall.supervisors.add(supervisor),
            lambda: supervisor.halls.add(self.archived_hall),
        ):
            with self.assertRaises(ModelValidationError), transaction.atomic():
                operation()
            self.assertFalse(SupervisorHall.objects.exists())
        supervisor.halls.add(self.hall, self.second_hall)
        self.assertEqual(SupervisorHall.objects.count(), 2)
        link = SupervisorHall.objects.filter(hall=self.hall).get()
        link.hall = self.foreign_hall
        with self.assertRaises(ModelValidationError):
            link.save()
        with self.assertRaises(ModelValidationError):
            SupervisorHall.objects.filter(pk=link.pk).update(hall=self.foreign_hall)
        with self.assertRaises(ModelValidationError):
            SupervisorHall.objects.bulk_update([link], ["hall"])

    def test_service_boundary_rejects_cross_tenant_and_stale_hall_state(self):
        supervisor = Supervisor.objects.get(pk=self.create(halls=[self.hall.pk])["id"])
        for halls in ([self.foreign_hall], [self.archived_hall]):
            with self.assertRaises(ValidationError):
                assign_supervisor_halls(supervisor, halls)
        Hall.objects.filter(pk=self.second_hall.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            assign_supervisor_halls(supervisor, [self.second_hall])
        self.assertEqual(list(supervisor.halls.values_list("pk", flat=True)), [self.hall.pk])
        self.action(supervisor.pk, "archive")
        with self.assertRaises(ValidationError):
            assign_supervisor_halls(supervisor, [])
        with self.assertRaises(ModelValidationError), transaction.atomic():
            supervisor.halls.add(self.second_hall)


class SupervisorMigrationTests(TransactionTestCase):
    def test_additive_migration_preserves_halls_students_sessions_and_accounts(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old_target = [("operations", "0001_initial"), *executor.loader.graph.leaf_nodes("core")]
        executor.migrate(old_target)
        try:
            old = executor.loader.project_state(old_target).apps
            customer = old.get_model("core", "Customer").objects.create(
                name="موجود",
                manager_name="مدیر",
                phone="09123456789",
                slug="sup-legacy",
                capacity=40,
                identifier="SUPERVISORLEGACY",
                start_date="2026-01-01",
                expiration_date="2026-12-31",
            )
            account = old.get_model("core", "User").objects.create(
                username="legacy-supervisor-owner",
                role="tenant",
                organization_id=customer.pk,
                portal_username="manager",
                is_portal_owner=True,
                password="unchanged-password-hash",
            )
            hall = old.get_model("operations", "Hall").objects.create(
                organization_id=customer.pk, name="موجود"
            )
            session = old.get_model("operations", "StudySession").objects.create(
                organization_id=customer.pk, start_time="08:00", end_time="10:00"
            )
            old.get_model("operations", "HallSession").objects.create(hall_id=hall.pk, session_id=session.pk)
            student = old.get_model("operations", "Student").objects.create(
                organization_id=customer.pk,
                hall_id=hall.pk,
                identifier="LEGACY-STUDENT",
                first_name="سارا",
                last_name="احمدی",
                primary_phone="09123456789",
                grade=12,
                major="experimental",
            )
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            new = executor.loader.project_state(latest).apps
            self.assertEqual(
                new.get_model("core", "User").objects.get(pk=account.pk).password, "unchanged-password-hash"
            )
            self.assertEqual(
                new.get_model("operations", "Student").objects.get(pk=student.pk).hall_id, hall.pk
            )
            self.assertTrue(
                new.get_model("operations", "HallSession")
                .objects.filter(hall_id=hall.pk, session_id=session.pk)
                .exists()
            )
            self.assertEqual(new.get_model("operations", "Supervisor").objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(latest)

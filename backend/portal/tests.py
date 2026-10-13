"""Exercise the real session, authorization and migration boundaries."""

import json
from datetime import date, datetime, timedelta
from datetime import timezone as utc
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import AuditLog, Customer, User
from core.routing import RESERVED_SLUGS

from .services import provision_portal, subscription

PASSWORD = "TestingOnly$Mountain2026!"


class PortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username="central.owner", password=PASSWORD)
        cls.operator = User.objects.create_user(username="central.operator", password=PASSWORD)
        today = timezone.localdate()
        cls.a = Customer.objects.create(
            name="آفتاب",
            manager_name="سارا احمدی",
            phone="09123456789",
            slug="aftab",
            capacity=120,
            start_date=today - timedelta(days=20),
            expiration_date=today + timedelta(days=10),
        )
        cls.b = Customer.objects.create(
            name="دریا",
            manager_name="علی رضایی",
            phone="09351234567",
            slug="darya",
            capacity=80,
            start_date=today - timedelta(days=20),
            expiration_date=today + timedelta(days=90),
        )
        cls.owner = provision_portal(cls.a, {"login_username": "manager", "login_password": PASSWORD})
        cls.other = provision_portal(
            cls.b, {"login_username": "manager", "login_password": PASSWORD + "other"}
        )

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.central = APIClient()
        self.central.force_authenticate(self.admin)

    def csrf(self, client=None):
        client = client or self.client
        return client.get("/api/auth/csrf/").data["csrfToken"]

    def login(self, slug="aftab", username="manager", password=PASSWORD, client=None):
        client = client or self.client
        return client.post(
            f"/api/organizations/{slug}/login/",
            {"username": username, "password": password},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf(client),
        )

    def configure(self, **data):
        return self.central.post(f"/api/customers/{self.a.pk}/portal/", data, format="json")

    def test_public_metadata_has_no_private_or_authentication_information(self):
        response = self.client.get("/api/organizations/aftab/public/")
        self.assertEqual(response.data, {"name": "آفتاب", "slug": "aftab"})
        self.assertEqual(self.client.get("/api/organizations/missing/public/").status_code, 404)

    def test_provisioning_hashes_password_and_scopes_same_username(self):
        self.assertTrue(self.owner.check_password(PASSWORD))
        self.assertNotEqual(self.owner.password, PASSWORD)
        self.assertNotEqual(self.owner.username, self.other.username)
        self.assertEqual(self.owner.portal_username, self.other.portal_username)
        self.assertFalse(self.owner.is_staff or self.owner.is_superuser)
        self.assertEqual(self.owner.organization_id, self.a.pk)

    def test_customer_creation_can_atomically_provision_initial_credentials(self):
        response = self.central.post(
            "/api/customers/",
            {
                "name": "سپید",
                "manager_name": "مهسا",
                "phone": "09121234567",
                "slug": "sepid",
                "capacity": 50,
                "start_date": "2026-01-01",
                "expiration_date": "2026-12-31",
                "login_username": "Sepid.Manager",
                "login_password": PASSWORD,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["login_username"], "sepid.manager")
        self.assertTrue(response.data["portal_provisioned"])
        owner = User.objects.get(organization_id=response.data["id"])
        self.assertTrue(owner.check_password(PASSWORD))
        raw = response.content.decode()
        self.assertNotIn(PASSWORD, raw)
        self.assertNotIn(owner.password, raw)
        self.assertNotIn(owner.username, raw)

    def test_bad_initial_credentials_do_not_create_partial_organization(self):
        before = Customer.objects.count()
        response = self.central.post(
            "/api/customers/",
            {
                "name": "سپید",
                "manager_name": "مهسا",
                "phone": "09121234567",
                "capacity": 50,
                "start_date": "2026-01-01",
                "expiration_date": "2026-12-31",
                "login_username": "manager",
                "login_password": "123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Customer.objects.count(), before)

    def test_strong_credentials_and_username_validation(self):
        for payload in (
            {"login_password": "1234567890"},
            {"login_password": "short"},
            {"login_username": "a"},
            {"login_username": "bad name"},
            {"organization_id": self.b.pk},
        ):
            with self.subTest(payload=list(payload)):
                self.assertEqual(self.configure(**payload).status_code, 400)

    def test_capacity_rejects_zero_negative_boolean_null_fraction_and_overflow(self):
        for value in (0, -1, True, None, 1.5, 2147483648):
            with self.subTest(value=value):
                self.assertEqual(
                    self.central.patch(
                        f"/api/customers/{self.a.pk}/", {"capacity": value}, format="json"
                    ).status_code,
                    400,
                )
                self.assertEqual(self.configure(capacity=value).status_code, 400)

    def test_legacy_capacity_is_unknown_and_portal_requires_explicit_provisioning(self):
        org = Customer.objects.create(
            name="قدیمی",
            manager_name="مدیر",
            phone="09123456789",
            start_date=date(2026, 1, 1),
            expiration_date=date(2026, 12, 31),
        )
        self.assertIsNone(org.capacity)
        self.assertEqual(self.client.get(f"/api/organizations/{org.slug}/public/").status_code, 404)
        self.assertEqual(
            self.central.post(
                f"/api/customers/{org.pk}/portal/",
                {"login_username": "manager", "login_password": PASSWORD},
                format="json",
            ).status_code,
            400,
        )

    def test_reserved_invalid_and_duplicate_slugs_are_rejected(self):
        for slug in (*RESERVED_SLUGS, "Aftab", "ab", "-aftab", "aftab-", "foo--bar", "aftab"):
            with self.subTest(slug=slug):
                with self.assertRaises(ValidationError):
                    Customer.objects.create(
                        name="دیگر",
                        manager_name="مدیر",
                        phone="09123456789",
                        slug=slug,
                        start_date=date(2026, 1, 1),
                        expiration_date=date(2026, 12, 31),
                    )

    def test_slug_is_immutable_through_api_and_model(self):
        self.assertEqual(
            self.central.patch(
                f"/api/customers/{self.a.pk}/", {"slug": "new-slug"}, format="json"
            ).status_code,
            400,
        )
        self.a.slug = "new-slug"
        with self.assertRaises(ValidationError):
            self.a.save()

    def test_operators_cannot_provision_or_view_portal_username(self):
        self.central.force_authenticate(self.operator)
        self.assertEqual(self.configure(login_username="changed").status_code, 403)
        self.assertIsNone(self.central.get(f"/api/customers/{self.a.pk}/").data["login_username"])

    def test_tenants_are_excluded_from_central_user_administration(self):
        users = self.central.get("/api/users/").data["results"]
        self.assertNotIn(self.owner.pk, [u["id"] for u in users])
        self.assertEqual(
            self.central.patch(
                f"/api/users/{self.owner.pk}/", {"role": "super_admin"}, format="json"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.central.post(
                "/api/users/",
                {"username": "forged", "password": PASSWORD, "role": "tenant", "organization": self.a.pk},
                format="json",
            ).status_code,
            400,
        )

    def test_login_sets_scoped_secure_session_without_leaking_identity_secrets(self):
        response = self.login()
        self.assertEqual(response.status_code, 200, response.data)
        cookie = response.cookies[settings.PORTAL_SESSION_COOKIE_NAME]
        self.assertEqual(cookie["path"], "/api/organizations/")
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertNotIn(settings.SESSION_COOKIE_NAME, response.cookies)
        raw = response.content.decode()
        for secret in (PASSWORD, self.owner.password, self.owner.username):
            self.assertNotIn(secret, raw)
        self.assertEqual(self.client.get("/api/organizations/aftab/dashboard/").status_code, 200)

    def test_private_portal_responses_are_never_cached(self):
        self.login()
        response = self.client.get("/api/organizations/aftab/dashboard/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])

    @override_settings(SESSION_COOKIE_SECURE=True)
    def test_portal_cookie_obeys_secure_production_setting(self):
        self.assertTrue(self.login().cookies[settings.PORTAL_SESSION_COOKIE_NAME]["secure"])

    def test_login_requires_csrf(self):
        self.assertEqual(
            self.client.post(
                "/api/organizations/aftab/login/",
                {"username": "manager", "password": PASSWORD},
                format="json",
            ).status_code,
            403,
        )

    def test_incorrect_credentials_account_rate_limit_and_retry_header(self):
        for _ in range(5):
            self.assertEqual(self.login(password="wrong").status_code, 400)
        response = self.login()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "900")

    def test_rate_limit_case_variations_cannot_bypass_normalized_account_key(self):
        for i in range(5):
            self.assertEqual(
                self.login(username="MANAGER" if i % 2 else "manager", password="wrong").status_code, 400
            )
        self.assertEqual(self.login(username="Manager").status_code, 429)

    def test_ip_rate_limit_covers_multiple_nonexistent_accounts(self):
        for i in range(20):
            self.assertEqual(self.login(username=f"missing{i}", password="wrong").status_code, 400)
        self.assertEqual(self.login().status_code, 429)

    def test_unknown_inactive_and_wrong_organization_credentials(self):
        self.assertEqual(self.login(slug="missing").status_code, 404)
        self.assertEqual(self.login(slug="darya").status_code, 400)
        self.owner.is_active = False
        self.owner.save()
        self.assertEqual(self.login().status_code, 400)

    def test_session_fixation_is_rotated_on_login(self):
        session = SessionStore()
        session["anonymous"] = True
        session.save()
        self.client.cookies[settings.PORTAL_SESSION_COOKIE_NAME] = session.session_key
        response = self.login()
        self.assertNotEqual(response.cookies[settings.PORTAL_SESSION_COOKIE_NAME].value, session.session_key)
        self.assertFalse(SessionStore().exists(session.session_key))

    def test_cross_tenant_dashboard_and_logout_are_denied(self):
        self.login()
        response = self.client.get("/api/organizations/darya/dashboard/", {"organization_id": self.a.pk})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(self.b.manager_name, str(response.data))
        self.assertEqual(
            self.client.post(
                "/api/organizations/darya/logout/", {}, format="json", HTTP_X_CSRFTOKEN=self.csrf()
            ).status_code,
            403,
        )
        self.assertEqual(self.client.get("/api/organizations/aftab/dashboard/").status_code, 200)

    def test_client_supplied_ids_do_not_change_dashboard_owner(self):
        self.login()
        response = self.client.get(
            "/api/organizations/aftab/dashboard/", {"organization_id": self.b.pk, "slug": "darya"}
        )
        self.assertEqual(response.data["organization"]["name"], self.a.name)

    def test_tenant_cannot_use_any_central_api_or_hidden_username_login(self):
        self.login()
        for path in ("customers/", "users/", "dashboard/", "auth/me/", "audit/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get("/api/" + path).status_code, 401)
        self.client.cookies[settings.SESSION_COOKIE_NAME] = self.client.cookies[
            settings.PORTAL_SESSION_COOKIE_NAME
        ].value
        self.assertEqual(self.client.get("/api/customers/").status_code, 403)
        response = self.client.post(
            "/api/auth/login/",
            {"username": self.owner.username, "password": PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )
        self.assertEqual(response.status_code, 400)

    def test_central_and_portal_sessions_coexist_and_logout_is_scoped(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": self.admin.username, "password": PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )
        self.assertEqual(response.status_code, 200)
        central_key = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        self.assertEqual(self.client.get("/api/organizations/aftab/dashboard/").status_code, 401)
        self.login()
        self.assertEqual(self.client.cookies[settings.SESSION_COOKIE_NAME].value, central_key)
        self.assertEqual(self.client.get("/api/auth/me/").data["id"], self.admin.pk)
        self.assertEqual(
            self.client.post("/api/organizations/aftab/logout/", {}, format="json").status_code, 403
        )
        response = self.client.post(
            "/api/organizations/aftab/logout/", {}, format="json", HTTP_X_CSRFTOKEN=self.csrf()
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.cookies[settings.PORTAL_SESSION_COOKIE_NAME]["max-age"], 0)
        self.assertEqual(self.client.get("/api/organizations/aftab/dashboard/").status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)

    def test_password_reset_and_username_changes_revoke_prior_sessions(self):
        self.login()
        self.assertEqual(self.configure(login_password=PASSWORD + "reset").status_code, 200)
        self.assertEqual(self.client.get("/api/organizations/aftab/dashboard/").status_code, 401)
        self.assertEqual(self.login(password=PASSWORD).status_code, 400)
        self.assertEqual(self.login(password=PASSWORD + "reset").status_code, 200)
        self.assertEqual(self.configure(login_username="new.manager").status_code, 200)
        self.assertEqual(self.client.get("/api/organizations/aftab/dashboard/").status_code, 401)
        self.assertEqual(self.login(username="new.manager", password=PASSWORD + "reset").status_code, 200)

    def test_deactivate_reactivate_does_not_restore_revoked_sessions(self):
        self.login()
        key = self.client.cookies[settings.PORTAL_SESSION_COOKIE_NAME].value
        self.assertEqual(self.configure(is_active=False).status_code, 200)
        self.assertEqual(self.configure(is_active=True).status_code, 200)
        self.client.cookies[settings.PORTAL_SESSION_COOKIE_NAME] = key
        self.assertEqual(self.client.get("/api/organizations/aftab/dashboard/").status_code, 401)

    def test_soft_delete_and_restore_cannot_restore_old_sessions(self):
        self.login()
        key = self.client.cookies[settings.PORTAL_SESSION_COOKIE_NAME].value
        self.assertEqual(self.central.delete(f"/api/customers/{self.a.pk}/").status_code, 204)
        self.assertEqual(self.client.get("/api/organizations/aftab/public/").status_code, 404)
        self.assertEqual(
            self.central.post(f"/api/customers/{self.a.pk}/restore/", {}, format="json").status_code, 200
        )
        self.client.cookies[settings.PORTAL_SESSION_COOKIE_NAME] = key
        self.assertEqual(self.client.get("/api/organizations/aftab/dashboard/").status_code, 401)

    def test_expired_subscription_allows_login_and_dashboard(self):
        self.a.expiration_date = timezone.localdate() - timedelta(days=1)
        self.a.save()
        self.assertEqual(self.login().status_code, 200)
        data = self.client.get("/api/organizations/aftab/dashboard/").data["organization"]["subscription"]
        self.assertEqual(data["status"], "expired")
        self.assertEqual(data["remaining_days"], 0)

    def test_central_changes_and_renewal_are_visible_without_duplication(self):
        self.login()
        count = Customer.objects.count()
        self.assertEqual(
            self.central.patch(
                f"/api/customers/{self.a.pk}/",
                {"capacity": 175, "name": "آفتاب نو", "phone": "09121111111", "manager_name": "مدیر جدید"},
                format="json",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.central.post(
                f"/api/customers/{self.a.pk}/renew/",
                {"expiration_date": (timezone.localdate() + timedelta(days=120)).isoformat()},
                format="json",
            ).status_code,
            200,
        )
        org = self.client.get("/api/organizations/aftab/dashboard/").data["organization"]
        self.assertEqual((org["capacity"], org["name"], org["manager_name"]), (175, "آفتاب نو", "مدیر جدید"))
        self.assertEqual(org["subscription"]["remaining_days"], 121)
        self.assertEqual(Customer.objects.count(), count)

    def test_audit_never_contains_password_or_hash(self):
        self.login()
        self.configure(login_password=PASSWORD + "reset")
        raw = json.dumps(list(AuditLog.objects.values("changes", "description")))
        self.assertNotIn(PASSWORD, raw)
        self.assertNotIn(self.owner.password, raw)

    def test_old_model_backend_central_session_is_preserved(self):
        session = SessionStore()
        session[SESSION_KEY] = str(self.admin.pk)
        session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
        session[HASH_SESSION_KEY] = self.admin.get_session_auth_hash()
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
        self.assertEqual(self.client.get("/api/auth/me/").data["id"], self.admin.pk)

    def test_database_rejects_cross_realm_identity_and_duplicate_owner(self):
        for fields in (
            {
                "username": "forged",
                "role": "super_admin",
                "organization": self.a,
                "portal_username": "forged",
            },
            {
                "username": "second-owner",
                "role": "tenant",
                "organization": self.a,
                "portal_username": "other",
                "is_portal_owner": True,
            },
        ):
            with self.subTest(username=fields["username"]):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    User.objects.create(**fields)


class SubscriptionTests(TestCase):
    def test_inclusive_boundaries_and_thirty_day_warning(self):
        today = date(2026, 10, 12)
        for start, end, status, remaining, progress in (
            (today, today, "expiring", 1, 0),
            (today - timedelta(days=10), today, "expiring", 1, 90.9),
            (today - timedelta(days=10), today - timedelta(days=1), "expired", 0, 100),
            (today, today + timedelta(days=30), "expiring", 31, 0),
            (today, today + timedelta(days=31), "active", 32, 0),
            (today + timedelta(days=10), today + timedelta(days=19), "scheduled", 10, 0),
        ):
            with self.subTest(start=start, end=end):
                result = subscription(Customer(start_date=start, expiration_date=end), today)
                self.assertEqual(
                    (result["status"], result["remaining_days"], result["progress_percent"]),
                    (status, remaining, progress),
                )
                self.assertTrue(result["end_date_inclusive"])

    def test_business_date_rolls_over_in_tehran_before_utc(self):
        instant = datetime(2026, 10, 12, 21, 0, tzinfo=utc.utc)
        with timezone.override("UTC"), patch("django.utils.timezone.now", return_value=instant):
            result = subscription(Customer(start_date=date(2026, 10, 12), expiration_date=date(2026, 10, 12)))
        self.assertEqual(result["business_date"], date(2026, 10, 13))
        self.assertEqual(result["status"], "expired")


class LegacyMigrationTests(TransactionTestCase):
    def test_existing_rows_receive_unique_slugs_without_invented_credentials(self):
        executor = MigrationExecutor(connection)
        executor.migrate([("core", "0002_alter_customer_phone")])
        try:
            old = executor.loader.project_state([("core", "0002_alter_customer_phone")]).apps
            CustomerOld = old.get_model("core", "Customer")
            for identifier in ("LEGACY01", "legacy01"):
                CustomerOld.objects.create(
                    name="قدیمی",
                    manager_name="مدیر",
                    phone="09123456789",
                    identifier=identifier,
                    start_date=date(2026, 1, 1),
                    expiration_date=date(2026, 12, 31),
                )
            executor = MigrationExecutor(connection)
            executor.migrate([("core", "0003_organization_portal")])
            migrated = executor.loader.project_state([("core", "0003_organization_portal")]).apps
            rows = list(migrated.get_model("core", "Customer").objects.order_by("pk"))
            self.assertEqual(rows[0].slug, "org-legacy01")
            self.assertNotEqual(rows[0].slug, rows[1].slug)
            self.assertTrue(all(row.capacity is None for row in rows))
            self.assertEqual(migrated.get_model("core", "User").objects.filter(role="tenant").count(), 0)
        finally:
            MigrationExecutor(connection).migrate([("core", "0003_organization_portal")])

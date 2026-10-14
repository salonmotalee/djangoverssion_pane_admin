"""Exercise real supervisor sessions, scoped identities and durable revocation."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from time import sleep

from django.conf import settings
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError, OperationalError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from core.models import AuditLog, Customer, User
from operations.models import Hall, Supervisor
from portal.services import provision_portal

from .models import SupervisorAccount
from .permissions import authorized_halls
from .services import provision_supervisor

PASSWORD = "TestingOnly$Damavand2026!"
NEW_PASSWORD = "TestingOnly$Changed2026!"


def organization(slug, expired=False):
    today = timezone.localdate()
    return Customer.objects.create(
        name=slug,
        manager_name="مدیر",
        phone="09123456789",
        slug=slug,
        capacity=80,
        start_date=today - timedelta(days=40),
        expiration_date=today + timedelta(days=-5 if expired else 90),
    )


class SupervisorAccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = organization("staff-test", expired=True)
        cls.other_organization = organization("staff-other")
        cls.manager = provision_portal(
            cls.organization, {"login_username": "manager", "login_password": PASSWORD}
        )
        cls.other_manager = provision_portal(
            cls.other_organization, {"login_username": "manager", "login_password": PASSWORD}
        )
        cls.central = User.objects.create_superuser(username="staff-central", password=PASSWORD)
        cls.hall = Hall.objects.create(organization=cls.organization, name="آفتاب")
        cls.other_hall = Hall.objects.create(organization=cls.organization, name="دریا")
        cls.foreign_hall = Hall.objects.create(organization=cls.other_organization, name="بیگانه")
        cls.supervisor = Supervisor.objects.create(
            organization=cls.organization, first_name="سارا", last_name="احمدی", phone="۰۹۱۲۳۴۵۶۷۸۹"
        )
        cls.duplicate_personnel = Supervisor.objects.create(
            organization=cls.organization, first_name="علی", last_name="رضایی", phone="09123456789"
        )
        cls.foreign_supervisor = Supervisor.objects.create(
            organization=cls.other_organization, first_name="مهسا", last_name="محمدی", phone="09123456789"
        )
        cls.supervisor.halls.add(cls.hall)

    def setUp(self):
        self.manager_client = APIClient()
        self.manager_client.force_authenticate(self.manager)
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf(self, client=None):
        return (client or self.client).get("/api/auth/csrf/").data["csrfToken"]

    def endpoint(self, action, slug="staff-test"):
        return f"/api/organizations/{slug}/supervisor/{action}/"

    def provision(self, supervisor=None, **data):
        supervisor = supervisor or self.supervisor
        payload = {"enabled": True, "password": PASSWORD, **data}
        return self.manager_client.put(
            f"/api/organizations/staff-test/supervisor-access/{supervisor.pk}/", payload, format="json"
        )

    def login(self, client=None, slug="staff-test", username="09123456789", password=PASSWORD):
        client = client or self.client
        return client.post(
            self.endpoint("login", slug),
            {"username": username, "password": password},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf(client),
        )

    def test_manager_provisioning_separates_personnel_and_hashes_password(self):
        response = self.provision()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["phone"], "09123456789")
        self.assertTrue(response.data["enabled"] and response.data["usable"])
        account = SupervisorAccount.objects.get(supervisor=self.supervisor)
        self.assertTrue(account.check_password(PASSWORD))
        self.assertNotEqual(account.password, PASSWORD)
        self.assertEqual(account.provisioned_by, self.manager)
        self.assertEqual(
            Supervisor.objects.filter(organization=self.organization, phone=account.phone).count(), 2
        )
        self.assertEqual(AuditLog.objects.filter(action="supervisor_access").count(), 1)
        self.assertNotIn(PASSWORD, response.content.decode())
        self.assertNotIn(account.password, response.content.decode())

    def test_provision_validation_and_server_owned_identity_fields(self):
        url = f"/api/organizations/staff-test/supervisor-access/{self.supervisor.pk}/"
        for payload in (
            {"enabled": True},
            {"enabled": True, "password": "short"},
            {"enabled": True, "password": "123456789000"},
            {"enabled": True, "password": PASSWORD, "organization_id": self.other_organization.pk},
            {"enabled": True, "password": PASSWORD, "phone": "09351234567"},
            {"enabled": True, "password": PASSWORD, "halls": [self.other_hall.pk]},
            {"enabled": True, "password": PASSWORD, "role": "tenant"},
        ):
            with self.subTest(payload={key: value for key, value in payload.items() if key != "password"}):
                self.assertEqual(self.manager_client.put(url, payload, format="json").status_code, 400)
        self.assertFalse(SupervisorAccount.objects.exists())
        self.assertEqual(self.manager_client.get(url).data["provisioned"], False)
        self.assertEqual(self.manager_client.put(url, {"enabled": False}, format="json").status_code, 200)

    def test_active_phone_is_unique_per_organization_but_personnel_remain_non_unique(self):
        self.assertEqual(self.provision().status_code, 200)
        self.assertEqual(self.provision(self.duplicate_personnel).status_code, 400)
        other = SupervisorAccount.objects.create_user(supervisor=self.foreign_supervisor, password=PASSWORD)
        self.assertEqual(other.phone, self.supervisor.phone)
        inactive = SupervisorAccount.objects.create_user(
            supervisor=self.duplicate_personnel, password=PASSWORD, is_active=False
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            SupervisorAccount.objects.filter(pk=inactive.pk).update(is_active=True)
        self.assertEqual(
            SupervisorAccount.objects.filter(organization=self.organization, is_active=True).count(), 1
        )

    def test_account_model_rejects_cross_tenant_or_identity_rebinding(self):
        with self.assertRaises(ModelValidationError):
            SupervisorAccount.objects.create(
                supervisor=self.foreign_supervisor,
                organization=self.organization,
                phone=self.foreign_supervisor.phone,
            )
        self.provision()
        account = SupervisorAccount.objects.get(supervisor=self.supervisor)
        account.supervisor = self.duplicate_personnel
        with self.assertRaises(ModelValidationError):
            account.save()

    def test_scoped_phone_login_normalization_and_expired_subscription_warning(self):
        self.provision()
        response = self.login(username="+۹۸ ۹۱۲-۳۴۵۶۷۸۹")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["supervisor_id"], self.supervisor.pk)
        self.assertEqual(response.data["halls"], [{"id": self.hall.pk, "name": self.hall.name}])
        self.assertEqual(response.data["organization"]["subscription"]["status"], "expired")
        self.assertEqual(self.client.get(self.endpoint("me")).status_code, 200)
        self.assertIn(self.client.get(self.endpoint("me", "staff-other")).status_code, (401, 403))
        self.assertEqual(self.login(slug="staff-other").status_code, 400)
        # No shift was ever created: access does not depend on shift hours.
        self.assertEqual(self.client.get(self.endpoint("profile")).status_code, 200)

    def test_supervisor_cannot_provision_accounts_or_access_manager_and_central_realms(self):
        self.provision()
        self.login()
        for path in (
            "/api/auth/me/",
            "/api/organizations/staff-test/dashboard/",
            f"/api/organizations/staff-test/supervisor-access/{self.supervisor.pk}/",
        ):
            self.assertIn(self.client.get(path).status_code, (401, 403))
        outsider = APIClient()
        outsider.force_authenticate(self.other_manager)
        url = f"/api/organizations/staff-test/supervisor-access/{self.supervisor.pk}/"
        self.assertEqual(
            outsider.put(url, {"enabled": True, "password": PASSWORD}, format="json").status_code, 403
        )
        foreign_personnel = f"/api/organizations/staff-test/supervisor-access/{self.foreign_supervisor.pk}/"
        self.assertEqual(
            self.manager_client.put(
                foreign_personnel, {"enabled": True, "password": PASSWORD}, format="json"
            ).status_code,
            404,
        )

    def test_three_cookie_realms_coexist_and_supervisor_logout_keeps_other_logins(self):
        self.provision()
        token = self.csrf()
        self.assertEqual(
            self.client.post(
                "/api/auth/login/",
                {"username": self.central.username, "password": PASSWORD},
                format="json",
                HTTP_X_CSRFTOKEN=token,
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/api/organizations/staff-test/login/",
                {"username": "manager", "password": PASSWORD},
                format="json",
                HTTP_X_CSRFTOKEN=self.csrf(),
            ).status_code,
            200,
        )
        self.assertEqual(self.login().status_code, 200)
        for name in (
            settings.SESSION_COOKIE_NAME,
            settings.PORTAL_SESSION_COOKIE_NAME,
            settings.SUPERVISOR_SESSION_COOKIE_NAME,
        ):
            self.assertIn(name, self.client.cookies)
        for path in ("/api/auth/me/", "/api/organizations/staff-test/dashboard/", self.endpoint("me")):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.assertEqual(
            self.client.post(self.endpoint("logout"), HTTP_X_CSRFTOKEN=self.csrf()).status_code, 204
        )
        self.assertIn(self.client.get(self.endpoint("me")).status_code, (401, 403))
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)
        self.assertEqual(self.client.get("/api/organizations/staff-test/dashboard/").status_code, 200)

    def test_login_logout_password_and_provisioning_require_csrf(self):
        self.provision()
        self.assertEqual(
            self.client.post(
                self.endpoint("login"),
                {"username": self.supervisor.phone, "password": PASSWORD},
                format="json",
            ).status_code,
            403,
        )
        self.login()
        self.assertEqual(self.client.post(self.endpoint("logout")).status_code, 403)
        self.assertEqual(
            self.client.patch(
                self.endpoint("profile"),
                {"current_password": PASSWORD, "new_password": NEW_PASSWORD},
                format="json",
            ).status_code,
            403,
        )
        manager = APIClient(enforce_csrf_checks=True)
        manager.post(
            "/api/organizations/staff-test/login/",
            {"username": "manager", "password": PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf(manager),
        )
        self.assertEqual(
            manager.put(
                f"/api/organizations/staff-test/supervisor-access/{self.supervisor.pk}/",
                {"enabled": False},
                format="json",
            ).status_code,
            403,
        )

    def test_disable_reenable_and_manager_reset_invalidate_all_previous_sessions(self):
        self.provision()
        self.login()
        second = APIClient(enforce_csrf_checks=True)
        self.login(client=second)
        self.assertEqual(self.provision(enabled=False).status_code, 200)
        self.assertEqual(self.provision().status_code, 200)
        for client in (self.client, second):
            self.assertIn(client.get(self.endpoint("me")).status_code, (401, 403))
        self.login()
        self.assertEqual(self.provision(password=NEW_PASSWORD).status_code, 200)
        self.assertIn(self.client.get(self.endpoint("me")).status_code, (401, 403))
        self.assertEqual(self.login().status_code, 400)
        self.assertEqual(self.login(password=NEW_PASSWORD).status_code, 200)

    def test_self_password_change_preserves_current_session_and_revokes_other_devices(self):
        self.provision()
        self.login()
        second = APIClient(enforce_csrf_checks=True)
        self.login(client=second)
        response = self.client.patch(
            self.endpoint("profile"),
            {"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.get(self.endpoint("me")).status_code, 200)
        self.assertIn(second.get(self.endpoint("me")).status_code, (401, 403))

    def test_live_personnel_phone_change_requires_reprovision_and_old_sessions_stay_invalid(self):
        self.provision()
        self.login()
        self.supervisor.phone = "09351234567"
        self.supervisor.save()
        self.assertEqual(self.login().status_code, 400)
        self.assertIn(self.client.get(self.endpoint("me")).status_code, (401, 403))
        self.assertEqual(self.provision().status_code, 200)
        self.assertEqual(self.login(username="09351234567").status_code, 200)

    def test_personnel_archive_and_deactivate_restore_never_revive_sessions(self):
        self.provision()
        for field, value, restored in (("is_active", False, True), ("archived_at", timezone.now(), None)):
            with self.subTest(field=field):
                self.login()
                setattr(self.supervisor, field, value)
                self.supervisor.save()
                setattr(self.supervisor, field, restored)
                self.supervisor.save()
                self.assertIn(self.client.get(self.endpoint("me")).status_code, (401, 403))
                self.assertEqual(self.login().status_code, 200)

    def test_organization_archive_restore_never_revives_sessions(self):
        self.provision()
        self.login()
        self.organization.deleted_at = timezone.now()
        self.organization.save()
        self.organization.deleted_at = None
        self.organization.save()
        self.assertIn(self.client.get(self.endpoint("me")).status_code, (401, 403))
        self.assertEqual(self.login().status_code, 200)

    def test_hall_authorization_is_live_same_tenant_and_excludes_archived_halls(self):
        self.provision()
        account = SupervisorAccount.objects.get(supervisor=self.supervisor)
        self.assertEqual(list(authorized_halls(account)), [self.hall])
        self.supervisor.halls.remove(self.hall)
        self.assertFalse(authorized_halls(account).exists())
        self.supervisor.halls.add(self.other_hall)
        Hall.objects.filter(pk=self.other_hall.pk).update(is_active=False)
        self.assertFalse(authorized_halls(account).exists())
        self.assertFalse(authorized_halls(account).filter(pk=self.foreign_hall.pk).exists())

    def test_login_throttle_is_normalized_and_does_not_cross_organization_account_keys(self):
        self.provision()
        for _ in range(5):
            self.assertEqual(self.login(password="wrong", username="+98 9123456789").status_code, 400)
        self.assertEqual(self.login(username="۰۹۱۲۳۴۵۶۷۸۹").status_code, 429)
        self.assertEqual(self.login(slug="staff-other").status_code, 400)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ConcurrentSupervisorProvisioningTests(TransactionTestCase):
    def test_concurrent_same_phone_only_one_active_identity_is_provisioned(self):
        tenant = organization("staff-concurrent")
        manager = provision_portal(tenant, {"login_username": "manager", "login_password": PASSWORD})
        personnel = [
            Supervisor.objects.create(
                organization=tenant, first_name=f"مراقب {i}", last_name="آزمون", phone="09123456789"
            )
            for i in range(2)
        ]
        ready = Barrier(2)

        def provision_one(personnel_id):
            close_old_connections()
            ready.wait(timeout=5)
            try:
                for attempt in range(40):
                    try:
                        provision_supervisor(tenant, personnel_id, manager, True, PASSWORD)
                        return "created"
                    except ValidationError:
                        return "duplicate"
                    except OperationalError as exc:
                        # Django's shared in-memory SQLite uses SQLITE_LOCKED,
                        # whereas file SQLite IMMEDIATE/PostgreSQL wait on locks.
                        if "locked" not in str(exc).lower() or attempt == 39:
                            raise
                        sleep(0.02)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(provision_one, [person.pk for person in personnel]))
        self.assertCountEqual(outcomes, ["created", "duplicate"])
        self.assertEqual(SupervisorAccount.objects.filter(organization=tenant, is_active=True).count(), 1)

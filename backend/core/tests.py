"""Behavior and security regression tests for the administration API."""

import csv
import io
import json
from datetime import date, datetime, timedelta
from datetime import timezone as datetime_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import Customer

User = get_user_model()
PASSWORD = "CorrectHorse$2026!"


def response_rows(response):
    """Unwrap the API's standard paginated list response."""
    return response.data["results"] if isinstance(response.data, dict) else response.data


class AdminAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.super_admin = User.objects.create_superuser(username="owner", password=PASSWORD)
        cls.admin = User.objects.create_user(username="administrator", password=PASSWORD, role="admin")
        cls.operator = User.objects.create_user(username="operator", password=PASSWORD, role="operator")

    def setUp(self):
        self.today = timezone.localdate()
        self.client.force_authenticate(self.super_admin)

    def customer_data(self, **changes):
        data = {
            "name": "مجموعه مطالعه سپید",
            "manager_name": "سارا احمدی",
            "phone": "09123456789",
            "start_date": self.today.isoformat(),
            "expiration_date": (self.today + timedelta(days=90)).isoformat(),
        }
        data.update(changes)
        return data

    def customer(self, **changes):
        data = self.customer_data()
        data["start_date"] = date.fromisoformat(data["start_date"])
        data["expiration_date"] = date.fromisoformat(data["expiration_date"])
        data.update(changes)
        return Customer.objects.create(**data)


class AuthenticationTests(AdminAPITestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf(self):
        response = self.client.get("/api/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        return self.client.cookies["csrftoken"].value

    def login(self, username="owner", password=PASSWORD):
        return self.client.post(
            "/api/auth/login/",
            {"username": username, "password": password},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )

    def test_session_login_and_logout_require_csrf(self):
        missing_csrf = self.client.post(
            "/api/auth/login/", {"username": "owner", "password": PASSWORD}, format="json"
        )
        self.assertEqual(missing_csrf.status_code, 403)
        self.assertEqual(self.login().status_code, 200)
        session_cookie = self.client.cookies["sessionid"]
        self.assertTrue(session_cookie["httponly"])
        self.assertEqual(session_cookie["samesite"], "Lax")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)

        without_token = self.client.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(without_token.status_code, 403)
        logout = self.client.post("/api/auth/logout/", {}, format="json", HTTP_X_CSRFTOKEN=self.csrf())
        self.assertIn(logout.status_code, (200, 204))
        self.assertIn(self.client.get("/api/auth/me/").status_code, (401, 403))

    def test_login_does_not_expose_password_or_hash(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        serialized = json.dumps(response.data)
        self.assertNotIn(PASSWORD, serialized)
        self.assertNotIn(self.super_admin.password, serialized)
        self.assertNotIn('"password"', serialized)

    def test_inactive_user_cannot_login(self):
        self.operator.is_active = False
        self.operator.save(update_fields=["is_active"])
        response = self.login(username="operator")
        self.assertIn(response.status_code, (400, 401, 403))
        self.assertNotIn("sessionid", self.client.cookies)

    def test_credentials_checked_before_concurrent_reset_do_not_create_a_session(self):
        User.objects.filter(pk=self.super_admin.pk).update(password=make_password("Concurrent$Reset2026!"))
        with patch("core.views.authenticate", return_value=self.super_admin):
            response = self.login()
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("sessionid", self.client.cookies)

    def test_repeated_failed_login_is_throttled(self):
        statuses = [self.login(password="wrong-password").status_code for _ in range(7)]
        self.assertEqual(statuses[:5], [400] * 5)
        self.assertIn(429, statuses)
        self.assertEqual(self.login().status_code, 429)

    def test_late_window_failure_keeps_account_locked_until_full_lockout_expires(self):
        started = timezone.now()
        with patch("django.utils.timezone.now", return_value=started):
            for _ in range(4):
                self.assertEqual(self.login(password="incorrect").status_code, 400)
        with patch("django.utils.timezone.now", return_value=started + timedelta(minutes=14)):
            self.assertEqual(self.login(password="incorrect").status_code, 400)
        # The original counting window has ended, but the newer lock is still live.
        with patch("django.utils.timezone.now", return_value=started + timedelta(minutes=16)):
            self.assertEqual(self.login().status_code, 429)
        with patch("django.utils.timezone.now", return_value=started + timedelta(minutes=30)):
            self.assertEqual(self.login().status_code, 200)

    def test_deactivated_user_loses_access_with_existing_session(self):
        self.assertEqual(self.login(username="operator").status_code, 200)
        self.operator.is_active = False
        self.operator.save(update_fields=["is_active"])
        self.assertIn(self.client.get("/api/auth/me/").status_code, (401, 403))

    def test_authenticated_session_requires_csrf_for_customer_write(self):
        self.assertEqual(self.login().status_code, 200)
        response = self.client.post("/api/customers/", self.customer_data(), format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Customer.objects.exists())

    def test_password_change_requires_current_password_and_valid_new_password(self):
        self.assertEqual(self.login().status_code, 200)
        for changes in (
            {"current_password": "incorrect", "new_password": "Replacement$Strong2026!"},
            {"current_password": PASSWORD, "new_password": "123"},
        ):
            with self.subTest(changes=changes):
                response = self.client.post(
                    "/api/auth/password/", changes, format="json", HTTP_X_CSRFTOKEN=self.csrf()
                )
                self.assertEqual(response.status_code, 400)
        self.super_admin.refresh_from_db()
        self.assertTrue(self.super_admin.check_password(PASSWORD))

    def test_password_change_hashes_new_password_and_old_password_stops_working(self):
        self.assertEqual(self.login().status_code, 200)
        new_password = "Replacement$Strong2026!"
        response = self.client.post(
            "/api/auth/password/",
            {"current_password": PASSWORD, "new_password": new_password},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )
        self.assertIn(response.status_code, (200, 204), response.data)
        self.super_admin.refresh_from_db()
        self.assertTrue(self.super_admin.check_password(new_password))
        self.assertFalse(self.super_admin.check_password(PASSWORD))
        self.assertNotEqual(self.super_admin.password, new_password)
        self.client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(self.login(password=PASSWORD).status_code, 400)
        self.assertEqual(self.login(password=new_password).status_code, 200)

    def test_anonymous_requests_cannot_read_internal_data(self):
        for url in ("/api/users/", "/api/customers/", "/api/dashboard/", "/api/audit/"):
            with self.subTest(url=url):
                self.assertIn(self.client.get(url).status_code, (401, 403))


class UserPermissionTests(AdminAPITestCase):
    def test_stale_login_timestamp_update_keeps_concurrent_privilege_revocation(self):
        stale_user = self.admin
        User.objects.filter(pk=stale_user.pk).update(role="operator", is_superuser=False, is_staff=False)
        stale_user.last_login = timezone.now()
        stale_user.save(update_fields=["last_login"])
        current = User.objects.get(pk=stale_user.pk)
        self.assertEqual(current.role, "operator")
        self.assertFalse(current.is_superuser)
        self.assertFalse(current.is_staff)
        self.assertEqual(current.last_login, stale_user.last_login)

    def test_stale_profile_request_cannot_restore_concurrently_revoked_permissions(self):
        stale_user = self.admin
        self.client.force_authenticate(stale_user)
        password_hash = make_password("Concurrent$Reset2026!")
        User.objects.filter(pk=stale_user.pk).update(
            role="operator", is_superuser=False, is_staff=False, is_active=False, password=password_hash
        )
        response = self.client.patch("/api/auth/me/", {"first_name": "نام جدید"}, format="json")
        self.assertEqual(response.status_code, 403)
        current = User.objects.get(pk=stale_user.pk)
        self.assertEqual(current.role, "operator")
        self.assertFalse(current.is_active)
        self.assertEqual(current.password, password_hash)

    def test_stale_profile_request_keeps_concurrent_demotion_and_password_reset(self):
        stale_user = self.admin
        self.client.force_authenticate(stale_user)
        password_hash = make_password("Concurrent$Reset2026!")
        User.objects.filter(pk=stale_user.pk).update(
            role="operator", is_superuser=False, is_staff=False, password=password_hash
        )
        response = self.client.patch("/api/auth/me/", {"first_name": "نام جدید"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        current = User.objects.get(pk=stale_user.pk)
        self.assertEqual(current.first_name, "نام جدید")
        self.assertEqual(current.role, "operator")
        self.assertFalse(current.is_staff)
        self.assertEqual(current.password, password_hash)

    def test_stale_password_request_checks_current_database_password(self):
        stale_user = self.admin
        self.client.force_authenticate(stale_user)
        password_hash = make_password("Concurrent$Reset2026!")
        User.objects.filter(pk=stale_user.pk).update(password=password_hash)
        response = self.client.post(
            "/api/auth/password/",
            {"current_password": PASSWORD, "new_password": "Attacker$Chosen2026!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.get(pk=stale_user.pk).password, password_hash)

    def test_operator_can_edit_profile_without_changing_permissions(self):
        self.client.force_authenticate(self.operator)
        response = self.client.patch(
            "/api/auth/me/",
            {"first_name": "سارا", "last_name": "احمدی", "email": "sara@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.operator.refresh_from_db()
        self.assertEqual(self.operator.first_name, "سارا")
        self.assertEqual(self.operator.role, "operator")

    def test_profile_endpoint_rejects_privilege_escalation(self):
        self.client.force_authenticate(self.operator)
        response = self.client.patch(
            "/api/auth/me/", {"role": "super_admin", "is_superuser": True, "is_active": True}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.operator.refresh_from_db()
        self.assertEqual(self.operator.role, "operator")
        self.assertFalse(self.operator.is_superuser)

    def test_operator_cannot_manage_users(self):
        self.client.force_authenticate(self.operator)
        self.assertEqual(self.client.get("/api/users/").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/users/", {"username": "new", "password": PASSWORD, "role": "operator"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(f"/api/users/{self.admin.pk}/", {"is_active": False}).status_code, 403
        )

    def test_administrator_can_create_and_manage_operator(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/users/",
            {"username": "new-operator", "password": PASSWORD, "role": "operator"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(pk=response.data["id"])
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_superuser)
        self.assertNotIn("password", response.data)
        update = self.client.patch(f"/api/users/{user.pk}/", {"is_active": False}, format="json")
        self.assertEqual(update.status_code, 200, update.data)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_administrator_cannot_create_privileged_role(self):
        self.client.force_authenticate(self.admin)
        for role in ("admin", "super_admin"):
            with self.subTest(role=role):
                response = self.client.post(
                    "/api/users/",
                    {"username": "promoted-" + role, "password": PASSWORD, "role": role},
                    format="json",
                )
                self.assertIn(response.status_code, (400, 403))
        self.assertFalse(User.objects.filter(username__startswith="promoted-").exists())

    def test_administrator_cannot_promote_operator(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/api/users/{self.operator.pk}/", {"role": "super_admin"}, format="json"
        )
        self.assertIn(response.status_code, (400, 403))
        self.operator.refresh_from_db()
        self.assertEqual(self.operator.role, "operator")

    def test_administrator_cannot_manage_another_administrator(self):
        self.client.force_authenticate(self.admin)
        other_admin = User.objects.create_user(username="other-admin", password=PASSWORD, role="admin")
        for target in (self.super_admin, other_admin):
            for method in ("get", "patch", "delete"):
                with self.subTest(method=method, role=target.role):
                    url = f"/api/users/{target.pk}/"
                    response = (
                        self.client.get(url)
                        if method == "get"
                        else getattr(self.client, method)(url, {"is_active": False}, format="json")
                    )
                    self.assertEqual(response.status_code, 403)
        response = self.client.post(
            f"/api/users/{self.super_admin.pk}/reset_password/",
            {"new_password": "DifferentSecure$2026!"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_framework_privilege_fields_do_not_allow_escalation(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/api/users/{self.operator.pk}/", {"is_superuser": True, "is_staff": True}, format="json"
        )
        self.assertIn(response.status_code, (200, 400))
        self.operator.refresh_from_db()
        self.assertEqual(self.operator.role, "operator")
        self.assertFalse(self.operator.is_superuser)

    def test_administrator_can_reset_only_operator_password(self):
        self.client.force_authenticate(self.admin)
        new_password = "Operator$Replacement2026!"
        response = self.client.post(
            f"/api/users/{self.operator.pk}/reset_password/", {"new_password": new_password}, format="json"
        )
        self.assertIn(response.status_code, (200, 204), response.data)
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.check_password(new_password))
        self.assertNotIn(new_password, json.dumps(response.data))

    def test_weak_password_is_rejected_during_user_creation(self):
        response = self.client.post(
            "/api/users/", {"username": "weak-user", "password": "123", "role": "operator"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="weak-user").exists())

    def test_last_active_super_administrator_cannot_be_removed(self):
        for changes in ({"is_active": False}, {"role": "admin"}):
            with self.subTest(changes=changes):
                response = self.client.patch(f"/api/users/{self.super_admin.pk}/", changes, format="json")
                self.assertIn(response.status_code, (400, 403, 409))
        self.assertIn(self.client.delete(f"/api/users/{self.super_admin.pk}/").status_code, (400, 403, 409))
        self.super_admin.refresh_from_db()
        self.assertEqual(self.super_admin.role, "super_admin")
        self.assertTrue(self.super_admin.is_active)

    def test_inactive_super_administrator_does_not_remove_last_admin_guard(self):
        User.objects.create_user(
            username="inactive-owner", password=PASSWORD, role="super_admin", is_active=False
        )
        response = self.client.patch(
            f"/api/users/{self.super_admin.pk}/", {"is_active": False}, format="json"
        )
        self.assertIn(response.status_code, (400, 403, 409))
        self.super_admin.refresh_from_db()
        self.assertTrue(self.super_admin.is_active)

    def test_super_administrator_can_demote_when_another_active_super_exists(self):
        second = User.objects.create_user(username="second-owner", password=PASSWORD, role="super_admin")
        response = self.client.patch(f"/api/users/{second.pk}/", {"role": "admin"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        second.refresh_from_db()
        self.assertEqual(second.role, "admin")
        self.assertFalse(second.is_superuser)


class CustomerTests(AdminAPITestCase):
    def test_identifier_is_generated_unique_and_stable(self):
        first = self.client.post("/api/customers/", self.customer_data(), format="json")
        second = self.client.post("/api/customers/", self.customer_data(name="مجموعه دوم"), format="json")
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertRegex(first.data["identifier"], r"^[A-Za-z0-9]+$")
        self.assertNotEqual(first.data["identifier"], second.data["identifier"])
        update = self.client.patch(
            f"/api/customers/{first.data['id']}/", {"manager_name": "مدیر جدید"}, format="json"
        )
        self.assertEqual(update.status_code, 200, update.data)
        self.assertEqual(update.data["identifier"], first.data["identifier"])

    def test_identifier_cannot_be_changed(self):
        customer = self.customer(identifier="IMMUTABLE01")
        response = self.client.patch(
            f"/api/customers/{customer.pk}/", {"identifier": "REPLACEMENT01"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        customer.refresh_from_db()
        self.assertEqual(customer.identifier, "IMMUTABLE01")

    def test_custom_identifier_must_be_unique_and_alphanumeric(self):
        self.customer(identifier="SALON01")
        for identifier in ("SALON01", "invalid-value", "فارسی", "value with space"):
            with self.subTest(identifier=identifier):
                response = self.client.post(
                    "/api/customers/", self.customer_data(identifier=identifier), format="json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("identifier", response.data)

    def test_phone_and_service_date_validation(self):
        for changes, field in (
            ({"phone": "12345"}, "phone"),
            ({"phone": "08123456789"}, "phone"),
            ({"expiration_date": (self.today - timedelta(days=1)).isoformat()}, "expiration_date"),
            ({"start_date": "not-a-date"}, "start_date"),
        ):
            with self.subTest(changes=changes):
                response = self.client.post("/api/customers/", self.customer_data(**changes), format="json")
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(field, response.data)

    def test_iranian_phone_input_is_normalized_to_ascii(self):
        for phone in ("۰۹۱۲۳۴۵۶۷۸۹", "+989123456789", "0912-345-6789"):
            with self.subTest(phone=phone):
                response = self.client.post("/api/customers/", self.customer_data(phone=phone), format="json")
                self.assertEqual(response.status_code, 201, response.data)
                self.assertEqual(response.data["phone"], "09123456789")

    def test_international_0098_phone_prefix_accepts_ascii_and_persian_input(self):
        for phone in ("00989123456789", "۰۰۹۸۹۱۲۳۴۵۶۷۸۹"):
            with self.subTest(phone=phone):
                response = self.client.post("/api/customers/", self.customer_data(phone=phone), format="json")
                self.assertEqual(response.status_code, 201, response.data)
                self.assertEqual(response.data["phone"], "09123456789")
                self.assertEqual(Customer.objects.get(pk=response.data["id"]).phone, "09123456789")

    def test_partial_update_validates_dates_against_existing_values(self):
        customer = self.customer()
        response = self.client.patch(
            f"/api/customers/{customer.pk}/",
            {"expiration_date": (self.today - timedelta(days=1)).isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        customer.refresh_from_db()
        self.assertEqual(customer.expiration_date, self.today + timedelta(days=90))

    def test_operator_can_create_and_edit_customer(self):
        self.client.force_authenticate(self.operator)
        response = self.client.post("/api/customers/", self.customer_data(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        update = self.client.patch(
            f"/api/customers/{response.data['id']}/", {"name": "نام اصلاح شده"}, format="json"
        )
        self.assertEqual(update.status_code, 200, update.data)
        self.assertEqual(update.data["name"], "نام اصلاح شده")

    def test_soft_delete_preserves_record_and_restore_identifier(self):
        customer = self.customer(identifier="RESTORE01")
        self.assertEqual(self.client.delete(f"/api/customers/{customer.pk}/").status_code, 204)
        customer.refresh_from_db()
        self.assertIsNotNone(customer.deleted_at)
        self.assertEqual(self.client.get(f"/api/customers/{customer.pk}/").status_code, 404)
        self.assertNotIn(
            customer.pk, [row["id"] for row in response_rows(self.client.get("/api/customers/"))]
        )
        response = self.client.post(f"/api/customers/{customer.pk}/restore/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        customer.refresh_from_db()
        self.assertIsNone(customer.deleted_at)
        self.assertEqual(customer.identifier, "RESTORE01")

    def test_operator_cannot_delete_or_restore(self):
        customer = self.customer()
        self.client.force_authenticate(self.operator)
        self.assertEqual(self.client.delete(f"/api/customers/{customer.pk}/").status_code, 403)
        customer.deleted_at = timezone.now()
        customer.save(update_fields=["deleted_at"])
        self.assertEqual(self.client.post(f"/api/customers/{customer.pk}/restore/", {}).status_code, 403)
        customer.refresh_from_db()
        self.assertIsNotNone(customer.deleted_at)

    def test_search_and_status_filters_use_real_customer_data(self):
        expired = self.customer(
            name="کتاب آبی",
            start_date=self.today - timedelta(days=100),
            expiration_date=self.today - timedelta(days=1),
        )
        self.customer(name="کتاب سبز")
        response = self.client.get("/api/customers/", {"search": "آبی", "status": "expired"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response_rows(response)], [expired.pk])

    def test_customer_identifiers_remain_reserved_after_soft_deletion(self):
        customer = self.customer(identifier="RESERVED01")
        self.client.delete(f"/api/customers/{customer.pk}/")
        response = self.client.post(
            "/api/customers/", self.customer_data(identifier="RESERVED01"), format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_phone_search_accepts_persian_arabic_and_international_digits(self):
        matching = self.customer(phone="09123456789")
        self.customer(phone="09351234567")
        for search in ("۰۹۱۲", "٠٩١٢", "+۹۸۹۱۲", "۰۹۱۲ ۳۴۵"):
            with self.subTest(search=search):
                response = self.client.get("/api/customers/", {"search": search})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([row["id"] for row in response_rows(response)], [matching.pk])

    def test_phone_search_normalization_keeps_persian_digits_in_names(self):
        named = self.customer(name="مجموعه ۱۴۰۵", phone="09351234567")
        self.customer(name="مجموعه 1405", phone="09123456789")
        response = self.client.get("/api/customers/", {"search": "مجموعه ۱۴۰۵"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response_rows(response)], [named.pk])

    def test_operator_can_renew_without_changing_identifier_or_start_date(self):
        customer = self.customer(identifier="RENEW01")
        self.client.force_authenticate(self.operator)
        new_expiration = self.today + timedelta(days=180)
        response = self.client.post(
            f"/api/customers/{customer.pk}/renew/",
            {"expiration_date": new_expiration.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        customer.refresh_from_db()
        self.assertEqual(customer.expiration_date, new_expiration)
        self.assertEqual(customer.start_date, self.today)
        self.assertEqual(customer.identifier, "RENEW01")

    def test_renewal_must_extend_existing_service(self):
        customer = self.customer()
        original_expiration = customer.expiration_date
        for expiration in (original_expiration, original_expiration - timedelta(days=1)):
            with self.subTest(expiration=expiration):
                response = self.client.post(
                    f"/api/customers/{customer.pk}/renew/",
                    {"expiration_date": expiration.isoformat()},
                    format="json",
                )
                self.assertEqual(response.status_code, 400)
        customer.refresh_from_db()
        self.assertEqual(customer.expiration_date, original_expiration)

    def test_deleted_filter_and_sorting_are_applied(self):
        earlier = self.customer(name="First", expiration_date=self.today + timedelta(days=40))
        later = self.customer(name="Second", expiration_date=self.today + timedelta(days=80))
        deleted = self.customer(name="Deleted", deleted_at=timezone.now())
        response = self.client.get("/api/customers/", {"ordering": "expiration_date"})
        self.assertEqual([row["id"] for row in response_rows(response)], [earlier.pk, later.pk])
        response = self.client.get("/api/customers/", {"deleted": "deleted"})
        self.assertEqual([row["id"] for row in response_rows(response)], [deleted.pk])
        response = self.client.get("/api/customers/", {"deleted": "all"})
        self.assertCountEqual(
            [row["id"] for row in response_rows(response)], [earlier.pk, later.pk, deleted.pk]
        )

    def test_customer_pagination_has_total_and_distinct_pages(self):
        for index in range(12):
            self.customer(name=f"مجموعه {index}")
        first = self.client.get("/api/customers/", {"page_size": 5})
        second = self.client.get("/api/customers/", {"page_size": 5, "page": 2})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["count"], 12)
        self.assertEqual(len(first.data["results"]), 5)
        self.assertEqual(len(second.data["results"]), 5)
        self.assertTrue(
            {row["id"] for row in first.data["results"]}.isdisjoint(
                {row["id"] for row in second.data["results"]}
            )
        )

    def test_invalid_ordering_returns_validation_error(self):
        for ordering in ("--name", "password", "name,,created_at"):
            with self.subTest(ordering=ordering):
                response = self.client.get("/api/customers/", {"ordering": ordering})
                self.assertEqual(response.status_code, 400)

    def test_malformed_date_filters_fail_with_validation_error(self):
        for field in ("start_date_from", "expiration_date_to", "created_date_from", "created_date_to"):
            with self.subTest(field=field):
                response = self.client.get("/api/customers/", {field: "not-a-date"})
                self.assertEqual(response.status_code, 400)

    def test_reversed_customer_date_ranges_are_rejected(self):
        for prefix in ("start_date", "expiration_date", "created_date"):
            with self.subTest(prefix=prefix):
                response = self.client.get(
                    "/api/customers/",
                    {
                        prefix + "_from": (self.today + timedelta(days=1)).isoformat(),
                        prefix + "_to": self.today.isoformat(),
                    },
                )
                self.assertEqual(response.status_code, 400)


class ServiceStatusTests(AdminAPITestCase):
    def test_status_uses_tehran_date_after_utc_day_boundary(self):
        # 21:00 UTC on October 11 is 00:30 on October 12 in Tehran.
        instant = datetime(2026, 10, 11, 21, 0, tzinfo=datetime_timezone.utc)
        with override_settings(TIME_ZONE="Asia/Tehran"), timezone.override("Asia/Tehran"):
            with patch("django.utils.timezone.now", return_value=instant):
                customer = self.customer(start_date=date(2026, 9, 1), expiration_date=date(2026, 10, 11))
                self.assertEqual(customer.status, "expired")

    def test_status_boundaries_follow_tehran_business_date(self):
        today = date(2026, 10, 12)
        with override_settings(TIME_ZONE="Asia/Tehran"):
            with patch("django.utils.timezone.localdate", return_value=today):
                cases = (
                    (today + timedelta(days=1), today + timedelta(days=90), "scheduled"),
                    (today, today + timedelta(days=31), "active"),
                    (today, today + timedelta(days=30), "expiring"),
                    (today, today, "expiring"),
                    (today - timedelta(days=90), today - timedelta(days=1), "expired"),
                )
                for start, expiration, expected in cases:
                    with self.subTest(start=start, expiration=expiration):
                        customer = self.customer(start_date=start, expiration_date=expiration)
                        self.assertEqual(customer.status, expected)

    def test_expired_service_remains_visible_and_editable(self):
        customer = self.customer(
            start_date=self.today - timedelta(days=100), expiration_date=self.today - timedelta(days=1)
        )
        detail = self.client.get(f"/api/customers/{customer.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["status"], "expired")
        update = self.client.patch(
            f"/api/customers/{customer.pk}/", {"manager_name": "مدیر جدید"}, format="json"
        )
        self.assertEqual(update.status_code, 200)
        customer.refresh_from_db()
        self.assertIsNone(customer.deleted_at)


class ReportingTests(AdminAPITestCase):
    def test_dashboard_current_service_link_matches_count_and_creation_date_range(self):
        active = self.customer(expiration_date=self.today + timedelta(days=90))
        expiring = self.customer(expiration_date=self.today)
        self.customer(
            start_date=self.today + timedelta(days=1), expiration_date=self.today + timedelta(days=90)
        )
        self.customer(
            start_date=self.today - timedelta(days=90), expiration_date=self.today - timedelta(days=1)
        )
        old = self.customer(expiration_date=self.today + timedelta(days=90))
        Customer.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=10))
        self.customer(deleted_at=timezone.now())
        dashboard = self.client.get(
            "/api/dashboard/", {"date_from": self.today.isoformat(), "date_to": self.today.isoformat()}
        )
        listing = self.client.get(
            "/api/customers/",
            {
                "status": "current",
                "created_date_from": self.today.isoformat(),
                "created_date_to": self.today.isoformat(),
            },
        )
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["count"], dashboard.data["metrics"]["active_services"])
        self.assertCountEqual([row["id"] for row in response_rows(listing)], [active.pk, expiring.pk])
        self.assertCountEqual([row["status"] for row in response_rows(listing)], ["active", "expiring"])

    def test_invalid_dashboard_date_ranges_are_rejected(self):
        for params in (
            {"date_from": "not-a-date"},
            {"date_to": "not-a-date"},
            {"date_from": (self.today + timedelta(days=1)).isoformat(), "date_to": self.today.isoformat()},
        ):
            with self.subTest(params=params):
                self.assertEqual(self.client.get("/api/dashboard/", params).status_code, 400)

    def test_audit_api_is_read_only(self):
        response = self.client.post("/api/audit/", {"action": "forged"}, format="json")
        self.assertEqual(response.status_code, 405)

    def test_empty_dashboard_has_real_zero_customer_counts(self):
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, 200)
        metrics = response.data["metrics"]
        for metric in (
            "total_customers",
            "active_services",
            "expiring_services",
            "expired_services",
            "scheduled_services",
            "expiring_7_days",
        ):
            with self.subTest(metric=metric):
                self.assertEqual(metrics[metric], 0)
        self.assertEqual(metrics["active_administrators"], 2)
        self.assertEqual(response.data["recent_customers"], [])
        self.assertEqual(response.data["upcoming_expirations"], [])
        self.assertTrue(all(point["count"] == 0 for point in response.data["growth"]))

    def test_dashboard_uses_actual_status_counts_and_excludes_deleted_customers(self):
        active = self.customer(expiration_date=self.today + timedelta(days=90))
        expiring_seven = self.customer(expiration_date=self.today + timedelta(days=7))
        expiring_thirty = self.customer(expiration_date=self.today + timedelta(days=30))
        expired = self.customer(
            start_date=self.today - timedelta(days=100), expiration_date=self.today - timedelta(days=1)
        )
        scheduled = self.customer(
            start_date=self.today + timedelta(days=1), expiration_date=self.today + timedelta(days=90)
        )
        deleted = self.customer(deleted_at=timezone.now())
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["metrics"],
            {
                "total_customers": 5,
                "active_services": 3,
                "expiring_services": 2,
                "expired_services": 1,
                "scheduled_services": 1,
                "active_administrators": 2,
                "expiring_7_days": 1,
            },
        )
        distribution = {item["status"]: item["count"] for item in response.data["distribution"]}
        self.assertEqual(distribution, {"active": 1, "expiring": 2, "expired": 1, "scheduled": 1})
        upcoming = [item["id"] for item in response.data["upcoming_expirations"]]
        self.assertEqual(upcoming, [expiring_seven.pk, expiring_thirty.pk])
        recent = [item["id"] for item in response.data["recent_customers"]]
        self.assertNotIn(deleted.pk, recent)
        self.assertCountEqual(
            recent, [active.pk, expiring_seven.pk, expiring_thirty.pk, expired.pk, scheduled.pk]
        )
        self.assertEqual(sum(point["count"] for point in response.data["growth"]), 5)

    def test_csv_export_applies_filters_and_neutralizes_spreadsheet_formulas(self):
        self.customer(
            name='=HYPERLINK("https://example.invalid")', manager_name="+formula", identifier="EXPORT01"
        )
        self.customer(name="مجموعه دیگر", identifier="EXPORT02")
        response = self.client.get("/api/customers/export/", {"search": "EXPORT01"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        raw = b"".join(response.streaming_content) if response.streaming else response.content
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 2)
        self.assertIn("EXPORT01", rows[1])
        self.assertNotIn("EXPORT02", raw.decode("utf-8-sig"))
        self.assertFalse(any(value.startswith(("=", "+", "-", "@")) for value in rows[1]))

    def test_operator_cannot_export_or_view_audit_log(self):
        self.client.force_authenticate(self.operator)
        self.assertEqual(self.client.get("/api/customers/export/").status_code, 403)
        self.assertEqual(self.client.get("/api/audit/").status_code, 403)

    def test_operator_dashboard_does_not_bypass_audit_permissions(self):
        self.client.post("/api/customers/", self.customer_data(), format="json")
        self.client.force_authenticate(self.operator)
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["recent_activities"], [])

    def test_audit_records_writes_without_recording_password_values(self):
        customer = self.client.post("/api/customers/", self.customer_data(), format="json")
        self.assertEqual(customer.status_code, 201)
        self.client.patch(
            f"/api/customers/{customer.data['id']}/", {"manager_name": "مدیر جدید"}, format="json"
        )
        sentinel = "NeverLogThis$Secret2026!"
        user = self.client.post(
            "/api/users/", {"username": "audit-user", "password": sentinel, "role": "operator"}, format="json"
        )
        self.assertEqual(user.status_code, 201, user.data)
        response = self.client.get("/api/audit/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response_rows(response)), 3)
        self.assertNotIn(sentinel, json.dumps(response.data))
        self.assertNotIn(User.objects.get(username="audit-user").password, json.dumps(response.data))

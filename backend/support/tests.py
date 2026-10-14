"""Conversation, authorization and recipient-isolation regression tests."""

from datetime import timedelta
from types import SimpleNamespace

from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient, APITestCase

from core.models import AuditLog, Customer, User
from core.serializers import UserSerializer
from portal.services import provision_portal

from .models import Message, Notification, StatusEvent, Ticket

PASSWORD = "TestingSupport$Mountain2026!"


class SupportTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.super_admin = User.objects.create_superuser(username="support.owner", password=PASSWORD)
        cls.staff = User.objects.create_user(
            username="support.staff", password=PASSWORD, role="admin", can_support=True
        )
        cls.admin = User.objects.create_user(username="ordinary.admin", password=PASSWORD, role="admin")
        cls.operator = User.objects.create_user(username="ordinary.operator", password=PASSWORD)
        cls.support_operator = User.objects.create_user(
            username="support.operator", password=PASSWORD, can_support=True
        )
        today = timezone.localdate()
        cls.a = Customer.objects.create(
            name="آفتاب",
            manager_name="سارا احمدی",
            phone="09123456789",
            slug="support-aftab",
            capacity=120,
            start_date=today - timedelta(days=20),
            expiration_date=today + timedelta(days=30),
        )
        cls.b = Customer.objects.create(
            name="دریا",
            manager_name="علی رضایی",
            phone="09351234567",
            slug="support-darya",
            capacity=80,
            start_date=today - timedelta(days=20),
            expiration_date=today + timedelta(days=90),
        )
        cls.owner = provision_portal(cls.a, {"login_username": "manager", "login_password": PASSWORD})
        cls.other = provision_portal(cls.b, {"login_username": "manager", "login_password": PASSWORD})

    def setUp(self):
        self.client.force_authenticate(self.owner)
        self.tenant = f"/api/organizations/{self.a.slug}/support/"
        self.central = "/api/support/"

    def create_ticket(self, user=None, organization=None, **changes):
        user = user or self.owner
        organization = organization or self.a
        self.client.force_authenticate(user)
        data = {
            "subject": "مشکل صفحه سالن",
            "category": "technical",
            "priority": "high",
            "description": "فهرست سالن باز نمی‌شود.",
        }
        data.update(changes)
        response = self.client.post(
            f"/api/organizations/{organization.slug}/support/tickets/", data, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def reply(self, ticket_id, user, body="پیام جدید"):
        self.client.force_authenticate(user)
        prefix = self.tenant if user.role == User.Role.TENANT else self.central
        return self.client.post(f"{prefix}tickets/{ticket_id}/messages/", {"body": body}, format="json")

    def transition(self, ticket_id, user, action):
        self.client.force_authenticate(user)
        prefix = self.tenant if user.role == User.Role.TENANT else self.central
        return self.client.post(f"{prefix}tickets/{ticket_id}/transition/", {"action": action}, format="json")

    def notifications(self, user):
        self.client.force_authenticate(user)
        prefix = self.tenant if user.role == User.Role.TENANT else self.central
        return self.client.get(prefix + "notifications/")

    def test_creation_owns_org_and_records_description_and_initial_history(self):
        ticket = self.create_ticket()
        self.assertEqual(ticket["organization"]["id"], self.a.pk)
        self.assertEqual(ticket["status"], "open")
        self.assertFalse(ticket["can_assign"])
        self.assertFalse(ticket["can_resolve"])
        self.assertTrue(ticket["can_reply"])
        message = Message.objects.get(ticket_id=ticket["id"])
        self.assertEqual(message.author, self.owner)
        self.assertEqual(message.body, "فهرست سالن باز نمی‌شود.")
        self.assertEqual(StatusEvent.objects.get(ticket_id=ticket["id"]).previous_status, "")
        self.assertTrue(
            AuditLog.objects.filter(
                action="support_create", entity_type="support_ticket", entity_id=str(ticket["id"])
            ).exists()
        )
        self.assertEqual(self.notifications(self.staff).data["unread_messages"], 1)
        self.assertEqual(self.notifications(self.owner).data["unread_messages"], 0)

    def test_creation_validates_content_choices_and_rejects_controlled_fields(self):
        valid = {"subject": "کمک", "category": "general", "description": "پرسش درباره حساب"}
        for changes in [
            {"subject": "   "},
            {"description": "\n "},
            {"category": "invented"},
            {"priority": "critical"},
            {"subject": "a" * 201},
            {"description": "a" * 10001},
            {"organization": self.b.pk},
            {"status": "closed"},
            {"created_by": self.other.pk},
            {"attachments": ["fake"]},
        ]:
            with self.subTest(changes=list(changes)):
                response = self.client.post(self.tenant + "tickets/", {**valid, **changes}, format="json")
                self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Ticket.objects.exists())
        self.assertFalse(Message.objects.exists())

    def test_only_tenant_owner_can_create_and_central_realm_cannot_create(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(self.central + "tickets/", {}, format="json").status_code, 403)
        self.assertEqual(self.client.get(self.tenant + "tickets/").status_code, 403)
        secondary = User.objects.create_user(
            username="secondary", role="tenant", organization=self.a, portal_username="secondary"
        )
        self.client.force_authenticate(secondary)
        self.assertEqual(self.client.get(self.tenant + "tickets/").status_code, 403)

    def test_ordinary_internal_staff_denied_and_explicit_operator_grant_allowed(self):
        self.create_ticket()
        for user in [self.admin, self.operator, self.owner]:
            self.client.force_authenticate(user)
            for resource in ["tickets/", "notifications/", "staff/"]:
                with self.subTest(user=user.username, resource=resource):
                    self.assertEqual(self.client.get(self.central + resource).status_code, 403)
        for user in [self.super_admin, self.staff, self.support_operator]:
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(self.central + "tickets/").status_code, 200)
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get(self.central + "tickets/").status_code, [401, 403])

    def test_revoked_permission_and_deactivated_accounts_cannot_use_stale_user(self):
        ticket = self.create_ticket()
        User.objects.filter(pk=self.staff.pk).update(can_support=False)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(self.central + "tickets/").status_code, 403)
        self.assertEqual(self.reply(ticket["id"], self.staff).status_code, 403)
        User.objects.filter(pk=self.owner.pk).update(is_active=False)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(self.tenant + "tickets/").status_code, 403)

    def test_deleted_organization_cannot_read_or_mutate_support(self):
        ticket = self.create_ticket()
        Customer.objects.filter(pk=self.a.pk).update(deleted_at=timezone.now())
        self.assertEqual(self.client.get(self.tenant + "tickets/").status_code, 403)
        self.assertEqual(self.reply(ticket["id"], self.owner).status_code, 403)
        self.client.force_authenticate(self.super_admin)
        self.assertEqual(self.client.get(f"{self.central}tickets/{ticket['id']}/").status_code, 200)

    def test_super_admin_only_grants_and_revokes_support_access(self):
        self.client.force_authenticate(self.super_admin)
        granted = self.client.patch(f"/api/users/{self.operator.pk}/", {"can_support": True}, format="json")
        self.assertEqual(granted.status_code, 200, granted.data)
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.can_support)
        audit = AuditLog.objects.filter(action="update_user", entity_id=str(self.operator.pk)).first()
        self.assertEqual(audit.changes["can_support"], {"before": False, "after": True})
        self.client.force_authenticate(self.admin)
        denied = self.client.patch(f"/api/users/{self.operator.pk}/", {"can_support": False}, format="json")
        self.assertEqual(denied.status_code, 400)
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.can_support)
        denied = self.client.post(
            "/api/users/",
            {"username": "forged-support", "role": "operator", "password": PASSWORD, "can_support": True},
            format="json",
        )
        self.assertEqual(denied.status_code, 400)
        self.assertFalse(User.objects.filter(username="forged-support").exists())
        denied_profile = self.client.patch("/api/auth/me/", {"can_support": True}, format="json")
        self.assertEqual(denied_profile.status_code, 400)

    def test_tenant_cannot_access_cross_org_ticket_and_notification_routes(self):
        own = self.create_ticket()
        other = self.create_ticket(user=self.other, organization=self.b, subject="خصوصی دریا")
        self.client.force_authenticate(self.owner)
        listing = self.client.get(self.tenant + "tickets/").data
        self.assertEqual([row["id"] for row in listing["results"]], [own["id"]])
        for suffix in ["", "messages/", "history/"]:
            self.assertEqual(self.client.get(f"{self.tenant}tickets/{other['id']}/{suffix}").status_code, 404)
        for suffix, payload in [
            ("messages/", {"body": "forged"}),
            ("transition/", {"action": "reopen"}),
            ("assign/", {"assigned_to": self.staff.pk}),
        ]:
            response = self.client.post(
                f"{self.tenant}tickets/{other['id']}/{suffix}", payload, format="json"
            )
            self.assertIn(response.status_code, [403, 404])
        self.assertEqual(
            self.client.get(f"/api/organizations/{self.b.slug}/support/tickets/").status_code, 403
        )
        self.assertEqual(
            self.client.post(
                self.tenant + "notifications/read/", {"ticket_id": other["id"]}, format="json"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(self.tenant + "tickets/", {"organization": self.b.pk}).data["count"], 0
        )
        self.assertEqual(self.client.get(self.tenant + "staff/").status_code, 403)

    def test_stale_super_admin_cannot_grant_after_demotion(self):
        User.objects.filter(pk=self.super_admin.pk).update(role="admin", is_superuser=False, is_staff=True)
        self.client.force_authenticate(self.super_admin)
        denied = self.client.patch(f"/api/users/{self.operator.pk}/", {"can_support": True}, format="json")
        self.assertEqual(denied.status_code, 400)
        self.operator.refresh_from_db()
        self.assertFalse(self.operator.can_support)

    def test_demotion_after_serializer_validation_prevents_permission_save(self):
        serializer = UserSerializer(
            self.operator,
            data={"can_support": True},
            partial=True,
            context={"request": SimpleNamespace(user=self.super_admin)},
        )
        serializer.is_valid(raise_exception=True)
        User.objects.filter(pk=self.super_admin.pk).update(role="admin", is_superuser=False, is_staff=True)
        with self.assertRaises(PermissionDenied):
            serializer.save()
        self.operator.refresh_from_db()
        self.assertFalse(self.operator.can_support)

    def test_replies_set_turn_and_chronological_history_preserves_author_snapshot(self):
        ticket = self.create_ticket()
        self.assertEqual(self.reply(ticket["id"], self.staff, "پاسخ پشتیبانی").status_code, 201)
        self.assertEqual(Ticket.objects.get(pk=ticket["id"]).status, "awaiting_customer")
        self.assertEqual(self.reply(ticket["id"], self.owner, "هنوز مشکل وجود دارد").status_code, 201)
        self.assertEqual(Ticket.objects.get(pk=ticket["id"]).status, "awaiting_support")
        messages = self.client.get(f"{self.tenant}tickets/{ticket['id']}/messages/").data["results"]
        self.assertEqual(
            [message["body"] for message in messages],
            ["فهرست سالن باز نمی‌شود.", "پاسخ پشتیبانی", "هنوز مشکل وجود دارد"],
        )
        self.assertEqual([message["is_mine"] for message in messages], [True, False, True])
        User.objects.filter(pk=self.staff.pk).update(username="renamed.support")
        self.assertEqual(
            Message.objects.get(ticket_id=ticket["id"], author=self.staff).author_name, "support.staff"
        )
        detail = self.client.get(f"{self.tenant}tickets/{ticket['id']}/").data
        self.assertEqual(
            [event["status"] for event in detail["status_history"]],
            ["open", "awaiting_customer", "awaiting_support"],
        )

    def test_lifecycle_requires_customer_confirmation_and_explicit_reopening(self):
        ticket = self.create_ticket()
        ticket_id = ticket["id"]
        self.assertEqual(self.transition(ticket_id, self.owner, "resolve").status_code, 403)
        self.assertEqual(self.transition(ticket_id, self.staff, "close").status_code, 403)
        self.assertEqual(self.transition(ticket_id, self.owner, "close").status_code, 400)
        self.assertEqual(self.transition(ticket_id, self.owner, "reopen").status_code, 400)
        resolved = self.transition(ticket_id, self.staff, "resolve")
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.data["status"], "resolved")
        self.assertFalse(resolved.data["can_reply"])
        self.assertEqual(self.transition(ticket_id, self.staff, "resolve").status_code, 400)
        self.assertEqual(self.transition(ticket_id, self.staff, "reopen").status_code, 403)
        for user in [self.owner, self.staff]:
            self.assertEqual(self.reply(ticket_id, user).status_code, 400)
        reopened = self.transition(ticket_id, self.owner, "reopen")
        self.assertEqual(reopened.data["status"], "awaiting_support")
        self.assertEqual(self.reply(ticket_id, self.owner, "درخواست بررسی دوباره").status_code, 201)
        self.assertEqual(self.transition(ticket_id, self.staff, "resolve").status_code, 200)
        closed = self.transition(ticket_id, self.owner, "close")
        self.assertEqual(closed.data["status"], "closed")
        self.assertFalse(closed.data["can_close"])
        self.assertTrue(closed.data["can_reopen"])
        self.assertEqual(self.reply(ticket_id, self.staff).status_code, 400)
        self.assertEqual(self.transition(ticket_id, self.owner, "reopen").data["status"], "awaiting_support")
        self.assertEqual(Message.objects.filter(ticket_id=ticket_id).count(), 2)

    def test_repeated_same_side_replies_do_not_duplicate_status_events(self):
        ticket = self.create_ticket()
        self.reply(ticket["id"], self.staff, "اول")
        self.reply(ticket["id"], self.staff, "دوم")
        self.assertEqual(StatusEvent.objects.filter(ticket_id=ticket["id"]).count(), 2)
        self.assertEqual(Message.objects.filter(ticket_id=ticket["id"]).count(), 3)

    def test_reply_rejects_blank_oversized_and_forged_author_or_ticket_fields(self):
        ticket = self.create_ticket()
        for payload in [
            {"body": " "},
            {"body": "x" * 10001},
            {"body": "hi", "author": self.staff.pk},
            {"body": "hi", "ticket": 999},
            {"body": "hi", "attachment": "file"},
        ]:
            response = self.client.post(
                f"{self.tenant}tickets/{ticket['id']}/messages/", payload, format="json"
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(Message.objects.count(), 1)

    def test_history_and_messages_cannot_be_overwritten_or_deleted_by_api(self):
        ticket = self.create_ticket()
        message = Message.objects.get(ticket_id=ticket["id"])
        for url in [
            f"{self.tenant}tickets/{ticket['id']}/",
            f"{self.tenant}tickets/{ticket['id']}/messages/{message.pk}/",
        ]:
            for method in [self.client.patch, self.client.delete]:
                self.assertIn(method(url, {"body": "forged"}, format="json").status_code, [404, 405])
        message.refresh_from_db()
        self.assertEqual(message.body, "فهرست سالن باز نمی‌شود.")

    def test_assignment_only_to_active_authorized_staff_and_idempotent_notifications(self):
        ticket = self.create_ticket()
        url = f"{self.central}tickets/{ticket['id']}/assign/"
        self.client.force_authenticate(self.super_admin)
        ids = {row["id"] for row in self.client.get(self.central + "staff/").data}
        self.assertEqual(ids, {self.super_admin.pk, self.staff.pk, self.support_operator.pk})
        for assigned_id in [self.admin.pk, self.operator.pk, self.owner.pk, 999999]:
            self.assertEqual(
                self.client.post(url, {"assigned_to": assigned_id}, format="json").status_code, 400
            )
        assigned = self.client.post(url, {"assigned_to": self.staff.pk}, format="json")
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.data["assigned_to"]["id"], self.staff.pk)
        count = Notification.objects.filter(kind="assignment").count()
        self.assertEqual(
            self.client.post(url, {"assigned_to": self.staff.pk}, format="json").status_code, 200
        )
        self.assertEqual(Notification.objects.filter(kind="assignment").count(), count)
        self.assertEqual(
            self.client.post(url, {"assigned_to": None}, format="json").data["assigned_to"], None
        )
        User.objects.filter(pk=self.staff.pk).update(is_active=False)
        self.assertEqual(
            self.client.post(url, {"assigned_to": self.staff.pk}, format="json").status_code, 400
        )

    def test_recipient_read_status_is_independent_and_notification_polling_never_duplicates(self):
        ticket = self.create_ticket()
        staff_before = self.notifications(self.staff).data
        self.assertEqual(staff_before["unread_messages"], 1)
        count = Notification.objects.count()
        for _ in range(3):
            self.assertEqual(self.notifications(self.staff).data["unread_messages"], 1)
        self.assertEqual(Notification.objects.count(), count)
        read = self.client.post(
            self.central + "notifications/read/", {"ticket_id": ticket["id"]}, format="json"
        )
        self.assertEqual(read.data["updated"], 1)
        self.assertEqual(self.notifications(self.staff).data["unread_messages"], 0)
        self.assertTrue(self.notifications(self.staff).data["items"][0]["is_read"])
        self.assertEqual(self.notifications(self.super_admin).data["unread_messages"], 1)
        self.assertEqual(self.notifications(self.support_operator).data["unread_messages"], 1)

    def test_notification_ids_cannot_mark_another_recipient_read(self):
        self.create_ticket()
        owner_event = Notification.objects.filter(recipient=self.super_admin).get()
        own_event = Notification.objects.filter(recipient=self.staff).get()
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            self.central + "notifications/read/", {"ids": [owner_event.pk, own_event.pk]}, format="json"
        )
        self.assertEqual(response.data["updated"], 1)
        owner_event.refresh_from_db()
        self.assertIsNone(owner_event.read_at)
        response = self.client.post(
            self.central + "notifications/read/", {"ids": [own_event.pk]}, format="json"
        )
        self.assertEqual(response.data["updated"], 0)
        for data in [{}, {"ids": [], "ticket_id": 1}, {"ids": [0]}, {"all": True}]:
            self.assertEqual(
                self.client.post(self.central + "notifications/read/", data, format="json").status_code, 400
            )

    def test_paginated_message_reads_only_mark_visible_page_and_leave_status_unread(self):
        ticket = self.create_ticket()
        self.reply(ticket["id"], self.staff, "پاسخ یک")
        self.reply(ticket["id"], self.staff, "پاسخ دو")
        self.assertEqual(self.notifications(self.owner).data["unread_messages"], 2)
        messages = self.client.get(
            f"{self.tenant}tickets/{ticket['id']}/messages/", {"page_size": 1, "page": 2}
        )
        self.assertEqual(messages.data["count"], 3)
        self.assertEqual(messages.data["results"][0]["body"], "پاسخ یک")
        self.assertEqual(self.notifications(self.owner).data["unread_messages"], 1)
        self.assertEqual(self.notifications(self.owner).data["unread_count"], 2)
        self.client.post(self.tenant + "notifications/read/", {"ticket_id": ticket["id"]}, format="json")
        self.assertEqual(self.notifications(self.owner).data["unread_count"], 0)

    def test_list_unread_count_matches_requester_and_real_dashboard_counts(self):
        ticket = self.create_ticket()
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(self.central + "tickets/").data["results"][0]["unread_count"], 1)
        self.client.get(f"{self.central}tickets/{ticket['id']}/messages/")
        self.assertEqual(self.client.get(self.central + "tickets/").data["results"][0]["unread_count"], 0)
        self.reply(ticket["id"], self.staff, "راه حل")
        data = self.notifications(self.owner).data
        self.assertEqual(
            (
                data["open_tickets"],
                data["awaiting_support"],
                data["awaiting_customer"],
                data["unread_messages"],
            ),
            (1, 0, 1, 1),
        )
        self.transition(ticket["id"], self.staff, "resolve")
        data = self.notifications(self.owner).data
        self.assertEqual((data["open_tickets"], data["awaiting_customer"]), (0, 0))
        self.assertTrue(any(item["kind"] == "status" for item in data["items"]))

    def test_latest_message_page_and_status_reads_keep_hidden_messages_unread(self):
        ticket = self.create_ticket()
        for index in range(25):
            self.assertEqual(self.reply(ticket["id"], self.staff, f"پاسخ {index}").status_code, 201)
        self.client.force_authenticate(self.owner)
        page = self.client.get(f"{self.tenant}tickets/{ticket['id']}/messages/", {"ordering": "-created_at"})
        self.assertEqual(page.data["count"], 26)
        self.assertEqual(page.data["results"][0]["body"], "پاسخ 24")
        self.assertEqual(len(page.data["results"]), 20)
        self.assertEqual(self.notifications(self.owner).data["unread_messages"], 5)
        response = self.client.post(
            self.tenant + "notifications/read/",
            {"ticket_id": ticket["id"], "include_messages": False},
            format="json",
        )
        self.assertEqual(response.data["updated"], 1)
        self.assertEqual(self.notifications(self.owner).data["unread_count"], 5)
        self.assertEqual(self.notifications(self.super_admin).data["unread_messages"], 1)
        self.assertEqual(
            self.client.get(
                f"{self.central}tickets/{ticket['id']}/messages/", {"ordering": "body"}
            ).status_code,
            400,
        )

    def test_search_filters_dates_recent_order_and_pagination_remain_tenant_scoped(self):
        first = self.create_ticket(
            subject="حساب قدیمی", category="account", priority="low", description="عبارت ویژه تاریخچه"
        )
        second = self.create_ticket(subject="مسئله جدید", priority="urgent")
        third = self.create_ticket(user=self.other, organization=self.b, subject="حساب دریا")
        Ticket.objects.filter(pk=first["id"]).update(
            created_at=timezone.now() - timedelta(days=10), updated_at=timezone.now() - timedelta(days=10)
        )
        self.client.force_authenticate(self.staff)
        self.assertEqual(
            [row["id"] for row in self.client.get(self.central + "tickets/").data["results"]],
            [third["id"], second["id"], first["id"]],
        )
        filters_and_expected = [
            ({"search": f"#{first['id']}"}, [first["id"]]),
            (
                {"search": str(second["id"]).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))},
                [second["id"]],
            ),
            ({"search": "ویژه تاریخچه"}, [first["id"]]),
            ({"organization": self.a.pk, "priority": "urgent"}, [second["id"]]),
            ({"organization": self.b.slug}, [third["id"]]),
            (
                {
                    "date_from": timezone.localdate().isoformat(),
                    "date_to": timezone.localdate().isoformat(),
                    "organization": self.a.pk,
                },
                [second["id"]],
            ),
            ({"date_to": (timezone.localdate() - timedelta(days=5)).isoformat()}, [first["id"]]),
        ]
        for filters, expected in filters_and_expected:
            with self.subTest(filters=filters):
                response = self.client.get(self.central + "tickets/", filters)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual([row["id"] for row in response.data["results"]], expected)
        page = self.client.get(self.central + "tickets/", {"page_size": 1, "page": 2}).data
        self.assertEqual(page["count"], 3)
        self.assertEqual(page["results"][0]["id"], second["id"])
        for filters in [
            {"status": "bad"},
            {"priority": "bad"},
            {"date_from": "yesterday"},
            {"date_from": "2026-10-10", "date_to": "2026-10-01"},
        ]:
            self.assertEqual(self.client.get(self.central + "tickets/", filters).status_code, 400)

    def test_ticket_list_uses_constant_queries_and_notification_items_are_bounded(self):
        self.create_ticket()
        self.client.force_authenticate(self.staff)
        with CaptureQueriesContext(connection) as initial_queries:
            self.client.get(self.central + "tickets/")
        for index in range(25):
            self.create_ticket(subject=f"درخواست {index}")
        self.client.force_authenticate(self.staff)
        with CaptureQueriesContext(connection) as many_queries:
            response = self.client.get(self.central + "tickets/")
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(many_queries), len(initial_queries) + 1)
        notifications = self.notifications(self.staff).data
        self.assertEqual(len(notifications["items"]), 20)
        self.assertEqual(notifications["unread_messages"], 26)

    def test_older_unread_notification_remains_visible_after_newer_twenty_are_read(self):
        oldest = self.create_ticket(subject="درخواست قدیمی خوانده‌نشده")
        for index in range(20):
            self.create_ticket(subject=f"درخواست جدید {index}")
        Notification.objects.filter(recipient=self.staff).exclude(ticket_id=oldest["id"]).update(
            read_at=timezone.now()
        )
        data = self.notifications(self.staff).data
        self.assertEqual(data["unread_messages"], 1)
        self.assertEqual(len(data["items"]), 20)
        self.assertEqual(data["items"][0]["ticket_id"], oldest["id"])
        self.assertFalse(data["items"][0]["is_read"])
        response = self.client.post(
            self.central + "notifications/read/", {"ids": [data["items"][0]["id"]]}, format="json"
        )
        self.assertEqual(response.data["updated"], 1)
        self.assertEqual(self.notifications(self.staff).data["unread_count"], 0)

    def test_detail_history_is_bounded_and_all_older_events_are_paginated(self):
        ticket = self.create_ticket()
        StatusEvent.objects.bulk_create(
            [
                StatusEvent(
                    ticket_id=ticket["id"],
                    actor=self.owner,
                    actor_name="manager",
                    previous_status="resolved" if index % 2 else "awaiting_support",
                    status="awaiting_support" if index % 2 else "resolved",
                )
                for index in range(120)
            ]
        )
        all_ids = list(StatusEvent.objects.filter(ticket_id=ticket["id"]).values_list("pk", flat=True))
        detail = self.client.get(f"{self.tenant}tickets/{ticket['id']}/").data
        self.assertEqual(detail["status_history_count"], 121)
        self.assertEqual([event["id"] for event in detail["status_history"]], all_ids[-50:])
        history_ids = []
        for page in [1, 2, 3]:
            history = self.client.get(
                f"{self.tenant}tickets/{ticket['id']}/history/", {"page": page, "page_size": 50}
            )
            self.assertEqual(history.data["count"], 121)
            self.assertLessEqual(len(history.data["results"]), 50)
            history_ids.extend(event["id"] for event in history.data["results"])
        self.assertEqual(history_ids, list(reversed(all_ids)))

    def test_unanswered_and_unread_filters_include_new_tickets_and_use_own_recipient_state(self):
        first = self.create_ticket(subject="پرسش تازه")
        second = self.create_ticket(subject="پاسخ داده‌شده")
        self.reply(second["id"], self.staff, "پاسخ پشتیبانی")
        self.client.force_authenticate(self.staff)
        unanswered = self.client.get(self.central + "tickets/", {"unanswered": "true"})
        self.assertEqual([row["id"] for row in unanswered.data["results"]], [first["id"]])
        answered = self.client.get(self.central + "tickets/", {"unanswered": "false"})
        self.assertEqual([row["id"] for row in answered.data["results"]], [second["id"]])
        self.client.get(f"{self.central}tickets/{first['id']}/messages/")
        unread = self.client.get(self.central + "tickets/", {"unread": "true"})
        self.assertEqual([row["id"] for row in unread.data["results"]], [second["id"]])
        self.client.force_authenticate(self.super_admin)
        self.assertEqual(self.client.get(self.central + "tickets/", {"unread": "true"}).data["count"], 2)
        self.client.force_authenticate(self.owner)
        unread = self.client.get(self.tenant + "tickets/", {"unread": "true"})
        self.assertEqual([row["id"] for row in unread.data["results"]], [second["id"]])
        for filters in [{"unread": "yes"}, {"unanswered": "1"}]:
            self.assertEqual(self.client.get(self.tenant + "tickets/", filters).status_code, 400)

    def test_database_rejects_unknown_status_and_duplicate_recipient_message(self):
        ticket = self.create_ticket()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Ticket.objects.filter(pk=ticket["id"]).update(status="forged")
        event = Notification.objects.filter(recipient=self.staff).get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notification.objects.create(
                recipient=self.staff,
                ticket=event.ticket,
                message=event.message,
                kind="message",
                body="duplicate",
            )

    def test_deleted_support_author_keeps_conversation_and_status_history(self):
        ticket = self.create_ticket()
        self.reply(ticket["id"], self.support_operator, "پاسخ ثبت‌شده")
        self.support_operator.delete()
        message = Message.objects.filter(ticket_id=ticket["id"]).last()
        self.assertIsNone(message.author_id)
        self.assertEqual(message.author_name, "support.operator")
        history = StatusEvent.objects.filter(ticket_id=ticket["id"]).last()
        self.assertIsNone(history.actor_id)
        self.assertEqual(history.actor_name, "support.operator")

    def test_real_session_writes_require_csrf_for_both_realms(self):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get("/api/auth/csrf/").data["csrfToken"]
        login = client.post(
            f"/api/organizations/{self.a.slug}/login/",
            {"username": "manager", "password": PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(login.status_code, 200)
        data = {"subject": "کمک", "category": "general", "description": "پرسش"}
        self.assertEqual(client.post(self.tenant + "tickets/", data, format="json").status_code, 403)
        token = client.get("/api/auth/csrf/").data["csrfToken"]
        created = client.post(self.tenant + "tickets/", data, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(created.status_code, 201)
        central = APIClient(enforce_csrf_checks=True)
        token = central.get("/api/auth/csrf/").data["csrfToken"]
        login = central.post(
            "/api/auth/login/",
            {"username": "support.owner", "password": PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(
            central.post(
                f"{self.central}tickets/{created.data['id']}/messages/", {"body": "پاسخ"}, format="json"
            ).status_code,
            403,
        )

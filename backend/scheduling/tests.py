"""Real tenant boundaries, conflict acknowledgements and calendar-safe proposals."""

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

import jdatetime
from django.conf import settings
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from core.models import Customer, User
from operations.models import Hall, Supervisor, SupervisorHall
from portal.services import provision_portal
from staff.models import SupervisorAccount

from .models import ScheduleAssignment, ScheduleAudit, WorkShift
from .services import apply_preview, copy_preview


class SchedulingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Customer.objects.create(
            name="دماوند",
            manager_name="مدیر",
            phone="09123456789",
            slug="damavand",
            capacity=100,
            start_date="2020-01-01",
            expiration_date="2020-12-31",
        )
        cls.foreign = Customer.objects.create(
            name="بیگانه",
            manager_name="مدیر",
            phone="09123456789",
            slug="foreign",
            capacity=100,
            start_date="2020-01-01",
            expiration_date="2020-12-31",
        )
        cls.manager = provision_portal(
            cls.organization, {"login_username": "manager", "login_password": "Testing$Only2026!"}
        )
        cls.other_manager = provision_portal(
            cls.foreign, {"login_username": "manager", "login_password": "Testing$Only2026!"}
        )
        cls.hall = Hall.objects.create(organization=cls.organization, name="سپید")
        cls.second_hall = Hall.objects.create(organization=cls.organization, name="سبز")
        cls.foreign_hall = Hall.objects.create(organization=cls.foreign, name="دیگر")
        cls.supervisor = Supervisor.objects.create(
            organization=cls.organization, first_name="سارا", last_name="محمدی", phone="09123456789"
        )
        cls.second_supervisor = Supervisor.objects.create(
            organization=cls.organization, first_name="علی", last_name="امیری", phone="09123456780"
        )
        cls.unassigned = Supervisor.objects.create(
            organization=cls.organization, first_name="بهنام", last_name="آرام", phone="09123456781"
        )
        for supervisor in (cls.supervisor, cls.second_supervisor):
            supervisor.halls.add(cls.hall, cls.second_hall)
        cls.shift = WorkShift.objects.create(
            organization=cls.organization, name="صبح", start_time="08:00", end_time="12:00"
        )
        cls.overlap_shift = WorkShift.objects.create(
            organization=cls.organization, name="میانه", start_time="10:00", end_time="14:00"
        )
        cls.later_shift = WorkShift.objects.create(
            organization=cls.organization, name="عصر", start_time="12:00", end_time="16:00"
        )
        cls.foreign_shift = WorkShift.objects.create(
            organization=cls.foreign, name="دیگر", start_time="08:00", end_time="12:00"
        )
        cls.week = date(2026, 10, 17)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.manager)
        self.base = "/api/organizations/damavand/"

    def post(self, path, data):
        return self.client.post(self.base + path, data, format="json")

    def spec(self, **values):
        return {
            "date": str(self.week),
            "hall": self.hall.pk,
            "shift": self.shift.pk,
            "supervisor": self.supervisor.pk,
            **values,
        }

    def preview(self, specs=None, removes=None):
        response = self.post(
            "schedule/preview/",
            {"assignments": specs if specs is not None else [self.spec()], "remove_ids": removes or []},
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def apply(self, preview, actions=None, **values):
        return self.post(
            "schedule/apply/",
            {
                "token": preview["token"],
                "actions": actions
                if actions is not None
                else [{"index": row["index"], "action": row["default_action"]} for row in preview["rows"]],
                **values,
            },
        )

    def create_assignment(self, **values):
        response = self.apply(self.preview([self.spec(**values)]))
        self.assertEqual(response.status_code, 200, response.data)
        return ScheduleAssignment.objects.get(pk=response.data["assignments"][-1]["id"])

    def test_work_shift_crud_same_day_validation_archive_restore(self):
        created = self.post("work-shifts/", {"name": "پایان روز", "start_time": "17:00", "end_time": "20:00"})
        self.assertEqual(created.status_code, 201, created.data)
        pk = created.data["id"]
        for start, end in [("08:00", "08:00"), ("22:00", "02:00"), ("26:00", "27:00")]:
            self.assertEqual(
                self.post(
                    "work-shifts/", {"name": "نامعتبر", "start_time": start, "end_time": end}
                ).status_code,
                400,
            )
        invalid = self.client.patch(self.base + f"work-shifts/{pk}/", {"end_time": "16:00"}, format="json")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(self.client.delete(self.base + f"work-shifts/{pk}/").status_code, 204)
        self.assertFalse(WorkShift.objects.get(pk=pk).is_active)
        self.assertEqual(self.post(f"work-shifts/{pk}/restore/", {}).status_code, 200)
        self.assertTrue(ScheduleAudit.objects.filter(action="update_shift").exists())

    def test_work_shift_database_time_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            WorkShift.objects.create(
                organization=self.organization, name="نامعتبر", start_time="23:00", end_time="01:00"
            )

    def test_shift_change_preserves_committed_interval(self):
        row = self.create_assignment()
        response = self.client.patch(
            self.base + f"work-shifts/{self.shift.pk}/",
            {"start_time": "09:00", "end_time": "13:00"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(str(row.start_time), "08:00:00")
        self.assertEqual(str(row.end_time), "12:00:00")

    def test_refreshing_existing_snapshot_previews_and_confirms_new_conflict(self):
        old = self.create_assignment()
        self.create_assignment(shift=self.later_shift.pk)
        self.shift.end_time = "13:00"
        self.shift.save()
        preview = self.preview()
        self.assertEqual(preview["rows"][0]["status"], "existing")
        self.assertEqual(len(preview["conflicts"]), 1)
        actions = [{"index": 0, "action": "replace", "replace_ids": [old.pk]}]
        self.assertEqual(self.apply(preview, actions).status_code, 400)
        response = self.apply(
            preview, actions, confirm_conflicts=True, override_reason="تغییر ساعت با اطلاع مدیر"
        )
        self.assertEqual(response.status_code, 200, response.data)
        refreshed = ScheduleAssignment.objects.get(shift=self.shift)
        self.assertEqual(str(refreshed.end_time), "13:00:00")
        self.assertTrue(refreshed.conflict_override)

    def test_optional_removal_conflicts_are_visible_and_only_surviving_conflicts_need_confirmation(self):
        old = self.create_assignment()
        preview = self.preview([self.spec(shift=self.overlap_shift.pk)], [old.pk])
        self.assertEqual(len(preview["conflicts"]), 1)
        self.assertTrue(preview["conflicts"][0]["resolved_by_removal"])
        # Choosing to keep the old row leaves the conflict and still needs consent.
        self.assertEqual(self.apply(preview).status_code, 400)
        # Explicit deletion resolves it; no override is required for the final state.
        response = self.apply(preview, remove_ids=[old.pk])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(ScheduleAssignment.objects.get().conflict_override)

    def test_week_matrix_multi_supervisors_and_jalali_dates(self):
        preview = self.preview([self.spec(), self.spec(supervisor=self.second_supervisor.pk)])
        self.assertEqual(self.apply(preview).data["added"], 2)
        response = self.client.get(self.base + f"schedule/?week_start={self.week}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["assignments"]), 2)
        self.assertEqual(len(response.data["days"]), 7)
        self.assertEqual(response.data["days"][0]["weekday"], 0)
        self.assertEqual(
            response.data["days"][0]["jalali_date"], jdatetime.date.fromgregorian(date=self.week).isoformat()
        )
        person = next(item for item in response.data["supervisors"] if item["id"] == self.supervisor.pk)
        self.assertEqual(set(person["halls"]), {self.hall.pk, self.second_hall.pk})
        self.assertEqual(self.client.get(self.base + "schedule/?week_start=2026-10-18").status_code, 400)

    def test_only_authorized_active_personnel_halls_and_shifts_can_be_added(self):
        preview = self.preview([self.spec(supervisor=self.unassigned.pk)])
        self.assertEqual(preview["rows"][0]["status"], "invalid")
        self.assertEqual(self.apply(preview, [{"index": 0, "action": "add"}]).status_code, 400)
        self.shift.is_active = False
        self.shift.save()
        self.assertEqual(self.preview()["rows"][0]["status"], "invalid")
        self.assertFalse(ScheduleAssignment.objects.exists())

    def test_cross_tenant_refs_and_routes_are_rejected(self):
        for spec in [self.spec(hall=self.foreign_hall.pk), self.spec(shift=self.foreign_shift.pk)]:
            self.assertEqual(self.post("schedule/preview/", {"assignments": [spec]}).status_code, 400)
        self.assertEqual(
            self.client.get(self.base + f"work-shifts/{self.foreign_shift.pk}/").status_code, 404
        )
        self.assertEqual(
            self.client.get(self.base + f"schedule/?hall={self.foreign_hall.pk}").status_code, 400
        )
        self.client.force_authenticate(self.other_manager)
        self.assertEqual(self.client.get(self.base + "schedule/").status_code, 403)

    def test_same_hall_and_cross_hall_overlap_require_explicit_confirmation_and_reason(self):
        self.create_assignment()
        for hall in (self.hall, self.second_hall):
            preview = self.preview([self.spec(hall=hall.pk, shift=self.overlap_shift.pk)])
            self.assertEqual(len(preview["conflicts"]), 1)
            self.assertEqual(preview["conflicts"][0]["start_time"], "10:00:00")
            self.assertEqual(self.apply(preview).status_code, 400)
            self.assertEqual(self.apply(preview, confirm_conflicts=True).status_code, 400)
        response = self.apply(preview, confirm_conflicts=True, override_reason="پوشش هم‌زمان با اطلاع مدیر")
        self.assertEqual(response.status_code, 200, response.data)
        row = ScheduleAssignment.objects.get(hall=self.second_hall)
        self.assertTrue(row.conflict_override)
        audit = ScheduleAudit.objects.filter(reason="پوشش هم‌زمان با اطلاع مدیر").get()
        self.assertEqual(audit.actor, self.manager)
        self.assertEqual(len(audit.changes["conflicts"]), 1)

    def test_adjacent_shifts_and_different_supervisors_do_not_conflict(self):
        self.create_assignment()
        preview = self.preview(
            [
                self.spec(shift=self.later_shift.pk),
                self.spec(shift=self.overlap_shift.pk, supervisor=self.second_supervisor.pk),
            ]
        )
        self.assertEqual(preview["conflicts"], [])
        self.assertEqual(self.apply(preview).data["added"], 2)

    def test_overlaps_between_proposed_rows_are_detected(self):
        preview = self.preview(
            [self.spec(), self.spec(hall=self.second_hall.pk, shift=self.overlap_shift.pk)]
        )
        self.assertEqual(len(preview["conflicts"]), 1)
        self.assertEqual(self.apply(preview).status_code, 400)
        self.assertEqual(
            self.apply(preview, confirm_conflicts=True, override_reason="استثنا").data["added"], 2
        )
        self.assertEqual(ScheduleAssignment.objects.filter(conflict_override=True).count(), 2)

    def test_duplicate_proposal_and_existing_assignment_never_insert_duplicate(self):
        preview = self.preview([self.spec(), self.spec()])
        self.assertEqual(preview["rows"][1]["status"], "duplicate")
        bad = self.apply(preview, [{"index": 0, "action": "add"}, {"index": 1, "action": "add"}])
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.apply(preview).data["added"], 1)
        again = self.preview()
        self.assertEqual(again["rows"][0]["status"], "existing")
        self.assertEqual(self.apply(again).data["preserved"], 1)
        self.assertEqual(self.apply(again, [{"index": 0, "action": "add"}]).status_code, 400)
        self.assertEqual(ScheduleAssignment.objects.count(), 1)

    def test_database_duplicate_constraint(self):
        row = self.create_assignment()
        row.pk = None
        with self.assertRaises(IntegrityError), transaction.atomic():
            row.save()

    def test_cell_batch_remove_and_add_are_explicit_and_atomic(self):
        old = self.create_assignment()
        preview = self.preview([self.spec(supervisor=self.second_supervisor.pk)], [old.pk])
        # Omitted remove_ids cannot delete even though included in preview.
        result = self.apply(preview)
        self.assertEqual(result.data["removed"], 0)
        self.assertTrue(ScheduleAssignment.objects.filter(pk=old.pk).exists())
        preview = self.preview([], [old.pk])
        self.assertEqual(self.apply(preview, remove_ids=[old.pk]).data["removed"], 1)
        self.assertTrue(ScheduleAudit.objects.filter(changes__removed__0__id=old.pk).exists())

    def test_selective_replace_ids_preserves_other_supervisors(self):
        old = self.create_assignment()
        second = self.create_assignment(supervisor=self.second_supervisor.pk)
        self.unassigned.halls.add(self.hall)
        preview = self.preview([self.spec(supervisor=self.unassigned.pk)])
        self.assertEqual(set(preview["rows"][0]["existing_ids"]), {old.pk, second.pk})
        response = self.apply(preview, [{"index": 0, "action": "replace", "replace_ids": [old.pk]}])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(ScheduleAssignment.objects.filter(pk=old.pk).exists())
        self.assertTrue(ScheduleAssignment.objects.filter(pk=second.pk).exists())

    def test_preserve_and_replace_same_record_is_rejected(self):
        old = self.create_assignment()
        preview = self.preview([self.spec(), self.spec(supervisor=self.second_supervisor.pk)])
        response = self.apply(
            preview,
            [{"index": 0, "action": "preserve"}, {"index": 1, "action": "replace", "replace_ids": [old.pk]}],
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(ScheduleAssignment.objects.filter(pk=old.pk).exists())

    def test_unpreviewed_removal_and_wrong_replacement_scope_are_rejected(self):
        old = self.create_assignment()
        preview = self.preview([self.spec(supervisor=self.second_supervisor.pk)])
        self.assertEqual(self.apply(preview, remove_ids=[old.pk]).status_code, 400)
        self.assertEqual(
            self.apply(preview, [{"index": 0, "action": "replace", "replace_ids": [999999]}]).status_code, 400
        )
        self.assertEqual(self.apply(preview, [{"index": 0, "action": "replace"}]).status_code, 400)

    def test_stale_preview_cannot_overwrite_new_schedule(self):
        first, second = self.preview(), self.preview()
        self.assertEqual(self.apply(first).status_code, 200)
        self.assertEqual(self.apply(second).status_code, 409)
        self.assertEqual(ScheduleAssignment.objects.count(), 1)

    def test_changed_shift_or_hall_permissions_invalidates_preview(self):
        preview = self.preview()
        SupervisorHall.objects.filter(supervisor=self.supervisor, hall=self.hall).delete()
        self.assertEqual(self.apply(preview).status_code, 409)
        self.supervisor.halls.add(self.hall)
        preview = self.preview()
        self.shift.end_time = "13:00"
        self.shift.save()
        self.assertEqual(self.apply(preview).status_code, 409)

    def test_token_tampering_actor_binding_and_live_manager_status(self):
        preview = self.preview()
        self.assertEqual(self.apply({**preview, "token": preview["token"] + "x"}).status_code, 409)
        self.client.force_authenticate(self.other_manager)
        response = self.client.post(
            "/api/organizations/foreign/schedule/apply/",
            {"token": preview["token"], "actions": [{"index": 0, "action": "add"}]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        # Direct service call tests a request whose manager was revoked while in flight.
        User.objects.filter(pk=self.manager.pk).update(is_active=False)
        from rest_framework.exceptions import PermissionDenied

        with self.assertRaises(PermissionDenied):
            apply_preview(
                self.organization,
                self.manager,
                {
                    "token": preview["token"],
                    "actions": [],
                    "remove_ids": [],
                    "confirm_conflicts": False,
                    "override_reason": "",
                },
            )

    def test_week_copy_preview_selective_preserve_and_skip(self):
        self.create_assignment()
        self.create_assignment(date=str(self.week + timedelta(days=2)), supervisor=self.second_supervisor.pk)
        target = self.week + timedelta(days=7)
        existing = self.create_assignment(date=str(target))
        preview = self.post(
            "schedule/copy-preview/",
            {"mode": "week", "source_week": str(self.week), "target_week": str(target)},
        )
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual([row["status"] for row in preview.data["rows"]], ["existing", "new"])
        response = self.apply(
            preview.data, [{"index": 0, "action": "preserve"}, {"index": 1, "action": "skip"}]
        )
        self.assertEqual(response.data["added"], 0)
        self.assertTrue(ScheduleAssignment.objects.filter(pk=existing.pk).exists())

    def test_copy_source_change_invalidates_already_signed_preview(self):
        self.create_assignment()
        preview = self.post(
            "schedule/copy-preview/",
            {
                "mode": "week",
                "source_week": str(self.week),
                "target_week": str(self.week + timedelta(days=7)),
            },
        ).data
        self.create_assignment(supervisor=self.second_supervisor.pk)
        self.assertEqual(self.apply(preview).status_code, 409)

    def test_month_copy_exact_jalali_leap_and_nonleap_partial_weeks(self):
        for offset in range(7):
            self.create_assignment(date=str(self.week + timedelta(days=offset)))
        for year, month, expected in [(1403, 12, 30), (1404, 12, 29), (1405, 1, 31), (1405, 7, 30)]:
            with self.subTest(year=year, month=month):
                response = self.post(
                    "schedule/copy-preview/",
                    {
                        "mode": "month",
                        "source_week": str(self.week),
                        "jalali_year": year,
                        "jalali_month": month,
                    },
                )
                self.assertEqual(response.status_code, 200, response.data)
                dates = [date.fromisoformat(row["date"]) for row in response.data["rows"]]
                self.assertEqual(len(dates), expected)
                self.assertTrue(
                    all(
                        (
                            jdatetime.date.fromgregorian(date=d).year,
                            jdatetime.date.fromgregorian(date=d).month,
                        )
                        == (year, month)
                        for d in dates
                    )
                )
                self.assertEqual(dates[0], jdatetime.date(year, month, 1).togregorian())
                self.assertEqual(jdatetime.date.fromgregorian(date=dates[-1]).day, expected)

    def test_month_copy_preserves_weekday_and_does_not_touch_boundary_days(self):
        self.create_assignment(date=str(self.week + timedelta(days=6)))  # Friday only.
        response = self.post(
            "schedule/copy-preview/",
            {"mode": "month", "source_week": str(self.week), "jalali_year": 1403, "jalali_month": 12},
        )
        self.assertEqual(response.status_code, 200)
        rows = response.data["rows"]
        self.assertTrue(all(date.fromisoformat(row["date"]).weekday() == 4 for row in rows))
        self.assertEqual(self.apply(response.data).data["added"], len(rows))
        target_rows = ScheduleAssignment.objects.exclude(date=self.week + timedelta(days=6))
        self.assertTrue(all(jdatetime.date.fromgregorian(date=row.date).month == 12 for row in target_rows))

    def test_copy_preview_shows_shift_snapshot_differences_and_invalid_grants(self):
        self.create_assignment()
        self.shift.start_time = "09:00"
        self.shift.save()
        preview = copy_preview(
            self.organization,
            self.manager,
            {"mode": "week", "source_week": self.week, "target_week": self.week + timedelta(days=7)},
        )
        self.assertTrue(preview["rows"][0]["times_changed"])
        self.assertEqual(preview["rows"][0]["source_start_time"], "08:00:00")
        SupervisorHall.objects.filter(supervisor=self.supervisor, hall=self.hall).delete()
        preview = copy_preview(
            self.organization,
            self.manager,
            {"mode": "week", "source_week": self.week, "target_week": self.week + timedelta(days=7)},
        )
        self.assertEqual(preview["rows"][0]["status"], "invalid")

    def test_supervisor_reads_only_own_assignments_current_authorized_halls(self):
        self.create_assignment()
        self.create_assignment(supervisor=self.second_supervisor.pk)
        account = SupervisorAccount.objects.create_user(
            supervisor=self.supervisor, password="Testing$Only2026!"
        )
        self.client.force_authenticate(account)
        response = self.client.get(self.base + f"supervisor/schedule/?week_start={self.week}")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["assignments"]), 1)
        self.assertEqual(response.data["assignments"][0]["supervisor"], self.supervisor.pk)
        self.assertEqual(self.client.get(self.base + "schedule/").status_code, 403)
        self.assertEqual(
            self.post("work-shifts/", {"name": "رد", "start_time": "07:00", "end_time": "08:00"}).status_code,
            403,
        )
        SupervisorHall.objects.filter(supervisor=self.supervisor, hall=self.hall).delete()
        self.assertEqual(
            self.client.get(self.base + f"supervisor/schedule/?week_start={self.week}").data["assignments"],
            [],
        )
        self.assertEqual(
            self.client.get(self.base + f"supervisor/schedule/?hall={self.hall.pk}").status_code, 400
        )

    def test_expired_subscription_warns_but_does_not_block_scheduling(self):
        self.assertEqual(self.organization.status, "expired")
        self.assertEqual(self.apply(self.preview()).status_code, 200)

    def test_preview_size_and_action_shape_validation(self):
        self.assertEqual(
            self.post("schedule/preview/", {"assignments": [self.spec()] * 5001}).status_code, 400
        )
        preview = self.preview()
        self.assertEqual(
            self.apply(preview, [{"index": 0, "action": "add"}, {"index": 0, "action": "skip"}]).status_code,
            400,
        )
        self.assertEqual(self.apply(preview, [{"index": 99, "action": "skip"}]).status_code, 400)
        self.assertEqual(
            self.post(
                "schedule/copy-preview/",
                {"mode": "month", "source_week": str(self.week), "jalali_year": 1405, "jalali_month": 13},
            ).status_code,
            400,
        )

    def test_existing_hall_filter_still_reports_conflicts_across_halls(self):
        self.create_assignment()
        preview = self.preview([self.spec(hall=self.second_hall.pk, shift=self.overlap_shift.pk)])
        self.assertEqual(
            self.apply(preview, confirm_conflicts=True, override_reason="پوشش دو سالن").status_code, 200
        )
        response = self.client.get(self.base + f"schedule/?week_start={self.week}&hall={self.hall.pk}")
        self.assertEqual(len(response.data["assignments"]), 1)
        self.assertEqual(len(response.data["conflicts"]), 1)


class ConcurrentScheduleTests(SimpleTestCase):
    def test_real_competing_processes_one_preview_cannot_insert_twice(self):
        """A file-backed SQLite lock, not an in-memory SQLITE_LOCKED shortcut."""
        bootstrap = """
import django, os
from pathlib import Path
django.setup()
from django.core.management import call_command
from core.models import Customer, User
from operations.models import Hall, Supervisor
from scheduling.models import WorkShift
from scheduling.services import build_preview
call_command('migrate', verbosity=0, interactive=False)
o = Customer.objects.create(name='Concurrent', manager_name='Test', phone='09123456789', slug='concurrent-schedule', capacity=10, start_date='2026-01-01', expiration_date='2026-12-31')
u = User.objects.create(username='manager', role='tenant', organization=o, portal_username='manager')
h = Hall.objects.create(organization=o, name='Hall')
s = Supervisor.objects.create(organization=o, first_name='Test', last_name='Supervisor', phone='09123456789')
s.halls.add(h)
w = WorkShift.objects.create(organization=o, name='Morning', start_time='08:00', end_time='12:00')
p = build_preview(o, u, [{'date': '2026-10-17', 'hall': h.pk, 'shift': w.pk, 'supervisor': s.pk}])
Path(os.environ['TOKEN_FILE']).write_text(p['token'])
"""
        worker = """
import django, os, time, json
from pathlib import Path
django.setup()
from core.models import User
from rest_framework.test import APIClient
from scheduling.models import ScheduleAssignment
import scheduling.services as service
original = service.revision
def slow(*args, **kwargs):
    time.sleep(.2)
    return original(*args, **kwargs)
service.revision = slow
c = APIClient()
c.force_authenticate(User.objects.get(username='manager'))
Path(os.environ['READY']).touch()
while not Path(os.environ['RELEASE']).exists(): time.sleep(.01)
r = c.post('/api/organizations/concurrent-schedule/schedule/apply/', {'token': Path(os.environ['TOKEN_FILE']).read_text(), 'actions': [{'index': 0, 'action': 'add'}]}, format='json')
print(json.dumps({'status': r.status_code, 'count': ScheduleAssignment.objects.count()}))
"""
        with tempfile.TemporaryDirectory(prefix="damavand-schedule-concurrency-") as tmp:
            env = {
                **os.environ,
                "DATABASE_URL": "sqlite:///" + str(Path(tmp) / "test.sqlite3"),
                "DJANGO_SETTINGS_MODULE": "config.settings",
                "DEBUG": "true",
                "ALLOWED_HOSTS": "testserver",
                "TOKEN_FILE": str(Path(tmp) / "proposal"),
            }
            subprocess.run(
                [sys.executable, "-c", bootstrap],
                env=env,
                cwd=settings.BASE_DIR,
                check=True,
                capture_output=True,
                timeout=30,
            )
            processes = []
            try:
                for index in range(2):
                    processes.append(
                        subprocess.Popen(
                            [sys.executable, "-c", worker],
                            cwd=settings.BASE_DIR,
                            env={
                                **env,
                                "READY": str(Path(tmp) / f"ready-{index}"),
                                "RELEASE": str(Path(tmp) / "release"),
                            },
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                    )
                deadline = time.monotonic() + 15
                while not all((Path(tmp) / f"ready-{index}").exists() for index in range(2)):
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
                self.assertEqual(sorted(result["status"] for result in results), [200, 409])
                self.assertTrue(all(result["count"] == 1 for result in results))
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                    process.wait()

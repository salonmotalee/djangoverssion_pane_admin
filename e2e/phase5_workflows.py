"""Real Phase 5 manager/supervisor workflows, using only the runner's disposable DB."""

import re
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from playwright.sync_api import expect
from tenant_workflows import portal_login
from workflows import BASE_URL, assert_api, set_date, snapshot


def run_phase5_only(browser, username, password, artifacts):
    from workflows import login

    context = browser.new_context(
        locale="fa-IR", timezone_id="Asia/Tehran", reduced_motion="reduce"
    )
    try:
        page = context.new_page()
        page.goto(BASE_URL + "/login")
        login(page, username, password)
        return run_phase5_workflows(browser, context, artifacts)
    finally:
        context.close()


def write(context, method, path, payload, status=200):
    token = assert_api(context.request.get(BASE_URL + "/api/auth/csrf/"))["csrfToken"]
    response = context.request.fetch(
        BASE_URL + "/api/" + path,
        method=method,
        data=payload,
        headers={"X-CSRFToken": token},
    )
    return assert_api(response, status)


def run_phase5_workflows(browser, central_context, artifacts):
    today = datetime.now(ZoneInfo("Asia/Tehran")).date()
    week = today - timedelta(days=(today.weekday() + 2) % 7)
    password = secrets.token_urlsafe(24)
    slug = "phase5-study"
    prefix = f"organizations/{slug}/"
    write(
        central_context,
        "POST",
        "customers/",
        {
            "name": "مطالعه‌سرای مسیر پنجم",
            "manager_name": "مهسا کریمی",
            "phone": "09120000111",
            "slug": slug,
            "capacity": 40,
            "start_date": str(today - timedelta(days=60)),
            "expiration_date": str(today - timedelta(days=1)),
            "login_username": "phase5.manager",
            "login_password": password,
        },
        201,
    )
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000},
        locale="fa-IR",
        timezone_id="Asia/Tehran",
        reduced_motion="reduce",
    )
    page = context.new_page()
    staff_page = context.new_page()
    errors = []
    for tab in (page, staff_page):
        tab.on("pageerror", lambda error: errors.append(str(error)))
    checks = 0
    try:
        portal_login(page, slug, "phase5.manager", password)
        halls = [
            write(context, "POST", prefix + "halls/", {"name": name}, 201)
            for name in ("سالن سپید", "سالن نارون")
        ]
        session = write(
            context,
            "POST",
            prefix + "study-sessions/",
            {
                "title": "پارت تمرکز",
                "start_time": "00:00:00",
                "end_time": "23:59:59",
            },
            201,
        )
        write(
            context,
            "PUT",
            prefix + "assignments/",
            {
                "assignments": [
                    {"hall": hall["id"], "session": session["id"]} for hall in halls
                ]
            },
        )
        supervisors = [
            write(
                context,
                "POST",
                prefix + "supervisors/",
                {
                    "first_name": first,
                    "last_name": "ناظمی",
                    "phone": phone,
                    "halls": [hall["id"] for hall in halls],
                },
                201,
            )
            for first, phone in (("نیلوفر", "09120000222"), ("آرمان", "09120000333"))
        ]
        for person in supervisors:
            write(
                context,
                "PUT",
                prefix + f"supervisor-access/{person['id']}/",
                {
                    "enabled": True,
                    "password": password,
                },
            )
        students = [
            write(
                context,
                "POST",
                prefix + "students/",
                {
                    "first_name": first,
                    "last_name": "دانشور",
                    "identifier": f"PHASE5-{index}",
                    "primary_phone": "09120000444",
                    "grade": 11,
                    "major": "mathematics",
                    "hall": halls[0]["id"],
                },
                201,
            )
            for index, first in enumerate(("ریحانه", "سینا"), 1)
        ]
        write(
            context,
            "POST",
            prefix + "work-shifts/",
            {
                "name": "شیفت آغاز",
                "start_time": "08:00",
                "end_time": "10:00",
                "is_active": True,
            },
            201,
        )
        checks += 1

        # The real matrix schedules two supervisors in one cell through preview.
        page.get_by_role("link", name="برنامه‌ریزی شیفت‌ها", exact=False).click()
        expect(page.locator(".schedule-matrix")).to_be_visible()
        page.locator(".schedule-cell").first.click()
        dialog = page.get_by_role("dialog")
        for first in ("نیلوفر", "آرمان"):
            dialog.get_by_role("checkbox", name=re.compile(first)).check()
        dialog.get_by_role("button", name="پیش‌نمایش تغییرات", exact=True).click()
        preview = page.get_by_role("dialog")
        expect(preview).to_contain_text("نیلوفر")
        expect(preview).to_contain_text("آرمان")
        preview.get_by_role("button", name=re.compile("ثبت برنامه")).click()
        expect(page.get_by_role("dialog")).to_have_count(0)
        schedule = assert_api(
            context.request.get(BASE_URL + f"/api/{prefix}schedule/?week_start={week}")
        )
        assert len(schedule["assignments"]) == 2
        snapshot(page, artifacts / "phase5-schedule.png")
        checks += 1

        page.get_by_role("button", name="هفته بعد", exact=True).click()
        page.get_by_role("button", name=re.compile("کپی هفته.*قبل")).click()
        preview = page.get_by_role("dialog")
        expect(preview).to_contain_text("نیلوفر")
        preview.get_by_role("button", name=re.compile("ثبت برنامه")).click()
        expect(page.get_by_role("dialog")).to_have_count(0)
        copied = assert_api(
            context.request.get(
                BASE_URL
                + f"/api/{prefix}schedule/?week_start={week + timedelta(days=7)}"
            )
        )
        assert len(copied["assignments"]) == 2
        checks += 1

        page.get_by_role("button", name="تکرار در ماه", exact=True).click()
        with page.expect_response(
            lambda response: response.url.endswith("/schedule/copy-preview/")
        ) as monthly_response:
            page.get_by_role("dialog").get_by_role(
                "button", name="دیدن برنامهٔ پیشنهادی", exact=True
            ).click()
        monthly = monthly_response.value.json()
        new_rows = [row for row in monthly["rows"] if row["status"] == "new"]
        assert new_rows and any(row["status"] == "existing" for row in monthly["rows"])
        skipped = new_rows[0]
        preview = page.get_by_role("dialog")
        preview.locator("tr").filter(
            has=page.locator(".schedule-diff.new")
        ).first.get_by_role("combobox").select_option("skip")
        preview.get_by_role("button", name=re.compile("ثبت برنامه")).click()
        expect(page.get_by_role("dialog")).to_have_count(0)
        target_day = datetime.fromisoformat(skipped["date"]).date()
        target_week = target_day - timedelta(days=(target_day.weekday() + 2) % 7)
        saved_month = assert_api(
            context.request.get(
                BASE_URL + f"/api/{prefix}schedule/?week_start={target_week}"
            )
        )
        assert not any(
            row["date"] == skipped["date"]
            and row["supervisor"] == skipped["supervisor"]
            for row in saved_month["assignments"]
        )
        assert saved_month["assignments"], (
            "Other chosen monthly assignments must be saved"
        )
        checks += 1

        staff_page.goto(f"{BASE_URL}/{slug}/supervisor/login")
        form = staff_page.get_by_test_id("supervisor-login-form")
        form.locator('input[name="username"]').fill("۰۹۱۲۰۰۰۰۲۲۲")
        form.locator('input[name="password"]').fill(password)
        form.get_by_role("button", name="ورود به پنل مراقب", exact=True).click()
        expect(staff_page).to_have_url(f"{BASE_URL}/{slug}/supervisor/dashboard")
        expect(staff_page.locator(".tenant-shell")).to_be_visible()
        dashboard = assert_api(
            context.request.get(BASE_URL + f"/api/{prefix}supervisor/dashboard/")
        )
        assert dashboard["student_count"] == 2
        assert dashboard["upcoming_shifts"]
        assert_api(context.request.get(BASE_URL + f"/api/{prefix}dashboard/"))
        snapshot(staff_page, artifacts / "phase5-supervisor-dashboard.png")
        checks += 1

        staff_page.locator(".staff-sidebar").get_by_role(
            "link", name="ورود و خروج", exact=True
        ).click()
        toggle = staff_page.get_by_test_id(f"presence-toggle-{students[0]['id']}")
        expect(toggle).to_contain_text("ورود")
        toggle.click()
        expect(toggle).to_contain_text("خروج")
        toggle.click()
        expect(toggle).to_contain_text("ورود")
        events = assert_api(
            context.request.get(
                BASE_URL
                + f"/api/{prefix}supervisor/presence/?student={students[0]['id']}"
            )
        )["results"]
        assert [event["kind"] for event in events] == ["entry", "exit"]
        assert all(event["hall"] == halls[0]["id"] for event in events)
        snapshot(staff_page, artifacts / "phase5-presence.png")
        checks += 1

        staff_page.locator(".staff-sidebar").get_by_role(
            "link", name="حضور و غیاب", exact=True
        ).click()
        expect(staff_page.get_by_test_id("attendance-session")).to_be_visible()
        staff_page.get_by_test_id("attendance-session").select_option(
            str(session["id"])
        )
        staff_page.get_by_test_id("attendance-auto-preview").click()
        expect(staff_page.get_by_role("dialog")).to_contain_text("موقت")
        expect(staff_page.get_by_test_id("attendance-auto-save")).to_have_count(0)
        staff_page.get_by_role("button", name="بستن پنجره", exact=True).click()
        set_date(staff_page, staff_page, "تاریخ", today - timedelta(days=1))
        staff_page.get_by_test_id("attendance-session").select_option(
            str(session["id"])
        )
        staff_page.get_by_test_id("attendance-auto-preview").click()
        expect(staff_page.get_by_role("dialog")).to_contain_text("غایب")
        staff_page.get_by_test_id("attendance-auto-save").click()
        expect(staff_page.get_by_role("dialog")).to_have_count(0)
        query = f"hall={halls[0]['id']}&date={today - timedelta(days=1)}&session={session['id']}"
        roster = assert_api(
            context.request.get(
                BASE_URL + f"/api/{prefix}supervisor/attendance/?{query}"
            )
        )
        assert all(row["record"]["source"] == "automatic" for row in roster["students"])
        original = roster["students"][0]["record"]
        snapshot(staff_page, artifacts / "phase5-attendance.png")
        checks += 1

        # Manual controls correct only the original recorder's records.
        row = staff_page.get_by_test_id(
            f"attendance-student-{roster['students'][0]['id']}"
        )
        row.get_by_role("button", name="حاضر", exact=True).click()
        with staff_page.expect_response(
            lambda response: (
                response.url.endswith("/attendance/bulk/")
                and response.request.method == "POST"
            )
        ) as manual_response:
            staff_page.get_by_test_id("attendance-manual-save").click()
        assert_api(manual_response.value)
        expect(staff_page.get_by_test_id("attendance-manual-save")).to_be_disabled()
        manual = assert_api(
            context.request.get(
                BASE_URL + f"/api/{prefix}supervisor/attendance/?{query}"
            )
        )
        changed = next(
            item["record"]
            for item in manual["students"]
            if item["record"]["id"] == original["id"]
        )
        assert changed["status"] == "present" and changed["source"] == "manual"
        assert changed["created_at"] == original["created_at"]
        checks += 1

        # A manager correction remains auditable and does not transfer ownership.
        page.goto(f"{BASE_URL}/{slug}/attendance")
        expect(
            page.get_by_role("heading", name="نظارت بر حضور و غیاب", exact=True)
        ).to_be_visible()
        page.get_by_label("سالن حضور و غیاب", exact=True).select_option(
            str(halls[0]["id"])
        )
        set_date(page, page, "تاریخ حضور و غیاب", today - timedelta(days=1))
        page.get_by_label("پارت حضور و غیاب", exact=True).select_option(
            str(session["id"])
        )
        row = page.locator(".manager-attendance tbody tr").filter(
            has_text=roster["students"][0]["identifier"]
        )
        row.get_by_role("button", name="تأخیر", exact=True).click()
        page.get_by_role("button", name="ثبت اصلاحات", exact=True).click()
        correction_dialog = page.get_by_role("dialog")
        expect(
            correction_dialog.get_by_role("button", name="تأیید اصلاحات", exact=True)
        ).to_be_disabled()
        correction_dialog.get_by_label("دلیل اصلاح حضور و غیاب", exact=True).fill(
            "اصلاح پس از بررسی گزارش روزانه"
        )
        with page.expect_response(
            lambda response: (
                response.url.endswith("/attendance/corrections/")
                and response.request.method == "POST"
            )
        ) as correction_response:
            correction_dialog.get_by_role(
                "button", name="تأیید اصلاحات", exact=True
            ).click()
        assert_api(correction_response.value)
        expect(page.get_by_role("dialog")).to_have_count(0)
        corrected = assert_api(
            context.request.get(BASE_URL + f"/api/{prefix}attendance/?{query}")
        )
        result = next(
            item["record"]
            for item in corrected["students"]
            if item["record"]["id"] == original["id"]
        )
        assert result["status"] == "late" and result["recorder"] == original["recorder"]
        assert result["created_at"] == original["created_at"]
        assert any(
            audit["reason"] == "اصلاح پس از بررسی گزارش روزانه"
            for audit in result["audit"]
        )
        snapshot(page, artifacts / "phase5-manager-attendance.png")
        checks += 1

        staff_page.goto(f"{BASE_URL}/{slug}/supervisor/presence")
        staff_page.get_by_test_id(f"presence-toggle-{students[0]['id']}").click()
        expect(
            staff_page.get_by_test_id(f"presence-toggle-{students[0]['id']}")
        ).to_contain_text("خروج")
        write(
            context,
            "PATCH",
            prefix + f"students/{students[0]['id']}/",
            {"hall": halls[1]["id"]},
        )
        staff_page.reload()
        expect(
            staff_page.get_by_test_id(f"presence-student-{students[0]['id']}")
        ).to_contain_text("ورودِ سالن قبلی")
        staff_page.get_by_test_id(f"presence-toggle-{students[0]['id']}").click()
        expect(
            staff_page.get_by_test_id(f"presence-toggle-{students[0]['id']}")
        ).to_contain_text("ورود")
        closed = assert_api(
            context.request.get(
                BASE_URL
                + f"/api/{prefix}supervisor/presence/?student={students[0]['id']}"
            )
        )["results"]
        assert closed[-1]["kind"] == "exit" and closed[-1]["hall"] == halls[0]["id"]
        checks += 1

        staff_page.set_viewport_size({"width": 390, "height": 844})
        assert staff_page.evaluate(
            "document.documentElement.scrollWidth <= innerWidth"
        ), "Staff mobile overflow"
        staff_page.get_by_role("button", name="بازکردن منو", exact=True).click()
        expect(staff_page.get_by_role("dialog", name="ناوبری مراقب")).to_be_visible()
        staff_page.keyboard.press("Escape")
        expect(
            staff_page.get_by_role("button", name="بازکردن منو", exact=True)
        ).to_be_focused()
        snapshot(staff_page, artifacts / "phase5-mobile.png")
        write(
            context,
            "PUT",
            prefix + f"supervisor-access/{supervisors[0]['id']}/",
            {"enabled": False},
        )
        staff_page.reload()
        expect(staff_page).to_have_url(f"{BASE_URL}/{slug}/supervisor/login")
        assert_api(context.request.get(BASE_URL + f"/api/{prefix}dashboard/"))
        assert_api(central_context.request.get(BASE_URL + "/api/auth/me/"))
        assert not errors, "Phase5 browser runtime errors: " + "; ".join(errors)
        checks += 1
        return checks
    except Exception:
        staff_page.screenshot(
            path=str(artifacts / "phase5-failure.png"),
            full_page=True,
            mask=[staff_page.locator('input[type="password"]')],
        )
        raise
    finally:
        context.close()

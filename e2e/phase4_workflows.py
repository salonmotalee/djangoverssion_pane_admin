"""Phase 4 acceptance checks with real sessions, persistent data and Persian UI."""

import re
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from playwright.sync_api import expect
from tenant_workflows import portal_login
from workflows import BASE_URL, assert_api, login, snapshot


def write(context, method, path, data=None, status=200):
    token = assert_api(context.request.get(BASE_URL + "/api/auth/csrf/"))["csrfToken"]
    return assert_api(
        context.request.fetch(
            BASE_URL + path,
            method=method,
            data=data,
            headers={"X-CSRFToken": token},
        ),
        status,
    )


def run_phase4_workflows(page, context, artifacts):
    """Called after earlier workflows while the central super admin is logged in."""
    today = datetime.now(ZoneInfo("Asia/Tehran")).date()
    slug = "e2ephase4"
    portal_password = secrets.token_urlsafe(24)
    staff_password = secrets.token_urlsafe(24)
    operator_password = secrets.token_urlsafe(24)
    organization = write(
        context,
        "POST",
        "/api/customers/",
        {
            "name": "مجموعه آزمون فاز چهارم",
            "manager_name": "سارا احمدی",
            "phone": "09123456789",
            "capacity": 40,
            "slug": slug,
            "start_date": (today - timedelta(days=5)).isoformat(),
            "expiration_date": (today + timedelta(days=90)).isoformat(),
            "login_username": "phase4.manager",
            "login_password": portal_password,
        },
        201,
    )
    staff = write(
        context,
        "POST",
        "/api/users/",
        {
            "username": "e2e.phase4.support",
            "first_name": "پشتیبان آزمایشی",
            "role": "admin",
            "can_support": True,
            "password": staff_password,
        },
        201,
    )
    write(
        context,
        "POST",
        "/api/users/",
        {
            "username": "e2e.phase4.denied",
            "role": "operator",
            "password": operator_password,
        },
        201,
    )
    portal_context = context.browser.new_context(
        viewport={"width": 1440, "height": 1000},
        locale="fa-IR",
        timezone_id="Asia/Tehran",
        has_touch=True,
        reduced_motion="reduce",
    )
    staff_context = context.browser.new_context()
    denied_context = context.browser.new_context()
    portal = portal_context.new_page()
    errors = []
    portal.on("pageerror", lambda error: errors.append(str(error)))
    checks = 0
    try:
        denied_page = denied_context.new_page()
        login(denied_page, "e2e.phase4.denied", operator_password)
        assert_api(denied_context.request.get(BASE_URL + "/api/support/tickets/"), 403)
        assert_api(
            denied_context.request.get(BASE_URL + "/api/support/notifications/"), 403
        )
        expect(
            denied_page.get_by_role("link", name="مدیریت تیکت‌ها", exact=True)
        ).to_have_count(0)
        checks += 1

        staff_page = staff_context.new_page()
        login(staff_page, staff["username"], staff_password)
        assert_api(staff_context.request.get(BASE_URL + "/api/support/tickets/"))
        portal_login(portal, slug, "phase4.manager", portal_password)
        base = f"/api/organizations/{slug}/"
        halls = [
            write(portal_context, "POST", base + "halls/", {"name": name}, 201)
            for name in ["سالن نیلوفر", "سالن یاس"]
        ]
        checks += supervisor_workflows(portal, portal_context, slug, halls, artifacts)
        checks += support_workflows(
            page,
            context,
            portal,
            portal_context,
            staff_context,
            slug,
            staff,
            organization,
            artifacts,
        )
        checks += accessibility_workflows(portal, portal_context, slug, artifacts)
        assert not errors, "Phase 4 browser errors: " + "; ".join(errors)
        return checks
    except Exception:
        portal.screenshot(
            path=str(artifacts / "phase4-failure.png"),
            full_page=True,
            mask=[portal.locator('input[type="password"]')],
        )
        raise
    finally:
        denied_context.close()
        staff_context.close()
        portal_context.close()


def supervisor_workflows(page, context, slug, halls, artifacts):
    base = f"/api/organizations/{slug}/supervisors/"
    page.goto(f"{BASE_URL}/{slug}/supervisors")
    for first_name, phone in [("مریم", "۰۹۱۲۳۴۵۶۷۸۹"), ("نرگس", "+989123456789")]:
        page.get_by_role("button", name="ثبت مراقب", exact=True).click()
        dialog = page.get_by_role("dialog", name="ثبت مراقب جدید", exact=True)
        help_button = dialog.get_by_role(
            "button", name="راهنمای تخصیص سالن", exact=True
        )
        help_button.focus()
        expect(page.get_by_role("tooltip")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.get_by_role("tooltip")).to_have_count(0)
        expect(dialog).to_be_visible()
        dialog.locator('input[name="first_name"]').fill(first_name)
        dialog.locator('input[name="last_name"]').fill("احمدی")
        dialog.locator('input[name="phone"]').fill(phone)
        for hall in halls:
            dialog.get_by_role("checkbox", name=hall["name"], exact=True).check()
        dialog.get_by_role("button", name="ثبت مراقب", exact=True).click()
        expect(dialog).to_have_count(0)
        expect(
            page.get_by_role("button", name=f"ویرایش {first_name} احمدی", exact=True)
        ).to_be_visible()
    supervisors = assert_api(context.request.get(BASE_URL + base))["results"]
    assert len(supervisors) == 2
    assert {item["phone"] for item in supervisors} == {"09123456789"}
    assert all(
        set(item["halls"]) == {hall["id"] for hall in halls} for item in supervisors
    )
    first = next(item for item in supervisors if item["first_name"] == "مریم")
    checks = 1

    page.get_by_role("button", name="ویرایش مریم احمدی", exact=True).click()
    dialog = page.get_by_role("dialog", name="ویرایش مراقب", exact=True)
    dialog.locator('input[name="last_name"]').fill("رضایی")
    dialog.get_by_role("textbox", name="جست‌وجوی سالن‌های مسئولیت", exact=True).fill(
        halls[0]["name"]
    )
    expect(dialog.get_by_role("checkbox")).to_have_count(1)
    dialog.get_by_role("checkbox", name=halls[0]["name"], exact=True).uncheck()
    dialog.get_by_role("button", name="ذخیره تغییرات", exact=True).click()
    expect(dialog).to_have_count(0)
    updated = assert_api(context.request.get(f"{BASE_URL}{base}{first['id']}/"))
    assert updated["last_name"] == "رضایی" and updated["halls"] == [halls[1]["id"]]
    page.get_by_role("combobox", name="سالن مسئولیت", exact=True).select_option(
        str(halls[0]["id"])
    )
    expect(
        page.get_by_role("button", name="ویرایش مریم رضایی", exact=True)
    ).to_have_count(0)
    expect(
        page.get_by_role("button", name="ویرایش نرگس احمدی", exact=True)
    ).to_be_visible()
    page.get_by_role("combobox", name="سالن مسئولیت", exact=True).select_option("")
    checks += 1

    def action(label, confirmation):
        page.get_by_role("button", name=f"{label} مریم رضایی", exact=True).click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_role("button", name=confirmation, exact=True).click()
        expect(dialog).to_have_count(0)

    action("غیرفعال‌سازی", "غیرفعال‌سازی مراقب")
    page.get_by_role("combobox", name="وضعیت", exact=True).select_option("inactive")
    expect(
        page.get_by_role("button", name="فعال‌سازی مریم رضایی", exact=True)
    ).to_be_visible()
    inactive = assert_api(context.request.get(f"{BASE_URL}{base}{first['id']}/"))
    assert not inactive["is_active"] and inactive["archived_at"] is None
    action("بایگانی", "بایگانی مراقب")
    page.get_by_role("combobox", name="وضعیت", exact=True).select_option("archived")
    expect(
        page.get_by_role("button", name="بازیابی مریم رضایی", exact=True)
    ).to_be_visible()
    action("بازیابی", "بازیابی مراقب")
    page.get_by_role("combobox", name="وضعیت", exact=True).select_option("inactive")
    expect(
        page.get_by_role("button", name="فعال‌سازی مریم رضایی", exact=True)
    ).to_be_visible()
    restored = assert_api(context.request.get(f"{BASE_URL}{base}{first['id']}/"))
    assert not restored["is_active"] and restored["halls"] == [halls[1]["id"]]
    action("فعال‌سازی", "فعال‌سازی مراقب")
    page.get_by_role("combobox", name="وضعیت", exact=True).select_option("active")
    page.get_by_role("link", name="مشاهدهٔ مریم رضایی", exact=True).click()
    expect(page.get_by_role("heading", name="مریم رضایی", exact=True)).to_be_visible()
    expect(page.locator(".supervisor-assigned-halls")).to_contain_text(halls[1]["name"])
    snapshot(page, artifacts / "phase4-supervisor.png")
    return checks + 1


def support_workflows(
    central,
    context,
    portal,
    tenant_context,
    staff_context,
    slug,
    staff,
    organization,
    artifacts,
):
    prefix = f"/api/organizations/{slug}/support/"
    subject = "بررسی دسترسی سالن‌های مجموعه"
    description = "شرح درخواست <img src=x onerror='window.phase4Injected=true'>"
    portal.goto(f"{BASE_URL}/{slug}/support")
    portal.get_by_role("button", name="تیکت جدید", exact=True).first.click()
    form = portal.get_by_test_id("support-create-form")
    form.locator('input[name="subject"]').fill(subject)
    form.locator('select[name="category"]').select_option("technical")
    form.locator('select[name="priority"]').select_option("high")
    form.locator('textarea[name="description"]').fill(description)
    form.get_by_role("button", name="ثبت تیکت", exact=True).click()
    expect(form).to_have_count(0)
    expect(portal.get_by_role("heading", name=subject, exact=True)).to_be_visible()
    tickets = assert_api(tenant_context.request.get(BASE_URL + prefix + "tickets/"))[
        "results"
    ]
    ticket = next(item for item in tickets if item["subject"] == subject)
    ticket_id = ticket["id"]
    assert ticket["status"] == "open"
    log = portal.get_by_role("log", name="پیام‌های تیکت", exact=True)
    expect(log).to_contain_text(description)
    expect(log.locator("img")).to_have_count(0)
    assert not portal.evaluate("Boolean(window.phase4Injected)"), (
        "Ticket content executed HTML"
    )
    checks = 1

    central.goto(BASE_URL + "/support")
    central.get_by_role("textbox", name="جست‌وجوی تیکت‌ها", exact=True).fill(subject)
    central.get_by_role("combobox", name="مجموعه", exact=True).select_option(
        str(organization["id"])
    )
    central.get_by_label("فیلتر اولویت تیکت", exact=True).select_option("high")
    central.get_by_test_id(f"support-ticket-{ticket_id}").click()
    assignment = central.get_by_test_id("support-assignment-form")
    expect(assignment.locator(f'option[value="{staff["id"]}"]')).to_have_count(1)
    assignment.get_by_role(
        "combobox", name="واگذاری به پشتیبان", exact=True
    ).select_option(str(staff["id"]))
    assignment.get_by_role("button", name="ثبت مسئول پیگیری", exact=True).click()
    expect(
        central.get_by_role("status").filter(has_text="مسئول پیگیری به‌روز شد.")
    ).to_be_visible()
    expect(
        assignment.get_by_role("button", name="ثبت مسئول پیگیری", exact=True)
    ).to_be_disabled()
    assert (
        assert_api(context.request.get(f"{BASE_URL}/api/support/tickets/{ticket_id}/"))[
            "assigned_to"
        ]["id"]
        == staff["id"]
    )
    other_notifications = assert_api(
        staff_context.request.get(BASE_URL + "/api/support/notifications/")
    )
    assert any(
        item["ticket_id"] == ticket_id and not item["is_read"]
        for item in other_notifications["items"]
    )
    assert other_notifications["unread_messages"] > 0, (
        "One staff member's reading cleared another's messages"
    )
    write(
        staff_context,
        "POST",
        "/api/support/notifications/read/",
        {
            "ids": [
                item["id"]
                for item in other_notifications["items"]
                if item["ticket_id"] == ticket_id
            ]
        },
    )
    assert (
        assert_api(staff_context.request.get(BASE_URL + "/api/support/notifications/"))[
            "unread_messages"
        ]
        == 0
    )
    checks += 1

    # Keep the customer on the dashboard while staff replies. Its bell must
    # refresh through the normal timer, without navigation or manual reload.
    portal.goto(f"{BASE_URL}/{slug}/dashboard")
    bell = portal.get_by_test_id("support-bell")
    expect(bell).to_have_attribute("aria-label", "اعلان‌های پشتیبانی")
    reply = central.get_by_test_id("support-reply-form")
    reply.get_by_role("textbox", name="متن پاسخ", exact=True).fill(
        "تنظیمات سالن بررسی شد؛ لطفاً نتیجه را اعلام کنید."
    )
    reply.get_by_role("button", name="ارسال پاسخ", exact=True).click()
    expect(central.locator(".support-status-awaiting_customer")).to_be_visible()
    expect(bell).to_have_attribute(
        "aria-label", re.compile("خوانده‌نشده"), timeout=35_000
    )
    notifications = assert_api(
        tenant_context.request.get(BASE_URL + prefix + "notifications/")
    )
    assert notifications["unread_messages"] == 1 and notifications["unread_count"] > 0
    bell.click()
    expect(portal.locator(".support-notification-item.unread")).not_to_have_count(0)
    portal.get_by_role(
        "button", name="خواندن اعلان‌های نمایش‌داده‌شده", exact=True
    ).click()
    expect(bell).to_have_attribute("aria-label", "اعلان‌های پشتیبانی")
    assert (
        assert_api(tenant_context.request.get(BASE_URL + prefix + "notifications/"))[
            "unread_messages"
        ]
        == 0
    )
    portal.keyboard.press("Escape")
    expect(bell).to_be_focused()
    checks += 1

    portal.goto(f"{BASE_URL}/{slug}/support/{ticket_id}")
    expect(portal.get_by_role("log", name="پیام‌های تیکت", exact=True)).to_contain_text(
        "تنظیمات سالن بررسی شد"
    )
    reply = portal.get_by_test_id("support-reply-form")
    reply.get_by_role("textbox", name="متن پاسخ", exact=True).fill(
        "اکنون سالن‌ها درست نمایش داده می‌شوند."
    )
    reply.get_by_role("button", name="ارسال پاسخ", exact=True).click()
    expect(portal.locator(".support-status-awaiting_support")).to_be_visible()
    central.get_by_role("button", name="تازه‌سازی گفت‌وگو", exact=True).click()
    expect(central.get_by_role("log", name="پیام‌های تیکت", exact=True)).to_contain_text(
        "اکنون سالن‌ها درست نمایش داده می‌شوند."
    )
    central.get_by_role("button", name="ثبت حل‌شدن تیکت", exact=True).click()
    central.get_by_test_id("support-confirm-resolve").click()
    expect(central.locator(".support-status-resolved")).to_be_visible()
    portal.get_by_role("button", name="تازه‌سازی گفت‌وگو", exact=True).click()
    expect(portal.locator(".support-status-resolved")).to_be_visible()
    expect(portal.get_by_test_id("support-reply-form")).to_have_count(0)
    write(
        tenant_context,
        "POST",
        f"{prefix}tickets/{ticket_id}/messages/",
        {"body": "پاسخ بدون بازگشایی"},
        400,
    )
    portal.get_by_role("button", name="تأیید و بستن تیکت", exact=True).click()
    portal.get_by_test_id("support-confirm-close").click()
    expect(portal.locator(".support-status-closed")).to_be_visible()
    checks += 1

    portal.get_by_role("button", name="بازگشایی تیکت", exact=True).first.click()
    portal.get_by_test_id("support-confirm-reopen").click()
    expect(portal.locator(".support-status-awaiting_support")).to_be_visible()
    reply = portal.get_by_test_id("support-reply-form")
    reply.get_by_role("textbox", name="متن پاسخ", exact=True).fill(
        "برای یک سالن دیگر نیز راهنمایی می‌خواهم."
    )
    reply.get_by_role("button", name="ارسال پاسخ", exact=True).click()
    expect(portal.get_by_role("log", name="پیام‌های تیکت", exact=True)).to_contain_text(
        "برای یک سالن دیگر نیز راهنمایی می‌خواهم."
    )
    history = assert_api(
        tenant_context.request.get(f"{BASE_URL}{prefix}tickets/{ticket_id}/")
    )["status_history"]
    assert len(history) >= 6, "Status history did not persist the full lifecycle"
    snapshot(portal, artifacts / "phase4-support.png")
    return checks + 1


def accessibility_workflows(page, context, slug, artifacts):
    page.goto(f"{BASE_URL}/{slug}/dashboard")
    help_button = page.get_by_role("button", name="راهنمای ظرفیت مجموعه", exact=True)
    help_button.focus()
    expect(page.get_by_role("tooltip")).to_be_visible()
    tooltip_id = page.get_by_role("tooltip").get_attribute("id")
    expect(help_button).to_have_attribute("aria-describedby", tooltip_id)
    page.keyboard.press("Escape")
    expect(page.get_by_role("tooltip")).to_have_count(0)
    expect(help_button).to_be_focused()
    page.get_by_role("heading", level=1).click()
    page.set_viewport_size({"width": 390, "height": 520})
    help_button.tap()
    expect(page.get_by_role("tooltip")).to_be_visible()
    assert page.get_by_role("tooltip").evaluate(
        "element => element.getBoundingClientRect().right <= innerWidth && element.getBoundingClientRect().left >= 0"
    )
    page.get_by_role("heading", level=1).tap()
    expect(page.get_by_role("tooltip")).to_have_count(0)
    bell = page.get_by_test_id("support-bell")
    bell.tap()
    notifications = page.locator(".support-notification-panel")
    expect(notifications).to_be_visible()
    assert notifications.evaluate(
        "element => element.getBoundingClientRect().left >= 0 && element.getBoundingClientRect().right <= innerWidth && element.getBoundingClientRect().bottom <= innerHeight"
    ), "Mobile notifications overflow the viewport"
    page.keyboard.press("Escape")
    expect(bell).to_be_focused()
    checks = 1

    menu = page.get_by_role("button", name="باز کردن منوی مجموعه", exact=True)
    menu.click()
    dialog = page.get_by_role("dialog", name="ناوبری مجموعه", exact=True)
    expect(dialog).to_be_visible()
    scroll = page.locator(".tenant-side-scroll")
    assert scroll.evaluate("element => element.scrollHeight > element.clientHeight"), (
        "Mobile sidebar has no independent scroll area"
    )
    page_y = page.evaluate("scrollY")
    scroll.hover()
    page.mouse.wheel(0, 900)
    page.wait_for_function(
        "document.querySelector('.tenant-side-scroll').scrollTop > 0"
    )
    assert page.evaluate("scrollY") == page_y, "Sidebar scrolling moved the workspace"
    expect(
        dialog.get_by_role("link", name="پشتیبانی و تیکت‌ها", exact=True)
    ).to_be_visible()
    logout = dialog.get_by_role("button", name="خروج از حساب", exact=True)
    expect(logout).to_be_in_viewport()
    page.keyboard.press("Escape")
    expect(menu).to_be_focused()
    expect(menu).to_have_attribute("aria-expanded", "false")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), (
        "Phase 4 mobile overflow"
    )
    snapshot(page, artifacts / "phase4-mobile.png")
    menu.click()
    dialog.get_by_role("button", name="خروج از حساب", exact=True).click()
    expect(page).to_have_url(f"{BASE_URL}/{slug}")
    assert_api(
        context.request.get(f"{BASE_URL}/api/organizations/{slug}/support/tickets/"),
        401,
    )
    return checks + 1

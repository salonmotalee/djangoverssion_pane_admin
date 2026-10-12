"""Customer portal acceptance tests using real forms, cookies and Django data."""

import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from playwright.sync_api import expect
from workflows import BASE_URL, assert_api, set_date, snapshot


def portal_login(page, slug, username, password):
    page.goto(f"{BASE_URL}/{slug}")
    form = page.get_by_test_id("organization-login-form")
    form.locator('input[name="username"]').fill(username)
    form.locator('input[name="password"]').fill(password)
    form.get_by_role("button", name="ورود به فضای مجموعه", exact=True).click()
    expect(page).to_have_url(f"{BASE_URL}/{slug}/dashboard")
    expect(page.get_by_test_id("tenant-capacity")).to_be_visible()


def run_tenant_workflows(page, context, artifacts):
    today = datetime.now(ZoneInfo("Asia/Tehran")).date()
    password = secrets.token_urlsafe(24)
    checks = 0
    for slug, name, capacity, expired in (
        ("aftab", "مجموعه آفتاب", 120, True),
        ("darya", "مجموعه دریا", 80, False),
    ):
        page.goto(BASE_URL + "/customers")
        page.get_by_role("button", name="مجموعه جدید", exact=True).click()
        form = page.get_by_test_id("customer-form")
        for field, value in {
            "name": name,
            "manager_name": "سارا احمدی",
            "phone": "09123456789",
            "capacity": str(capacity),
            "slug": slug,
        }.items():
            form.locator(f'input[name="{field}"]').fill(value)
        set_date(page, form, "تاریخ شروع سرویس", today - timedelta(days=40))
        set_date(
            page,
            form,
            "تاریخ پایان سرویس",
            today + timedelta(days=-1 if expired else 90),
        )
        form.get_by_label("هم‌زمان ورود اختصاصی مجموعه را راه‌اندازی کن").check()
        form.locator('input[name="login_username"]').fill("hall.manager")
        form.locator('input[name="login_password"]').fill(
            password + ("other" if slug == "darya" else "")
        )
        form.get_by_role("button", name="ثبت مجموعه", exact=True).click()
        expect(form).to_have_count(0)
    organizations = assert_api(
        context.request.get(BASE_URL + "/api/customers/?search=آفتاب")
    )["results"]
    org = next(row for row in organizations if row["slug"] == "aftab")
    page.goto(f"{BASE_URL}/customers/{org['id']}")
    expect(page.get_by_role("link", name="باز کردن ورود مجموعه")).to_have_attribute(
        "href", "/aftab"
    )
    expect(page.locator(".portal-url")).to_contain_text("/aftab")
    checks += 1

    portal = context.new_page()
    try:
        portal.goto(BASE_URL + "/aftab")
        expect(
            portal.get_by_role("heading", name="مجموعه آفتاب", exact=True)
        ).to_be_visible()
        snapshot(portal, artifacts / "tenant-login.png")
        form = portal.get_by_test_id("organization-login-form")
        form.locator('input[name="username"]').fill("hall.manager")
        form.locator('input[name="password"]').fill("incorrect")
        form.get_by_role("button", name="نمایش رمز عبور").click()
        expect(form.locator('input[name="password"]')).to_have_attribute("type", "text")
        form.get_by_role("button", name="پنهان کردن رمز عبور").click()
        form.get_by_role("button", name="ورود به فضای مجموعه", exact=True).click()
        expect(form.get_by_role("alert")).to_contain_text("صحیح نیست")
        form.locator('input[name="password"]').fill(password)
        form.get_by_role("button", name="ورود به فضای مجموعه", exact=True).click()
        expect(portal).to_have_url(BASE_URL + "/aftab/dashboard")
        expect(portal.get_by_test_id("tenant-capacity")).to_contain_text("۱۲۰")
        expect(portal.get_by_test_id("tenant-remaining")).to_have_text("۰")
        expect(
            portal.get_by_text("زمان تمدید سرویس رسیده است", exact=True)
        ).to_be_visible()
        snapshot(portal, artifacts / "tenant-dashboard.png")
        assert_api(context.request.get(BASE_URL + "/api/auth/me/"))
        checks += 1

        assert_api(
            context.request.get(BASE_URL + "/api/organizations/darya/dashboard/"), 403
        )
        portal.goto(BASE_URL + "/darya/dashboard")
        expect(
            portal.get_by_role("heading", name="این فضا متعلق به مجموعهٔ دیگری است")
        ).to_be_visible()
        expect(portal.get_by_test_id("tenant-capacity")).to_have_count(0)
        portal.goto(BASE_URL + "/aftab/dashboard")
        expect(portal.get_by_test_id("tenant-capacity")).to_be_visible()
        checks += 1

        page.get_by_role("button", name="ویرایش اطلاعات", exact=True).click()
        edit = page.get_by_test_id("customer-form")
        edit.locator('input[name="capacity"]').fill("175")
        expect(edit.locator('input[name="slug"]')).to_have_attribute("readonly", "")
        edit.get_by_role("button", name="ذخیره تغییرات", exact=True).click()
        expect(edit).to_have_count(0)
        page.get_by_role("button", name="تمدید سرویس", exact=True).click()
        renewal = page.get_by_test_id("renew-form")
        set_date(page, renewal, "تاریخ پایان جدید", today + timedelta(days=120))
        renewal.get_by_role("button", name="تمدید سرویس", exact=True).click()
        expect(renewal).to_have_count(0)
        portal.get_by_role("button", name="به‌روزرسانی اطلاعات مجموعه").click()
        expect(portal.get_by_test_id("tenant-capacity")).to_contain_text("۱۷۵")
        expect(portal.get_by_test_id("tenant-remaining")).to_have_text("۱۲۱")
        checks += 1

        page.get_by_role("button", name="تنظیم دسترسی پرتال", exact=True).click()
        provision = page.get_by_test_id("portal-provision-form")
        changed = password + "reset"
        provision.locator('input[name="login_password"]').fill(changed)
        provision.locator('input[name="confirm_password"]').fill(changed)
        provision.get_by_role("button", name="ذخیره دسترسی پرتال", exact=True).click()
        expect(provision).to_have_count(0)
        portal.get_by_role("button", name="به‌روزرسانی اطلاعات مجموعه").click()
        expect(portal).to_have_url(BASE_URL + "/aftab")
        assert_api(context.request.get(BASE_URL + "/api/auth/me/"))
        portal_login(portal, "aftab", "hall.manager", changed)
        checks += 1

        portal.set_viewport_size({"width": 390, "height": 844})
        portal.get_by_role("button", name="باز کردن منوی مجموعه").click()
        expect(portal.get_by_role("dialog", name="ناوبری مجموعه")).to_be_visible()
        portal.keyboard.press("Escape")
        expect(
            portal.get_by_role("button", name="باز کردن منوی مجموعه")
        ).to_be_focused()
        assert portal.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
            "Mobile overflow"
        )
        snapshot(portal, artifacts / "tenant-mobile.png")
        portal.get_by_role("button", name="باز کردن منوی مجموعه").click()
        portal.get_by_role("button", name="خروج از حساب", exact=True).click()
        expect(portal).to_have_url(BASE_URL + "/aftab")
        assert_api(
            context.request.get(BASE_URL + "/api/organizations/aftab/dashboard/"), 401
        )
        assert_api(context.request.get(BASE_URL + "/api/auth/me/"))
        checks += 1

        response = portal.goto(BASE_URL + "/unknown-study-hall")
        assert response.status == 404
        expect(
            portal.get_by_role("heading", name="این مسیر به قله نمی‌رسد")
        ).to_be_visible()
        portal.goto(BASE_URL + "/darya/dashboard")
        expect(portal).to_have_url(BASE_URL + "/darya")
        checks += 1
    except Exception:
        portal.screenshot(
            path=str(artifacts / "tenant-failure.png"),
            full_page=True,
            mask=[
                portal.locator('input[name="password"]'),
                portal.locator('input[name="login_password"]'),
            ],
        )
        raise
    finally:
        portal.close()
    return checks

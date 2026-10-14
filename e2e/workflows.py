"""Browser acceptance checks for real, permission-protected platform workflows."""

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import expect

BASE_URL = "http://127.0.0.1:3000"


def login(page, username: str, password: str) -> None:
    page.goto(BASE_URL + "/login")
    form = page.get_by_test_id("login-form")
    form.locator('input[name="username"]').fill(username)
    form.locator('input[name="password"]').fill(password)
    form.get_by_role("button", name="ورود به مدار").click()
    expect(page).to_have_url(re.compile(r"/dashboard$"))
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    expect(page.locator(".metric-grid")).to_be_visible()


def snapshot(page, path: Path) -> None:
    page.evaluate(
        "() => document.fonts.ready.then(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))"
    )
    page.screenshot(path=str(path), full_page=True, animations="disabled")


def jalali(page, day: date) -> str:
    return page.evaluate(
        """iso => {
            const parts = new Intl.DateTimeFormat('en-US-u-ca-persian', {
                year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'Asia/Tehran'
            }).formatToParts(new Date(iso + 'T12:00:00Z'));
            const part = type => parts.find(p => p.type === type).value;
            return `${part('year')}/${part('month')}/${part('day')}`;
        }""",
        day.isoformat(),
    )


def set_date(page, form, label: str, day: date) -> None:
    field = form.get_by_label(re.compile("^" + re.escape(label)))
    field.fill(jalali(page, day))
    field.press("Tab")
    # Close the calendar with a normal outside click before the next action.
    # DatePicker intentionally keeps its calendar open after typing and Tab.
    heading = page.locator(".modal-heading h2")
    if heading.count():
        heading.first.click()
    else:
        page.get_by_role("heading", level=1).click()


def assert_api(response, status: int = 200):
    assert response.status == status, (
        f"Unexpected API status {response.status}: {response.text()[:500]}"
    )
    return response.json() if status != 204 else None


def run_workflows(browser, username: str, password: str, artifacts: Path) -> int:
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000},
        locale="fa-IR",
        timezone_id="Asia/Tehran",
        reduced_motion="reduce",
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    checks = 0
    try:
        # Unauthenticated users must land on the real login, never a fake dashboard.
        page.goto(BASE_URL + "/dashboard")
        expect(page).to_have_url(re.compile(r"/login$"))
        assert_api(context.request.get(BASE_URL + "/api/customers/"), 401)
        snapshot(page, artifacts / "login.png")
        # A failed CSRF preflight must not submit credentials; retry after the
        # service recovers should complete the real authenticated login.
        attempts = []
        page.on("request", lambda request: attempts.append(request.url))
        page.route(
            "**/api/auth/csrf/",
            lambda route: route.fulfill(status=503, body="Service unavailable"),
        )
        form = page.get_by_test_id("login-form")
        form.locator('input[name="username"]').fill(username)
        form.locator('input[name="password"]').fill(password)
        form.get_by_role("button", name="ورود به مدار").click()
        expect(
            page.get_by_text("سرویس ورود در دسترس نیست. کمی بعد دوباره تلاش کنید.")
        ).to_be_visible()
        assert not any(url.endswith("/api/auth/login/") for url in attempts)
        page.unroute("**/api/auth/csrf/")
        attempts.clear()
        login(page, username, password)
        assert sum(url.endswith("/api/auth/csrf/") for url in attempts) == 1
        checks += 1
        data = assert_api(context.request.get(BASE_URL + "/api/dashboard/"))
        assert data["metrics"]["total_customers"] == 0
        assert data["metrics"]["active_administrators"] == 1
        expect(page.get_by_text("دریافت اطلاعات ناموفق بود")).to_have_count(0)
        expect(page.locator(".metric-card strong").first).to_have_text("۰")
        snapshot(page, artifacts / "dashboard-empty.png")
        checks += 1

        # The rest of the workflow uses actual form interactions and persisted API
        # assertions; its labels are aligned with the final application below.
        checks += customer_and_user_workflows(
            page, context, username, password, artifacts
        )

        from tenant_workflows import run_tenant_workflows

        checks += run_tenant_workflows(page, context, artifacts)

        from phase4_workflows import run_phase4_workflows

        checks += run_phase4_workflows(page, context, artifacts)

        from phase5_workflows import run_phase5_workflows

        checks += run_phase5_workflows(browser, context, artifacts)

        assert not errors, "Browser runtime errors: " + "; ".join(errors)
        return checks
    except Exception:
        page.screenshot(
            path=str(artifacts / "failure.png"),
            full_page=True,
            mask=[page.locator('input[type="password"]')],
        )
        raise
    finally:
        context.close()


def customer_and_user_workflows(
    page, context, username: str, password: str, artifacts: Path
) -> int:
    checks = 0
    today = datetime.now(ZoneInfo("Asia/Tehran")).date()
    collection = "مجموعه بهار آزمایشی"
    page.goto(BASE_URL + "/customers")
    page.get_by_role("button", name="مجموعه جدید", exact=True).click()
    form = page.get_by_test_id("customer-form")
    form.locator('input[name="name"]').fill(collection)
    form.locator('input[name="manager_name"]').fill("سارا رضایی")
    form.locator('input[name="phone"]').fill("07001234567")
    form.locator('input[name="capacity"]').fill("120")
    start_input = form.get_by_label(re.compile("^تاریخ شروع سرویس"))
    start_input.fill("1405/13/10")
    start_input.press("Tab")
    assert not start_input.evaluate("input => input.validity.valid"), (
        "Impossible Jalali month must be rejected"
    )
    page.get_by_role("heading", name="ثبت مجموعه جدید", exact=True).click()
    form.get_by_role("button", name="ثبت مجموعه", exact=True).click()
    assert assert_api(context.request.get(BASE_URL + "/api/customers/"))["count"] == 0
    set_date(page, form, "تاریخ شروع سرویس", today - timedelta(days=20))
    set_date(page, form, "تاریخ پایان سرویس", today + timedelta(days=5))
    form.get_by_role("button", name="ثبت مجموعه", exact=True).click()
    expect(form.get_by_role("alert")).to_contain_text("شماره تلفن")
    assert assert_api(context.request.get(BASE_URL + "/api/customers/"))["count"] == 0
    form.locator('input[name="phone"]').fill("۰۹۱۲۳۴۵۶۷۸۹")
    form.get_by_role("button", name="ثبت مجموعه", exact=True).click()
    expect(form).to_have_count(0)
    expect(page.get_by_role("link", name=re.compile(collection))).to_be_visible()
    customer = assert_api(context.request.get(BASE_URL + "/api/customers/"))["results"][
        0
    ]
    customer_id, identifier = customer["id"], customer["identifier"]
    assert customer["phone"] == "09123456789"
    assert customer["start_date"] == (today - timedelta(days=20)).isoformat(), {
        "expected_start": (today - timedelta(days=20)).isoformat(),
        "actual_start": customer["start_date"],
    }
    assert customer["expiration_date"] == (today + timedelta(days=5)).isoformat(), {
        "expected_expiration": (today + timedelta(days=5)).isoformat(),
        "actual_expiration": customer["expiration_date"],
    }
    assert customer["status"] == "expiring" and re.fullmatch(
        r"[A-Za-z0-9]{4,32}", identifier
    )
    checks += 1

    page.get_by_label("جستجوی مجموعه‌ها", exact=True).fill(
        "هیچ مجموعه‌ای با این نام نیست"
    )
    expect(page.get_by_role("heading", name="نتیجه‌ای پیدا نشد")).to_be_visible()
    page.get_by_label("جستجوی مجموعه‌ها", exact=True).fill("۰۹۱۲۳۴۵۶۷۸۹")
    expect(page.get_by_role("link", name=re.compile(collection))).to_be_visible()
    page.get_by_label("جستجوی مجموعه‌ها", exact=True).fill(collection)
    expect(page.get_by_role("link", name=re.compile(collection))).to_be_visible()
    page.get_by_role("button", name=f"ویرایش {collection}", exact=True).click()
    form = page.get_by_test_id("customer-form")
    expect(form.locator('input[name="identifier"]')).to_have_attribute("readonly", "")
    collection = "مجموعه بهار ویرایش‌شده"
    form.locator('input[name="name"]').fill(collection)
    form.get_by_role("button", name="ذخیره تغییرات", exact=True).click()
    expect(form).to_have_count(0)
    page.get_by_label("جستجوی مجموعه‌ها", exact=True).fill(collection)
    expect(page.get_by_role("link", name=re.compile(collection))).to_be_visible()
    updated = assert_api(
        context.request.get(f"{BASE_URL}/api/customers/{customer_id}/")
    )
    assert updated["name"] == collection and updated["identifier"] == identifier
    checks += 1

    page.goto(BASE_URL + "/alerts")
    expect(page.get_by_role("link", name=re.compile(collection))).to_be_visible()
    dashboard = assert_api(context.request.get(BASE_URL + "/api/dashboard/"))
    assert dashboard["metrics"]["expiring_7_days"] == 1
    page.goto(f"{BASE_URL}/customers/{customer_id}")
    expect(page.get_by_role("heading", level=1)).to_have_text(collection)
    page.get_by_role("button", name="تمدید سرویس", exact=True).click()
    renewal = page.get_by_test_id("renew-form")
    set_date(page, renewal, "تاریخ پایان جدید", today + timedelta(days=120))
    renewal.get_by_role("button", name="تمدید سرویس", exact=True).click()
    expect(renewal).to_have_count(0)
    renewed = assert_api(
        context.request.get(f"{BASE_URL}/api/customers/{customer_id}/")
    )
    assert renewed["expiration_date"] == (today + timedelta(days=120)).isoformat()
    assert renewed["status"] == "active" and renewed["identifier"] == identifier
    page.goto(BASE_URL + "/alerts")
    set_date(page, page, "پایان سرویس از تاریخ", today + timedelta(days=100))
    set_date(page, page, "پایان سرویس تا تاریخ", today + timedelta(days=130))
    expect(page.get_by_role("link", name=re.compile(collection))).to_be_visible()
    page.get_by_role("button", name="۷ روز آینده", exact=True).click()
    expect(
        page.get_by_role("heading", name="در این بازه سررسیدی ندارید")
    ).to_be_visible()
    checks += 1

    page.goto(BASE_URL + "/customers")
    with page.expect_download() as download_info:
        page.get_by_role("button", name="خروجی CSV", exact=True).click()
    download_path = Path(download_info.value.path())
    exported = download_path.read_text(encoding="utf-8-sig")
    assert collection in exported and identifier in exported
    csrf = assert_api(context.request.get(BASE_URL + "/api/auth/csrf/"))["csrfToken"]
    assert_api(
        context.request.patch(
            f"{BASE_URL}/api/customers/{customer_id}/",
            data={"identifier": "CHANGED1"},
            headers={"X-CSRFToken": csrf},
        ),
        400,
    )
    assert_api(
        context.request.patch(
            f"{BASE_URL}/api/customers/{customer_id}/", data={"name": "بدون CSRF"}
        ),
        403,
    )
    checks += 1

    page.get_by_role("button", name=f"حذف {collection}", exact=True).click()
    page.get_by_role("button", name="بله، حذف شود", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(page.get_by_role("link", name=re.compile(collection))).to_have_count(0)
    page.get_by_label("وضعیت بایگانی", exact=True).select_option("deleted")
    expect(page.get_by_role("link", name=re.compile(collection))).to_be_visible()
    deleted = assert_api(
        context.request.get(f"{BASE_URL}/api/customers/{customer_id}/?deleted=all")
    )
    assert deleted["deleted_at"] and deleted["identifier"] == identifier
    page.get_by_role("link", name=re.compile(collection)).click()
    expect(page.get_by_role("heading", level=1)).to_have_text(collection)
    page.get_by_role("button", name="بازیابی مجموعه", exact=True).click()
    page.get_by_role("button", name="بله، بازیابی شود", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    page.goto(BASE_URL + "/customers")
    expect(page.get_by_role("link", name=re.compile(collection))).to_be_visible()
    restored = assert_api(
        context.request.get(f"{BASE_URL}/api/customers/{customer_id}/")
    )
    assert restored["deleted_at"] is None and restored["identifier"] == identifier
    audit = assert_api(
        context.request.get(
            f"{BASE_URL}/api/audit/?entity_type=customer&entity_id={customer_id}"
        )
    )
    actions = {entry["action"] for entry in audit["results"]}
    assert {
        "create_customer",
        "update_customer",
        "renew_customer",
        "delete_customer",
        "restore_customer",
    }.issubset(actions), actions
    checks += 1

    page.goto(BASE_URL + "/dashboard")
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    expect(page.locator(".metric-grid")).to_be_visible()
    expect(page.locator(".growth-chart svg")).to_be_visible()
    assert (
        assert_api(context.request.get(BASE_URL + "/api/dashboard/"))["metrics"][
            "total_customers"
        ]
        == 1
    )
    snapshot(page, artifacts / "dashboard.png")
    page.goto(BASE_URL + "/customers")
    expect(page.get_by_role("link", name=re.compile(collection))).to_be_visible()
    snapshot(page, artifacts / "customers.png")
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="باز کردن منو", exact=True).click()
    expect(
        page.get_by_role("navigation").get_by_role("link", name="نمای کلی", exact=True)
    ).to_be_visible()
    page.get_by_role("navigation").get_by_role(
        "link", name="نمای کلی", exact=True
    ).click()
    expect(page).to_have_url(re.compile(r"/dashboard$"))
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    expect(page.locator(".metric-grid")).to_be_visible()
    assert page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth + 1"
    ), "Mobile viewport overflows horizontally"
    snapshot(page, artifacts / "dashboard-mobile.png")
    page.get_by_role("button", name="باز کردن منو", exact=True).click()
    page.get_by_role("navigation").get_by_role(
        "link", name="نمای کلی", exact=True
    ).click()
    expect(
        page.get_by_role("button", name="باز کردن منو", exact=True)
    ).to_have_attribute("aria-expanded", "false")
    page.get_by_role("button", name="باز کردن منو", exact=True).click()
    page.set_viewport_size({"width": 1440, "height": 1000})
    expect(page.locator(".workspace")).not_to_have_attribute("inert", "")
    checks += 1

    checks += user_and_security_workflows(
        page, context, username, password, customer_id
    )
    return checks


def user_and_security_workflows(
    page, context, username: str, password: str, customer_id: int
) -> int:
    checks = 0
    operator_username = "e2e.operator"
    operator_password = password + "-operator"
    page.goto(BASE_URL + "/users")
    page.get_by_role("button", name="کاربر جدید", exact=True).click()
    form = page.get_by_test_id("user-form")
    form.locator('input[name="username"]').fill(operator_username)
    form.locator('input[name="first_name"]').fill("اپراتور آزمایشی")
    form.locator('input[name="password"]').fill(operator_password)
    form.get_by_role("button", name="ایجاد کاربر", exact=True).click()
    expect(form).to_have_count(0)
    page.get_by_role(
        "button", name=f"ویرایش کاربر {operator_username}", exact=True
    ).click()
    form = page.get_by_test_id("user-form")
    form.locator('input[name="first_name"]').fill("مهسا")
    form.get_by_role("button", name="ذخیره تغییرات", exact=True).click()
    expect(form).to_have_count(0)
    users = assert_api(context.request.get(BASE_URL + "/api/users/"))["results"]
    operator = next(user for user in users if user["username"] == operator_username)
    supervisor = next(user for user in users if user["username"] == username)
    assert operator["role"] == "operator" and operator["first_name"] == "مهسا"
    checks += 1

    page.get_by_role(
        "button", name=f"غیرفعال کردن {operator_username}", exact=True
    ).click()
    page.get_by_role("button", name="بله، غیرفعال شود", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(
        page.get_by_role("button", name=f"فعال کردن {operator_username}", exact=True)
    ).to_be_visible()
    assert not assert_api(
        context.request.get(f"{BASE_URL}/api/users/{operator['id']}/")
    )["is_active"]
    blocked_context = context.browser.new_context()
    try:
        blocked_page = blocked_context.new_page()
        blocked_page.goto(BASE_URL + "/login")
        blocked_form = blocked_page.get_by_test_id("login-form")
        blocked_form.locator('input[name="username"]').fill(operator_username)
        blocked_form.locator('input[name="password"]').fill(operator_password)
        blocked_form.get_by_role("button", name="ورود به مدار").click()
        expect(blocked_form.get_by_role("alert")).to_contain_text("صحیح نیست")
    finally:
        blocked_context.close()
    page.get_by_role(
        "button", name=f"فعال کردن {operator_username}", exact=True
    ).click()
    page.get_by_role("button", name="بله، فعال شود", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(
        page.get_by_role("button", name=f"غیرفعال کردن {operator_username}", exact=True)
    ).to_be_visible()
    checks += 1

    page.get_by_role(
        "button", name=f"تغییر رمز {operator_username}", exact=True
    ).click()
    reset = page.get_by_test_id("reset-password-form")
    operator_password += "-reset"
    reset.locator('input[name="new_password"]').fill(operator_password)
    reset.locator('input[name="confirm_password"]').fill(operator_password)
    reset.get_by_role("button", name="تغییر رمز عبور", exact=True).click()
    expect(reset).to_have_count(0)
    page.get_by_role("button", name="خروج از حساب", exact=True).click()
    expect(page).to_have_url(re.compile(r"/login$"))
    login(page, operator_username, operator_password)
    expect(
        page.get_by_role("navigation").get_by_role(
            "link", name="کاربران و دسترسی", exact=True
        )
    ).to_have_count(0)
    assert_api(context.request.get(BASE_URL + "/api/users/"), 403)
    assert_api(context.request.get(BASE_URL + "/api/audit/"), 403)
    assert_api(context.request.get(BASE_URL + "/api/customers/export/"), 403)
    csrf = assert_api(context.request.get(BASE_URL + "/api/auth/csrf/"))["csrfToken"]
    assert_api(
        context.request.delete(
            f"{BASE_URL}/api/customers/{customer_id}/", headers={"X-CSRFToken": csrf}
        ),
        403,
    )
    assert_api(
        context.request.patch(
            BASE_URL + "/api/auth/me/",
            data={"role": "super_admin"},
            headers={"X-CSRFToken": csrf},
        ),
        400,
    )
    assert (
        assert_api(context.request.get(BASE_URL + "/api/dashboard/"))[
            "recent_activities"
        ]
        == []
    )
    checks += 1

    # Expiration remains informational: operators still see and edit expired
    # customers. The application has no external access-disable functionality.
    today = datetime.now(ZoneInfo("Asia/Tehran")).date()
    page.goto(BASE_URL + "/customers")
    page.get_by_role("button", name="مجموعه جدید", exact=True).click()
    form = page.get_by_test_id("customer-form")
    form.locator('input[name="name"]').fill("مجموعه منقضی آزمایشی")
    form.locator('input[name="manager_name"]').fill("علی احمدی")
    form.locator('input[name="phone"]').fill("09351234567")
    form.locator('input[name="capacity"]').fill("80")
    set_date(page, form, "تاریخ شروع سرویس", today - timedelta(days=90))
    set_date(page, form, "تاریخ پایان سرویس", today - timedelta(days=1))
    form.get_by_role("button", name="ثبت مجموعه", exact=True).click()
    expect(form).to_have_count(0)
    expired = assert_api(
        context.request.get(BASE_URL + "/api/customers/?status=expired")
    )["results"][0]
    assert expired["status"] == "expired"
    page.get_by_role("button", name="ویرایش مجموعه منقضی آزمایشی", exact=True).click()
    form = page.get_by_test_id("customer-form")
    form.locator('input[name="manager_name"]').fill("علی رضایی")
    form.get_by_role("button", name="ذخیره تغییرات", exact=True).click()
    expect(form).to_have_count(0)
    assert (
        assert_api(context.request.get(f"{BASE_URL}/api/customers/{expired['id']}/"))[
            "manager_name"
        ]
        == "علی رضایی"
    )
    assert (
        assert_api(context.request.get(BASE_URL + "/api/dashboard/"))["metrics"][
            "expired_services"
        ]
        == 1
    )
    checks += 1

    page.get_by_role("button", name="خروج از حساب", exact=True).click()
    expect(page).to_have_url(re.compile(r"/login$"))
    login(page, username, password)
    page.goto(BASE_URL + "/users")
    page.get_by_role("button", name=f"غیرفعال کردن {username}", exact=True).click()
    page.get_by_role("button", name="بله، غیرفعال شود", exact=True).click()
    expect(page.get_by_role("dialog").get_by_role("alert")).to_contain_text(
        "آخرین مدیر"
    )
    page.get_by_role("button", name="انصراف", exact=True).click()
    current = assert_api(context.request.get(BASE_URL + "/api/auth/me/"))
    assert current["is_active"] and current["role"] == "super_admin"
    csrf = assert_api(context.request.get(BASE_URL + "/api/auth/csrf/"))["csrfToken"]
    assert_api(
        context.request.patch(
            f"{BASE_URL}/api/users/{supervisor['id']}/",
            data={"role": "operator"},
            headers={"X-CSRFToken": csrf},
        ),
        400,
    )
    assert_api(
        context.request.delete(
            f"{BASE_URL}/api/users/{supervisor['id']}/", headers={"X-CSRFToken": csrf}
        ),
        400,
    )
    page.goto(f"{BASE_URL}/activity?entity_id={customer_id}")
    page.get_by_role("button", name="پاک کردن فیلترها", exact=True).click()
    expect(
        page.get_by_text(f"ایجاد کاربر {operator_username}", exact=True)
    ).to_be_visible()
    page.get_by_label("نوع فعالیت", exact=True).select_option("renew_customer")
    expect(page.get_by_text(re.compile("تمدید خدمت مشتری"))).to_be_visible()
    page.get_by_role("button", name="جزئیات تغییر", exact=True).first.click()
    expect(page.locator(".change-details")).to_contain_text("پایان سرویس")
    checks += 1

    other_context = context.browser.new_context()
    try:
        other_page = other_context.new_page()
        login(other_page, username, password)
        page.goto(BASE_URL + "/profile")
        profile = page.get_by_test_id("profile-form")
        profile.locator('input[name="first_name"]').fill("مدیر آزمایش")
        profile.get_by_role("button", name="ذخیره پروفایل", exact=True).click()
        expect(
            page.get_by_role("status").filter(has_text="پروفایل شما به‌روز شد")
        ).to_be_visible()
        assert (
            assert_api(context.request.get(BASE_URL + "/api/auth/me/"))["first_name"]
            == "مدیر آزمایش"
        )
        new_password = password + "-changed"
        form = page.get_by_test_id("password-form")
        form.locator('input[name="current_password"]').fill(password)
        form.locator('input[name="new_password"]').fill(new_password)
        form.locator('input[name="confirm_password"]').fill(new_password)
        form.get_by_role("button", name="تغییر رمز عبور", exact=True).click()
        expect(
            page.get_by_role("status").filter(
                has_text="رمز عبور شما با موفقیت تغییر کرد"
            )
        ).to_be_visible()
        assert_api(context.request.get(BASE_URL + "/api/auth/me/"))
        assert_api(other_context.request.get(BASE_URL + "/api/auth/me/"), 401)
        page.get_by_role("button", name="خروج از حساب", exact=True).click()
        expect(page).to_have_url(re.compile(r"/login$"))
        login(page, username, new_password)
        assert (
            assert_api(context.request.get(BASE_URL + "/api/dashboard/"))["metrics"][
                "total_customers"
            ]
            == 2
        )
    finally:
        other_context.close()
    checks += 1
    return checks

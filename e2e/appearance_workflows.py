"""Appearance editing through real UI, persistence, tenant sessions and mobile navigation."""

from playwright.sync_api import expect
from workflows import BASE_URL, assert_api, snapshot


def run_appearance_workflows(page, context, artifacts, password):
    from tenant_workflows import portal_login

    page.get_by_role("link", name="تنظیمات ظاهر", exact=False).click()
    expect(page.get_by_role("heading", name="تنظیمات ظاهر", exact=True)).to_be_visible()
    shell = page.locator(".tenant-shell")
    expect(shell).to_have_attribute("data-theme", "light")
    save = page.get_by_role("button", name="ذخیرهٔ تنظیمات ظاهر", exact=True)
    expect(save).to_be_disabled()
    page.get_by_role("button", name="تیره", exact=True).click()
    expect(shell).to_have_attribute("data-theme", "dark")
    for label, color in (
        ("دکمه‌ها و المان‌های اصلی", "#14b8a6"),
        ("پس‌زمینهٔ پنل", "#141822"),
        ("کارت‌ها و فرم‌ها", "#242a3a"),
        ("منوی کناری", "#0b1020"),
    ):
        page.get_by_role("textbox", name=f"کد رنگ {label}", exact=True).fill(color)
    expect(page.locator(".appearance-preview .button.primary")).to_have_css(
        "background-color", "rgb(20, 184, 166)"
    )
    save.click()
    expect(page.get_by_role("status")).to_contain_text("همهٔ کاربران و دستگاه‌های")
    stored = assert_api(
        context.request.get(BASE_URL + "/api/organizations/aftab/appearance/")
    )
    assert stored["mode"] == "dark"
    assert stored["palettes"]["dark"]["primary"] == "#14b8a6"
    page.reload()
    expect(shell).to_have_attribute("data-theme", "dark")
    expect(shell).to_have_css("background-color", "rgb(20, 24, 34)")
    expect(page.locator(".tenant-sidebar")).to_have_css(
        "background-color", "rgb(11, 16, 32)"
    )
    expect(page.locator(".appearance-section").first).to_have_css(
        "background-color", "rgb(36, 42, 58)"
    )
    snapshot(page, artifacts / "appearance-dark.png")

    # Independent cookies and browser storage must still receive the saved theme.
    device = context.browser.new_context(viewport={"width": 1280, "height": 900})
    try:
        other_page = device.new_page()
        portal_login(other_page, "aftab", "hall.manager", password)
        expect(other_page.locator(".tenant-shell")).to_have_attribute(
            "data-theme", "dark"
        )
        expect(other_page.locator(".tenant-card").first).to_have_css(
            "background-color", "rgb(36, 42, 58)"
        )
        portal_login(other_page, "darya", "hall.manager", password + "other")
        expect(other_page.locator(".tenant-shell")).to_have_attribute(
            "data-theme", "light"
        )
        assert (
            assert_api(
                device.request.get(BASE_URL + "/api/organizations/darya/appearance/")
            )["mode"]
            == "light"
        )
    finally:
        device.close()

    # A failed save reports an error, retains the draft and allows a retry.
    page.route(
        "**/api/organizations/aftab/appearance/",
        lambda route: (
            route.fulfill(
                status=503,
                content_type="application/json",
                body='{"detail":"ذخیره موقتاً ممکن نیست"}',
            )
            if route.request.method == "PUT"
            else route.continue_()
        ),
    )
    primary = page.get_by_role(
        "textbox", name="کد رنگ دکمه‌ها و المان‌های اصلی", exact=True
    )
    primary.fill("#f59e0b")
    save.click()
    expect(page.locator(".appearance-page").get_by_role("alert")).to_contain_text(
        "ذخیره موقتاً ممکن نیست"
    )
    expect(primary).to_have_value("#f59e0b")
    page.unroute("**/api/organizations/aftab/appearance/")
    save.click()
    expect(page.get_by_role("status")).to_contain_text("ذخیره شد")
    primary.fill("#22cc88")
    primary.fill("#bad")
    save.click()
    expect(primary).to_have_attribute("aria-invalid", "true")
    assert (
        assert_api(
            context.request.get(BASE_URL + "/api/organizations/aftab/appearance/")
        )["palettes"]["dark"]["primary"]
        == "#f59e0b"
    )
    primary.fill("#14b8a6")
    page.get_by_role("button", name="بازگردانی رنگ‌های این تم").click()
    expect(primary).to_have_value("#a78bfa")
    page.get_by_role("button", name="لغو تغییرات", exact=True).click()
    expect(primary).to_have_value("#f59e0b")

    page.get_by_role("button", name="روشن", exact=True).click()
    expect(primary).to_have_value("#7860cc")
    snapshot(page, artifacts / "appearance-light.png")
    page.get_by_role("button", name="هماهنگ با سیستم", exact=True).click()
    page.emulate_media(color_scheme="dark")
    expect(shell).to_have_attribute("data-theme", "dark")
    page.emulate_media(color_scheme="light")
    expect(shell).to_have_attribute("data-theme", "light")
    save.click()
    expect(page.get_by_role("status")).to_contain_text("ذخیره شد")
    page.reload()
    expect(
        page.get_by_role("button", name="هماهنگ با سیستم", exact=True)
    ).to_have_attribute("aria-pressed", "true")
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
        "Appearance mobile overflow"
    )
    snapshot(page, artifacts / "appearance-mobile.png")
    page.get_by_role("button", name="باز کردن منوی مجموعه").click()
    expect(page.get_by_role("link", name="تنظیمات ظاهر", exact=False)).to_be_visible()
    page.keyboard.press("Escape")
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(BASE_URL + "/aftab/dashboard")
    return 6

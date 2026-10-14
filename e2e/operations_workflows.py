"""Phase 3 acceptance checks: real forms, persisted relations and capacity rules."""

from playwright.sync_api import expect
from workflows import BASE_URL, assert_api, snapshot


def write(context, method, path, data=None, status=200):
    token = assert_api(context.request.get(BASE_URL + "/api/auth/csrf/"))["csrfToken"]
    return assert_api(
        context.request.fetch(
            BASE_URL + path, method=method, data=data, headers={"X-CSRFToken": token}
        ),
        status,
    )


def run_operations_workflows(page, context, organization, artifacts):
    base = "/api/organizations/aftab/"
    checks = 0
    page.get_by_role("link", name="سالن‌ها", exact=True).click()
    expect(page.get_by_role("heading", name="سالن‌ها", exact=True)).to_be_visible()
    for name in ["سالن سپید", "سالن سرو"]:
        page.get_by_role("button", name="سالن جدید", exact=True).click()
        form = page.get_by_test_id("hall-form")
        form.locator('input[name="name"]').fill(name)
        form.locator('textarea[name="description"]').fill("فضایی آرام برای تمرکز")
        form.get_by_role("button", name="ثبت و ذخیره", exact=True).click()
        expect(form).to_have_count(0)
        expect(
            page.get_by_test_id("halls-table").get_by_text(name, exact=True)
        ).to_be_visible()
    halls = assert_api(context.request.get(BASE_URL + base + "halls/options/"))
    white = next(hall for hall in halls if hall["name"] == "سالن سپید")
    cypress = next(hall for hall in halls if hall["name"] == "سالن سرو")
    checks += 1

    page.get_by_role("link", name="پارت‌های مطالعاتی", exact=True).click()
    for title, start, end in [
        ("بعدازظهر", "14:00", "16:00"),
        ("صبح", "08:00", "10:00"),
        ("میانه", "11:00", "13:00"),
    ]:
        page.get_by_role("button", name="پارت جدید", exact=True).click()
        form = page.get_by_test_id("study-session-form")
        form.locator('input[name="title"]').fill(title)
        form.locator('input[name="start_time"]').fill(start)
        form.locator('input[name="end_time"]').fill("07:00")
        form.get_by_role("button", name="ثبت و ذخیره", exact=True).click()
        expect(form.get_by_role("alert")).to_contain_text("بعد از شروع")
        form.locator('input[name="end_time"]').fill(end)
        form.get_by_role("button", name="ثبت و ذخیره", exact=True).click()
        expect(form).to_have_count(0)
    rows = page.get_by_test_id("sessions-table").locator("tbody tr")
    expect(rows).to_have_count(3)
    assert [row.locator("td").nth(1).inner_text() for row in rows.all()] == [
        "۰۸:۰۰",
        "۱۱:۰۰",
        "۱۴:۰۰",
    ]
    checks += 1

    page.get_by_role("link", name="تخصیص پارت‌ها", exact=True).first.click()
    page.get_by_role("button", name="انتخاب همه", exact=True).click()
    page.get_by_role(
        "checkbox", name="سالن سپید، بعدازظهر، ۱۴:۰۰", exact=True
    ).uncheck()
    page.get_by_role("button", name="ذخیره تخصیص‌ها", exact=True).click()
    expect(page.get_by_text("تخصیص‌ها ذخیره شدند.", exact=True)).to_be_visible()
    assert (
        len(
            assert_api(context.request.get(BASE_URL + base + "assignments/"))[
                "assignments"
            ]
        )
        == 5
    )
    page.reload()
    expect(
        page.get_by_role("checkbox", name="سالن سپید، صبح، ۰۸:۰۰", exact=True)
    ).to_be_checked()
    expect(
        page.get_by_role("checkbox", name="سالن سپید، بعدازظهر، ۱۴:۰۰", exact=True)
    ).not_to_be_checked()
    snapshot(page, artifacts / "operations-matrix.png")
    checks += 1

    def fill_student(identifier, first_name, grade="12"):
        page.get_by_role("button", name="ثبت دانش‌آموز", exact=True).first.click()
        form = page.get_by_test_id("student-form")
        for field, value in {
            "identifier": identifier,
            "desk_number": "7",
            "first_name": first_name,
            "last_name": "احمدی",
            "primary_phone": "۰۹۱۲۳۴۵۶۷۸۹",
            "secondary_phone": "09351234567",
        }.items():
            form.locator(f'input[name="{field}"]').fill(value)
        form.locator('select[name="grade"]').select_option(grade)
        form.locator('select[name="major"]').select_option("experimental")
        form.locator('select[name="hall"]').select_option(str(white["id"]))
        form.get_by_role("button", name="ثبت و ذخیره", exact=True).click()
        return form

    page.get_by_role("link", name="دانش‌آموزان", exact=True).click()
    expect(fill_student("ST-100", "سارا")).to_have_count(0)
    expect(fill_student("ST-200", "نگار", "11")).to_have_count(0)
    form = fill_student("ST-100", "تکراری")
    expect(form.get_by_role("alert")).to_contain_text("ثبت شده")
    page.get_by_role("button", name="بستن پنجره", exact=True).click()
    search = page.get_by_role("textbox", name="جست‌وجوی دانش‌آموز")
    search.fill("سارا")
    expect(page.get_by_test_id("students-table").locator("tbody tr")).to_have_count(1)
    search.fill("۷")
    expect(page.get_by_test_id("students-table").locator("tbody tr")).to_have_count(2)
    search.fill("")
    students = assert_api(context.request.get(BASE_URL + base + "students/"))["results"]
    first = next(student for student in students if student["identifier"] == "ST-100")
    next(student for student in students if student["identifier"] == "ST-200")
    page.get_by_role("link", name="جزئیات ST-100", exact=True).click()
    expect(
        page.get_by_role("heading", name="سارا احمدی", exact=True).first
    ).to_be_visible()
    expect(page.get_by_text("رشته تحصیلی", exact=True)).to_be_visible()
    checks += 1

    write(context, "PATCH", f"/api/customers/{organization['id']}/", {"capacity": 1})
    page.goto(BASE_URL + "/aftab/dashboard")
    expect(
        page.get_by_text("تعداد ثبت‌نام از ظرفیت فعلی بیشتر است.", exact=True)
    ).to_be_visible()
    expect(page.get_by_test_id("ops-students-purple")).to_have_text("۲")
    expect(page.get_by_test_id("ops-students-turquoise")).to_have_text("۰")
    page.goto(BASE_URL + "/aftab/students")
    form = fill_student("ST-300", "اضافی")
    expect(form.get_by_role("alert")).to_contain_text("ظرفیت فعال مجموعه تکمیل")
    page.get_by_role("button", name="بستن پنجره", exact=True).click()
    page.get_by_role("button", name="ویرایش ST-100", exact=True).click()
    form = page.get_by_test_id("student-form")
    form.locator('select[name="hall"]').select_option(str(cypress["id"]))
    form.locator('input[name="last_name"]').fill("رضایی")
    form.get_by_role("button", name="ذخیره تغییرات", exact=True).click()
    expect(form).to_have_count(0)
    assert assert_api(context.request.get(BASE_URL + base + "students/"))["count"] == 2
    checks += 1

    page.get_by_role("button", name="بایگانی ST-100", exact=True).click()
    page.get_by_role("button", name="بایگانی شود", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    page.get_by_role("combobox", name="وضعیت دانش‌آموزان").select_option("archived")
    page.get_by_role("button", name="بازیابی ST-100", exact=True).click()
    expect(page.locator(".ops-page .form-error")).to_contain_text(
        "ظرفیت فعال مجموعه تکمیل"
    )
    page.get_by_role("combobox", name="وضعیت دانش‌آموزان").select_option("active")
    page.get_by_role("button", name="بایگانی ST-200", exact=True).click()
    page.get_by_role("button", name="بایگانی شود", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    page.get_by_role("combobox", name="وضعیت دانش‌آموزان").select_option("archived")
    page.get_by_role("button", name="بازیابی ST-100", exact=True).click()
    expect(page.get_by_role("button", name="بازیابی ST-100", exact=True)).to_have_count(
        0
    )
    write(context, "PATCH", f"/api/customers/{organization['id']}/", {"capacity": 120})
    page.get_by_role("button", name="بازیابی ST-200", exact=True).click()
    expect(page.get_by_role("button", name="بازیابی ST-200", exact=True)).to_have_count(
        0
    )
    checks += 1

    page.get_by_role("combobox", name="وضعیت دانش‌آموزان").select_option("active")
    page.get_by_role("checkbox", name="انتخاب همهٔ دانش‌آموزان این صفحه").check()
    page.get_by_role("button", name="انتقال به سالن", exact=True).click()
    page.get_by_role("combobox", name="سالن مقصد").select_option(str(cypress["id"]))
    page.get_by_role("button", name="تأیید عملیات گروهی", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    assert all(
        student["hall"] == cypress["id"]
        for student in assert_api(context.request.get(BASE_URL + base + "students/"))[
            "results"
        ]
    )
    page.get_by_role("link", name="سالن‌ها", exact=True).click()
    occupied = (
        page.get_by_test_id("halls-table")
        .locator("tbody tr")
        .filter(has_text="سالن سرو")
    )
    occupied.get_by_role("button", name="بایگانی", exact=True).click()
    page.get_by_role("button", name="بایگانی شود", exact=True).click()
    expect(page.get_by_role("dialog").get_by_role("alert")).to_contain_text(
        "دانش‌آموزان فعال"
    )
    page.get_by_role("button", name="انصراف", exact=True).click()
    empty = (
        page.get_by_test_id("halls-table")
        .locator("tbody tr")
        .filter(has_text="سالن سپید")
    )
    empty.get_by_role("button", name="بایگانی", exact=True).click()
    page.get_by_role("button", name="بایگانی شود", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    page.get_by_role("combobox", name="وضعیت نمایش").select_option("archived")
    page.get_by_role("button", name="بازیابی", exact=True).click()
    expect(page.get_by_role("button", name="بازیابی", exact=True)).to_have_count(0)
    assignments = assert_api(context.request.get(BASE_URL + base + "assignments/"))[
        "assignments"
    ]
    assert not any(pair["hall"] == white["id"] for pair in assignments)
    checks += 1

    for index in range(19):
        write(
            context,
            "POST",
            base + "students/",
            {
                "identifier": f"EXTRA-{index:02}",
                "first_name": "آزمون",
                "last_name": str(index),
                "primary_phone": "09123456789",
                "grade": 10,
                "major": "mathematics",
                "hall": white["id"],
                "desk_number": "99",
            },
            201,
        )
    page.goto(BASE_URL + "/aftab/students")
    expect(page.get_by_test_id("students-table").locator("tbody tr")).to_have_count(20)
    page.get_by_role("button", name="صفحه بعد", exact=True).click()
    expect(page.get_by_test_id("students-table").locator("tbody tr")).to_have_count(1)
    # Archiving the final row of the final page must return to a valid page.
    page.get_by_role("button", name="بایگانی ST-100", exact=True).click()
    page.get_by_role("button", name="بایگانی شود", exact=True).click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(page.get_by_test_id("students-table").locator("tbody tr")).to_have_count(20)
    write(context, "POST", base + f"students/{first['id']}/restore/", {})
    page.reload()
    page.get_by_role("combobox", name="فیلتر پایه").select_option("10")
    expect(page.get_by_test_id("students-table").locator("tbody tr")).to_have_count(19)
    page.get_by_role("combobox", name="مرتب‌سازی دانش‌آموزان").select_option("identifier")
    expect(
        page.get_by_test_id("students-table").locator("tbody tr").first
    ).to_contain_text("EXTRA-00")
    snapshot(page, artifacts / "operations-students.png")
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
        "Students mobile overflow"
    )
    snapshot(page, artifacts / "operations-students-mobile.png")
    page.goto(BASE_URL + "/aftab/assignments")
    expect(page.locator(".ops-matrix")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
        "Matrix mobile overflow"
    )
    page.set_viewport_size({"width": 1440, "height": 1000})
    checks += 1

    for suffix in ["halls/", "study-sessions/", "students/", "assignments/"]:
        assert_api(
            context.request.get(BASE_URL + "/api/organizations/darya/" + suffix), 403
        )
    page.goto(BASE_URL + "/darya/students")
    expect(
        page.get_by_role("heading", name="این فضا متعلق به مجموعهٔ دیگری است")
    ).to_be_visible()
    expect(page.get_by_test_id("students-table")).to_have_count(0)
    page.goto(BASE_URL + "/aftab/dashboard")
    expect(page.get_by_test_id("ops-students-purple")).to_have_text("۲۱")
    snapshot(page, artifacts / "operations-dashboard.png")
    checks += 1
    return checks

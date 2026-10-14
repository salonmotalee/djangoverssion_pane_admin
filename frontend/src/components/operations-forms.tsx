"use client";
import { useState } from "react";
import { mutate } from "@/lib/api";
import { isIranianPhone, latinDigits } from "@/lib/format";
import {
  grades,
  majors,
  type Hall,
  type Student,
  type StudySession,
} from "@/lib/operations";
import { Field, InlineError, Modal, Submit } from "./ui";

type DialogProps = { onClose: () => void; onSaved: () => void };

function EditDialog({
  title,
  testid,
  endpoint,
  recordId,
  children,
  build,
  onClose,
  onSaved,
  wide = false,
}: DialogProps & {
  title: string;
  testid: string;
  endpoint: string;
  recordId?: number;
  children: React.ReactNode;
  build: (form: FormData) => unknown;
  wide?: boolean;
}) {
  const [pending, setPending] = useState(false),
    [error, setError] = useState<string | null>(null);
  return (
    <Modal
      title={title}
      description="اطلاعات فقط در فضای همین مجموعه ذخیره می‌شود."
      onClose={() => {
        if (!pending) onClose();
      }}
      wide={wide}
    >
      <form
        data-testid={testid}
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          setError(null);
          setPending(true);
          try {
            await mutate(
              endpoint + (recordId ? `${recordId}/` : ""),
              recordId ? "PATCH" : "POST",
              build(form),
            );
            onSaved();
          } catch (error) {
            setError((error as Error).message);
          } finally {
            setPending(false);
          }
        }}
      >
        <fieldset disabled={pending} className="ops-form-fields">
          {children}
        </fieldset>
        <InlineError message={error} />
        <div className="modal-footer">
          <button
            type="button"
            className="button secondary"
            onClick={onClose}
            disabled={pending}
          >
            انصراف
          </button>
          <Submit pending={pending}>
            {recordId ? "ذخیره تغییرات" : "ثبت و ذخیره"}
          </Submit>
        </div>
      </form>
    </Modal>
  );
}

export function HallForm({
  slug,
  hall,
  ...dialog
}: DialogProps & { slug: string; hall?: Hall }) {
  return (
    <EditDialog
      {...dialog}
      title={hall ? "ویرایش سالن" : "سالن جدید"}
      testid="hall-form"
      endpoint={`organizations/${slug}/halls/`}
      recordId={hall?.id}
      build={(form) => ({
        name: form.get("name"),
        description: form.get("description"),
      })}
    >
      <Field label="نام سالن" required>
        <input
          name="name"
          required
          maxLength={160}
          defaultValue={hall?.name}
          placeholder="مثلاً سالن سپید"
        />
      </Field>
      <Field label="توضیحات">
        <textarea
          name="description"
          maxLength={2000}
          rows={3}
          defaultValue={hall?.description}
          placeholder="توضیحات و ویژگی‌های سالن"
        />
      </Field>
      <p className="ops-form-note">
        ظرفیت دانش‌آموزان در سطح کل مجموعه محاسبه می‌شود و محدودیت جداگانه‌ای
        برای سالن وجود ندارد.
      </p>
    </EditDialog>
  );
}

export function StudySessionForm({
  slug,
  session,
  ...dialog
}: DialogProps & { slug: string; session?: StudySession }) {
  return (
    <EditDialog
      {...dialog}
      title={session ? "ویرایش پارت مطالعاتی" : "پارت مطالعاتی جدید"}
      testid="study-session-form"
      endpoint={`organizations/${slug}/study-sessions/`}
      recordId={session?.id}
      build={(form) => {
        const start = String(form.get("start_time")),
          end = String(form.get("end_time"));
        if (end <= start)
          throw new Error("ساعت پایان باید بعد از شروع، در همان روز باشد.");
        return { title: form.get("title"), start_time: start, end_time: end };
      }}
    >
      <Field label="عنوان پارت" hint="اختیاری؛ مانند مطالعهٔ صبح">
        <input name="title" maxLength={160} defaultValue={session?.title} />
      </Field>
      <div className="form-grid">
        <Field label="ساعت شروع" required>
          <input
            name="start_time"
            type="time"
            step={60}
            required
            dir="ltr"
            defaultValue={session?.start_time.slice(0, 5)}
          />
        </Field>
        <Field label="ساعت پایان" required>
          <input
            name="end_time"
            type="time"
            step={60}
            required
            dir="ltr"
            defaultValue={session?.end_time.slice(0, 5)}
          />
        </Field>
      </div>
      <p className="ops-form-note">
        هر پارت در یک روز پایان می‌یابد. پارت‌ها مستقل از سالن‌اند؛ پس از ثبت،
        آن‌ها را از صفحهٔ تخصیص به سالن‌ها اضافه کنید.
      </p>
    </EditDialog>
  );
}

export function StudentForm({
  slug,
  student,
  halls,
  ...dialog
}: DialogProps & { slug: string; student?: Student; halls: Hall[] }) {
  return (
    <EditDialog
      {...dialog}
      wide
      title={student ? "ویرایش دانش‌آموز" : "ثبت دانش‌آموز"}
      testid="student-form"
      endpoint={`organizations/${slug}/students/`}
      recordId={student?.id}
      build={(form) => {
        const primary = latinDigits(String(form.get("primary_phone"))),
          secondary = latinDigits(String(form.get("secondary_phone") || ""));
        if (
          !isIranianPhone(primary) ||
          (secondary && !isIranianPhone(secondary))
        )
          throw new Error(
            "شماره همراه معتبر ایران وارد کنید؛ مانند ۰۹۱۲۳۴۵۶۷۸۹.",
          );
        return {
          identifier: latinDigits(String(form.get("identifier"))).trim(),
          desk_number: latinDigits(
            String(form.get("desk_number") || ""),
          ).trim(),
          first_name: form.get("first_name"),
          last_name: form.get("last_name"),
          primary_phone: primary,
          secondary_phone: secondary,
          grade: Number(form.get("grade")),
          major: form.get("major"),
          hall: Number(form.get("hall")),
        };
      }}
    >
      <div className="ops-form-section">
        <span>۰۱</span>
        <div>
          <h3>مشخصات دانش‌آموز</h3>
          <p>شناسه در مجموعه یکتا است؛ شماره میز می‌تواند تکراری باشد.</p>
        </div>
      </div>
      <div className="form-grid">
        <Field label="شناسه دانش‌آموز" required>
          <input
            name="identifier"
            required
            maxLength={64}
            defaultValue={student?.identifier}
          />
        </Field>
        <Field label="شماره میز">
          <input
            name="desk_number"
            maxLength={30}
            defaultValue={student?.desk_number}
          />
        </Field>
        <Field label="نام" required>
          <input
            name="first_name"
            required
            maxLength={100}
            defaultValue={student?.first_name}
            autoComplete="given-name"
          />
        </Field>
        <Field label="نام خانوادگی" required>
          <input
            name="last_name"
            required
            maxLength={100}
            defaultValue={student?.last_name}
            autoComplete="family-name"
          />
        </Field>
        <Field label="شماره همراه اصلی" required>
          <input
            name="primary_phone"
            required
            type="tel"
            dir="ltr"
            maxLength={24}
            defaultValue={student?.primary_phone}
            placeholder="09123456789"
          />
        </Field>
        <Field label="شماره همراه دوم">
          <input
            name="secondary_phone"
            type="tel"
            dir="ltr"
            maxLength={24}
            defaultValue={student?.secondary_phone}
          />
        </Field>
      </div>
      <div className="ops-form-section">
        <span>۰۲</span>
        <div>
          <h3>مسیر مطالعه</h3>
          <p>پایه، رشته و سالن دانش‌آموز را مشخص کنید.</p>
        </div>
      </div>
      <div className="form-grid">
        <Field label="پایه تحصیلی" required>
          <select name="grade" required defaultValue={student?.grade || ""}>
            <option value="" disabled>
              انتخاب پایه
            </option>
            {Object.entries(grades).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="رشته تحصیلی" required>
          <select name="major" required defaultValue={student?.major || ""}>
            <option value="" disabled>
              انتخاب رشته
            </option>
            {Object.entries(majors).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="سالن" required>
          <select name="hall" required defaultValue={student?.hall || ""}>
            <option value="" disabled>
              انتخاب سالن
            </option>
            {student && !halls.some((hall) => hall.id === student.hall) && (
              <option value={student.hall}>
                {student.hall_name} (بایگانی)
              </option>
            )}
            {halls.map((hall) => (
              <option key={hall.id} value={hall.id}>
                {hall.name}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <p className="ops-form-note">
        {student
          ? "ویرایش اطلاعات و انتقال به سالن دیگر ظرفیت جدید مصرف نمی‌کند."
          : "ثبت دانش‌آموز فعال فقط تا سقف ظرفیت مجموعه امکان‌پذیر است."}
      </p>
    </EditDialog>
  );
}

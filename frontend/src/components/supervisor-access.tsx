"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Check,
  Copy,
  Eye,
  EyeOff,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";
import { mutate } from "@/lib/api";
import { date } from "@/lib/format";
import type { SupervisorAccess } from "@/lib/staff";
import type { Supervisor } from "@/lib/supervisors";
import { useData } from "@/lib/use-data";
import { HelpTooltip } from "./help-tooltip";
import {
  Empty,
  ErrorState,
  Field,
  InlineError,
  Modal,
  Panel,
  Spinner,
  Submit,
} from "./ui";
import "./supervisor-portal.css";

function AccessForm({
  slug,
  supervisor,
  access,
  onClose,
  onSaved,
}: {
  slug: string;
  supervisor: Supervisor;
  access: SupervisorAccess;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [enabled, setEnabled] = useState(access.enabled);
  const [visible, setVisible] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal
      title="دسترسی پنل مراقب"
      description={`${supervisor.first_name} ${supervisor.last_name}`}
      onClose={() => !pending && onClose()}
    >
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          const values = new FormData(event.currentTarget);
          const password = String(values.get("password") || "");
          setPending(true);
          setError(null);
          try {
            await mutate(
              `organizations/${slug}/supervisor-access/${supervisor.id}/`,
              "PUT",
              { enabled, ...(password ? { password } : {}) },
            );
            onSaved();
          } catch (error) {
            setError((error as Error).message);
          } finally {
            setPending(false);
          }
        }}
      >
        <InlineError message={error} />
        <fieldset className="staff-access-fields" disabled={pending}>
          <legend className="sr-only">تنظیمات حساب مراقب</legend>
          <div className="staff-access-identity">
            <LockKeyhole size={22} />
            <div>
              <small>نام کاربری (شماره همراه)</small>
              <strong dir="ltr">{supervisor.phone}</strong>
            </div>
          </div>
          <label className="staff-switch">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(event) => setEnabled(event.target.checked)}
            />
            <span>دسترسی به پنل مراقب فعال باشد</span>
          </label>
          <Field
            label={access.provisioned ? "رمز عبور جدید" : "رمز عبور اولیه"}
            required={enabled && !access.provisioned}
            hint="حداقل ۱۰ کاراکتر؛ از رمز رایج یا مشابه شماره همراه استفاده نکنید."
          >
            <div className="staff-password-field">
              <input
                name="password"
                type={visible ? "text" : "password"}
                minLength={10}
                maxLength={4096}
                autoComplete="new-password"
                dir="ltr"
                required={enabled && !access.provisioned}
                disabled={!enabled}
              />
              <button
                className="icon-button"
                type="button"
                aria-label={visible ? "پنهان کردن رمز" : "نمایش رمز"}
                aria-pressed={visible}
                disabled={!enabled}
                onClick={() => setVisible(!visible)}
              >
                {visible ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </Field>
          {access.provisioned && enabled && (
            <small className="staff-muted">
              برای حفظ رمز فعلی، این قسمت را خالی بگذارید.
            </small>
          )}
          <div className="staff-access-halls">
            <strong>سالن‌های مجاز</strong>
            {access.halls.length ? (
              access.halls.map((hall) => <span key={hall.id}>{hall.name}</span>)
            ) : (
              <small>هنوز سالنی واگذار نشده است.</small>
            )}
          </div>
          {!enabled && (
            <p className="staff-warning">
              با غیرفعال‌سازی، نشست‌های قبلی مراقب نیز دسترسی نخواهند داشت.
            </p>
          )}
        </fieldset>
        <div className="modal-footer">
          <button
            type="button"
            className="button secondary"
            disabled={pending}
            onClick={onClose}
          >
            انصراف
          </button>
          <Submit pending={pending} />
        </div>
      </form>
    </Modal>
  );
}

export function SupervisorAccessPanel({
  slug,
  supervisor,
}: {
  slug: string;
  supervisor: Supervisor;
}) {
  const data = useData<SupervisorAccess>(
    `organizations/${slug}/supervisor-access/${supervisor.id}/`,
  );
  const [edit, setEdit] = useState(false);
  const [notice, setNotice] = useState("");
  const status = data.data?.usable
    ? "فعال"
    : data.data?.enabled
      ? "نیازمند بررسی پرونده"
      : data.data?.provisioned
        ? "غیرفعال"
        : "ایجاد نشده";
  return (
    <Panel
      title="حساب ورود مراقب"
      action={
        <HelpTooltip
          label="راهنمای حساب مراقب"
          content="شماره تماس پرونده‌ها می‌تواند تکراری باشد؛ در هر مجموعه فقط یک حساب ورود فعال برای هر شماره همراه مجاز است. سالن‌ها از پروندهٔ مراقب تعیین می‌شوند و ساعت شیفت، دسترسی را محدود نمی‌کند."
        />
      }
    >
      {notice && (
        <div className="staff-success" role="status">
          <Check size={16} />
          {notice}
        </div>
      )}
      {data.error ? (
        <ErrorState error={data.error} retry={data.refresh} />
      ) : data.loading && !data.data ? (
        <Spinner />
      ) : data.data ? (
        <div className="staff-access-panel">
          <div className="staff-access-identity">
            <ShieldCheck size={27} />
            <div>
              <strong>{status}</strong>
              <small dir="ltr">{data.data.phone}</small>
            </div>
          </div>
          <dl>
            <div>
              <dt>آخرین ورود</dt>
              <dd>
                {date(data.data.last_login, {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </dd>
            </div>
            <div>
              <dt>سالن‌های مجاز</dt>
              <dd>
                {data.data.halls.map((h) => h.name).join("، ") || "بدون سالن"}
              </dd>
            </div>
          </dl>
          {data.data.enabled && !data.data.usable && (
            <p className="staff-warning">
              فعال‌بودن پرونده، شماره همراه حساب و سالن‌های مسئولیت را بررسی
              کنید. در صورت تغییر شماره، تنظیمات دسترسی را دوباره ذخیره کنید.
            </p>
          )}
          <div className="staff-access-actions">
            <button className="button primary" onClick={() => setEdit(true)}>
              <LockKeyhole size={16} />
              مدیریت دسترسی / رمز
            </button>
            <button
              className="button secondary"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(
                    `${window.location.origin}/${slug}/supervisor/login`,
                  );
                  setNotice("نشانی ورود کپی شد.");
                } catch {
                  setNotice(`نشانی ورود: /${slug}/supervisor/login`);
                }
              }}
            >
              <Copy size={16} />
              کپی نشانی ورود
            </button>
            <Link
              className="text-link"
              href={`/${slug}/supervisor/login`}
              target="_blank"
              rel="noopener noreferrer"
            >
              صفحهٔ ورود
            </Link>
          </div>
          {!supervisor.is_active || supervisor.archived_at ? (
            <small className="staff-muted">
              برای فعال‌کردن دسترسی، ابتدا پروندهٔ مراقب را فعال کنید.
            </small>
          ) : null}
        </div>
      ) : (
        <Empty title="حساب در دسترس نیست" description="دوباره تلاش کنید." />
      )}
      {edit && data.data && (
        <AccessForm
          slug={slug}
          supervisor={supervisor}
          access={data.data}
          onClose={() => setEdit(false)}
          onSaved={() => {
            setEdit(false);
            data.refresh();
            setNotice("تنظیمات دسترسی ذخیره شد.");
          }}
        />
      )}
    </Panel>
  );
}

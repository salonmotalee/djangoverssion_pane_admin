"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Bell,
  CalendarClock,
  ChevronDown,
  Clock3,
  Download,
  History,
  KeyRound,
  Search,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { mutate, resetCsrf } from "@/lib/api";
import {
  date,
  displayName,
  number,
  queryString,
  roles,
  safeExportName,
  time,
} from "@/lib/format";
import type { Audit, Customer, Paginated, User } from "@/lib/types";
import { useData } from "@/lib/use-data";
import { useAuth, useToast } from "./providers";
import {
  DateField,
  Empty,
  ErrorState,
  Field,
  InlineError,
  PageHeading,
  Pagination,
  Panel,
  Spinner,
  Submit,
} from "./ui";

function businessDate(days = 0) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(
    parts.map((part) => [part.type, part.value]),
  );
  const value = new Date(
    `${values.year}-${values.month}-${values.day}T12:00:00Z`,
  );
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}
export function Alerts() {
  const { user } = useAuth();
  const toast = useToast();
  const [range, setRange] = useState(30);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const [exporting, setExporting] = useState(false);
  const query = queryString({
    status: from || to ? "" : "expiring",
    expiration_date_from: from || businessDate(),
    expiration_date_to: to || businessDate(range),
    ordering: "expiration_date",
  });
  const { data, error, loading, refresh } = useData<Paginated<Customer>>(
    `customers/?${query}&page=${page}&page_size=20`,
  );
  return (
    <>
      <PageHeading
        eyebrow="همیشه یک قدم جلوتر"
        title="هشدارهای سرویس"
        description="سررسیدهای نزدیک را ببینید و برای ادامه همکاری آماده باشید."
      >
        {user?.role !== "operator" && (
          <button
            className="button secondary"
            disabled={exporting}
            onClick={async () => {
              setExporting(true);
              try {
                const response = await fetch(
                  `/api/customers/export/?${query}`,
                  { credentials: "include" },
                );
                if (!response.ok) throw new Error("دریافت گزارش ناموفق بود.");
                const url = URL.createObjectURL(await response.blob());
                const link = document.createElement("a");
                link.href = url;
                link.download = safeExportName();
                link.click();
                URL.revokeObjectURL(url);
                toast("گزارش سررسیدها دریافت شد.");
              } catch (error) {
                toast((error as Error).message, "error");
              } finally {
                setExporting(false);
              }
            }}
          >
            <Download size={17} />
            {exporting ? "در حال دریافت…" : "خروجی گزارش"}
          </button>
        )}
      </PageHeading>
      <div className="alert-banner">
        <span>
          <Bell size={25} />
        </span>
        <div>
          <strong>یادآوری برای پیگیری، با خیال آسوده</strong>
          <p>
            انقضای سرویس تنها جنبه اطلاع‌رسانی دارد. هیچ دسترسی‌ای به‌صورت
            خودکار غیرفعال نمی‌شود.
          </p>
        </div>
        <ShieldCheck size={31} />
      </div>
      <section className="panel table-panel">
        <div className="alerts-toolbar">
          <div className="segmented">
            <button
              className={range === 7 && !from && !to ? "active" : ""}
              onClick={() => {
                setRange(7);
                setFrom("");
                setTo("");
                setPage(1);
              }}
            >
              <Clock3 size={16} />۷ روز آینده
            </button>
            <button
              className={range === 30 && !from && !to ? "active" : ""}
              onClick={() => {
                setRange(30);
                setFrom("");
                setTo("");
                setPage(1);
              }}
            >
              <CalendarClock size={16} />
              ۳۰ روز آینده
            </button>
          </div>
          <span className="alert-count">
            {data ? number(data.count) : "—"} مجموعه در این بازه
          </span>
        </div>
        <div className="filter-panel">
          <DateField
            label="پایان سرویس از تاریخ"
            value={from}
            onChange={(value) => {
              setFrom(value);
              setPage(1);
            }}
          />
          <DateField
            label="پایان سرویس تا تاریخ"
            value={to}
            onChange={(value) => {
              setTo(value);
              setPage(1);
            }}
          />
          <small>بازه پیش‌فرض بر اساس امروز در تهران محاسبه می‌شود.</small>
        </div>
        {error ? (
          <ErrorState error={error} retry={refresh} />
        ) : loading && !data ? (
          <Spinner />
        ) : data?.results.length ? (
          <div className={`table-scroll ${loading ? "refreshing" : ""}`}>
            <table>
              <thead>
                <tr>
                  <th>مجموعه</th>
                  <th>مدیر مجموعه</th>
                  <th>پایان سرویس</th>
                  <th>زمان باقی‌مانده</th>
                  <th>پیگیری</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link
                        className="customer-name"
                        href={`/customers/${item.id}`}
                      >
                        <span className="collection-avatar small">
                          {item.name.slice(0, 1)}
                        </span>
                        <strong>{item.name}</strong>
                      </Link>
                    </td>
                    <td>
                      <div className="table-person">
                        <strong>{item.manager_name}</strong>
                        <a dir="ltr" href={`tel:${item.phone}`}>
                          {item.phone}
                        </a>
                      </div>
                    </td>
                    <td>{date(item.expiration_date)}</td>
                    <td>
                      <span
                        className={`remaining ${item.days_remaining <= 7 ? "urgent" : ""}`}
                      >
                        {number(item.subscription.remaining_days)} روز
                        باقی‌مانده
                      </span>
                    </td>
                    <td>
                      <Link
                        className="button secondary compact"
                        href={`/customers/${item.id}`}
                      >
                        <CalendarClock size={15} />
                        بررسی و تمدید
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="در این بازه سررسیدی ندارید"
            description="می‌توانید بازه زمانی را تغییر دهید یا بعداً دوباره بررسی کنید."
          />
        )}
        {data && <Pagination count={data.count} page={page} onPage={setPage} />}
      </section>
    </>
  );
}
const auditActionNames: Record<string, string> = {
  configure_portal: "تنظیم ورود پرتال",
  portal_login: "ورود مجموعه",
  portal_logout: "خروج مجموعه",
  create_customer: "ایجاد مجموعه",
  update_customer: "ویرایش مجموعه",
  delete_customer: "حذف مجموعه",
  restore_customer: "بازیابی مجموعه",
  renew_customer: "تمدید سرویس",
  create_user: "ایجاد کاربر",
  update_user: "ویرایش کاربر",
  delete_user: "حذف کاربر",
  update_profile: "ویرایش پروفایل",
  change_password: "تغییر رمز شخصی",
  reset_password: "بازنشانی رمز",
  login: "ورود",
  logout: "خروج",
};
const changeLabels: Record<string, string> = {
  slug: "نشانی اختصاصی",
  capacity: "ظرفیت مجموعه",
  name: "نام مجموعه",
  manager_name: "نام مدیر",
  phone: "تلفن",
  identifier: "شناسه",
  start_date: "شروع سرویس",
  expiration_date: "پایان سرویس",
  deleted_at: "حذف",
  first_name: "نام",
  last_name: "نام خانوادگی",
  role: "نقش",
  is_active: "فعال بودن",
  email: "ایمیل",
  username: "نام کاربری",
};
function changeValue(key: string, value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (
    [
      "start_date",
      "expiration_date",
      "deleted_at",
      "created_at",
      "updated_at",
    ].includes(key)
  )
    return date(String(value));
  if (key === "role")
    return roles[value as keyof typeof roles] || String(value);
  if (typeof value === "boolean") return value ? "فعال" : "غیرفعال";
  return String(value);
}
function ChangeDetails({ changes }: { changes: Record<string, unknown> }) {
  const entries = Object.entries(changes);
  return (
    <div className="change-details">
      {entries.length ? (
        entries.map(([key, value]) => {
          const pair =
            value && typeof value === "object"
              ? (value as { before?: unknown; after?: unknown })
              : { after: value };
          const ltr = ["phone", "identifier", "email", "username"].includes(
            key,
          );
          return (
            <div key={key}>
              <strong>{changeLabels[key] || key}</strong>
              <span className="change-before">
                قبل:{" "}
                <bdi dir={ltr ? "ltr" : "auto"}>
                  {changeValue(key, pair.before)}
                </bdi>
              </span>
              <span className="change-after">
                بعد:{" "}
                <bdi dir={ltr ? "ltr" : "auto"}>
                  {changeValue(key, pair.after)}
                </bdi>
              </span>
            </div>
          );
        })
      ) : (
        <p>جزئیات تکمیلی برای این فعالیت ثبت نشده است.</p>
      )}
    </div>
  );
}
export function Activity() {
  const { user } = useAuth();
  const params = useSearchParams();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [entity, setEntity] = useState(
    params.get("entity_id") ? "customer" : "",
  );
  const [entityId, setEntityId] = useState(params.get("entity_id") || "");
  const [action, setAction] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<number | null>(null);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebounced(search);
      setPage(1);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [search]);
  const { data, error, loading, refresh } = useData<Paginated<Audit>>(
    user?.role !== "operator"
      ? `audit/?${queryString({ search: debounced, entity_type: entity, entity_id: entityId, action, date_from: from, date_to: to, page, page_size: 20 })}`
      : null,
  );
  if (user?.role === "operator")
    return (
      <ErrorState error="مشاهده تاریخچه مدیریتی فقط برای مدیران مجاز است." />
    );
  return (
    <>
      {entityId && (
        <div className="scope-note">
          نمایش فعالیت‌های یک مجموعه{" "}
          <button
            className="text-link"
            onClick={() => {
              setEntityId("");
              setEntity("");
              setPage(1);
            }}
          >
            مشاهده همه فعالیت‌ها
          </button>
        </div>
      )}
      <PageHeading
        eyebrow="شفاف، دقیق، قابل پیگیری"
        title="تاریخچه فعالیت‌ها"
        description="هر تغییر یک رد روشن دارد؛ ببینید چه کسی، چه زمانی، چه کاری انجام داده است."
      />
      <section className="panel table-panel">
        <div className="table-toolbar">
          <div className="search-box">
            <Search size={18} />
            <input
              aria-label="جستجوی فعالیت‌ها"
              placeholder="جستجوی شرح فعالیت یا نام کاربر…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div className="table-filters">
            <select
              aria-label="موضوع فعالیت"
              value={entity}
              onChange={(event) => {
                setEntity(event.target.value);
                setEntityId("");
                setPage(1);
              }}
            >
              <option value="">همه موضوع‌ها</option>
              <option value="customer">مجموعه‌ها</option>
              <option value="user">کاربران</option>
            </select>
            <select
              aria-label="نوع فعالیت"
              value={action}
              onChange={(event) => {
                setAction(event.target.value);
                setPage(1);
              }}
            >
              <option value="">همه فعالیت‌ها</option>
              {Object.entries(auditActionNames).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="filter-panel">
          <DateField
            label="فعالیت از تاریخ"
            value={from}
            onChange={(value) => {
              setFrom(value);
              setPage(1);
            }}
          />
          <DateField
            label="تا تاریخ"
            value={to}
            onChange={(value) => {
              setTo(value);
              setPage(1);
            }}
          />
          <button
            className="button subtle"
            onClick={() => {
              setFrom("");
              setTo("");
              setSearch("");
              setAction("");
              setEntity("");
              setEntityId("");
              setPage(1);
            }}
          >
            پاک کردن فیلترها
          </button>
        </div>
        {error ? (
          <ErrorState error={error} retry={refresh} />
        ) : loading && !data ? (
          <Spinner />
        ) : data?.results.length ? (
          <div className={`audit-feed ${loading ? "refreshing" : ""}`}>
            {data.results.map((item) => (
              <div className="audit-entry" key={item.id}>
                <span className={`activity-icon ${item.action}`}>
                  <History size={17} />
                </span>
                <div className="audit-entry-content">
                  <div className="audit-entry-top">
                    <strong>
                      {item.description ||
                        auditActionNames[item.action] ||
                        item.action}
                    </strong>
                    <span className="audit-type">
                      {auditActionNames[item.action] || item.action}
                    </span>
                  </div>
                  <div className="audit-entry-meta">
                    <span>
                      <UserRound size={13} />
                      {item.actor ? displayName(item.actor) : "سیستم"}
                    </span>
                    <span>
                      {date(item.created_at)}، {time(item.created_at)}
                    </span>
                    {item.entity_type === "customer" && (
                      <Link href={`/customers/${item.entity_id}`}>
                        پرونده مجموعه
                      </Link>
                    )}
                  </div>
                  <button
                    className="text-link changes-toggle"
                    aria-expanded={expanded === item.id}
                    onClick={() =>
                      setExpanded((current) =>
                        current === item.id ? null : item.id,
                      )
                    }
                  >
                    جزئیات تغییر
                    <ChevronDown size={14} />
                  </button>
                  {expanded === item.id && (
                    <ChangeDetails changes={item.changes} />
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <Empty
            title="فعالیتی در این بازه پیدا نشد"
            description="پس از ایجاد یا تغییر اطلاعات، رد فعالیت‌ها در این بخش ثبت می‌شود."
          />
        )}
        {data && <Pagination count={data.count} page={page} onPage={setPage} />}
      </section>
    </>
  );
}
export function Profile() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [changing, setChanging] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  if (!user) return null;
  return (
    <>
      <PageHeading
        eyebrow="فضای شخصی شما"
        title="پروفایل و امنیت"
        description="اطلاعات خود را به‌روز کنید و از امنیت حساب‌تان مراقبت کنید."
      />
      <div className="profile-grid">
        <aside className="panel profile-summary">
          <span className="profile-avatar">
            {displayName(user).slice(0, 1)}
          </span>
          <h2>{displayName(user)}</h2>
          <span className={`role-badge ${user.role}`}>
            <ShieldCheck size={14} />
            {roles[user.role]}
          </span>
          <dl>
            <div>
              <dt>نام کاربری</dt>
              <dd dir="ltr">{user.username}</dd>
            </div>
            <div>
              <dt>عضویت از</dt>
              <dd>{date(user.date_joined)}</dd>
            </div>
            <div>
              <dt>آخرین ورود</dt>
              <dd>{date(user.last_login)}</dd>
            </div>
          </dl>
          <div className="profile-safe">
            <ShieldCheck size={18} />
            حساب شما فعال است
          </div>
        </aside>
        <div className="profile-forms">
          <Panel title="اطلاعات شخصی" subtitle="نام و اطلاعات تماس حساب شما">
            <form
              data-testid="profile-form"
              onSubmit={async (event) => {
                event.preventDefault();
                const form = new FormData(event.currentTarget);
                setSaving(true);
                setProfileError(null);
                try {
                  const result = await mutate<User>("auth/me/", "PATCH", {
                    first_name: form.get("first_name"),
                    last_name: form.get("last_name"),
                    email: form.get("email"),
                  });
                  setUser(result);
                  toast("پروفایل شما به‌روز شد.");
                } catch (error) {
                  setProfileError((error as Error).message);
                } finally {
                  setSaving(false);
                }
              }}
            >
              <div className="form-grid">
                <Field label="نام">
                  <input
                    name="first_name"
                    autoComplete="given-name"
                    defaultValue={user.first_name}
                    maxLength={150}
                    disabled={saving}
                  />
                </Field>
                <Field label="نام خانوادگی">
                  <input
                    name="last_name"
                    autoComplete="family-name"
                    defaultValue={user.last_name}
                    maxLength={150}
                    disabled={saving}
                  />
                </Field>
                <Field label="ایمیل">
                  <input
                    name="email"
                    type="email"
                    autoComplete="email"
                    dir="ltr"
                    defaultValue={user.email}
                    disabled={saving}
                  />
                </Field>
                <Field
                  label="نام کاربری"
                  hint="نام کاربری از این بخش قابل تغییر نیست."
                >
                  <input value={user.username} readOnly dir="ltr" />
                </Field>
              </div>
              <InlineError message={profileError} />
              <div className="form-footer">
                <Submit pending={saving}>ذخیره پروفایل</Submit>
              </div>
            </form>
          </Panel>
          <Panel
            title="تغییر رمز عبور"
            subtitle="از یک رمز قوی و منحصر به‌فرد استفاده کنید"
          >
            <form
              data-testid="password-form"
              onSubmit={async (event) => {
                event.preventDefault();
                const formElement = event.currentTarget;
                const form = new FormData(formElement);
                const password = String(form.get("new_password"));
                if (password !== form.get("confirm_password")) {
                  setPasswordError("تکرار رمز عبور با رمز جدید یکسان نیست.");
                  return;
                }
                setChanging(true);
                setPasswordError(null);
                try {
                  await mutate("auth/password/", "POST", {
                    current_password: form.get("current_password"),
                    new_password: password,
                  });
                  resetCsrf();
                  formElement.reset();
                  toast("رمز عبور شما با موفقیت تغییر کرد.");
                } catch (error) {
                  setPasswordError((error as Error).message);
                } finally {
                  setChanging(false);
                }
              }}
            >
              <Field label="رمز عبور فعلی" required>
                <input
                  name="current_password"
                  type="password"
                  autoComplete="current-password"
                  dir="ltr"
                  required
                  disabled={changing}
                />
              </Field>
              <div className="form-grid">
                <Field label="رمز عبور جدید" required>
                  <input
                    name="new_password"
                    type="password"
                    autoComplete="new-password"
                    dir="ltr"
                    required
                    minLength={10}
                    disabled={changing}
                  />
                </Field>
                <Field label="تکرار رمز عبور جدید" required>
                  <input
                    name="confirm_password"
                    type="password"
                    autoComplete="new-password"
                    dir="ltr"
                    required
                    minLength={10}
                    disabled={changing}
                  />
                </Field>
              </div>
              <div className="form-note">
                <KeyRound size={18} />
                <p>
                  حداقل ۱۰ نویسه انتخاب کنید. رمز نباید کاملاً عددی، رایج یا
                  شبیه اطلاعات شخصی شما باشد.
                </p>
              </div>
              <InlineError message={passwordError} />
              <div className="form-footer">
                <Submit pending={changing}>تغییر رمز عبور</Submit>
              </div>
            </form>
          </Panel>
        </div>
      </div>
    </>
  );
}

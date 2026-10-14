"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Building2,
  Clock3,
  Grid2x2,
  GraduationCap,
  CalendarDays,
  Check,
  ChevronLeft,
  Eye,
  EyeOff,
  Fingerprint,
  LayoutDashboard,
  LoaderCircle,
  LockKeyhole,
  LogOut,
  Menu,
  Mountain,
  Phone,
  RefreshCw,
  ShieldCheck,
  Headset,
  UserRoundCheck,
  Sun,
  Users,
  X,
} from "lucide-react";
import { api, ApiError, mutate, resetCsrf } from "@/lib/api";
import { date, number } from "@/lib/format";
import type { OrganizationPublic, OrganizationSession } from "@/lib/types";
import { Badge, InlineError, Spinner } from "./ui";
import { OperationsContent } from "./study-operations";
import { OperationsOverview } from "./operations-overview";
import {
  operationPages,
  operationTitles,
  type OperationPage,
} from "@/lib/operations";
import { DamavandBrand, MountainScene } from "./portal-scene";
import { HelpTooltip } from "./help-tooltip";
import { Supervisors } from "./supervisors";
import { SupportBell, SupportTickets } from "./support";
import "../app/ux-refinement.css";

export type PortalPage =
  | "dashboard"
  | OperationPage
  | "supervisors"
  | "support";

export function OrganizationLogin({
  organization,
}: {
  organization: OrganizationPublic;
}) {
  const router = useRouter();
  const [visible, setVisible] = useState(false),
    [pending, setPending] = useState(false),
    [success, setSuccess] = useState(false),
    [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    try {
      await mutate<OrganizationSession>(
        `organizations/${organization.slug}/login/`,
        "POST",
        { username: form.get("username"), password: form.get("password") },
      );
      resetCsrf();
      setSuccess(true);
      timer.current = setTimeout(
        () => router.replace(`/${organization.slug}/dashboard`),
        window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 700,
      );
    } catch (error) {
      setError((error as Error).message);
      setPending(false);
    }
  }
  return (
    <main className={`portal-login ${success ? "portal-login-success" : ""}`}>
      <MountainScene />
      <header className="portal-login-header">
        <DamavandBrand />
        <span className="portal-private-label">
          <ShieldCheck size={15} />
          فضای اختصاصی مجموعه
        </span>
      </header>
      <div className="portal-login-layout">
        <section className="summit-story">
          <div className="summit-eyebrow">
            <span />
            از اینجا، مسیر روشن است
          </div>
          <h1>
            تمرکز بر فردا.
            <br />
            <span>آغاز از دماوند.</span>
          </h1>
          <p>
            فضایی برای نظم، آرامش و رشد.
            <br />
            مدیریت مجموعهٔ شما، در یک چشم‌انداز روشن.
          </p>
          <div className="summit-coordinate">
            <span>۳۵° ۵۷′ شمالی</span>
            <i />
            <span>۵۲° ۰۶′ شرقی</span>
            <Mountain size={16} />
          </div>
          <div className="summit-caption">
            <span>۰۱ / قلهٔ تمرکز</span>
            <div />
          </div>
        </section>
        <section
          className="portal-login-card"
          aria-labelledby="portal-login-title"
        >
          <div className="portal-entry-icon">
            <Fingerprint size={30} strokeWidth={1.3} />
          </div>
          <span className="portal-card-eyebrow">به فضای خودتان خوش آمدید</span>
          <h2 id="portal-login-title">{organization.name}</h2>
          <p className="portal-card-description">
            برای ادامهٔ مسیر، وارد حساب مجموعه شوید.
          </p>
          <form onSubmit={submit} data-testid="organization-login-form">
            <label className="portal-field">
              <span>نام کاربری</span>
              <input
                name="username"
                required
                maxLength={64}
                autoComplete="username"
                dir="ltr"
                disabled={pending}
                placeholder="نام کاربری مجموعه"
                aria-invalid={!!error}
                aria-describedby={error ? "portal-login-error" : undefined}
              />
            </label>
            <label className="portal-field">
              <span>رمز عبور</span>
              <div className="portal-password">
                <input
                  name="password"
                  required
                  maxLength={4096}
                  type={visible ? "text" : "password"}
                  autoComplete="current-password"
                  dir="ltr"
                  disabled={pending}
                  placeholder="رمز عبور شما"
                  aria-invalid={!!error}
                  aria-describedby={error ? "portal-login-error" : undefined}
                />
                <button
                  type="button"
                  onClick={() => setVisible(!visible)}
                  aria-label={
                    visible ? "پنهان کردن رمز عبور" : "نمایش رمز عبور"
                  }
                  aria-pressed={visible}
                  disabled={pending}
                >
                  {visible ? <EyeOff size={19} /> : <Eye size={19} />}
                </button>
              </div>
            </label>
            {error && (
              <div
                id="portal-login-error"
                className="portal-login-error"
                role="alert"
              >
                {error}
              </div>
            )}
            <button className="portal-enter" type="submit" disabled={pending}>
              {success ? (
                <Check size={20} />
              ) : pending ? (
                <LoaderCircle className="spin" size={20} />
              ) : (
                <ArrowLeft size={20} />
              )}
              <span>
                {success
                  ? "خوش آمدید؛ در حال ورود…"
                  : pending
                    ? "در حال بررسی حساب…"
                    : "ورود به فضای مجموعه"}
              </span>
            </button>
            <div role="status" className="sr-only">
              {success
                ? "ورود موفق؛ انتقال به داشبورد"
                : pending
                  ? "در حال بررسی اطلاعات ورود"
                  : ""}
            </div>
          </form>
          <div className="portal-login-help">
            <LockKeyhole size={14} />
            <span>
              برای دریافت یا بازیابی رمز، با مدیریت دماوند تماس بگیرید.
            </span>
          </div>
          <div className="portal-card-bottom">
            <span>یک فضای امن، فقط برای شما</span>
            <span dir="ltr">/{organization.slug}</span>
          </div>
        </section>
      </div>
      <footer className="portal-login-footer">
        <span>دماوند · همراهِ مسیر رشد</span>
        <span>تمرکز. نظم. پیشرفت.</span>
      </footer>
      {success && (
        <div className="summit-arrival" aria-hidden="true">
          <Check size={40} />
        </div>
      )}
    </main>
  );
}

export function OrganizationDashboard({
  slug,
  page = "dashboard",
  studentId,
  supervisorId,
  ticketId,
}: {
  slug: string;
  page?: PortalPage;
  studentId?: number;
  supervisorId?: number;
  ticketId?: number;
}) {
  const router = useRouter();
  const [session, setSession] = useState<OrganizationSession | null>(null),
    [error, setError] = useState<string | null>(null),
    [denied, setDenied] = useState(false),
    [refresh, setRefresh] = useState(0),
    [busy, setBusy] = useState(true),
    [menu, setMenu] = useState(false),
    [logoutPending, setLogoutPending] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null),
    sidebar = useRef<HTMLElement>(null);
  useEffect(() => {
    let alive = true;
    api<OrganizationSession>(`organizations/${slug}/dashboard/`)
      .then((data) => {
        if (alive) {
          setSession(data);
          setError(null);
          setDenied(false);
        }
      })
      .catch((error) => {
        if (!alive) return;
        setSession(null);
        if (error instanceof ApiError && error.status === 401)
          router.replace(`/${slug}`);
        else {
          setDenied(error instanceof ApiError && error.status === 403);
          setError((error as Error).message);
        }
      })
      .finally(() => {
        if (alive) setBusy(false);
      });
    return () => {
      alive = false;
    };
  }, [slug, refresh, router]);
  useEffect(() => {
    if (!menu) return;
    const triggerButton = trigger.current;
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    sidebar.current?.querySelector<HTMLElement>("button,a")?.focus();
    function handle(event: KeyboardEvent) {
      if (event.key === "Escape") setMenu(false);
      if (event.key !== "Tab") return;
      const items = sidebar.current?.querySelectorAll<HTMLElement>(
        "button:not([disabled]),a[href]",
      );
      if (!items?.length) return;
      const first = items[0],
        last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    window.addEventListener("keydown", handle);
    return () => {
      document.body.style.overflow = old;
      window.removeEventListener("keydown", handle);
      triggerButton?.focus();
    };
  }, [menu]);
  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 901px)");
    function closeOnDesktop() {
      if (desktop.matches) setMenu(false);
    }
    desktop.addEventListener("change", closeOnDesktop);
    return () => desktop.removeEventListener("change", closeOnDesktop);
  }, []);
  async function logout() {
    setLogoutPending(true);
    try {
      await mutate(`organizations/${slug}/logout/`, "POST");
      resetCsrf();
      setSession(null);
      router.replace(`/${slug}`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401)
        router.replace(`/${slug}`);
      else setError((error as Error).message);
    } finally {
      setLogoutPending(false);
    }
  }
  // A route transition must never render a previously loaded tenant's profile.
  if (!session || session.organization.slug !== slug)
    return (
      <main className="portal-gate">
        <DamavandBrand />
        {error ? (
          <div className="portal-gate-error">
            <ShieldCheck size={36} />
            <h1>
              {denied
                ? "این فضا متعلق به مجموعهٔ دیگری است"
                : "دریافت اطلاعات ناموفق بود"}
            </h1>
            <p role="alert">{error}</p>
            {denied ? (
              <Link className="button primary" href={`/${slug}`}>
                ورود با حساب این مجموعه
              </Link>
            ) : (
              <button
                className="button primary"
                onClick={() => {
                  setBusy(true);
                  setRefresh((n) => n + 1);
                }}
              >
                تلاش دوباره
              </button>
            )}
          </div>
        ) : (
          <Spinner label="در حال باز کردن فضای مجموعه…" />
        )}
      </main>
    );
  const currentTitle =
    page === "dashboard"
      ? "نمای کلی"
      : page === "supervisors"
        ? "مدیریت مراقبین"
        : page === "support"
          ? "پشتیبانی و تیکت‌ها"
          : operationTitles[page];
  const icons = {
    halls: Building2,
    "study-sessions": Clock3,
    assignments: Grid2x2,
    students: GraduationCap,
  };
  const org = session.organization,
    sub = org.subscription;
  return (
    <div className="tenant-shell">
      {menu && (
        <div
          className="tenant-menu-scrim"
          onClick={() => setMenu(false)}
          aria-hidden="true"
        />
      )}
      <aside
        id="tenant-navigation"
        ref={sidebar}
        className={`tenant-sidebar ${menu ? "open" : ""}`}
        role={menu ? "dialog" : undefined}
        aria-modal={menu ? true : undefined}
        aria-label="ناوبری مجموعه"
      >
        <div className="tenant-side-brand">
          <DamavandBrand />
          <button
            className="tenant-mobile-close"
            aria-label="بستن منوی مجموعه"
            onClick={() => setMenu(false)}
          >
            <X size={20} />
          </button>
        </div>
        <div className="tenant-side-scroll">
          <div className="tenant-organization">
            <span className="tenant-org-avatar">{org.name.slice(0, 1)}</span>
            <div>
              <strong>{org.name}</strong>
              <small>فضای اختصاصی مجموعه</small>
            </div>
          </div>
          <span className="tenant-nav-label">فضای کار</span>
          <nav>
            <Link
              href={`/${slug}/dashboard`}
              className={page === "dashboard" ? "selected" : ""}
              aria-current={page === "dashboard" ? "page" : undefined}
              onClick={() => setMenu(false)}
            >
              <LayoutDashboard size={19} /> نمای کلی <ChevronLeft size={15} />
            </Link>
            {operationPages.map((item) => {
              const Icon = icons[item];
              return (
                <Link
                  key={item}
                  href={`/${slug}/${item}`}
                  className={page === item ? "selected" : ""}
                  aria-current={page === item ? "page" : undefined}
                  onClick={() => setMenu(false)}
                >
                  <Icon size={19} />
                  {operationTitles[item]}
                  <ChevronLeft size={15} />
                </Link>
              );
            })}
            <Link
              href={`/${slug}/supervisors`}
              className={page === "supervisors" ? "selected" : ""}
              aria-current={page === "supervisors" ? "page" : undefined}
              onClick={() => setMenu(false)}
            >
              <UserRoundCheck size={19} />
              مدیریت مراقبین
              <ChevronLeft size={15} />
            </Link>
            <Link
              href={`/${slug}/support`}
              className={page === "support" ? "selected" : ""}
              aria-current={page === "support" ? "page" : undefined}
              onClick={() => setMenu(false)}
            >
              <Headset size={19} />
              پشتیبانی و تیکت‌ها
              <ChevronLeft size={15} />
            </Link>
            <Link
              href={`/${slug}/dashboard#subscription`}
              onClick={() => setMenu(false)}
            >
              <CalendarDays size={19} />
              اشتراک و سرویس
            </Link>
            <Link
              href={`/${slug}/dashboard#organization-profile`}
              onClick={() => setMenu(false)}
            >
              <Fingerprint size={19} />
              اطلاعات مجموعه
            </Link>
          </nav>
        </div>
        <div className="tenant-side-bottom">
          <span dir="ltr">@{session.username}</span>
          <button onClick={logout} disabled={logoutPending}>
            <LogOut size={18} />
            {logoutPending ? "در حال خروج…" : "خروج از حساب"}
          </button>
        </div>
      </aside>
      <div className="tenant-workspace" inert={menu ? true : undefined}>
        <header className="tenant-topbar">
          <div>
            <button
              ref={trigger}
              className="icon-button tenant-menu-button"
              aria-label="باز کردن منوی مجموعه"
              aria-expanded={menu}
              aria-controls="tenant-navigation"
              onClick={() => setMenu(true)}
            >
              <Menu size={22} />
            </button>
            <span>
              فضای مجموعه
              <ChevronLeft size={13} />
              <strong>{currentTitle}</strong>
            </span>
          </div>
          <div>
            <span className="tenant-today">
              <Sun size={16} />
              {date(sub.business_date)}
            </span>
            <SupportBell slug={slug} />
            <button
              className="icon-button"
              aria-label="به‌روزرسانی اطلاعات مجموعه"
              disabled={busy}
              onClick={() => {
                setBusy(true);
                setRefresh((n) => n + 1);
              }}
            >
              <RefreshCw size={17} className={busy ? "spin" : ""} />
            </button>
            <span className="tenant-user-mark">
              {org.manager_name.slice(0, 1)}
            </span>
          </div>
        </header>
        <main className="tenant-main" id="overview">
          {page === "supervisors" ? (
            <Supervisors
              key={slug + (supervisorId || "")}
              slug={slug}
              supervisorId={supervisorId}
            />
          ) : page === "support" ? (
            <SupportTickets
              key={slug + (ticketId || "")}
              slug={slug}
              ticketId={ticketId}
            />
          ) : page !== "dashboard" ? (
            <OperationsContent
              key={slug + page + (studentId || "")}
              slug={slug}
              page={page}
              studentId={studentId}
              summary={session.operations}
              onChanged={() => setRefresh((n) => n + 1)}
            />
          ) : (
            <>
              <div className="tenant-heading">
                <div>
                  <h1>سلام، {org.manager_name}</h1>
                </div>
                <Badge status={sub.status} />
              </div>
              <InlineError message={error} />
              {(sub.status === "expired" ||
                sub.status === "expiring" ||
                sub.status === "scheduled") && (
                <div className={`tenant-notice ${sub.status}`} role="status">
                  <CalendarDays size={21} />
                  <div>
                    <strong>
                      {sub.status === "expired"
                        ? "زمان تمدید سرویس رسیده است"
                        : sub.status === "scheduled"
                          ? "سرویس شما به‌زودی آغاز می‌شود"
                          : "تا پایان سرویس، فرصت کمی باقی مانده است"}
                    </strong>
                    <p>
                      {sub.status === "expired"
                        ? `${number(sub.days_since_expiration)} روز از پایان سرویس گذشته است. برای تمدید با مدیریت دماوند تماس بگیرید. دسترسی شما به داشبورد برقرار است.`
                        : sub.status === "scheduled"
                          ? `شروع سرویس در ${date(sub.start_date)}؛ ${number(sub.days_until_start)} روز دیگر.`
                          : `${number(sub.remaining_days)} روز از اشتراک باقی مانده است؛ برای تمدید با مدیریت دماوند هماهنگ کنید.`}
                    </p>
                  </div>
                </div>
              )}
              <section
                className="tenant-summary-strip"
                aria-label="ظرفیت مجموعه"
              >
                <div className="tenant-card-icon turquoise">
                  <Users size={21} />
                </div>
                <h2>ظرفیت مجموعه</h2>
                <HelpTooltip
                  label="راهنمای ظرفیت مجموعه"
                  content="ظرفیت مجموعه، سقف دانش‌آموزان فعال در مجموع همهٔ سالن‌هاست. برای تغییر ظرفیت با مدیریت دماوند هماهنگ کنید."
                />
                <strong data-testid="tenant-capacity">
                  {org.capacity === null ? "—" : number(org.capacity)}
                  <small>نفر</small>
                </strong>
              </section>
              {session.operations && (
                <OperationsOverview slug={slug} stats={session.operations} />
              )}
              <div className="tenant-detail-grid">
                <section
                  className="tenant-card tenant-subscription"
                  id="subscription"
                >
                  <div className="tenant-card-heading">
                    <div className="tenant-card-icon purple">
                      <CalendarDays size={22} />
                    </div>
                    <div>
                      <h2>
                        اشتراک مجموعه
                        <HelpTooltip
                          label="راهنمای اشتراک مجموعه"
                          content="وضعیت اشتراک از تاریخ آغاز تا پایان محاسبه می‌شود. روز پایان سرویس نیز در روزهای باقی‌مانده لحاظ شده است."
                        />
                      </h2>
                    </div>
                    <Badge status={sub.status} />
                  </div>
                  <div className="subscription-visual">
                    <div
                      className={`subscription-ring ${sub.status}`}
                      style={
                        {
                          "--progress": `${sub.progress_percent}%`,
                        } as React.CSSProperties
                      }
                    >
                      <div>
                        <strong data-testid="tenant-remaining">
                          {number(sub.remaining_days)}
                        </strong>
                        <span>روز باقی‌مانده</span>
                      </div>
                    </div>
                    <div className="subscription-duration">
                      <span>مسیر اشتراک شما</span>
                      <strong>{number(sub.total_days)} روز</strong>
                      <p>
                        {sub.status === "scheduled"
                          ? "در انتظار آغاز سرویس"
                          : sub.status === "expired"
                            ? "دورهٔ سرویس به پایان رسیده است"
                            : `${number(sub.elapsed_days)} روز سپری شده است`}
                      </p>
                    </div>
                  </div>
                  <div className="subscription-dates">
                    <div>
                      <i />
                      <span>آغاز سرویس</span>
                      <strong>{date(sub.start_date)}</strong>
                    </div>
                    <div>
                      <i />
                      <span>پایان سرویس</span>
                      <strong>{date(sub.expiration_date)}</strong>
                    </div>
                  </div>
                  <div
                    className="subscription-progress"
                    role="progressbar"
                    aria-label="زمان سپری‌شده از اشتراک"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={sub.progress_percent}
                  >
                    <span style={{ width: `${sub.progress_percent}%` }} />
                  </div>
                </section>
                <section
                  className="tenant-card tenant-profile"
                  id="organization-profile"
                >
                  <div className="tenant-card-heading">
                    <div className="tenant-card-icon blue">
                      <Fingerprint size={22} />
                    </div>
                    <div>
                      <h2>
                        شناسنامهٔ مجموعه
                        <HelpTooltip
                          label="راهنمای اطلاعات مجموعه"
                          content="این اطلاعات در مدیریت دماوند ثبت شده است. برای اصلاح اطلاعات با مدیریت دماوند هماهنگ کنید."
                        />
                      </h2>
                    </div>
                  </div>
                  <dl>
                    <div>
                      <dt>نام مجموعه</dt>
                      <dd>{org.name}</dd>
                    </div>
                    <div>
                      <dt>مدیر مجموعه</dt>
                      <dd>{org.manager_name}</dd>
                    </div>
                    <div>
                      <dt>
                        <Phone size={14} />
                        شماره تماس
                      </dt>
                      <dd dir="ltr">
                        {org.phone.replace(/[0-9]/g, (n) => number(Number(n)))}
                      </dd>
                    </div>
                    <div>
                      <dt>شناسهٔ یکتا</dt>
                      <dd dir="ltr">{org.identifier}</dd>
                    </div>
                    <div>
                      <dt>نشانی اختصاصی</dt>
                      <dd dir="ltr">/{org.slug}</dd>
                    </div>
                  </dl>
                </section>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}

"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUpLeft,
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
  Sparkles,
  Sun,
  Users,
  X,
} from "lucide-react";
import { api, ApiError, mutate, resetCsrf } from "@/lib/api";
import { date, number } from "@/lib/format";
import type { OrganizationPublic, OrganizationSession } from "@/lib/types";
import { Badge, InlineError, Spinner } from "./ui";
import { DamavandBrand, MountainScene } from "./portal-scene";

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

export function OrganizationDashboard({ slug }: { slug: string }) {
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
        <div className="tenant-organization">
          <span className="tenant-org-avatar">{org.name.slice(0, 1)}</span>
          <div>
            <strong>{org.name}</strong>
            <small>فضای اختصاصی مجموعه</small>
          </div>
        </div>
        <span className="tenant-nav-label">فضای کار</span>
        <nav>
          <a
            href="#overview"
            className="selected"
            onClick={() => setMenu(false)}
          >
            <LayoutDashboard size={19} />
            نمای کلی
            <ChevronLeft size={15} />
          </a>
          <a href="#subscription" onClick={() => setMenu(false)}>
            <CalendarDays size={19} />
            اشتراک و سرویس
          </a>
          <a href="#organization-profile" onClick={() => setMenu(false)}>
            <Fingerprint size={19} />
            اطلاعات مجموعه
          </a>
        </nav>
        <div className="tenant-side-note">
          <Sparkles size={23} />
          <strong>فضایی برای رشد</strong>
          <p>اطلاعات مجموعه و وضعیت سرویس، همیشه در دسترس شماست.</p>
          <span>دماوند، همراه مسیر شما</span>
        </div>
        <div className="tenant-side-bottom">
          <span dir="ltr">@{session.username}</span>
          <button onClick={logout} disabled={logoutPending}>
            <LogOut size={18} />
            {logoutPending ? "در حال خروج…" : "خروج از حساب"}
          </button>
        </div>
      </aside>
      <div className="tenant-workspace">
        <header className="tenant-topbar">
          <div>
            <button
              ref={trigger}
              className="icon-button tenant-menu-button"
              aria-label="باز کردن منوی مجموعه"
              aria-expanded={menu}
              onClick={() => setMenu(true)}
            >
              <Menu size={22} />
            </button>
            <span>
              فضای مجموعه
              <ChevronLeft size={13} />
              <strong>نمای کلی</strong>
            </span>
          </div>
          <div>
            <span className="tenant-today">
              <Sun size={16} />
              {date(sub.business_date)}
            </span>
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
          <div className="tenant-heading">
            <div>
              <span className="eyebrow">یک چشم‌انداز روشن</span>
              <h1>سلام، {org.manager_name}</h1>
              <p>به فضای اختصاصی {org.name} خوش آمدید.</p>
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
          <div className="tenant-overview-grid">
            <section className="tenant-welcome">
              <div className="tenant-welcome-art" aria-hidden="true">
                <Mountain size={145} strokeWidth={0.7} />
                <div />
              </div>
              <span className="tenant-chip">
                <Sparkles size={14} />
                همراه مسیر شما
              </span>
              <h2>
                تمرکز شما بر رشد،
                <br />
                نظم مجموعه با دماوند.
              </h2>
              <p>
                اطلاعات اصلی مجموعه و جزئیات اشتراک شما،
                <br />
                همه در یک فضای روشن و آرام.
              </p>
              <a href="#organization-profile">
                مشاهده اطلاعات مجموعه
                <ArrowUpLeft size={17} />
              </a>
            </section>
            <section className="tenant-card tenant-capacity">
              <div className="tenant-card-icon turquoise">
                <Users size={24} />
              </div>
              <span className="tenant-card-kicker">ظرفیت مجموعه</span>
              <div
                className="tenant-capacity-value"
                data-testid="tenant-capacity"
              >
                {org.capacity === null ? "—" : number(org.capacity)}
                <small>نفر</small>
              </div>
              <p>حداکثر ظرفیت ثبت‌شدهٔ {org.name}</p>
              <div className="capacity-decoration" aria-hidden="true">
                {Array.from({ length: 12 }, (_, i) => (
                  <span key={i} />
                ))}
              </div>
              <small className="capacity-footnote">
                ظرفیت ثبت‌شده، مستقل از تعداد دانش‌آموزان است.
              </small>
            </section>
          </div>
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
                  <h2>اشتراک مجموعه</h2>
                  <p>زمان‌بندی و وضعیت سرویس</p>
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
              <p className="subscription-end-note">
                روز پایان سرویس در محاسبهٔ روزهای باقی‌مانده لحاظ شده است.
              </p>
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
                  <h2>شناسنامهٔ مجموعه</h2>
                  <p>اطلاعات ثبت‌شده در مدیریت دماوند</p>
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
              <p>
                <ShieldCheck size={15} />
                برای اصلاح اطلاعات، با مدیریت دماوند هماهنگ کنید.
              </p>
            </section>
          </div>
          <section className="tenant-future">
            <div className="tenant-card-icon orange">
              <Sparkles size={22} />
            </div>
            <div>
              <h2>فضای رشد مجموعهٔ شما</h2>
              <p>
                مدیریت دانش‌آموزان و حضور و غیاب در مراحل بعدی اضافه می‌شوند. در
                این مرحله، اطلاعات واقعی مجموعه و سرویس شما نمایش داده می‌شود.
              </p>
            </div>
            <span>در مسیر توسعه</span>
          </section>
          <footer className="tenant-footer">
            <span>دماوند · مدیریت با چشم‌انداز</span>
            <span>
              <ShieldCheck size={14} />
              فضای اختصاصی {org.name}
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}

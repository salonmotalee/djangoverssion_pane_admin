"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  CalendarDays,
  Check,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  Clock3,
  DoorOpen,
  Eye,
  EyeOff,
  GraduationCap,
  LayoutDashboard,
  LoaderCircle,
  LockKeyhole,
  LogIn,
  LogOut,
  Menu,
  Mountain,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  UserRound,
  X,
} from "lucide-react";
import { api, ApiError, mutate, resetCsrf } from "@/lib/api";
import { normalizeAppearance, themeVariables } from "@/lib/appearance";
import { date, number, queryString, time } from "@/lib/format";
import { clockTime } from "@/lib/operations";
import {
  addCalendarDays,
  attendanceChanges,
  attendanceLabels,
  automaticSelection,
  saturdayOfWeek,
  staffName,
  supervisorPages,
  supervisorTitles,
  tehranToday,
  type AttendanceRoster,
  type AttendanceStatus,
  type PresenceEvent,
  type StaffDashboard,
  type StaffHall,
  type StaffSchedule,
  type StaffSession,
  type StaffShift,
  type StaffStudent,
  type SupervisorPage,
} from "@/lib/staff";
import { normalizeSupervisorPhone } from "@/lib/supervisors";
import type { OrganizationPublic, Paginated } from "@/lib/types";
import { useData } from "@/lib/use-data";
import { useThemeMode } from "./appearance";
import { HelpTooltip } from "./help-tooltip";
import { DamavandBrand, MountainScene } from "./portal-scene";
import {
  DateField,
  Empty,
  ErrorState,
  Field,
  InlineError,
  Modal,
  PageHeading,
  Pagination,
  Panel,
  Spinner,
  Submit,
} from "./ui";
import "../app/appearance.css";
import "./supervisor-portal.css";

export type { SupervisorPage } from "@/lib/staff";
const staffPath = (slug: string, endpoint: string) =>
  `organizations/${slug}/supervisor/${endpoint}`;
const pageIcons = {
  dashboard: LayoutDashboard,
  halls: Building2,
  students: GraduationCap,
  presence: DoorOpen,
  attendance: CheckCheck,
  schedule: CalendarDays,
  profile: UserRound,
};

export function SupervisorLogin({
  organization,
}: {
  organization: OrganizationPublic;
}) {
  const router = useRouter();
  const [visible, setVisible] = useState(false);
  const [pending, setPending] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  return (
    <main
      className={`portal-login staff-login ${success ? "portal-login-success" : ""}`}
      dir="rtl"
    >
      <MountainScene />
      <header className="portal-login-header">
        <DamavandBrand />
        <span className="portal-private-label">
          <ShieldCheck size={16} />
          فضای اختصاصی مراقبین
        </span>
      </header>
      <div className="portal-login-layout">
        <section className="summit-story">
          <div className="summit-eyebrow">
            <span />
            همراهِ مسیر تمرکز
          </div>
          <h1>
            آرامشِ سالن.
            <br />
            <span>با حضور شما.</span>
          </h1>
          <p>
            ورود، حضور و برنامهٔ امروز
            <br />
            در یک فضای روشن و هماهنگ.
          </p>
          <div className="staff-login-path" aria-hidden="true">
            <span>
              <DoorOpen size={18} />
              ورود
            </span>
            <i />
            <span>
              <CheckCheck size={18} />
              حضور
            </span>
            <i />
            <span>
              <Mountain size={18} />
              رشد
            </span>
          </div>
          <div className="summit-caption">
            <span>دماوند / همراهان نظم</span>
            <div />
          </div>
        </section>
        <section
          className="portal-login-card"
          aria-labelledby="staff-login-title"
        >
          <div className="portal-entry-icon">
            <ShieldCheck size={30} strokeWidth={1.4} />
          </div>
          <span className="portal-card-eyebrow">پنل مراقب</span>
          <h2 id="staff-login-title">{organization.name}</h2>
          <p className="portal-card-description">
            با شماره همراه و رمز دریافتی از مدیر وارد شوید.
          </p>
          <form
            data-testid="supervisor-login-form"
            onSubmit={async (event) => {
              event.preventDefault();
              const values = new FormData(event.currentTarget);
              const username = normalizeSupervisorPhone(
                String(values.get("username") || ""),
              );
              if (!username) {
                setError("شماره همراه معتبر ایران را وارد کنید.");
                return;
              }
              setPending(true);
              setError(null);
              try {
                await mutate<StaffSession>(
                  staffPath(organization.slug, "login/"),
                  "POST",
                  { username, password: values.get("password") },
                );
                resetCsrf();
                setSuccess(true);
                timer.current = setTimeout(
                  () =>
                    router.replace(
                      `/${organization.slug}/supervisor/dashboard`,
                    ),
                  window.matchMedia("(prefers-reduced-motion: reduce)").matches
                    ? 0
                    : 550,
                );
              } catch (error) {
                setError((error as Error).message);
                setPending(false);
              }
            }}
          >
            <label className="portal-field">
              <span>شماره همراه</span>
              <input
                name="username"
                type="tel"
                autoComplete="username"
                dir="ltr"
                inputMode="tel"
                required
                maxLength={24}
                disabled={pending}
                placeholder="09123456789"
                aria-invalid={!!error}
                aria-describedby={error ? "staff-login-error" : undefined}
              />
            </label>
            <label className="portal-field">
              <span>رمز عبور</span>
              <div className="portal-password">
                <input
                  name="password"
                  type={visible ? "text" : "password"}
                  required
                  maxLength={4096}
                  autoComplete="current-password"
                  dir="ltr"
                  disabled={pending}
                  placeholder="رمز عبور شما"
                  aria-invalid={!!error}
                  aria-describedby={error ? "staff-login-error" : undefined}
                />
                <button
                  type="button"
                  disabled={pending}
                  aria-label={
                    visible ? "پنهان کردن رمز عبور" : "نمایش رمز عبور"
                  }
                  aria-pressed={visible}
                  onClick={() => setVisible(!visible)}
                >
                  {visible ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </label>
            {error && (
              <div
                id="staff-login-error"
                className="portal-login-error"
                role="alert"
              >
                {error}
              </div>
            )}
            <button className="portal-enter" disabled={pending} type="submit">
              {success ? (
                <>
                  <Check size={20} />
                  ورود موفق
                </>
              ) : pending ? (
                <>
                  <LoaderCircle size={19} className="spin" />
                  در حال ورود…
                </>
              ) : (
                <>
                  ورود به پنل مراقب
                  <ArrowLeft size={20} />
                </>
              )}
            </button>
          </form>
          <div className="staff-login-footer">
            <LockKeyhole size={14} />
            <span>حساب شما توسط مدیر مجموعه مدیریت می‌شود.</span>
          </div>
          <Link className="staff-manager-link" href={`/${organization.slug}`}>
            ورود مدیر مجموعه
          </Link>
        </section>
      </div>
    </main>
  );
}

export function SupervisorPortal({
  slug,
  page = "dashboard",
}: {
  slug: string;
  page?: SupervisorPage;
}) {
  const router = useRouter();
  const [session, setSession] = useState<StaffSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [menu, setMenu] = useState(false);
  const [logoutPending, setLogoutPending] = useState(false);
  const sidebar = useRef<HTMLElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const appearance = normalizeAppearance(session?.organization.appearance);
  const mode = useThemeMode(appearance);
  useEffect(() => {
    const controller = new AbortController();
    const load = () =>
      api<StaffSession>(staffPath(slug, "me/"), { signal: controller.signal })
        .then((data) => {
          if (!controller.signal.aborted) {
            setSession(data);
            setError(null);
          }
        })
        .catch((error: Error) => {
          if (controller.signal.aborted) return;
          setSession(null);
          if (error instanceof ApiError && error.status === 401)
            router.replace(`/${slug}/supervisor/login`);
          else setError(error.message);
        });
    void load();
    const focus = () => {
      void load();
    };
    window.addEventListener("focus", focus);
    const interval = window.setInterval(load, 60000);
    return () => {
      controller.abort();
      window.removeEventListener("focus", focus);
      window.clearInterval(interval);
    };
  }, [slug, revision, router]);
  useEffect(() => {
    if (!menu) return;
    const original = document.body.style.overflow;
    const opener = trigger.current;
    document.body.style.overflow = "hidden";
    sidebar.current?.querySelector<HTMLElement>("button,a")?.focus();
    function key(event: KeyboardEvent) {
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
    function desktop() {
      if (window.innerWidth > 900) setMenu(false);
    }
    window.addEventListener("keydown", key);
    window.addEventListener("resize", desktop);
    return () => {
      document.body.style.overflow = original;
      window.removeEventListener("keydown", key);
      window.removeEventListener("resize", desktop);
      opener?.focus();
    };
  }, [menu]);
  async function logout() {
    setLogoutPending(true);
    try {
      await mutate(staffPath(slug, "logout/"), "POST");
      resetCsrf();
      router.replace(`/${slug}/supervisor/login`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401)
        router.replace(`/${slug}/supervisor/login`);
      else setError((error as Error).message);
    } finally {
      setLogoutPending(false);
    }
  }
  if (!session || session.organization.slug !== slug)
    return (
      <main className="portal-gate">
        <DamavandBrand />
        {error ? (
          <ErrorState
            error={error}
            retry={() => setRevision((value) => value + 1)}
          />
        ) : (
          <Spinner label="در حال بازکردن پنل مراقب…" />
        )}
        <Link className="text-link" href={`/${slug}/supervisor/login`}>
          ورود به حساب این مجموعه
        </Link>
      </main>
    );
  return (
    <div
      className="tenant-shell staff-shell"
      dir="rtl"
      data-theme={mode}
      style={themeVariables(appearance.palettes[mode]) as CSSProperties}
    >
      {menu && (
        <div
          className="staff-menu-scrim"
          aria-hidden="true"
          onClick={() => setMenu(false)}
        />
      )}
      <aside
        ref={sidebar}
        className={`staff-sidebar ${menu ? "open" : ""}`}
        aria-label="ناوبری مراقب"
        role={menu ? "dialog" : undefined}
        aria-modal={menu ? true : undefined}
      >
        <div className="staff-sidebar-brand">
          <DamavandBrand />
          <button
            className="icon-button staff-menu-close"
            aria-label="بستن منو"
            onClick={() => setMenu(false)}
          >
            <X size={21} />
          </button>
        </div>
        <div className="staff-organization">
          <span>پنل مراقب</span>
          <strong>{session.organization.name}</strong>
        </div>
        <nav>
          {supervisorPages.map((item) => {
            const Icon = pageIcons[item];
            return (
              <Link
                key={item}
                href={`/${slug}/supervisor/${item}`}
                className={page === item ? "active" : ""}
                aria-current={page === item ? "page" : undefined}
                onClick={() => setMenu(false)}
              >
                <Icon size={19} />
                <span>{supervisorTitles[item]}</span>
                {page === item && <i />}
              </Link>
            );
          })}
        </nav>
        <div className="staff-sidebar-bottom">
          <div className="staff-person">
            <span>{session.first_name.slice(0, 1)}</span>
            <div>
              <strong>{staffName(session)}</strong>
              <small dir="ltr">{session.phone}</small>
            </div>
          </div>
          <button
            className="staff-logout"
            disabled={logoutPending}
            onClick={logout}
          >
            <LogOut size={18} />
            {logoutPending ? "در حال خروج…" : "خروج"}
          </button>
        </div>
      </aside>
      <div className="staff-workspace">
        <header className="staff-topbar">
          <div>
            <button
              ref={trigger}
              className="icon-button staff-menu-button"
              onClick={() => setMenu(true)}
              aria-label="بازکردن منو"
              aria-expanded={menu}
            >
              <Menu size={22} />
            </button>
            <span>{supervisorTitles[page]}</span>
          </div>
          <span>
            <CalendarDays size={16} />
            {date(tehranToday(), { weekday: "long" })}
          </span>
        </header>
        <main id="staff-main" className="staff-content">
          {session.organization.subscription.status === "expired" && (
            <div className="staff-warning" role="status">
              اشتراک مجموعه منقضی شده است؛ دسترسی شما همچنان برقرار است.
            </div>
          )}
          {error && <InlineError message={error} />}
          {page === "dashboard" && (
            <StaffOverview slug={slug} session={session} />
          )}
          {page === "halls" && <StaffHalls slug={slug} />}
          {(page === "students" || page === "presence") && (
            <StaffStudents
              key={`${slug}:${page}`}
              slug={slug}
              presence={page === "presence"}
            />
          )}
          {page === "attendance" && <StaffAttendance slug={slug} />}
          {page === "schedule" && <StaffScheduleView slug={slug} />}
          {page === "profile" && (
            <StaffProfile
              slug={slug}
              session={session}
              onSaved={() => setRevision((value) => value + 1)}
            />
          )}
        </main>
        <footer className="staff-footer">
          <Mountain size={14} />
          <span>دماوند، همراهِ مسیر تمرکز</span>
        </footer>
      </div>
    </div>
  );
}

function ShiftList({
  assignments,
  empty = "شیفتی ثبت نشده است",
}: {
  assignments: StaffShift[];
  empty?: string;
}) {
  return assignments.length ? (
    <div className="staff-shift-list">
      {assignments.map((shift) => (
        <div className="staff-shift" key={shift.id}>
          <span className="staff-shift-icon">
            <Clock3 size={21} />
          </span>
          <div>
            <strong>{shift.shift_name}</strong>
            <small>
              {shift.hall_name} ·{" "}
              {date(shift.date, { weekday: "short", month: "short" })}
            </small>
          </div>
          <span className="staff-shift-time">
            {clockTime(shift.start_time)}
            <small>تا {clockTime(shift.end_time)}</small>
          </span>
          {shift.conflict_override && (
            <span
              className="staff-conflict-dot"
              title="هم‌پوشانی با تأیید مدیر"
              aria-label="هم‌پوشانی با تأیید مدیر"
            />
          )}
        </div>
      ))}
    </div>
  ) : (
    <Empty
      title={empty}
      description="پس از ثبت برنامه توسط مدیر، شیفت‌ها اینجا نمایش داده می‌شوند."
    />
  );
}

function StaffOverview({
  slug,
  session,
}: {
  slug: string;
  session: StaffSession;
}) {
  const data = useData<StaffDashboard>(staffPath(slug, "dashboard/"));
  if (data.error) return <ErrorState error={data.error} retry={data.refresh} />;
  if (!data.data) return <StaffSkeleton />;
  const overview = data.data;
  const cards = [
    {
      name: "سالن‌های من",
      value: overview.halls.length,
      icon: Building2,
      tone: "purple",
    },
    {
      name: "دانش‌آموزان",
      value: overview.student_count,
      icon: GraduationCap,
      tone: "blue",
    },
    {
      name: "حاضر در سالن",
      value: overview.inside_count,
      icon: DoorOpen,
      tone: "green",
    },
    {
      name: "حضور ثبت‌شدهٔ امروز",
      value: overview.today_attendance.completed,
      icon: CheckCheck,
      tone: "amber",
    },
  ];
  return (
    <>
      <section className="staff-welcome">
        <div>
          <span className="eyebrow">امروز، یک قدم منظم‌تر</span>
          <h1>{session.first_name} عزیز، خوش آمدید</h1>
          <p>سالن‌ها و حضور امروز، در یک نگاه.</p>
          <div className="staff-welcome-actions">
            <Link
              className="button primary"
              href={`/${slug}/supervisor/presence`}
            >
              <LogIn size={17} />
              ثبت ورود و خروج
            </Link>
            <Link
              className="button secondary"
              href={`/${slug}/supervisor/attendance`}
            >
              <CheckCheck size={17} />
              حضور و غیاب
            </Link>
          </div>
        </div>
        <div className="staff-welcome-art" aria-hidden="true">
          <Mountain size={82} strokeWidth={1} />
          <span />
          <i />
        </div>
      </section>
      <div className="staff-metrics">
        {cards.map((item) => (
          <div className={`staff-metric ${item.tone}`} key={item.name}>
            <span>
              <item.icon size={23} />
            </span>
            <div>
              <strong>{number(item.value)}</strong>
              <small>{item.name}</small>
            </div>
          </div>
        ))}
      </div>
      {overview.today_attendance.pending > 0 && (
        <Link href={`/${slug}/supervisor/attendance`} className="staff-pending">
          <Sparkles size={19} />
          <span>
            {number(overview.today_attendance.pending)} حضور امروز منتظر ثبت است
          </span>
          <ArrowLeft size={17} />
        </Link>
      )}
      <div className="staff-dashboard-grid">
        <Panel
          title="شیفت‌های امروز"
          action={
            <Link className="text-link" href={`/${slug}/supervisor/schedule`}>
              برنامهٔ هفته
              <ChevronLeft size={16} />
            </Link>
          }
        >
          <ShiftList assignments={overview.today_shifts} />
        </Panel>
        <Panel
          title="سالن‌های من"
          action={
            <Link className="text-link" href={`/${slug}/supervisor/halls`}>
              همهٔ سالن‌ها
              <ChevronLeft size={16} />
            </Link>
          }
        >
          <div className="staff-compact-halls">
            {overview.halls.map((hall) => (
              <Link
                href={`/${slug}/supervisor/presence?hall=${hall.id}`}
                key={hall.id}
              >
                <Building2 size={22} />
                <span>
                  <strong>{hall.name}</strong>
                  <small>
                    {number(hall.active_students)} دانش‌آموز ·{" "}
                    {number(hall.sessions.length)} پارت
                  </small>
                </span>
                <ChevronLeft size={17} />
              </Link>
            ))}
            {!overview.halls.length && (
              <Empty
                title="سالنی واگذار نشده"
                description="برای تعیین سالن مسئولیت با مدیر مجموعه تماس بگیرید."
              />
            )}
          </div>
        </Panel>
      </div>
      <Panel title="شیفت‌های پیش رو">
        <ShiftList assignments={overview.upcoming_shifts.slice(0, 8)} />
      </Panel>
    </>
  );
}

function StaffSkeleton() {
  return (
    <div
      className="staff-skeleton"
      role="status"
      aria-label="در حال دریافت اطلاعات"
    >
      <div />
      <section>
        {[1, 2, 3, 4].map((value) => (
          <div key={value} />
        ))}
      </section>
      <div />
      <span className="sr-only">در حال دریافت اطلاعات…</span>
    </div>
  );
}

function StaffHalls({ slug }: { slug: string }) {
  const data = useData<StaffHall[]>(staffPath(slug, "halls/"));
  return (
    <>
      <PageHeading title="سالن‌های من" eyebrow="فضای مسئولیت شما" />
      {data.error ? (
        <ErrorState error={data.error} retry={data.refresh} />
      ) : !data.data ? (
        <StaffSkeleton />
      ) : !data.data.length ? (
        <Empty
          title="سالنی به شما واگذار نشده"
          description="مدیر مجموعه می‌تواند سالن‌های مسئولیت شما را تعیین کند."
        />
      ) : (
        <div className="staff-hall-grid">
          {data.data.map((hall) => (
            <section className="staff-hall-card" key={hall.id}>
              <span className="staff-hall-mark">
                <Building2 size={28} />
              </span>
              <h2>{hall.name}</h2>
              <span className="staff-muted">
                {number(hall.active_students)} دانش‌آموز فعال
              </span>
              <div className="staff-hall-sessions">
                {hall.sessions.map((item) => (
                  <span key={item.id}>
                    <strong>{item.title || "پارت مطالعاتی"}</strong>
                    <small>
                      {clockTime(item.start_time)} — {clockTime(item.end_time)}
                    </small>
                  </span>
                ))}
              </div>
              <Link
                href={`/${slug}/supervisor/presence?hall=${hall.id}`}
                className="button secondary"
              >
                ورود و خروج
                <ArrowLeft size={16} />
              </Link>
              <Link
                href={`/${slug}/supervisor/attendance?hall=${hall.id}`}
                className="text-link"
              >
                حضور و غیاب سالن
              </Link>
            </section>
          ))}
        </div>
      )}
    </>
  );
}

function initialHall() {
  if (typeof window === "undefined") return "";
  const id = new URLSearchParams(window.location.search).get("hall");
  return id && /^\d+$/.test(id) ? id : "";
}

function PresenceHistory({
  slug,
  student,
  onClose,
}: {
  slug: string;
  student: StaffStudent;
  onClose: () => void;
}) {
  const [page, setPage] = useState(1);
  const data = useData<Paginated<PresenceEvent>>(
    staffPath(slug, `presence/?${queryString({ student: student.id, page })}`),
  );
  return (
    <Modal
      title="تاریخچهٔ ورود و خروج"
      description={`${staffName(student)} · ${student.identifier}`}
      onClose={onClose}
    >
      {data.error ? (
        <ErrorState error={data.error} retry={data.refresh} />
      ) : !data.data ? (
        <Spinner />
      ) : data.data.results.length ? (
        <>
          <ol className="staff-event-timeline">
            {data.data.results.map((event) => (
              <li key={event.id} className={event.kind}>
                <span>
                  {event.kind === "entry" ? (
                    <LogIn size={17} />
                  ) : (
                    <LogOut size={17} />
                  )}
                </span>
                <div>
                  <strong>
                    {event.kind === "entry" ? "ورود" : "خروج"} ·{" "}
                    {event.hall_name}
                  </strong>
                  <small>
                    {date(event.occurred_at, {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </small>
                  <small>ثبت توسط {event.supervisor_name}</small>
                </div>
              </li>
            ))}
          </ol>
          <Pagination page={page} count={data.data.count} onPage={setPage} />
        </>
      ) : (
        <Empty
          title="رویدادی ثبت نشده است"
          description="ورود و خروج‌های ثبت‌شده به ترتیب زمان نمایش داده می‌شوند."
        />
      )}
    </Modal>
  );
}

function StaffStudents({
  slug,
  presence,
}: {
  slug: string;
  presence: boolean;
}) {
  const halls = useData<StaffHall[]>(staffPath(slug, "halls/"));
  const [hall, setHall] = useState(initialHall);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [state, setState] = useState("");
  const [pending, setPending] = useState<number[]>([]);
  const [history, setHistory] = useState<StaffStudent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search);
      setPage(1);
    }, 220);
    return () => clearTimeout(timer);
  }, [search]);
  const data = useData<Paginated<StaffStudent>>(
    staffPath(
      slug,
      `students/?${queryString({ hall, search: query, page, inside: state, page_size: 30 })}`,
    ),
  );
  const events = useData<Paginated<PresenceEvent>>(
    presence
      ? staffPath(
          slug,
          `presence/?${queryString({ hall, page_size: 8, ordering: "-occurred_at" })}`,
        )
      : null,
  );
  async function mark(student: StaffStudent) {
    setPending((values) => [...values, student.id]);
    setError(null);
    setNotice("");
    try {
      await mutate(staffPath(slug, "presence/"), "POST", {
        student: student.id,
        kind: student.inside ? "exit" : "entry",
      });
      setNotice(
        `${student.inside ? "خروج" : "ورود"} ${staffName(student)} ثبت شد.`,
      );
      data.refresh();
      events.refresh();
    } catch (error) {
      setError((error as Error).message);
      data.refresh();
    } finally {
      setPending((values) => values.filter((id) => id !== student.id));
    }
  }
  return (
    <>
      <PageHeading
        title={presence ? "ورود و خروج" : "دانش‌آموزان"}
        eyebrow={presence ? "حضور زندهٔ سالن" : "دانش‌آموزان سالن‌های مسئولیت"}
      >
        <button
          className="button secondary"
          onClick={() => {
            data.refresh();
            events.refresh();
          }}
          disabled={data.loading}
        >
          <RefreshCw size={16} />
          به‌روزرسانی
        </button>
        <HelpTooltip content="زمان هر رویداد توسط سرور ثبت می‌شود. ورود یا خروج تکراری پذیرفته نمی‌شود؛ تاریخچه با سالن زمان ورود حفظ می‌شود. برای ثبت رویداد نیازی به شیفت فعال ندارید." />
      </PageHeading>
      <InlineError message={error} />
      {notice && (
        <div className="staff-success" role="status">
          <Check size={17} />
          {notice}
        </div>
      )}
      <section className="panel staff-directory">
        <div className="staff-toolbar">
          <label className="staff-search">
            <Search size={18} />
            <input
              aria-label="جست‌وجوی دانش‌آموز"
              placeholder="نام یا شناسهٔ دانش‌آموز…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <Field label="سالن">
            <select
              value={hall}
              disabled={halls.loading || !!halls.error}
              onChange={(event) => {
                setHall(event.target.value);
                setPage(1);
              }}
            >
              <option value="">همهٔ سالن‌های من</option>
              {halls.data?.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="حضور فعلی">
            <select
              value={state}
              onChange={(event) => {
                setState(event.target.value);
                setPage(1);
              }}
            >
              <option value="">همه</option>
              <option value="true">داخل سالن</option>
              <option value="false">خارج از سالن</option>
            </select>
          </Field>
        </div>
        {halls.error && <InlineError message={halls.error} />}
        {data.error ? (
          <ErrorState error={data.error} retry={data.refresh} />
        ) : !data.data ? (
          <Spinner />
        ) : !data.data.results.length ? (
          <Empty
            title="دانش‌آموزی پیدا نشد"
            description={
              hall || query || state
                ? "فیلتر یا عبارت جست‌وجو را تغییر دهید."
                : "دانش‌آموزان فعال سالن‌های واگذارشده اینجا نمایش داده می‌شوند."
            }
          />
        ) : (
          <div className="staff-student-list" aria-busy={data.loading}>
            {data.data.results.map((student) => (
              <article
                key={student.id}
                className={`staff-student-row ${student.inside ? "inside" : ""}`}
                data-testid={`presence-student-${student.id}`}
              >
                <span className="staff-student-avatar">
                  {student.first_name.slice(0, 1)}
                </span>
                <div className="staff-student-info">
                  <strong>{staffName(student)}</strong>
                  <small>
                    {student.hall_name} · شناسهٔ {student.identifier}
                  </small>
                </div>
                <span
                  className={`staff-presence ${student.inside ? "inside" : "outside"}`}
                >
                  <i />
                  {student.inside
                    ? student.presence_hall &&
                      student.presence_hall !== student.hall
                      ? "ورودِ سالن قبلی"
                      : "داخل سالن"
                    : "خارج از سالن"}
                  {student.inside &&
                    student.presence_hall &&
                    student.presence_hall !== student.hall && (
                      <HelpTooltip
                        label="راهنمای ورود پیش از انتقال"
                        content="این ورود پیش از انتقال دانش‌آموز ثبت شده است. با ثبت خروج، بازهٔ قبلی بسته می‌شود و سالن تاریخی آن حفظ خواهد شد."
                      />
                    )}
                </span>
                <div className="staff-student-last">
                  <small>آخرین رویداد</small>
                  <span>
                    {student.last_event_at ? time(student.last_event_at) : "—"}
                  </span>
                </div>
                <button
                  className={`button ${student.inside ? "secondary" : "primary"}`}
                  data-testid={`presence-toggle-${student.id}`}
                  disabled={pending.includes(student.id) || data.loading}
                  onClick={() => mark(student)}
                >
                  {pending.includes(student.id) ? (
                    <LoaderCircle size={16} className="spin" />
                  ) : student.inside ? (
                    <LogOut size={16} />
                  ) : (
                    <LogIn size={16} />
                  )}
                  ثبت {student.inside ? "خروج" : "ورود"}
                </button>
                <button
                  className="icon-button"
                  title="تاریخچه"
                  aria-label={`تاریخچهٔ ${staffName(student)}`}
                  onClick={() => setHistory(student)}
                >
                  <Clock3 size={19} />
                </button>
              </article>
            ))}
          </div>
        )}
        {data.data && (
          <Pagination
            count={data.data.count}
            page={page}
            pageSize={30}
            onPage={setPage}
          />
        )}
      </section>
      {presence && (
        <Panel title="آخرین رفت‌وآمدها">
          {events.error ? (
            <ErrorState error={events.error} retry={events.refresh} />
          ) : !events.data ? (
            <Spinner />
          ) : events.data.results.length ? (
            <div className="staff-recent-events">
              {events.data.results.map((event) => (
                <div key={event.id}>
                  <span className={`staff-event-icon ${event.kind}`}>
                    {event.kind === "entry" ? (
                      <LogIn size={17} />
                    ) : (
                      <LogOut size={17} />
                    )}
                  </span>
                  <div>
                    <strong>{event.student_name}</strong>
                    <small>
                      {event.hall_name} · {event.supervisor_name}
                    </small>
                  </div>
                  <span>
                    {event.kind === "entry" ? "ورود" : "خروج"}
                    <small>
                      {date(event.occurred_at, {
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </small>
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <Empty
              title="هنوز رفت‌وآمدی ثبت نشده"
              description="با اولین ورود، جریان حضور سالن اینجا نمایش داده می‌شود."
            />
          )}
        </Panel>
      )}
      {history && (
        <PresenceHistory
          slug={slug}
          student={history}
          onClose={() => setHistory(null)}
        />
      )}
    </>
  );
}

function AttendanceStatusControl({
  name,
  value,
  disabled,
  onChange,
}: {
  name: string;
  value?: AttendanceStatus;
  disabled: boolean;
  onChange: (status: AttendanceStatus) => void;
}) {
  return (
    <div
      className="staff-status-control"
      role="group"
      aria-label={`وضعیت ${name}`}
    >
      {(["present", "late", "absent"] as const).map((status) => (
        <button
          key={status}
          type="button"
          className={`${status} ${value === status ? "selected" : ""}`}
          disabled={disabled}
          aria-pressed={value === status}
          onClick={() => onChange(status)}
        >
          {value === status && <Check size={13} />} {attendanceLabels[status]}
        </button>
      ))}
    </div>
  );
}

function AutoPreview({
  slug,
  preview,
  onClose,
  onSaved,
}: {
  slug: string;
  preview: AttendanceRoster;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [selected, setSelected] = useState(() =>
    automaticSelection(preview.students).slice(0, 500),
  );
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const eligible = automaticSelection(preview.students);
  const filtered = preview.students.filter((student) =>
    `${staffName(student)} ${student.identifier}`.includes(query),
  );
  const rows = filtered.slice((page - 1) * 40, page * 40);
  return (
    <Modal
      title={preview.provisional ? "پیش‌نمایش موقت حضور" : "تأیید حضور خودکار"}
      description={`${date(preview.date)} · ${preview.sessions.find((item) => item.id === preview.session)?.title || "پارت مطالعاتی"}`}
      onClose={() => !pending && onClose()}
      wide
    >
      <div className="staff-auto-summary">
        {(["present", "late", "absent"] as const).map((status) => (
          <span key={status} className={status}>
            <strong>
              {number(
                preview.students.filter(
                  (row) => row.calculated_status === status,
                ).length,
              )}
            </strong>
            {attendanceLabels[status]}
          </span>
        ))}
      </div>
      {preview.provisional ? (
        <p className="staff-warning">
          <Clock3 size={17} />
          پارت هنوز پایان نیافته است. این وضعیت‌ها موقت‌اند؛ ثبت نهایی پس از{" "}
          {preview.ends_at ? time(preview.ends_at) : "پایان پارت"} امکان‌پذیر
          است.
        </p>
      ) : (
        <p className="staff-muted">
          وضعیت‌ها از تاریخچهٔ واقعی ورود و خروج محاسبه شده‌اند. فقط ردیف‌های
          انتخاب‌شده ثبت می‌شوند.
        </p>
      )}
      <InlineError message={error} />
      <div className="staff-toolbar">
        {!preview.provisional && eligible.length > 500 && (
          <p className="staff-warning">
            {number(selected.length)} از {number(eligible.length)} ردیف مجاز
            انتخاب شده است. در هر مرحله تا ۵۰۰ ردیف ثبت می‌شود؛ برای باقی
            دانش‌آموزان پس از ثبت، پیش‌نمایش تازه بگیرید و ردیف‌های دلخواه را
            انتخاب کنید.
          </p>
        )}
        <label className="staff-search">
          <Search size={17} />
          <input
            placeholder="جست‌وجوی دانش‌آموز…"
            aria-label="جست‌وجو در پیش‌نمایش"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
          />
        </label>
        {!preview.provisional && (
          <button
            className="button secondary"
            disabled={pending}
            onClick={() =>
              setSelected(
                selected.length === Math.min(eligible.length, 500)
                  ? []
                  : eligible.slice(0, 500),
              )
            }
          >
            {selected.length === Math.min(eligible.length, 500)
              ? "لغو انتخاب همه"
              : "انتخاب ردیف‌های مجاز"}
          </button>
        )}
      </div>
      <div className="staff-auto-list">
        {rows.map((student) => (
          <label
            key={student.id}
            className={`staff-auto-row ${!student.selectable ? "protected" : ""}`}
          >
            {!preview.provisional && (
              <input
                type="checkbox"
                checked={selected.includes(student.id)}
                disabled={
                  pending ||
                  !eligible.includes(student.id) ||
                  (!selected.includes(student.id) && selected.length >= 500)
                }
                onChange={(event) =>
                  setSelected((values) =>
                    event.target.checked
                      ? [...values, student.id]
                      : values.filter((id) => id !== student.id),
                  )
                }
              />
            )}
            <div>
              <strong>{staffName(student)}</strong>
              <small>
                {student.identifier}
                {student.record
                  ? ` · ثبت قبلی: ${attendanceLabels[student.record.status]}`
                  : " · ثبت جدید"}
              </small>
              {student.record && !student.selectable && (
                <small>
                  {student.record.source === "manual"
                    ? "ثبت دستی محفوظ است"
                    : "ثبت مراقب دیگر یا پایان مهلت ویرایش"}
                </small>
              )}
            </div>
            <span
              className={`staff-status-badge ${student.calculated_status || "absent"}`}
            >
              {attendanceLabels[student.calculated_status || "absent"]}
            </span>
            {student.early_departure && (
              <span className="staff-early">
                خروج زودهنگام
                <small>
                  {student.departed_at ? time(student.departed_at) : ""}
                </small>
              </span>
            )}
          </label>
        ))}
      </div>
      <Pagination
        count={filtered.length}
        page={page}
        pageSize={40}
        onPage={setPage}
      />
      <div className="modal-footer">
        <button
          type="button"
          className="button secondary"
          disabled={pending}
          onClick={onClose}
        >
          {preview.provisional ? "بستن پیش‌نمایش" : "انصراف"}
        </button>
        {!preview.provisional && (
          <button
            className="button primary"
            data-testid="attendance-auto-save"
            disabled={pending || !selected.length || selected.length > 500}
            onClick={async () => {
              setPending(true);
              setError(null);
              try {
                await mutate(staffPath(slug, "attendance/automatic/"), "POST", {
                  preview_token: preview.preview_token,
                  students: selected,
                });
                onSaved();
              } catch (error) {
                setError((error as Error).message);
              } finally {
                setPending(false);
              }
            }}
          >
            {pending ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <CheckCheck size={16} />
            )}
            ثبت نهایی {number(selected.length)} دانش‌آموز
          </button>
        )}
      </div>
    </Modal>
  );
}

function AttendanceTable({
  slug,
  roster,
  refresh,
}: {
  slug: string;
  roster: AttendanceRoster;
  refresh: () => void;
}) {
  const [draft, setDraft] = useState<Record<number, AttendanceStatus>>({});
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState<AttendanceRoster | null>(null);
  const filtered = roster.students.filter((student) =>
    `${staffName(student)} ${student.identifier}`.includes(query),
  );
  const rows = filtered.slice((page - 1) * 40, page * 40);
  const changes = attendanceChanges(roster.students, draft);
  const dirty = changes.length > 0;
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  return (
    <section className="panel staff-attendance-panel">
      <div className="staff-attendance-header">
        <div>
          <h2>
            {roster.sessions.find((item) => item.id === roster.session)
              ?.title || "پارت مطالعاتی"}
          </h2>
          <span className="staff-muted">
            {roster.starts_at ? time(roster.starts_at) : ""} —{" "}
            {roster.ends_at ? time(roster.ends_at) : ""} ·{" "}
            {number(roster.students.length)} دانش‌آموز
          </span>
        </div>
        <div className="staff-attendance-header-actions">
          <HelpTooltip
            label="راهنمای حضور خودکار"
            content="حضور در شروع پارت: حاضر. اولین ورود در طول پارت: تأخیر. نبودِ حضور در بازهٔ پارت: غایب. خروج زودهنگام جدا ثبت می‌شود. ثبت خودکار فقط پس از پایان پارت انجام می‌شود و ثبت‌های دستی را تغییر نمی‌دهد."
          />
          <button
            className="button primary staff-auto-button"
            data-testid="attendance-auto-preview"
            disabled={pending || !roster.students.length || dirty}
            title={
              dirty ? "ابتدا تغییرات دستی را ذخیره یا لغو کنید" : undefined
            }
            onClick={async () => {
              setPending(true);
              setError(null);
              try {
                setPreview(
                  await mutate<AttendanceRoster>(
                    staffPath(slug, "attendance/preview/"),
                    "POST",
                    {
                      hall: roster.hall,
                      date: roster.date,
                      session: roster.session,
                    },
                  ),
                );
              } catch (error) {
                setError((error as Error).message);
              } finally {
                setPending(false);
              }
            }}
          >
            <Sparkles size={17} />
            حضور خودکار
          </button>
        </div>
      </div>
      <InlineError message={error} />
      {notice && (
        <div className="staff-success" role="status">
          <Check size={16} />
          {notice}
        </div>
      )}
      <div className="staff-toolbar">
        <label className="staff-search">
          <Search size={18} />
          <input
            aria-label="جست‌وجو در حضور و غیاب"
            placeholder="نام یا شناسهٔ دانش‌آموز…"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
          />
        </label>
        <div className="staff-batch">
          <span>ثبت گروهی این صفحه:</span>
          {(["present", "late", "absent"] as const).map((status) => (
            <button
              className={`staff-status-badge ${status}`}
              key={status}
              disabled={pending}
              onClick={() =>
                setDraft((values) => ({
                  ...values,
                  ...Object.fromEntries(
                    rows
                      .filter(
                        (student) => !student.record || student.record.can_edit,
                      )
                      .map((student) => [student.id, status]),
                  ),
                }))
              }
            >
              {attendanceLabels[status]}
            </button>
          ))}
        </div>
      </div>
      {roster.students.length ? (
        <div className="staff-attendance-list">
          {rows.map((student) => {
            const editable = !student.record || student.record.can_edit;
            const value = draft[student.id] || student.record?.status;
            return (
              <article
                key={student.id}
                className={`staff-attendance-row ${!editable ? "readonly" : ""}`}
                data-testid={`attendance-student-${student.id}`}
              >
                <span className="staff-student-avatar">
                  {student.first_name.slice(0, 1)}
                </span>
                <div className="staff-attendance-person">
                  <strong>{staffName(student)}</strong>
                  <small>شناسهٔ {student.identifier}</small>
                  {student.record && (
                    <small>
                      {student.record.recorder.name} ·{" "}
                      {student.record.source === "automatic"
                        ? "خودکار"
                        : "دستی"}
                      {!editable ? " · فقط مشاهده" : ""}
                    </small>
                  )}
                </div>
                <AttendanceStatusControl
                  name={staffName(student)}
                  value={value}
                  disabled={pending || !editable}
                  onChange={(status) =>
                    setDraft((values) => ({ ...values, [student.id]: status }))
                  }
                />
                {student.record?.early_departure && (
                  <span className="staff-early">
                    خروج زودهنگام
                    <small>
                      {student.record.departed_at
                        ? time(student.record.departed_at)
                        : ""}
                    </small>
                  </span>
                )}
                {student.record && !editable && (
                  <LockKeyhole
                    size={15}
                    className="staff-muted"
                    aria-label="فقط مشاهده"
                  />
                )}
              </article>
            );
          })}
        </div>
      ) : (
        <Empty
          title="دانش‌آموز فعال ندارد"
          description="دانش‌آموزان فعال این سالن برای تمام پارت‌های سالن در فهرست حضور قرار می‌گیرند."
        />
      )}
      <Pagination
        count={filtered.length}
        page={page}
        pageSize={40}
        onPage={setPage}
      />
      <div className="staff-save-bar">
        {changes.length > 500 && (
          <span className="staff-warning">
            حداکثر ۵۰۰ تغییر در هر ثبت؛ برخی تغییرات را لغو کنید.
          </span>
        )}
        <span>
          {changes.length
            ? `${number(changes.length)} تغییر آمادهٔ ثبت`
            : "تغییری ثبت نشده"}
        </span>
        <HelpTooltip
          label="راهنمای مهلت ویرایش"
          content="ثبت‌کننده تا ۴۸ ساعت پس از اولین ثبت می‌تواند اصلاح کند. سایر مراقبین فقط امکان مشاهده دارند. مدیر مجموعه با ثبت دلیل می‌تواند همیشه اصلاح کند؛ ویرایش، مهلت را تمدید نمی‌کند."
        />
        <button
          className="button secondary"
          disabled={!dirty || pending}
          onClick={() => setDraft({})}
        >
          لغو تغییرات
        </button>
        <button
          className="button primary"
          data-testid="attendance-manual-save"
          disabled={!dirty || pending || changes.length > 500}
          onClick={async () => {
            setPending(true);
            setError(null);
            try {
              await mutate(staffPath(slug, "attendance/bulk/"), "POST", {
                hall: roster.hall,
                date: roster.date,
                session: roster.session,
                records: changes,
              });
              setDraft({});
              setNotice("حضور و غیاب ذخیره شد.");
              refresh();
            } catch (error) {
              setError((error as Error).message);
            } finally {
              setPending(false);
            }
          }}
        >
          {pending ? (
            <LoaderCircle size={17} className="spin" />
          ) : (
            <Check size={17} />
          )}
          ذخیرهٔ حضور و غیاب
        </button>
      </div>
      {preview && (
        <AutoPreview
          slug={slug}
          preview={preview}
          onClose={() => setPreview(null)}
          onSaved={() => {
            setPreview(null);
            setNotice("حضور خودکار ثبت شد.");
            refresh();
          }}
        />
      )}
    </section>
  );
}

function StaffAttendance({ slug }: { slug: string }) {
  const halls = useData<StaffHall[]>(staffPath(slug, "halls/"));
  const [hall, setHall] = useState(initialHall);
  const [selectedDate, setSelectedDate] = useState(tehranToday);
  const [session, setSession] = useState("");
  const selectedHall =
    hall || (halls.data?.[0] ? String(halls.data[0].id) : "");
  const data = useData<AttendanceRoster>(
    selectedHall && selectedDate
      ? staffPath(
          slug,
          `attendance/?${queryString({ hall: selectedHall, date: selectedDate, session })}`,
        )
      : null,
  );
  return (
    <>
      <PageHeading title="حضور و غیاب" eyebrow="حضور روشن، ثبت دقیق" />
      <div className="panel staff-attendance-filters">
        <Field label="سالن">
          <select
            value={selectedHall}
            disabled={halls.loading || !!halls.error}
            onChange={(event) => {
              setHall(event.target.value);
              setSession("");
            }}
          >
            <option value="" disabled>
              انتخاب سالن
            </option>
            {halls.data?.map((item) => (
              <option value={item.id} key={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </Field>
        <DateField
          label="تاریخ"
          value={selectedDate}
          required
          onChange={(value) => {
            setSelectedDate(value);
            setSession("");
          }}
        />
        <Field label="پارت مطالعاتی">
          <select
            value={session}
            data-testid="attendance-session"
            disabled={!data.data || data.loading}
            onChange={(event) => setSession(event.target.value)}
          >
            <option value="">انتخاب پارت</option>
            {data.data?.sessions.map((item) => (
              <option value={item.id} key={item.id}>
                {item.title} · {clockTime(item.start_time)} —{" "}
                {clockTime(item.end_time)}
              </option>
            ))}
          </select>
        </Field>
      </div>
      {halls.error ? (
        <ErrorState error={halls.error} retry={halls.refresh} />
      ) : halls.loading && !halls.data ? (
        <Spinner />
      ) : !halls.data?.length ? (
        <Empty
          title="سالنی واگذار نشده"
          description="برای ثبت حضور، مدیر باید سالن مسئولیت شما را تعیین کند."
        />
      ) : !selectedDate ? (
        <Empty
          title="تاریخ را انتخاب کنید"
          description="تاریخ را از تقویم شمسی انتخاب کنید."
        />
      ) : data.error ? (
        <ErrorState error={data.error} retry={data.refresh} />
      ) : !data.data || data.loading ? (
        <Spinner />
      ) : !session ? (
        <Empty
          title="پارت امروز را انتخاب کنید"
          description={
            data.data.sessions.length
              ? "فهرست دانش‌آموزان پس از انتخاب پارت نمایش داده می‌شود."
              : "پارتی برای این سالن تعیین نشده است."
          }
        />
      ) : (
        <AttendanceTable
          key={`${selectedHall}:${selectedDate}:${session}`}
          slug={slug}
          roster={data.data}
          refresh={data.refresh}
        />
      )}
    </>
  );
}

function StaffScheduleView({ slug }: { slug: string }) {
  const [week, setWeek] = useState(() => saturdayOfWeek(tehranToday()));
  const [hall, setHall] = useState("");
  const data = useData<StaffSchedule>(
    staffPath(slug, `schedule/?${queryString({ week_start: week, hall })}`),
  );
  return (
    <>
      <PageHeading title="برنامه شیفت‌ها" eyebrow="هفتهٔ هماهنگ شما">
        <HelpTooltip content="این برنامه برای هماهنگی کاری است. دسترسی شما به سالن‌های مسئولیت، محدود به ساعت شیفت نیست." />
      </PageHeading>
      <div className="panel staff-schedule-toolbar">
        <div className="staff-week-nav">
          <button
            className="icon-button"
            aria-label="هفتهٔ قبل"
            onClick={() => setWeek((value) => addCalendarDays(value, -7))}
          >
            <ChevronRight size={20} />
          </button>
          <strong>
            {date(week, { month: "short" })} —{" "}
            {date(addCalendarDays(week, 6), { month: "short" })}
          </strong>
          <button
            className="icon-button"
            aria-label="هفتهٔ بعد"
            onClick={() => setWeek((value) => addCalendarDays(value, 7))}
          >
            <ChevronLeft size={20} />
          </button>
          <button
            className="button secondary"
            onClick={() => setWeek(saturdayOfWeek(tehranToday()))}
          >
            این هفته
          </button>
        </div>
        <Field label="سالن">
          <select
            value={hall}
            onChange={(event) => setHall(event.target.value)}
          >
            <option value="">همهٔ سالن‌های من</option>
            {data.data?.halls.map((item) => (
              <option value={item.id} key={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </Field>
      </div>
      {data.error ? (
        <ErrorState error={data.error} retry={data.refresh} />
      ) : !data.data ? (
        <StaffSkeleton />
      ) : (
        <div className="staff-week-grid">
          {data.data.days.map((day) => {
            const shifts =
              data.data?.assignments.filter(
                (assignment) => assignment.date === day.date,
              ) || [];
            return (
              <section
                key={day.date}
                className={`staff-week-day ${day.date === tehranToday() ? "today" : ""}`}
              >
                <header>
                  <strong>
                    {date(day.date, {
                      weekday: "long",
                      year: undefined,
                      month: undefined,
                      day: undefined,
                    })}
                  </strong>
                  <span>
                    {date(day.date, { month: "short", year: undefined })}
                  </span>
                  {day.date === tehranToday() && <small>امروز</small>}
                </header>
                <div>
                  {shifts.length ? (
                    shifts.map((shift) => (
                      <article
                        className={`staff-week-shift ${shift.conflict_override ? "conflict" : ""}`}
                        key={shift.id}
                      >
                        <span>
                          <Clock3 size={14} />
                          {clockTime(shift.start_time)} —{" "}
                          {clockTime(shift.end_time)}
                        </span>
                        <strong>{shift.shift_name}</strong>
                        <small>{shift.hall_name}</small>
                        {shift.conflict_override && (
                          <small className="staff-conflict-label">
                            هم‌پوشانی با تأیید مدیر
                          </small>
                        )}
                      </article>
                    ))
                  ) : (
                    <span className="staff-week-empty">بدون شیفت</span>
                  )}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}

function StaffProfile({
  slug,
  session,
  onSaved,
}: {
  slug: string;
  session: StaffSession;
  onSaved: () => void;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  return (
    <>
      <PageHeading title="پروفایل" eyebrow="حساب شخصی شما" />
      <div className="staff-dashboard-grid">
        <Panel title="اطلاعات حساب">
          <div className="staff-profile-identity">
            <span className="staff-student-avatar">
              {session.first_name.slice(0, 1)}
            </span>
            <div>
              <h2>{staffName(session)}</h2>
              <span className="staff-status-badge present">حساب فعال</span>
            </div>
          </div>
          <dl className="staff-profile-info">
            <div>
              <dt>مجموعه</dt>
              <dd>{session.organization.name}</dd>
            </div>
            <div>
              <dt>شماره همراه / نام کاربری</dt>
              <dd dir="ltr">{session.phone}</dd>
            </div>
            <div>
              <dt>سالن‌های مسئولیت</dt>
              <dd>
                {session.halls.map((item) => item.name).join("، ") ||
                  "بدون سالن"}
              </dd>
            </div>
            <div>
              <dt>ایجاد حساب</dt>
              <dd>{date(session.created_at)}</dd>
            </div>
          </dl>
          <p className="staff-muted">
            برای تغییر اطلاعات پرونده یا سالن‌ها با مدیر مجموعه تماس بگیرید.
          </p>
        </Panel>
        <Panel title="تغییر رمز عبور" action={<LockKeyhole size={20} />}>
          <form
            className="staff-profile-form"
            onSubmit={async (event) => {
              event.preventDefault();
              const form = event.currentTarget;
              const values = new FormData(form);
              if (
                values.get("new_password") !== values.get("confirm_password")
              ) {
                setError("تکرار رمز عبور مطابقت ندارد.");
                return;
              }
              setPending(true);
              setError(null);
              setNotice("");
              try {
                await mutate(staffPath(slug, "profile/"), "PATCH", {
                  current_password: values.get("current_password"),
                  new_password: values.get("new_password"),
                });
                form.reset();
                setNotice(
                  "رمز عبور تغییر کرد. نشست‌های دیگر نیاز به ورود دوباره دارند.",
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
            {notice && (
              <div className="staff-success" role="status">
                <Check size={16} />
                {notice}
              </div>
            )}
            <fieldset disabled={pending}>
              <legend className="sr-only">تغییر رمز</legend>
              <Field label="رمز عبور فعلی" required>
                <input
                  type="password"
                  name="current_password"
                  autoComplete="current-password"
                  required
                  dir="ltr"
                  maxLength={4096}
                />
              </Field>
              <Field
                label="رمز عبور جدید"
                required
                hint="حداقل ۱۰ کاراکتر؛ رمز قوی و غیرتکراری انتخاب کنید."
              >
                <input
                  type="password"
                  name="new_password"
                  autoComplete="new-password"
                  minLength={10}
                  maxLength={4096}
                  required
                  dir="ltr"
                />
              </Field>
              <Field label="تکرار رمز عبور جدید" required>
                <input
                  type="password"
                  name="confirm_password"
                  autoComplete="new-password"
                  required
                  minLength={10}
                  maxLength={4096}
                  dir="ltr"
                />
              </Field>
            </fieldset>
            <Submit pending={pending}>تغییر رمز عبور</Submit>
          </form>
        </Panel>
      </div>
    </>
  );
}

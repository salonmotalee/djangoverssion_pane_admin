"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Bell,
  ChevronDown,
  MessagesSquare,
  LayoutDashboard,
  LogOut,
  Menu,
  ShieldCheck,
  Sparkles,
  Users,
  UserRound,
  History,
  X,
} from "lucide-react";
import { useAuth, useToast } from "./providers";
import { ErrorState, Logo, Spinner } from "./ui";
import { date, displayName, roles } from "@/lib/format";
import { SupportBell } from "./support";

const nav = [
  { href: "/dashboard", title: "نمای کلی", Icon: LayoutDashboard },
  { href: "/customers", title: "مجموعه‌ها", Icon: Users },
  { href: "/alerts", title: "هشدارهای سرویس", Icon: Bell },
  {
    href: "/support",
    title: "مدیریت تیکت‌ها",
    Icon: MessagesSquare,
    support: true,
  },
  { href: "/users", title: "کاربران و دسترسی", Icon: ShieldCheck, admin: true },
  { href: "/activity", title: "تاریخچه فعالیت‌ها", Icon: History, admin: true },
];
export function Shell({ children }: { children: React.ReactNode }) {
  const { user, loading, error, logout, refresh } = useAuth();
  const router = useRouter();
  const path = usePathname();
  const toast = useToast();
  const sidebarRef = useRef<HTMLElement>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const [openPath, setOpenPath] = useState<string | null>(null);
  const open = openPath === path;
  const setOpen = useCallback(
    (value: boolean) => setOpenPath(value ? path : null),
    [path],
  );
  const [leaving, setLeaving] = useState(false);
  useEffect(() => {
    if (!loading && !user && !error) router.replace("/login");
  }, [user, loading, router, error]);
  useEffect(() => {
    const viewport = window.matchMedia("(max-width: 900px)");
    const resize = (event: MediaQueryListEvent) => {
      if (!event.matches) setOpen(false);
    };
    viewport.addEventListener("change", resize);
    return () => viewport.removeEventListener("change", resize);
  }, [setOpen]);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement;
    const workspace = workspaceRef.current;
    const originalOverflow = document.body.style.overflow;
    if (workspace) workspace.inert = true;
    document.body.style.overflow = "hidden";
    sidebarRef.current
      ?.querySelector<HTMLElement>('.nav-item[aria-current="page"]')
      ?.focus();
    const fn = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
      if (event.key === "Tab") {
        const elements = Array.from(
          sidebarRef.current?.querySelectorAll<HTMLElement>(
            "a[href],button:not([disabled])",
          ) || [],
        ).filter((element) => element.offsetParent !== null);
        const first = elements[0];
        const last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    window.addEventListener("keydown", fn);
    return () => {
      window.removeEventListener("keydown", fn);
      if (workspace) workspace.inert = false;
      document.body.style.overflow = originalOverflow;
      previous?.focus();
    };
  }, [open, setOpen]);
  if (loading)
    return (
      <div className="session-loading">
        <Logo />
        <Spinner label="آماده‌سازی فضای کار…" />
      </div>
    );
  if (error)
    return (
      <div className="session-loading">
        <Logo />
        <ErrorState error={error} retry={() => void refresh()} />
      </div>
    );
  if (!user) return null;
  const canManage = user.role !== "operator";
  const canSupport = user.role === "super_admin" || user.can_support;
  const current =
    nav.find((item) => path.startsWith(item.href))?.title || "پروفایل من";
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        رفتن به محتوای اصلی
      </a>
      {open && (
        <button
          className="sidebar-backdrop"
          aria-label="بستن منو"
          onClick={() => setOpen(false)}
        />
      )}
      <aside
        ref={sidebarRef}
        className={`sidebar ${open ? "is-open" : ""}`}
        aria-label="ناوبری اصلی"
      >
        <div className="sidebar-logo">
          <Link
            href="/dashboard"
            aria-label="مدار، صفحه اصلی"
            onClick={() => setOpen(false)}
          >
            <Logo />
          </Link>
          <button
            className="icon-button mobile-close"
            aria-label="بستن منو"
            onClick={() => setOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <div className="workspace-selector">
          <span className="workspace-icon">
            <Sparkles size={19} />
          </span>
          <div>
            <strong>فضای مدیریت</strong>
            <small>پلتفرم مدار</small>
          </div>
          <span className="workspace-live" />
        </div>
        <div className="nav-label">فضای کار</div>
        <nav>
          {nav
            .filter(
              (item) =>
                (!item.admin || canManage) && (!item.support || canSupport),
            )
            .map(({ href, title, Icon }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className={`nav-item ${path.startsWith(href) ? "active" : ""}`}
                aria-current={path.startsWith(href) ? "page" : undefined}
              >
                <Icon size={20} strokeWidth={1.7} />
                <span>{title}</span>
                {path.startsWith(href) && <i />}
              </Link>
            ))}
        </nav>
        <div className="sidebar-bottom">
          <Link
            href="/profile"
            onClick={() => setOpen(false)}
            className={`nav-item ${path === "/profile" ? "active" : ""}`}
          >
            <UserRound size={20} />
            <span>پروفایل و امنیت</span>
          </Link>
          <button
            className="nav-item logout"
            disabled={leaving}
            onClick={async () => {
              setLeaving(true);
              try {
                await logout();
                router.replace("/login");
              } catch (error) {
                toast((error as Error).message, "error");
              } finally {
                setLeaving(false);
              }
            }}
          >
            <LogOut size={20} />
            <span>{leaving ? "در حال خروج…" : "خروج از حساب"}</span>
          </button>
        </div>
      </aside>
      <div className="workspace" ref={workspaceRef}>
        <header className="topbar">
          <div className="topbar-crumb">
            <button
              className="icon-button mobile-menu"
              aria-label="باز کردن منو"
              aria-expanded={open}
              onClick={() => setOpen(true)}
            >
              <Menu size={22} />
            </button>
            <span>فضای مدیریت</span>
            <span className="crumb-separator">/</span>
            <strong>{current}</strong>
          </div>
          <div className="topbar-end">
            {canSupport && <SupportBell />}
            <span className="today">
              <span className="green-dot" />
              {date(new Date().toISOString())}
            </span>
            <Link
              className="notification-button"
              href="/alerts"
              aria-label="هشدارهای سرویس"
            >
              <Bell size={19} />
            </Link>
            <span className="topbar-divider" />
            <Link className="user-mini" href="/profile">
              <span className="avatar">{displayName(user).slice(0, 1)}</span>
              <span>
                <strong>{displayName(user)}</strong>
                <small>{roles[user.role]}</small>
              </span>
              <ChevronDown size={14} />
            </Link>
          </div>
        </header>
        <main id="main-content" className="main-content">
          {children}
        </main>
        <footer className="workspace-footer">
          <span>مدار؛ همه چیز در مسیر درست</span>
          <span>
            زمان محلی تهران <span className="footer-dot">·</span> نسخه ۱.۰
          </span>
        </footer>
      </div>
    </div>
  );
}

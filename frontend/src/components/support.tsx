"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Bell,
  CheckCheck,
  CircleCheck,
  Clock3,
  LifeBuoy,
  MessageCircle,
  Plus,
  RotateCcw,
  Search,
  Send,
  X,
} from "lucide-react";
import { mutate } from "@/lib/api";
import {
  createSupportNotificationStore,
  emptySupportNotifications,
} from "@/lib/support-notifications";
import { date, displayName, number, queryString, time } from "@/lib/format";
import { useData } from "@/lib/use-data";
import type { Customer, Paginated } from "@/lib/types";
import {
  chronologicalMessages,
  supportHref,
  supportPrefix,
  ticketCategories,
  ticketNeedsReopen,
  ticketNotificationRevision,
  ticketPriorities,
  ticketStatuses,
  type SupportMessage,
  type SupportStaff,
  type SupportStatusEvent,
  type SupportTicket,
} from "@/lib/support";
import { useAuth, useToast } from "./providers";
import {
  DateField,
  Empty,
  ErrorState,
  Field,
  InlineError,
  Modal,
  PageHeading,
  Pagination,
  Spinner,
  Submit,
} from "./ui";
import "./support.css";

const notificationStores = new Map<
  string,
  ReturnType<typeof createSupportNotificationStore>
>();
function useSupportNotifications(slug?: string) {
  const { user } = useAuth();
  const prefix = supportPrefix(slug);
  const recipient = slug ? prefix : `${prefix}user:${user?.id || "guest"}`;
  let store = notificationStores.get(recipient);
  if (!store) {
    store = createSupportNotificationStore(prefix);
    notificationStores.set(recipient, store);
  }
  const snapshot = useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    () => emptySupportNotifications,
  );
  return { ...snapshot, refresh: store.refresh, invalidate: store.invalidate };
}

function TicketBadge({ ticket }: { ticket: SupportTicket }) {
  return (
    <span className={`support-status support-status-${ticket.status}`}>
      <i aria-hidden="true" />
      {ticketStatuses[ticket.status]}
    </span>
  );
}

export function SupportBell({ slug }: { slug?: string }) {
  const { data, loading, error, refresh, invalidate } =
    useSupportNotifications(slug);
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [readError, setReadError] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const unread = data?.unread_count || 0;
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  return (
    <div className="support-notifications" ref={root}>
      <button
        ref={button}
        className="icon-button support-bell"
        type="button"
        aria-label={
          unread
            ? `اعلان‌های پشتیبانی، ${number(unread)} خوانده‌نشده`
            : "اعلان‌های پشتیبانی"
        }
        aria-expanded={open}
        aria-controls={panelId}
        data-testid="support-bell"
        onClick={() => {
          setOpen((value) => !value);
          if (!open) void refresh();
        }}
      >
        <Bell size={20} />
        {unread > 0 && (
          <span className="support-bell-count" aria-hidden="true">
            {unread > 99 ? "۹۹+" : number(unread)}
          </span>
        )}
      </button>
      {open && (
        <section
          id={panelId}
          className="support-notification-panel"
          aria-label="اعلان‌های پشتیبانی"
        >
          <div className="support-notification-heading">
            <strong>اعلان‌های پشتیبانی</strong>
            <button
              className="icon-button"
              aria-label="بستن اعلان‌ها"
              onClick={() => {
                setOpen(false);
                button.current?.focus();
              }}
            >
              <X size={17} />
            </button>
          </div>
          {loading && !data ? (
            <Spinner label="دریافت اعلان‌ها…" />
          ) : error ? (
            <ErrorState error={error} retry={() => void refresh()} />
          ) : !data?.items.length ? (
            <div className="support-notification-empty">
              <CheckCheck size={24} />
              <p>اعلان تازه‌ای ندارید.</p>
            </div>
          ) : (
            <div className="support-notification-items">
              {data.items.map((item) => (
                <Link
                  key={item.id}
                  href={supportHref(slug, item.ticket_id)}
                  className={`support-notification-item ${item.is_read ? "read" : "unread"}`}
                  onClick={() => setOpen(false)}
                >
                  <span className="support-notification-symbol">
                    {item.kind === "message" ? (
                      <MessageCircle size={17} />
                    ) : (
                      <CircleCheck size={17} />
                    )}
                  </span>
                  <span>
                    <strong>{item.subject}</strong>
                    <span>{item.body}</span>
                    <small>
                      {date(item.created_at)} · {time(item.created_at)}
                      {!item.is_read && " · خوانده‌نشده"}
                    </small>
                  </span>
                </Link>
              ))}
            </div>
          )}
          <InlineError message={readError} />
          <div className="support-notification-footer">
            <Link href={supportHref(slug)} onClick={() => setOpen(false)}>
              همهٔ تیکت‌ها
            </Link>
            {unread > 0 && (
              <button
                className="text-link"
                disabled={pending}
                onClick={async () => {
                  setPending(true);
                  setReadError(null);
                  try {
                    await mutate(
                      `${supportPrefix(slug)}notifications/read/`,
                      "POST",
                      {
                        ids: data?.items
                          .filter((item) => !item.is_read)
                          .map((item) => item.id),
                      },
                    );
                    await invalidate();
                  } catch (error) {
                    setReadError((error as Error).message);
                  } finally {
                    setPending(false);
                  }
                }}
              >
                {pending ? "در حال ثبت…" : "خواندن اعلان‌های نمایش‌داده‌شده"}
              </button>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

export function SupportIndicators({ slug }: { slug?: string }) {
  const { data, error, loading, refresh } = useSupportNotifications(slug);
  if (loading && !data)
    return (
      <div className="support-indicators" role="status">
        <LifeBuoy size={18} /> دریافت وضعیت پشتیبانی…
      </div>
    );
  if (error)
    return (
      <div
        className="support-indicators support-indicators-error"
        role="status"
      >
        <LifeBuoy size={18} /> وضعیت پشتیبانی دریافت نشد.
        <button className="text-link" onClick={() => void refresh()}>
          تلاش دوباره
        </button>
      </div>
    );
  if (!data) return null;
  return (
    <Link className="support-indicators" href={supportHref(slug)}>
      <span className="support-indicator-title">
        <LifeBuoy size={19} /> پشتیبانی
      </span>
      <span>
        <b>{number(data.open_tickets)}</b> تیکت باز
      </span>
      <span>
        <b>{number(slug ? data.awaiting_customer : data.awaiting_support)}</b>{" "}
        {slug ? "منتظر پاسخ شما" : "منتظر پاسخ پشتیبانی"}
      </span>
      <span>
        <b>{number(data.unread_messages)}</b> پیام خوانده‌نشده
      </span>
    </Link>
  );
}

function CreateTicket({
  slug,
  onClose,
}: {
  slug: string;
  onClose: () => void;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const toast = useToast();
  const { invalidate } = useSupportNotifications(slug);
  return (
    <Modal
      title="تیکت جدید"
      onClose={() => {
        if (!pending) onClose();
      }}
      wide
    >
      <form
        data-testid="support-create-form"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const body = {
            subject: String(form.get("subject") || "").trim(),
            category: form.get("category"),
            priority: form.get("priority"),
            description: String(form.get("description") || "").trim(),
          };
          if (!body.subject || !body.description) {
            setError("موضوع و شرح درخواست را وارد کنید.");
            return;
          }
          setPending(true);
          setError(null);
          try {
            const ticket = await mutate<SupportTicket>(
              `${supportPrefix(slug)}tickets/`,
              "POST",
              body,
            );
            toast("تیکت شما ثبت شد.");
            void invalidate();
            onClose();
            router.push(supportHref(slug, ticket.id));
          } catch (error) {
            setError((error as Error).message);
          } finally {
            setPending(false);
          }
        }}
      >
        <Field label="موضوع" required>
          <input name="subject" required maxLength={200} disabled={pending} />
        </Field>
        <div className="form-grid">
          <Field label="دسته‌بندی" required>
            <select name="category" defaultValue="general" disabled={pending}>
              {Object.entries(ticketCategories).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="اولویت" required>
            <select name="priority" defaultValue="normal" disabled={pending}>
              {Object.entries(ticketPriorities).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Field label="شرح درخواست" required>
          <textarea
            name="description"
            required
            rows={6}
            maxLength={10000}
            disabled={pending}
            placeholder="چه مشکلی پیش آمده و چه کمکی نیاز دارید؟"
          />
        </Field>
        <InlineError message={error} />
        <div className="modal-footer">
          <button
            className="button secondary"
            type="button"
            disabled={pending}
            onClick={onClose}
          >
            انصراف
          </button>
          <Submit pending={pending}>ثبت تیکت</Submit>
        </div>
      </form>
    </Modal>
  );
}

function TicketList({ slug }: { slug?: string }) {
  const [create, setCreate] = useState(false);
  const [search, setSearch] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [queue, setQueue] = useState<"all" | "unanswered" | "unread">("all");
  const [organization, setOrganization] = useState("");
  const [organizationSearch, setOrganizationSearch] = useState("");
  const [organizationQuery, setOrganizationQuery] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const notifications = useSupportNotifications(slug);
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(search.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    const timer = setTimeout(
      () => setOrganizationQuery(organizationSearch.trim()),
      300,
    );
    return () => clearTimeout(timer);
  }, [organizationSearch]);
  const customers = useData<Paginated<Customer>>(
    slug
      ? null
      : `customers/?${queryString({ search: organizationQuery, page_size: 50 })}`,
  );
  const endpoint = `${supportPrefix(slug)}tickets/?${queryString({
    search: searchQuery,
    status,
    priority,
    organization,
    date_from: dateFrom,
    date_to: dateTo,
    unanswered: queue === "unanswered" ? "true" : "",
    unread: queue === "unread" ? "true" : "",
    page,
    page_size: 20,
  })}`;
  const { data, error, loading, refresh } =
    useData<Paginated<SupportTicket>>(endpoint);
  const revision = notifications.data?.items
    .map((item) => `${item.id}:${item.is_read}`)
    .join(",");
  const lastRevision = useRef(revision);
  useEffect(() => {
    if (lastRevision.current !== revision) {
      lastRevision.current = revision;
      refresh();
    }
  }, [revision, refresh]);
  const resetFilters = () => {
    setSearch("");
    setSearchQuery("");
    setStatus("");
    setPriority("");
    setQueue("all");
    setOrganization("");
    setOrganizationSearch("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  };
  return (
    <>
      <PageHeading
        eyebrow="ارتباط مستقیم"
        title={slug ? "پشتیبانی و تیکت‌ها" : "مدیریت تیکت‌ها"}
      >
        {slug && (
          <button className="button primary" onClick={() => setCreate(true)}>
            <Plus size={17} /> تیکت جدید
          </button>
        )}
      </PageHeading>
      <div className="support-list-summary">
        <LifeBuoy size={20} />
        <span>
          {notifications.data
            ? `${number(notifications.data.open_tickets)} تیکت باز`
            : "پشتیبانی مجموعه‌ها"}
        </span>
        {notifications.data && (
          <span>
            {number(
              slug
                ? notifications.data.awaiting_customer
                : notifications.data.awaiting_support,
            )}{" "}
            {slug ? "منتظر پاسخ شما" : "منتظر پشتیبانی"}
          </span>
        )}
      </div>
      <section className="panel support-list-panel" aria-label="فهرست تیکت‌ها">
        {!slug && (
          <div
            className="support-queue-filters"
            role="group"
            aria-label="صف پیگیری تیکت‌ها"
          >
            {(
              [
                ["all", "تازه‌ترین تیکت‌ها"],
                ["unanswered", "منتظر پاسخ پشتیبانی"],
                ["unread", "پیام‌های خوانده‌نشده"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                aria-pressed={queue === value}
                className={queue === value ? "selected" : ""}
                onClick={() => {
                  setQueue(value);
                  setPage(1);
                }}
              >
                {label}
              </button>
            ))}
          </div>
        )}
        <div className="support-filters">
          <label className="support-search">
            <Search size={17} />
            <input
              aria-label="جست‌وجوی تیکت‌ها"
              placeholder="جست‌وجوی موضوع یا شماره تیکت…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <select
            aria-label="فیلتر وضعیت تیکت"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">همهٔ وضعیت‌ها</option>
            {Object.entries(ticketStatuses).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            aria-label="فیلتر اولویت تیکت"
            value={priority}
            onChange={(event) => {
              setPriority(event.target.value);
              setPage(1);
            }}
          >
            <option value="">همهٔ اولویت‌ها</option>
            {Object.entries(ticketPriorities).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <button
            className="icon-button"
            aria-label="تازه‌سازی تیکت‌ها"
            onClick={refresh}
          >
            <RotateCcw size={17} />
          </button>
        </div>
        {!slug && (
          <div className="support-central-filters">
            <Field label="جست‌وجوی مجموعه">
              <input
                value={organizationSearch}
                onChange={(event) => setOrganizationSearch(event.target.value)}
                placeholder="نام، شناسه یا شماره تماس"
              />
            </Field>
            <Field label="مجموعه">
              <select
                value={organization}
                onChange={(event) => {
                  setOrganization(event.target.value);
                  setPage(1);
                }}
              >
                <option value="">همهٔ مجموعه‌ها</option>
                {customers.data?.results.map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name}
                  </option>
                ))}
              </select>
              {customers.error && (
                <small role="status">فهرست مجموعه‌ها دریافت نشد.</small>
              )}
            </Field>
            <DateField
              label="از تاریخ"
              value={dateFrom}
              onChange={(value) => {
                setDateFrom(value);
                setPage(1);
              }}
            />
            <DateField
              label="تا تاریخ"
              value={dateTo}
              onChange={(value) => {
                setDateTo(value);
                setPage(1);
              }}
            />
          </div>
        )}
        {dateFrom && dateTo && dateFrom > dateTo && (
          <InlineError message="تاریخ شروع باید پیش از تاریخ پایان باشد." />
        )}
        {loading && !data ? (
          <Spinner />
        ) : error ? (
          <ErrorState error={error} retry={refresh} />
        ) : !data?.results.length ? (
          <Empty
            title="تیکتی پیدا نشد"
            description={
              search ||
              status ||
              priority ||
              organization ||
              dateFrom ||
              dateTo ||
              queue !== "all"
                ? "فیلترها را تغییر دهید یا جست‌وجو را پاک کنید."
                : slug
                  ? "برای دریافت کمک، اولین درخواست خود را ثبت کنید."
                  : "درخواست‌های مجموعه‌ها اینجا نمایش داده می‌شوند."
            }
            action={
              search ||
              status ||
              priority ||
              organization ||
              dateFrom ||
              dateTo ||
              queue !== "all" ? (
                <button className="button secondary" onClick={resetFilters}>
                  پاک کردن فیلترها
                </button>
              ) : slug ? (
                <button
                  className="button primary"
                  onClick={() => setCreate(true)}
                >
                  تیکت جدید
                </button>
              ) : undefined
            }
          />
        ) : (
          <>
            <div className="support-ticket-list" aria-busy={loading}>
              {data.results.map((ticket) => (
                <Link
                  key={ticket.id}
                  href={supportHref(slug, ticket.id)}
                  className="support-ticket-row"
                  data-testid={`support-ticket-${ticket.id}`}
                >
                  <span
                    className={`support-ticket-symbol ${ticket.unread_count ? "unread" : ""}`}
                  >
                    <MessageCircle size={21} />
                  </span>
                  <div className="support-ticket-main">
                    <div className="support-ticket-subject">
                      <strong>{ticket.subject}</strong>
                      <small>#{number(ticket.id)}</small>
                    </div>
                    <p>{ticket.last_message_preview || "بدون پیام"}</p>
                    <div className="support-ticket-meta">
                      {!slug && <span>{ticket.organization.name}</span>}
                      <span>{ticketCategories[ticket.category]}</span>
                      <span
                        className={`support-priority support-priority-${ticket.priority}`}
                      >
                        اولویت {ticketPriorities[ticket.priority]}
                      </span>
                      {ticket.assigned_to && !slug && (
                        <span>{displayName(ticket.assigned_to)}</span>
                      )}
                    </div>
                  </div>
                  <div className="support-ticket-state">
                    <TicketBadge ticket={ticket} />
                    <small>
                      {date(ticket.updated_at)} · {time(ticket.updated_at)}
                    </small>
                    {ticket.unread_count > 0 && (
                      <span className="support-unread">
                        {number(ticket.unread_count)} پیام تازه
                      </span>
                    )}
                  </div>
                </Link>
              ))}
            </div>
            <Pagination count={data.count} page={page} onPage={setPage} />
          </>
        )}
      </section>
      {create && slug && (
        <CreateTicket slug={slug} onClose={() => setCreate(false)} />
      )}
    </>
  );
}

function TicketStatusHistory({
  ticket,
  endpoint,
}: {
  ticket: SupportTicket;
  endpoint: string;
}) {
  const [page, setPage] = useState(1);
  const history = useData<Paginated<SupportStatusEvent>>(
    page > 1 ? `${endpoint}history/?page=${page}&page_size=50` : null,
  );
  const count =
    ticket.status_history_count ?? ticket.status_history?.length ?? 0;
  const changes =
    page === 1
      ? ticket.status_history || []
      : [...(history.data?.results || [])].reverse();
  if (!count) return null;
  return (
    <details className="support-status-history">
      <summary>تاریخچهٔ وضعیت تیکت</summary>
      {page > 1 && history.loading ? (
        <Spinner label="دریافت تاریخچه…" />
      ) : history.error ? (
        <ErrorState error={history.error} retry={history.refresh} />
      ) : (
        <ol>
          {changes.map((change) => (
            <li key={change.id}>
              <span>
                {change.previous_status
                  ? `${ticketStatuses[change.previous_status]} ← `
                  : ""}
                {ticketStatuses[change.status]}
              </span>
              <small>
                {change.actor_name} · {date(change.created_at)} ·{" "}
                {time(change.created_at)}
              </small>
            </li>
          ))}
        </ol>
      )}
      {count > 50 && (
        <Pagination count={count} page={page} pageSize={50} onPage={setPage} />
      )}
    </details>
  );
}

function TicketConversation({
  slug,
  ticketId,
}: {
  slug?: string;
  ticketId: number;
}) {
  const prefix = supportPrefix(slug);
  const endpoint = `${prefix}tickets/${ticketId}/`;
  const ticketData = useData<SupportTicket>(endpoint);
  const [messagePage, setMessagePage] = useState(1);
  const messages = useData<Paginated<SupportMessage>>(
    `${endpoint}messages/?page=${messagePage}&page_size=30&ordering=-created_at`,
  );
  const notifications = useSupportNotifications(slug);
  const staff = useData<SupportStaff[] | Paginated<SupportStaff>>(
    !slug && ticketData.data?.can_assign ? `${prefix}staff/` : null,
  );
  const staffItems = Array.isArray(staff.data)
    ? staff.data
    : staff.data?.results || [];
  const [body, setBody] = useState("");
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<
    "resolve" | "close" | "reopen" | null
  >(null);
  const [assigneeDraft, setAssignee] = useState<string | null>(null);
  const [readError, setReadError] = useState<string | null>(null);
  const [readRetry, setReadRetry] = useState(0);
  const bottom = useRef<HTMLDivElement>(null);
  const toast = useToast();
  const revision = ticketNotificationRevision(
    notifications.data?.items || [],
    ticketId,
  );
  const previousRevision = useRef(revision);
  const refreshTicket = ticketData.refresh;
  const refreshMessages = messages.refresh;
  useEffect(() => {
    if (previousRevision.current !== revision) {
      previousRevision.current = revision;
      refreshTicket();
      refreshMessages();
    }
  }, [revision, refreshTicket, refreshMessages]);
  const ticket = ticketData.data;
  const assignee =
    assigneeDraft ?? (ticket?.assigned_to ? String(ticket.assigned_to.id) : "");
  const messageRevision = messages.data?.results
    .map((item) => item.id)
    .join(",");
  useEffect(() => {
    if (messagePage === 1) bottom.current?.scrollIntoView({ block: "nearest" });
  }, [messageRevision, messagePage]);
  const lastRead = useRef("");
  const readRevision = `${endpoint}:${messageRevision}:${revision}:${readRetry}`;
  const refreshNotifications = notifications.invalidate;
  const conversationReady = !!messages.data && !!ticket;
  useEffect(() => {
    if (!conversationReady) return;
    let cancelled = false;
    const markRead = () => {
      if (
        document.visibilityState === "hidden" ||
        lastRead.current === readRevision
      )
        return;
      lastRead.current = readRevision;
      mutate(`${prefix}notifications/read/`, "POST", {
        ticket_id: ticketId,
        include_messages: false,
      })
        .then(() => {
          if (!cancelled) {
            setReadError(null);
            void refreshNotifications();
          }
        })
        .catch((error: Error) => {
          if (!cancelled)
            setReadError(error.message || "ثبت خواندن پیام‌ها ناموفق بود.");
        });
    };
    markRead();
    document.addEventListener("visibilitychange", markRead);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", markRead);
    };
  }, [readRevision, conversationReady, prefix, ticketId, refreshNotifications]);
  const sync = useCallback(() => {
    refreshTicket();
    refreshMessages();
    void refreshNotifications();
  }, [refreshTicket, refreshMessages, refreshNotifications]);
  if (ticketData.loading && !ticket) return <Spinner />;
  if (ticketData.error)
    return <ErrorState error={ticketData.error} retry={ticketData.refresh} />;
  if (!ticket) return null;
  const closed = ticketNeedsReopen(ticket.status);
  const canReply = ticket.can_reply ?? !closed;
  const canResolve = ticket.can_resolve ?? (!slug && !closed);
  const canClose = ticket.can_close ?? (!!slug && ticket.status === "resolved");
  const canReopen = ticket.can_reopen ?? (!!slug && closed);
  const transitionCopy = {
    resolve: {
      title: "حل‌شدن تیکت",
      description:
        "تیکت حل‌شده علامت می‌خورد و مجموعه می‌تواند نتیجه را تأیید یا درخواست را دوباره باز کند.",
      button: "علامت‌گذاری به‌عنوان حل‌شده",
      success: "تیکت حل‌شده علامت‌گذاری شد.",
    },
    close: {
      title: "تأیید حل‌شدن تیکت",
      description:
        "با تأیید شما تیکت بسته می‌شود. اگر باز هم به کمک نیاز داشتید، می‌توانید آن را دوباره باز کنید.",
      button: "تأیید و بستن تیکت",
      success: "تیکت با تأیید شما بسته شد.",
    },
    reopen: {
      title: "بازگشایی تیکت",
      description:
        "درخواست دوباره به صف پشتیبانی می‌رود. پس از بازگشایی، پیام جدید خود را بنویسید.",
      button: "بازگشایی تیکت",
      success: "تیکت دوباره باز شد.",
    },
  };
  return (
    <>
      <Link className="support-back text-link" href={supportHref(slug)}>
        <ArrowRight size={16} /> بازگشت به تیکت‌ها
      </Link>
      <PageHeading
        eyebrow={`تیکت شمارهٔ ${number(ticket.id)}`}
        title={ticket.subject}
      >
        <TicketBadge ticket={ticket} />
      </PageHeading>
      <div className="support-conversation-layout">
        <section
          className="panel support-conversation"
          aria-label="گفت‌وگوی تیکت"
        >
          <div className="support-conversation-heading">
            <span>
              <MessageCircle size={19} /> گفت‌وگو
            </span>
            <button
              className="icon-button"
              aria-label="تازه‌سازی گفت‌وگو"
              onClick={sync}
            >
              <RotateCcw size={17} />
            </button>
          </div>
          <div
            className="support-messages"
            role="log"
            aria-label="پیام‌های تیکت"
            aria-live="polite"
            aria-relevant="additions"
          >
            {messages.loading && !messages.data ? (
              <Spinner label="دریافت گفت‌وگو…" />
            ) : messages.error ? (
              <ErrorState error={messages.error} retry={messages.refresh} />
            ) : !messages.data?.results.length ? (
              <Empty
                title="پیامی وجود ندارد"
                description="گفت‌وگوی این درخواست اینجا نمایش داده می‌شود."
              />
            ) : (
              <>
                <div className="support-message-pagination">
                  <Pagination
                    count={messages.data.count}
                    page={messagePage}
                    pageSize={30}
                    onPage={setMessagePage}
                  />
                </div>
                {chronologicalMessages(messages.data.results).map(
                  (message, index, ordered) => {
                    const previous = ordered[index - 1];
                    const showDate =
                      !previous ||
                      date(previous.created_at) !== date(message.created_at);
                    return (
                      <div key={message.id}>
                        {showDate && (
                          <div className="support-day-divider">
                            <span>{date(message.created_at)}</span>
                          </div>
                        )}
                        <article
                          className={`support-message ${message.is_mine ? "mine" : "theirs"}`}
                          data-testid={`support-message-${message.id}`}
                        >
                          <div className="support-message-author">
                            <strong>{message.author_name}</strong>
                            <small>
                              {["customer", "tenant"].includes(
                                message.author_role,
                              )
                                ? "مجموعه"
                                : "پشتیبانی"}
                            </small>
                          </div>
                          <p dir="auto">{message.body}</p>
                          <time dateTime={message.created_at}>
                            {time(message.created_at)}
                          </time>
                        </article>
                      </div>
                    );
                  },
                )}
                <div ref={bottom} />
              </>
            )}
          </div>
          <InlineError message={readError} />
          {readError && (
            <button
              className="text-link"
              onClick={() => setReadRetry((value) => value + 1)}
            >
              ثبت دوبارهٔ خواندن اعلان‌ها
            </button>
          )}
          {closed ? (
            <div className="support-closed-note">
              <CircleCheck size={21} />
              <div>
                <strong>{ticketStatuses[ticket.status]}</strong>
                <p>برای ارسال پیام جدید، ابتدا تیکت را بازگشایی کنید.</p>
              </div>
              {canReopen && (
                <button
                  className="button secondary"
                  disabled={pending}
                  onClick={() => {
                    setActionError(null);
                    setConfirmation("reopen");
                  }}
                >
                  بازگشایی تیکت
                </button>
              )}
            </div>
          ) : canReply ? (
            <form
              className="support-composer"
              data-testid="support-reply-form"
              onSubmit={async (event) => {
                event.preventDefault();
                if (!body.trim() || pending) return;
                setPending(true);
                setActionError(null);
                try {
                  await mutate(`${endpoint}messages/`, "POST", {
                    body: body.trim(),
                  });
                  setBody("");
                  setMessagePage(1);
                  sync();
                  toast("پیام ارسال شد.");
                } catch (error) {
                  setActionError((error as Error).message);
                } finally {
                  setPending(false);
                }
              }}
            >
              <label
                htmlFor="support-reply-body"
                className="support-composer-label"
              >
                پاسخ شما
              </label>
              <textarea
                id="support-reply-body"
                name="body"
                aria-label="متن پاسخ"
                rows={3}
                maxLength={10000}
                placeholder="پیام خود را بنویسید…"
                value={body}
                disabled={pending}
                onChange={(event) => setBody(event.target.value)}
              />
              <div className="support-composer-footer">
                <small>
                  {number(body.length)} / {number(10000)}
                </small>
                <button
                  className="button primary"
                  disabled={pending || !body.trim()}
                  type="submit"
                >
                  <Send size={16} />
                  {pending ? "در حال ارسال…" : "ارسال پاسخ"}
                </button>
              </div>
            </form>
          ) : null}
          <InlineError message={actionError} />
        </section>
        <aside
          className="support-ticket-details panel"
          aria-label="اطلاعات تیکت"
        >
          <h2>اطلاعات تیکت</h2>
          <dl>
            {!slug && (
              <>
                <dt>مجموعه</dt>
                <dd>{ticket.organization.name}</dd>
              </>
            )}
            <dt>دسته‌بندی</dt>
            <dd>{ticketCategories[ticket.category]}</dd>
            <dt>اولویت</dt>
            <dd>
              <span
                className={`support-priority support-priority-${ticket.priority}`}
              >
                {ticketPriorities[ticket.priority]}
              </span>
            </dd>
            <dt>ثبت</dt>
            <dd>
              {date(ticket.created_at)}
              <small>{time(ticket.created_at)}</small>
            </dd>
            <dt>آخرین به‌روزرسانی</dt>
            <dd>
              {date(ticket.updated_at)}
              <small>{time(ticket.updated_at)}</small>
            </dd>
            <dt>مسئول پیگیری</dt>
            <dd>
              {ticket.assigned_to
                ? displayName(ticket.assigned_to)
                : "تعیین نشده"}
            </dd>
          </dl>
          {!slug && ticket.can_assign && (
            <form
              className="support-assignment"
              data-testid="support-assignment-form"
              onSubmit={async (event) => {
                event.preventDefault();
                setPending(true);
                setActionError(null);
                try {
                  await mutate(`${endpoint}assign/`, "POST", {
                    assigned_to: assignee ? Number(assignee) : null,
                  });
                  setAssignee(null);
                  sync();
                  toast("مسئول پیگیری به‌روز شد.");
                } catch (error) {
                  setActionError((error as Error).message);
                } finally {
                  setPending(false);
                }
              }}
            >
              <Field label="واگذاری به پشتیبان">
                <select
                  value={assignee}
                  onChange={(event) => setAssignee(event.target.value)}
                  disabled={pending || staff.loading || !!staff.error}
                >
                  <option value="">بدون مسئول</option>
                  {staffItems.map((person) => (
                    <option key={person.id} value={person.id}>
                      {displayName(person)}
                    </option>
                  ))}
                </select>
              </Field>
              {staff.error ? (
                <InlineError message={staff.error} />
              ) : (
                <button
                  className="button secondary"
                  type="submit"
                  disabled={
                    pending ||
                    staff.loading ||
                    assignee ===
                      (ticket.assigned_to ? String(ticket.assigned_to.id) : "")
                  }
                >
                  ثبت مسئول پیگیری
                </button>
              )}
            </form>
          )}
          <div className="support-lifecycle-actions">
            {canResolve && (
              <button
                className="button secondary"
                disabled={pending}
                onClick={() => {
                  setActionError(null);
                  setConfirmation("resolve");
                }}
              >
                <CircleCheck size={17} /> ثبت حل‌شدن تیکت
              </button>
            )}
            {canClose && (
              <button
                className="button primary"
                disabled={pending}
                onClick={() => {
                  setActionError(null);
                  setConfirmation("close");
                }}
              >
                <CheckCheck size={17} /> تأیید و بستن تیکت
              </button>
            )}
            {canReopen && (
              <button
                className="button secondary"
                disabled={pending}
                onClick={() => {
                  setActionError(null);
                  setConfirmation("reopen");
                }}
              >
                <RotateCcw size={17} /> بازگشایی تیکت
              </button>
            )}
          </div>
          <TicketStatusHistory ticket={ticket} endpoint={endpoint} />
          <div className="support-ticket-footnote">
            <Clock3 size={15} />
            <span>زمان‌ها به وقت تهران نمایش داده می‌شوند.</span>
          </div>
        </aside>
      </div>
      {confirmation && (
        <Modal
          title={transitionCopy[confirmation].title}
          description={transitionCopy[confirmation].description}
          onClose={() => {
            if (!pending) setConfirmation(null);
          }}
        >
          <InlineError message={actionError} />
          <div className="modal-footer">
            <button
              className="button secondary"
              disabled={pending}
              onClick={() => setConfirmation(null)}
            >
              انصراف
            </button>
            <button
              className="button primary"
              data-testid={`support-confirm-${confirmation}`}
              disabled={pending}
              onClick={async () => {
                setPending(true);
                setActionError(null);
                try {
                  await mutate(`${endpoint}transition/`, "POST", {
                    action: confirmation,
                  });
                  toast(transitionCopy[confirmation].success);
                  setConfirmation(null);
                  sync();
                } catch (error) {
                  setActionError((error as Error).message);
                } finally {
                  setPending(false);
                }
              }}
            >
              {pending ? "در حال ثبت…" : transitionCopy[confirmation].button}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

export function SupportTickets({
  slug,
  ticketId,
}: {
  slug?: string;
  ticketId?: number;
}) {
  const { user, loading } = useAuth();
  if (!slug && loading) return <Spinner />;
  if (!slug && user?.role !== "super_admin" && !user?.can_support)
    return (
      <ErrorState error="برای مشاهدهٔ تیکت‌ها به مجوز پشتیبانی نیاز دارید." />
    );
  return ticketId === undefined ? (
    <TicketList slug={slug} />
  ) : (
    <TicketConversation
      key={`${slug || "central"}:${ticketId}`}
      slug={slug}
      ticketId={ticketId}
    />
  );
}

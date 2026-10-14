"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Archive,
  ArrowRight,
  Building2,
  Check,
  Eye,
  Pencil,
  Plus,
  Power,
  RotateCcw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { api, ApiError, mutate } from "@/lib/api";
import { date, number, queryString } from "@/lib/format";
import type { Hall } from "@/lib/operations";
import {
  editableSupervisorHalls,
  loadSupervisorHalls,
  normalizeSupervisorPhone,
  supervisorName,
  supervisorStatus,
  type Supervisor,
  type SupervisorAction,
} from "@/lib/supervisors";
import type { Paginated } from "@/lib/types";
import { useData } from "@/lib/use-data";
import { HelpTooltip } from "./help-tooltip";
import { SupervisorAccessPanel } from "./supervisor-access";
import {
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
import "./supervisors.css";

const statusLabels = {
  active: "فعال",
  inactive: "غیرفعال",
  archived: "بایگانی‌شده",
};
const actionLabels: Record<SupervisorAction, string> = {
  archive: "بایگانی مراقب",
  restore: "بازیابی مراقب",
  activate: "فعال‌سازی مراقب",
  deactivate: "غیرفعال‌سازی مراقب",
};

function SupervisorBadge({ supervisor }: { supervisor: Supervisor }) {
  const status = supervisorStatus(supervisor);
  return (
    <span className={`supervisor-status ${status}`}>
      <i aria-hidden="true" /> {statusLabels[status]}
    </span>
  );
}

function useHallChoices(slug: string) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<{
    slug: string;
    revision: number;
    data: Hall[];
    error: string | null;
  } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    loadSupervisorHalls((page) =>
      api<Paginated<Hall>>(
        `organizations/${slug}/halls/?${queryString({ status: "all", page_size: 100, page })}`,
        { signal: controller.signal },
      ),
    )
      .then((data) => {
        if (!controller.signal.aborted)
          setState({ slug, revision, data, error: null });
      })
      .catch((error: Error) => {
        if (!controller.signal.aborted)
          setState({ slug, revision, data: [], error: error.message });
      });
    return () => controller.abort();
  }, [slug, revision]);
  const current = state?.slug === slug;
  return {
    data: current ? state.data : [],
    error: current ? state.error : null,
    loading: !current || state.revision !== revision,
    refresh: () => setRevision((value) => value + 1),
  };
}

function saveError(error: unknown) {
  if (error instanceof ApiError) {
    const labels: Record<string, string> = {
      first_name: "نام",
      last_name: "نام خانوادگی",
      phone: "شماره تماس",
      halls: "سالن‌های مسئولیت",
      is_active: "وضعیت",
    };
    const errors = Object.entries(error.fields);
    if (errors.length)
      return errors
        .map(
          ([field, message]) =>
            `${labels[field] ? `${labels[field]}: ` : ""}${Array.isArray(message) ? message.join(" ") : String(message)}`,
        )
        .join(" • ");
  }
  return error instanceof Error ? error.message : "ذخیره اطلاعات ناموفق بود.";
}

function SupervisorForm({
  slug,
  supervisor,
  halls,
  onClose,
  onSaved,
}: {
  slug: string;
  supervisor?: Supervisor;
  halls: Hall[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [selected, setSelected] = useState(editableSupervisorHalls(supervisor));
  const [search, setSearch] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeHalls = halls.filter((hall) => hall.is_active);
  const available = activeHalls.filter((hall) =>
    hall.name.includes(search.trim()),
  );
  const archivedHalls =
    supervisor?.hall_details.filter((hall) => !hall.is_active) || [];
  return (
    <Modal
      title={supervisor ? "ویرایش مراقب" : "ثبت مراقب جدید"}
      description="اطلاعات تماس را ثبت کنید و سالن‌های مسئولیت را انتخاب کنید."
      onClose={() => !pending && onClose()}
      wide
    >
      <form
        className="supervisor-form"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const first_name = String(form.get("first_name") || "").trim();
          const last_name = String(form.get("last_name") || "").trim();
          const phone = normalizeSupervisorPhone(
            String(form.get("phone") || ""),
          );
          if (!first_name || !last_name) {
            setError("نام و نام خانوادگی مراقب را وارد کنید.");
            return;
          }
          if (!phone) {
            setError(
              "شماره همراه معتبر ایران را وارد کنید؛ مانند ۰۹۱۲۳۴۵۶۷۸۹.",
            );
            return;
          }
          setPending(true);
          setError(null);
          try {
            await mutate<Supervisor>(
              `organizations/${slug}/supervisors/${supervisor ? `${supervisor.id}/` : ""}`,
              supervisor ? "PATCH" : "POST",
              { first_name, last_name, phone, halls: selected },
            );
            onSaved();
          } catch (error) {
            setError(saveError(error));
          } finally {
            setPending(false);
          }
        }}
      >
        <InlineError message={error} />
        <fieldset disabled={pending} className="supervisor-form-fields">
          <legend className="supervisor-sr-only">اطلاعات مراقب</legend>
          <div className="supervisor-form-grid">
            <Field label="نام" required>
              <input
                name="first_name"
                required
                maxLength={100}
                autoComplete="given-name"
                defaultValue={supervisor?.first_name}
              />
            </Field>
            <Field label="نام خانوادگی" required>
              <input
                name="last_name"
                required
                maxLength={100}
                autoComplete="family-name"
                defaultValue={supervisor?.last_name}
              />
            </Field>
          </div>
          <Field
            label="شماره همراه"
            required
            hint="شماره تماس مشترک با مراقب دیگر مجاز است."
          >
            <input
              name="phone"
              type="tel"
              dir="ltr"
              required
              maxLength={30}
              autoComplete="tel"
              placeholder="09123456789"
              defaultValue={supervisor?.phone}
            />
          </Field>
          <fieldset className="supervisor-hall-picker">
            <legend>
              سالن‌های مسئولیت
              <HelpTooltip
                content="می‌توانید یک یا چند سالن انتخاب کنید یا مراقب را فعلاً بدون سالن ثبت کنید. سالن‌های بایگانی‌شده به مسئولیت جدید اضافه نمی‌شوند."
                label="راهنمای تخصیص سالن"
              />
            </legend>
            <p>
              انتخاب سالن اختیاری است؛ هر مراقب می‌تواند مسئول چند سالن باشد.
            </p>
            {activeHalls.length ? (
              <>
                <label className="supervisor-search">
                  <Search size={17} aria-hidden="true" />
                  <input
                    aria-label="جست‌وجوی سالن‌های مسئولیت"
                    placeholder="جست‌وجوی نام سالن…"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                </label>
                <div className="supervisor-hall-options">
                  {available.length ? (
                    available.map((hall) => (
                      <label
                        key={hall.id}
                        className={`supervisor-hall-choice ${selected.includes(hall.id) ? "selected" : ""}`}
                      >
                        <input
                          type="checkbox"
                          checked={selected.includes(hall.id)}
                          onChange={(event) =>
                            setSelected((ids) =>
                              event.target.checked
                                ? [...ids, hall.id]
                                : ids.filter((id) => id !== hall.id),
                            )
                          }
                        />
                        <Building2 size={17} aria-hidden="true" />
                        <span>{hall.name}</span>
                        {selected.includes(hall.id) && (
                          <Check size={16} aria-hidden="true" />
                        )}
                      </label>
                    ))
                  ) : (
                    <p className="supervisor-picker-empty">
                      سالنی با این نام پیدا نشد.
                    </p>
                  )}
                </div>
                <div className="supervisor-selection-count" role="status">
                  {number(selected.length)} سالن انتخاب شده است.
                </div>
              </>
            ) : (
              <p className="supervisor-picker-empty">
                هنوز سالن فعالی ثبت نشده است. می‌توانید مراقب را بدون سالن ذخیره
                کنید.
              </p>
            )}
            {!!archivedHalls.length && (
              <p className="supervisor-archive-hint">
                سالن‌های بایگانی‌شدهٔ قبلی حفظ می‌شوند:{" "}
                {archivedHalls.map((hall) => hall.name).join("، ")}
              </p>
            )}
          </fieldset>
        </fieldset>
        <div className="modal-footer">
          <button
            className="button secondary"
            type="button"
            disabled={pending}
            onClick={onClose}
          >
            انصراف
          </button>
          <Submit pending={pending}>
            {supervisor ? "ذخیره تغییرات" : "ثبت مراقب"}
          </Submit>
        </div>
      </form>
    </Modal>
  );
}

function SupervisorActionDialog({
  slug,
  action,
  supervisor,
  onClose,
  onSaved,
}: {
  slug: string;
  action: SupervisorAction;
  supervisor: Supervisor;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const descriptions: Record<SupervisorAction, string> = {
    archive:
      "اطلاعات و سالن‌های مسئولیت حفظ می‌شوند و امکان بازیابی وجود دارد. مراقب بایگانی‌شده تا بازیابی قابل ویرایش نیست.",
    restore: `اطلاعات و مسئولیت‌های قبلی بازیابی می‌شوند. وضعیت مراقب پس از بازیابی ${supervisor.is_active ? "فعال" : "غیرفعال"} خواهد بود.`,
    activate: "مراقب فعال می‌شود و سالن‌های مسئولیت او حفظ می‌شوند.",
    deactivate:
      "مراقب غیرفعال می‌شود؛ اطلاعات و سالن‌های مسئولیت او همچنان حفظ می‌شوند.",
  };
  return (
    <Modal
      title={actionLabels[action]}
      description={supervisorName(supervisor)}
      onClose={() => !pending && onClose()}
    >
      <InlineError message={error} />
      <p className="supervisor-confirm-description">{descriptions[action]}</p>
      <div className="modal-footer">
        <button
          className="button secondary"
          disabled={pending}
          onClick={onClose}
        >
          انصراف
        </button>
        <button
          className={`button ${action === "archive" ? "danger" : "primary"}`}
          disabled={pending}
          onClick={async () => {
            setPending(true);
            setError(null);
            try {
              await mutate<Supervisor>(
                `organizations/${slug}/supervisors/${supervisor.id}/${action}/`,
                "POST",
              );
              onSaved();
            } catch (error) {
              setError(saveError(error));
            } finally {
              setPending(false);
            }
          }}
        >
          {pending ? "در حال ذخیره…" : actionLabels[action]}
        </button>
      </div>
    </Modal>
  );
}

function HallLabels({ supervisor }: { supervisor: Supervisor }) {
  return supervisor.hall_details.length ? (
    <div className="supervisor-hall-tags">
      {supervisor.hall_details.map((hall) => (
        <span
          key={hall.id}
          className={`supervisor-hall-tag ${hall.is_active ? "" : "archived"}`}
        >
          {hall.name}
          {!hall.is_active && <small>بایگانی</small>}
        </span>
      ))}
    </div>
  ) : (
    <span className="supervisor-muted">بدون سالن</span>
  );
}

function SupervisorDirectory({ slug }: { slug: string }) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("active");
  const [hall, setHall] = useState("");
  const [edit, setEdit] = useState<Supervisor | "new" | null>(null);
  const [action, setAction] = useState<{
    supervisor: Supervisor;
    type: SupervisorAction;
  } | null>(null);
  const [notice, setNotice] = useState("");
  const choices = useHallChoices(slug);
  const data = useData<Paginated<Supervisor>>(
    `organizations/${slug}/supervisors/?${queryString({ search, status, hall, page })}`,
  );
  const filtered = !!search || !!hall || status !== "active";
  const saved = () => {
    setEdit(null);
    setAction(null);
    setPage(1);
    setNotice("اطلاعات مراقبین با موفقیت به‌روزرسانی شد.");
    data.refresh();
    choices.refresh();
  };
  const filter = (change: () => void) => {
    change();
    setPage(1);
  };
  return (
    <div className="supervisor-page" dir="rtl">
      <PageHeading
        eyebrow="همراهان نظم مجموعه"
        title="مراقبین"
        description="اطلاعات مراقبین و سالن‌های مسئولیت هر نفر را در یک نگاه مدیریت کنید."
      >
        <button
          className="button primary"
          disabled={choices.loading || !!choices.error}
          onClick={() => setEdit("new")}
        >
          <Plus size={18} />
          ثبت مراقب
        </button>
      </PageHeading>
      <div className="supervisor-banner">
        <span className="supervisor-banner-icon">
          <ShieldCheck size={28} aria-hidden="true" />
        </span>
        <div>
          <strong>مسئولیت روشن، هماهنگی ساده‌تر</strong>
          <p>
            هر مراقب می‌تواند مسئول چند سالن باشد. اطلاعات بایگانی‌شده نیز قابل
            بازیابی است.
          </p>
        </div>
        <HelpTooltip
          content="غیرفعال‌سازی وضعیت همکاری را تغییر می‌دهد. بایگانی پرونده را از فهرست فعال خارج می‌کند و پیش از ویرایش باید بازیابی شود."
          label="راهنمای وضعیت مراقبین"
        />
      </div>
      {notice && (
        <div className="supervisor-notice" role="status">
          {notice}
        </div>
      )}
      {choices.error && (
        <div className="supervisor-hall-error">
          <InlineError
            message={`دریافت فهرست سالن‌ها ناموفق بود: ${choices.error}`}
          />
          <button className="button secondary" onClick={choices.refresh}>
            تلاش دوباره برای سالن‌ها
          </button>
        </div>
      )}
      <section className="supervisor-table-card" aria-label="فهرست مراقبین">
        <div className="supervisor-toolbar">
          <label className="supervisor-search">
            <Search size={18} aria-hidden="true" />
            <input
              aria-label="جست‌وجوی مراقب"
              placeholder="نام، نام خانوادگی یا شماره تماس…"
              value={search}
              onChange={(event) => filter(() => setSearch(event.target.value))}
            />
          </label>
          <label className="supervisor-filter">
            <span>وضعیت</span>
            <select
              value={status}
              onChange={(event) => filter(() => setStatus(event.target.value))}
            >
              <option value="active">فعال</option>
              <option value="inactive">غیرفعال</option>
              <option value="archived">بایگانی‌شده</option>
              <option value="all">همهٔ مراقبین</option>
            </select>
          </label>
          <label className="supervisor-filter">
            <span>سالن مسئولیت</span>
            <select
              value={hall}
              disabled={choices.loading || !!choices.error}
              onChange={(event) => filter(() => setHall(event.target.value))}
            >
              <option value="">همهٔ سالن‌ها</option>
              {choices.data.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                  {!item.is_active ? " (بایگانی)" : ""}
                </option>
              ))}
            </select>
          </label>
          {filtered && (
            <button
              className="button subtle"
              onClick={() =>
                filter(() => {
                  setSearch("");
                  setHall("");
                  setStatus("active");
                })
              }
            >
              پاک کردن فیلترها
            </button>
          )}
        </div>
        <div className="supervisor-table-heading">
          <strong>فهرست مراقبین</strong>
          <span>{data.data ? `${number(data.data.count)} مراقب` : ""}</span>
        </div>
        {data.error ? (
          <ErrorState error={data.error} retry={data.refresh} />
        ) : data.loading && !data.data ? (
          <Spinner />
        ) : data.data?.results.length ? (
          <div className="table-scroll" aria-busy={data.loading}>
            <table className="supervisor-table">
              <thead>
                <tr>
                  <th scope="col">مراقب</th>
                  <th scope="col">شماره تماس</th>
                  <th scope="col">سالن‌های مسئولیت</th>
                  <th scope="col">وضعیت</th>
                  <th scope="col">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {data.data.results.map((supervisor) => {
                  const name = supervisorName(supervisor);
                  return (
                    <tr key={supervisor.id}>
                      <td>
                        <Link
                          className="supervisor-name"
                          href={`/${slug}/supervisors/${supervisor.id}`}
                        >
                          <span
                            className="supervisor-avatar"
                            aria-hidden="true"
                          >
                            {supervisor.first_name.slice(0, 1)}
                          </span>
                          <span>
                            <strong>{name}</strong>
                            <small>ثبت: {date(supervisor.created_at)}</small>
                          </span>
                        </Link>
                      </td>
                      <td>
                        <a
                          className="supervisor-phone"
                          href={`tel:${supervisor.phone}`}
                          dir="ltr"
                        >
                          {supervisor.phone}
                        </a>
                      </td>
                      <td>
                        <HallLabels supervisor={supervisor} />
                      </td>
                      <td>
                        <SupervisorBadge supervisor={supervisor} />
                      </td>
                      <td>
                        <div className="supervisor-row-actions">
                          <Link
                            className="icon-button"
                            href={`/${slug}/supervisors/${supervisor.id}`}
                            aria-label={`مشاهدهٔ ${name}`}
                            title="مشاهدهٔ جزئیات"
                          >
                            <Eye size={17} />
                          </Link>
                          {supervisor.archived_at ? (
                            <button
                              className="icon-button"
                              aria-label={`بازیابی ${name}`}
                              title="بازیابی"
                              onClick={() =>
                                setAction({ supervisor, type: "restore" })
                              }
                            >
                              <RotateCcw size={17} />
                            </button>
                          ) : (
                            <>
                              <button
                                className="icon-button"
                                aria-label={`ویرایش ${name}`}
                                title="ویرایش"
                                disabled={choices.loading || !!choices.error}
                                onClick={() => setEdit(supervisor)}
                              >
                                <Pencil size={17} />
                              </button>
                              <button
                                className="icon-button"
                                aria-label={`${supervisor.is_active ? "غیرفعال‌سازی" : "فعال‌سازی"} ${name}`}
                                title={
                                  supervisor.is_active
                                    ? "غیرفعال‌سازی"
                                    : "فعال‌سازی"
                                }
                                onClick={() =>
                                  setAction({
                                    supervisor,
                                    type: supervisor.is_active
                                      ? "deactivate"
                                      : "activate",
                                  })
                                }
                              >
                                <Power size={17} />
                              </button>
                              <button
                                className="icon-button danger-text"
                                aria-label={`بایگانی ${name}`}
                                title="بایگانی"
                                onClick={() =>
                                  setAction({ supervisor, type: "archive" })
                                }
                              >
                                <Archive size={17} />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title={
              filtered
                ? "مراقبی با این فیلترها پیدا نشد"
                : "هنوز مراقب فعالی ثبت نشده است"
            }
            description={
              filtered
                ? "جست‌وجو یا فیلترهای وضعیت و سالن را تغییر دهید."
                : "مراقب جدید ثبت کنید یا وضعیت فیلتر را برای مشاهدهٔ سایر پرونده‌ها تغییر دهید."
            }
            action={
              !filtered ? (
                <button
                  className="button primary"
                  disabled={choices.loading || !!choices.error}
                  onClick={() => setEdit("new")}
                >
                  <Plus size={17} />
                  ثبت اولین مراقب
                </button>
              ) : undefined
            }
          />
        )}
        {data.data && (
          <Pagination count={data.data.count} page={page} onPage={setPage} />
        )}
      </section>
      {edit && (
        <SupervisorForm
          slug={slug}
          supervisor={edit === "new" ? undefined : edit}
          halls={choices.data}
          onClose={() => setEdit(null)}
          onSaved={saved}
        />
      )}
      {action && (
        <SupervisorActionDialog
          slug={slug}
          action={action.type}
          supervisor={action.supervisor}
          onClose={() => setAction(null)}
          onSaved={saved}
        />
      )}
    </div>
  );
}

function SupervisorDetail({ slug, id }: { slug: string; id: number }) {
  const data = useData<Supervisor>(`organizations/${slug}/supervisors/${id}/`);
  const choices = useHallChoices(slug);
  const [edit, setEdit] = useState(false);
  const [action, setAction] = useState<SupervisorAction | null>(null);
  const [notice, setNotice] = useState("");
  const saved = () => {
    setEdit(false);
    setAction(null);
    setNotice("اطلاعات مراقب با موفقیت به‌روزرسانی شد.");
    data.refresh();
    choices.refresh();
  };
  if (data.error) return <ErrorState error={data.error} retry={data.refresh} />;
  if (data.loading && !data.data) return <Spinner />;
  if (!data.data) return null;
  const supervisor = data.data;
  return (
    <div className="supervisor-page" dir="rtl">
      <Link className="back-link" href={`/${slug}/supervisors`}>
        <ArrowRight size={17} />
        بازگشت به مراقبین
      </Link>
      <PageHeading
        eyebrow="پروندهٔ مراقب"
        title={supervisorName(supervisor)}
        description="اطلاعات تماس و سالن‌های مسئولیت"
      >
        <SupervisorBadge supervisor={supervisor} />
        {supervisor.archived_at ? (
          <button
            className="button primary"
            onClick={() => setAction("restore")}
          >
            <RotateCcw size={17} />
            بازیابی مراقب
          </button>
        ) : (
          <>
            <button
              className="button secondary"
              disabled={choices.loading || !!choices.error}
              onClick={() => setEdit(true)}
            >
              <Pencil size={17} />
              ویرایش اطلاعات
            </button>
            <button
              className="button secondary"
              onClick={() =>
                setAction(supervisor.is_active ? "deactivate" : "activate")
              }
            >
              <Power size={17} />
              {supervisor.is_active ? "غیرفعال‌سازی" : "فعال‌سازی"}
            </button>
          </>
        )}
      </PageHeading>
      {notice && (
        <div className="supervisor-notice" role="status">
          {notice}
        </div>
      )}
      {supervisor.archived_at && (
        <p className="supervisor-archive-note">
          این مراقب بایگانی شده است. برای ویرایش اطلاعات یا تغییر وضعیت، ابتدا
          پرونده را بازیابی کنید.
        </p>
      )}
      {choices.error && (
        <div className="supervisor-hall-error">
          <InlineError
            message={`دریافت سالن‌ها ناموفق بود: ${choices.error}`}
          />
          <button className="button secondary" onClick={choices.refresh}>
            تلاش دوباره برای سالن‌ها
          </button>
        </div>
      )}
      <div className="supervisor-detail-grid">
        <Panel title="اطلاعات مراقب" subtitle="اطلاعات پایه و راه ارتباطی">
          <dl className="supervisor-detail-info">
            <div>
              <dt>نام</dt>
              <dd>{supervisor.first_name}</dd>
            </div>
            <div>
              <dt>نام خانوادگی</dt>
              <dd>{supervisor.last_name}</dd>
            </div>
            <div>
              <dt>شماره تماس</dt>
              <dd dir="ltr">
                <a href={`tel:${supervisor.phone}`}>{supervisor.phone}</a>
              </dd>
            </div>
            <div>
              <dt>تاریخ ثبت</dt>
              <dd>{date(supervisor.created_at)}</dd>
            </div>
            <div>
              <dt>آخرین به‌روزرسانی</dt>
              <dd>{date(supervisor.updated_at)}</dd>
            </div>
            {supervisor.archived_at && (
              <div>
                <dt>تاریخ بایگانی</dt>
                <dd>{date(supervisor.archived_at)}</dd>
              </div>
            )}
          </dl>
          {!supervisor.archived_at && (
            <div className="supervisor-detail-footer">
              <button
                className="button subtle danger-text"
                onClick={() => setAction("archive")}
              >
                <Archive size={16} />
                بایگانی مراقب
              </button>
            </div>
          )}
        </Panel>
        <Panel
          title="سالن‌های مسئولیت"
          subtitle="همهٔ سالن‌های واگذارشده به این مراقب"
          action={
            <span className="supervisor-hall-total">
              {number(supervisor.hall_details.length)} سالن
            </span>
          }
        >
          {supervisor.hall_details.length ? (
            <div className="supervisor-assigned-halls">
              {supervisor.hall_details.map((hall) => (
                <div key={hall.id} className="supervisor-assigned-hall">
                  <span className="supervisor-hall-icon">
                    <Building2 size={22} aria-hidden="true" />
                  </span>
                  <div>
                    <strong>{hall.name}</strong>
                    <small>
                      {hall.is_active
                        ? "سالن فعال"
                        : "سالن بایگانی‌شده؛ ارتباط قبلی حفظ شده است."}
                    </small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <Empty
              title="هنوز سالنی تخصیص داده نشده است"
              description="از ویرایش اطلاعات، سالن‌های مسئولیت این مراقب را انتخاب کنید."
              action={
                !supervisor.archived_at ? (
                  <button
                    className="button secondary"
                    disabled={choices.loading || !!choices.error}
                    onClick={() => setEdit(true)}
                  >
                    انتخاب سالن‌ها
                  </button>
                ) : undefined
              }
            />
          )}
        </Panel>
      </div>
      <div id="supervisor-account">
        <SupervisorAccessPanel slug={slug} supervisor={supervisor} />
      </div>
      {edit && !supervisor.archived_at && (
        <SupervisorForm
          slug={slug}
          supervisor={supervisor}
          halls={choices.data}
          onClose={() => setEdit(false)}
          onSaved={saved}
        />
      )}
      {action && (
        <SupervisorActionDialog
          slug={slug}
          action={action}
          supervisor={supervisor}
          onClose={() => setAction(null)}
          onSaved={saved}
        />
      )}
    </div>
  );
}

export function Supervisors({
  slug,
  supervisorId,
}: {
  slug: string;
  supervisorId?: number;
}) {
  return supervisorId === undefined ? (
    <SupervisorDirectory key={slug} slug={slug} />
  ) : (
    <SupervisorDetail
      key={`${slug}:${supervisorId}`}
      slug={slug}
      id={supervisorId}
    />
  );
}

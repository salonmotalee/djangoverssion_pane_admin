"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ArrowDownUp,
  ArrowRight,
  CalendarClock,
  ChevronLeft,
  Copy,
  Download,
  Filter,
  Pencil,
  Phone,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  UserRound,
} from "lucide-react";
import { mutate } from "@/lib/api";
import {
  date,
  isIranianPhone,
  latinDigits,
  number,
  queryString,
  safeExportName,
  statuses,
} from "@/lib/format";
import type { Audit, Customer, Paginated } from "@/lib/types";
import { useData } from "@/lib/use-data";
import { useAuth, useToast } from "./providers";
import {
  Badge,
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
import { ActivityList } from "./dashboard";

export function CustomerForm({
  customer,
  onClose,
  onSaved,
}: {
  customer?: Customer;
  onClose: () => void;
  onSaved: (customer: Customer) => void;
}) {
  const [start, setStart] = useState(customer?.start_date || "");
  const [expiration, setExpiration] = useState(customer?.expiration_date || "");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const toast = useToast();
  return (
    <Modal
      wide
      title={customer ? "ویرایش مجموعه" : "ثبت مجموعه جدید"}
      description={
        customer
          ? "اطلاعات مجموعه را به‌روز نگه دارید."
          : "یک همراه جدید به فضای مدیریت خود اضافه کنید."
      }
      onClose={onClose}
    >
      <form
        data-testid="customer-form"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const phone = latinDigits(String(form.get("phone"))).replace(
            /[\s-]/g,
            "",
          );
          if (!isIranianPhone(phone)) {
            setError(
              "شماره تلفن همراه معتبر ایران وارد کنید؛ مانند ۰۹۱۲۳۴۵۶۷۸۹.",
            );
            return;
          }
          if (!start || !expiration) {
            setError("تاریخ شروع و پایان سرویس را انتخاب کنید.");
            return;
          }
          if (expiration < start) {
            setError("تاریخ پایان سرویس باید پس از تاریخ شروع باشد.");
            return;
          }
          setError(null);
          setPending(true);
          try {
            const body: Record<string, unknown> = {
              name: form.get("name"),
              manager_name: form.get("manager_name"),
              phone,
              start_date: start,
              expiration_date: expiration,
            };
            const identifier = String(form.get("identifier") || "").trim();
            if (!customer && identifier) body.identifier = identifier;
            const result = await mutate<Customer>(
              customer ? `customers/${customer.id}/` : "customers/",
              customer ? "PATCH" : "POST",
              body,
            );
            toast(
              customer
                ? "اطلاعات مجموعه با موفقیت به‌روز شد."
                : "مجموعه جدید با موفقیت ثبت شد.",
            );
            onSaved(result);
          } catch (error) {
            setError((error as Error).message);
          } finally {
            setPending(false);
          }
        }}
      >
        <div className="form-grid">
          <Field label="نام مجموعه" required>
            <input
              name="name"
              required
              maxLength={200}
              defaultValue={customer?.name}
              placeholder="مثلاً مجموعه آفتاب"
              disabled={pending}
            />
          </Field>
          <Field label="نام مدیر مجموعه" required>
            <input
              name="manager_name"
              required
              maxLength={150}
              defaultValue={customer?.manager_name}
              placeholder="نام و نام خانوادگی"
              disabled={pending}
            />
          </Field>
          <Field label="شماره تماس مدیر" required hint="شماره تلفن همراه ایران">
            <input
              name="phone"
              required
              type="tel"
              dir="ltr"
              defaultValue={customer?.phone}
              placeholder="09123456789"
              maxLength={20}
              disabled={pending}
            />
          </Field>
          <Field
            label="شناسه دائمی مجموعه"
            hint={
              customer
                ? "شناسه پس از ثبت قابل تغییر نیست."
                : "خالی: تولید خودکار؛ یا ۴ تا ۳۲ حرف و عدد انگلیسی."
            }
          >
            <input
              name="identifier"
              dir="ltr"
              defaultValue={customer?.identifier}
              placeholder="تولید خودکار"
              readOnly={!!customer}
              disabled={pending}
              pattern="[A-Za-z0-9]{4,32}"
              minLength={4}
              maxLength={32}
            />
          </Field>
          <DateField
            label="تاریخ شروع سرویس"
            value={start}
            onChange={setStart}
            required
            disabled={pending}
          />
          <DateField
            label="تاریخ پایان سرویس"
            value={expiration}
            onChange={setExpiration}
            required
            disabled={pending}
          />
        </div>
        <div className="form-note">
          <CalendarClock size={18} />
          <p>
            شناسه برای اتصال‌های آینده استفاده می‌شود و رمز ورود نیست. انقضای
            سرویس تنها اطلاع‌رسانی است.
          </p>
        </div>
        <InlineError message={error} />
        <div className="modal-footer">
          <button
            className="button secondary"
            type="button"
            onClick={onClose}
            disabled={pending}
          >
            انصراف
          </button>
          <Submit pending={pending}>
            {customer ? "ذخیره تغییرات" : "ثبت مجموعه"}
          </Submit>
        </div>
      </form>
    </Modal>
  );
}
function RenewForm({
  customer,
  onClose,
  onSaved,
}: {
  customer: Customer;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [expiration, setExpiration] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const toast = useToast();
  return (
    <Modal
      title="تمدید سرویس"
      description={`یک بازه تازه برای ${customer.name}`}
      onClose={onClose}
    >
      <form
        data-testid="renew-form"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!expiration || expiration <= customer.expiration_date) {
            setError("تاریخ جدید باید پس از تاریخ پایان فعلی باشد.");
            return;
          }
          setPending(true);
          setError(null);
          try {
            await mutate(`customers/${customer.id}/renew/`, "POST", {
              expiration_date: expiration,
            });
            toast("سرویس مجموعه با موفقیت تمدید شد.");
            onSaved();
          } catch (error) {
            setError((error as Error).message);
          } finally {
            setPending(false);
          }
        }}
      >
        <div className="renew-current">
          <span>پایان فعلی سرویس</span>
          <strong>{date(customer.expiration_date)}</strong>
          <Badge status={customer.status} />
        </div>
        <DateField
          label="تاریخ پایان جدید"
          value={expiration}
          onChange={setExpiration}
          required
          disabled={pending}
        />
        <InlineError message={error} />
        <div className="modal-footer">
          <button
            className="button secondary"
            type="button"
            onClick={onClose}
            disabled={pending}
          >
            انصراف
          </button>
          <Submit pending={pending}>تمدید سرویس</Submit>
        </div>
      </form>
    </Modal>
  );
}
function DeleteConfirm({
  customer,
  onClose,
  onSaved,
}: {
  customer: Customer;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();
  const restore = !!customer.deleted_at;
  return (
    <Modal title={restore ? "بازیابی مجموعه" : "حذف مجموعه"} onClose={onClose}>
      <div className={`confirm-icon ${restore ? "positive" : "danger"}`}>
        {restore ? <RotateCcw size={28} /> : <Trash2 size={28} />}
      </div>
      <p className="confirm-text">
        {restore ? (
          <>
            مجموعه <strong>{customer.name}</strong> دوباره به فهرست فعال برگردد؟
          </>
        ) : (
          <>
            مجموعه <strong>{customer.name}</strong> به بایگانی حذف‌شده‌ها منتقل
            شود؟ اطلاعات و شناسه آن حفظ می‌شود و امکان بازیابی دارید.
          </>
        )}
      </p>
      <InlineError message={error} />
      <div className="modal-footer">
        <button
          className="button secondary"
          onClick={onClose}
          disabled={pending}
        >
          انصراف
        </button>
        <button
          className={`button ${restore ? "primary" : "danger"}`}
          disabled={pending}
          onClick={async () => {
            setPending(true);
            setError(null);
            try {
              await mutate(
                `customers/${customer.id}/${restore ? "restore/" : ""}`,
                restore ? "POST" : "DELETE",
                restore ? {} : undefined,
              );
              toast(
                restore ? "مجموعه بازیابی شد." : "مجموعه به بایگانی منتقل شد.",
              );
              onSaved();
            } catch (error) {
              setError((error as Error).message);
            } finally {
              setPending(false);
            }
          }}
        >
          {pending
            ? "در حال انجام…"
            : restore
              ? "بله، بازیابی شود"
              : "بله، حذف شود"}
        </button>
      </div>
    </Modal>
  );
}
type Action = { type: "edit" | "renew" | "delete"; customer: Customer };
function ActionModal({
  action,
  close,
  saved,
}: {
  action: Action | null;
  close: () => void;
  saved: () => void;
}) {
  if (!action) return null;
  const onSaved = () => {
    close();
    saved();
  };
  if (action.type === "edit")
    return (
      <CustomerForm
        customer={action.customer}
        onClose={close}
        onSaved={onSaved}
      />
    );
  if (action.type === "renew")
    return (
      <RenewForm customer={action.customer} onClose={close} onSaved={onSaved} />
    );
  return (
    <DeleteConfirm
      customer={action.customer}
      onClose={close}
      onSaved={onSaved}
    />
  );
}
function RowActions({
  customer,
  onAction,
  canManage,
}: {
  customer: Customer;
  onAction: (action: Action) => void;
  canManage: boolean;
}) {
  return (
    <div className="row-actions">
      {customer.deleted_at ? (
        canManage && (
          <button
            className="icon-button green"
            aria-label={`بازیابی ${customer.name}`}
            title="بازیابی"
            onClick={() => onAction({ type: "delete", customer })}
          >
            <RotateCcw size={16} />
          </button>
        )
      ) : (
        <>
          <button
            className="icon-button"
            aria-label={`ویرایش ${customer.name}`}
            title="ویرایش"
            onClick={() => onAction({ type: "edit", customer })}
          >
            <Pencil size={15} />
          </button>
          <button
            className="icon-button indigo"
            aria-label={`تمدید ${customer.name}`}
            title="تمدید سرویس"
            onClick={() => onAction({ type: "renew", customer })}
          >
            <CalendarClock size={16} />
          </button>
          {canManage && (
            <button
              className="icon-button rose"
              aria-label={`حذف ${customer.name}`}
              title="حذف"
              onClick={() => onAction({ type: "delete", customer })}
            >
              <Trash2 size={15} />
            </button>
          )}
        </>
      )}
    </div>
  );
}
export function Customers() {
  const params = useSearchParams();
  const { user } = useAuth();
  const toast = useToast();
  const canManage = user?.role !== "operator";
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState(params.get("status") || "");
  const [deleted, setDeleted] = useState("active");
  const [ordering, setOrdering] = useState("-created_at");
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState(false);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [createdFrom, setCreatedFrom] = useState(
    params.get("created_date_from") || "",
  );
  const [createdTo, setCreatedTo] = useState(
    params.get("created_date_to") || "",
  );
  const [create, setCreate] = useState(false);
  const [action, setAction] = useState<Action | null>(null);
  const [exporting, setExporting] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebounced(search);
      setPage(1);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [search]);
  const query = queryString({
    search: debounced,
    status,
    deleted,
    ordering,
    expiration_date_from: from,
    expiration_date_to: to,
    created_date_from: createdFrom,
    created_date_to: createdTo,
  });
  const { data, loading, error, refresh } = useData<Paginated<Customer>>(
    `customers/?${query}&page=${page}&page_size=20`,
  );
  const close = useCallback(() => setAction(null), []);
  const sort = (field: string) => {
    setOrdering((current) => (current === field ? `-${field}` : field));
    setPage(1);
  };
  return (
    <>
      <PageHeading
        eyebrow="همراهان مدار"
        title="مجموعه‌ها"
        description="اطلاعات، وضعیت سرویس و مسیر همکاری هر مجموعه، در یک جا."
      >
        {canManage && (
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
                if (!response.ok)
                  throw new Error(
                    "دریافت خروجی ناموفق بود. مجوز دسترسی و اتصال را بررسی کنید.",
                  );
                const url = URL.createObjectURL(await response.blob());
                const link = document.createElement("a");
                link.href = url;
                link.download = safeExportName();
                link.click();
                URL.revokeObjectURL(url);
                toast("خروجی CSV آماده شد.");
              } catch (error) {
                toast((error as Error).message, "error");
              } finally {
                setExporting(false);
              }
            }}
          >
            <Download size={17} />
            {exporting ? "در حال دریافت…" : "خروجی CSV"}
          </button>
        )}
        <button className="button primary" onClick={() => setCreate(true)}>
          <Plus size={18} />
          مجموعه جدید
        </button>
      </PageHeading>
      {(createdFrom || createdTo) && (
        <div className="scope-note">
          بازه ثبت مجموعه‌ها: {date(createdFrom)} تا {date(createdTo)}{" "}
          <button
            className="text-link"
            onClick={() => {
              setCreatedFrom("");
              setCreatedTo("");
              setPage(1);
            }}
          >
            پاک کردن بازه ثبت
          </button>
        </div>
      )}
      <section className="panel table-panel">
        <div className="table-toolbar">
          <div className="search-box">
            <Search size={18} />
            <input
              aria-label="جستجوی مجموعه‌ها"
              placeholder="جستجوی نام، مدیر، شناسه یا تلفن…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div className="table-filters">
            <select
              aria-label="وضعیت سرویس"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                setPage(1);
              }}
            >
              <option value="">همه وضعیت‌ها</option>
              <option value="current">فعال و نزدیک انقضا</option>
              {Object.entries(statuses).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            {canManage && (
              <select
                aria-label="وضعیت بایگانی"
                value={deleted}
                onChange={(event) => {
                  setDeleted(event.target.value);
                  setPage(1);
                }}
              >
                <option value="active">مجموعه‌های جاری</option>
                <option value="deleted">حذف‌شده‌ها</option>
                <option value="all">تمام مجموعه‌ها</option>
              </select>
            )}
            <button
              className={`button secondary compact ${filters ? "selected" : ""}`}
              onClick={() => setFilters(!filters)}
            >
              <Filter size={16} />
              فیلتر تاریخ
            </button>
          </div>
        </div>
        {filters && (
          <div className="filter-panel">
            <DateField
              label="پایان سرویس از"
              value={from}
              onChange={(value) => {
                setFrom(value);
                setPage(1);
              }}
            />
            <DateField
              label="پایان سرویس تا"
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
                setStatus("");
                setCreatedFrom("");
                setCreatedTo("");
                setSearch("");
                setPage(1);
              }}
            >
              پاک کردن فیلترها
            </button>
          </div>
        )}
        <div className="table-description">
          <strong>
            فهرست مجموعه‌ها <span>{data ? number(data.count) : "—"}</span>
          </strong>
          <small>شناسه‌ها دائمی و غیرقابل تغییر هستند.</small>
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
                  <th>
                    <button onClick={() => sort("name")}>
                      نام مجموعه
                      <ArrowDownUp size={13} />
                    </button>
                  </th>
                  <th>مدیر و تماس</th>
                  <th>شناسه مجموعه</th>
                  <th>
                    <button onClick={() => sort("expiration_date")}>
                      پایان سرویس
                      <ArrowDownUp size={13} />
                    </button>
                  </th>
                  <th>وضعیت سرویس</th>
                  <th className="actions-head">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((customer) => (
                  <tr key={customer.id}>
                    <td>
                      <Link
                        className="customer-name"
                        href={`/customers/${customer.id}`}
                      >
                        <span className="collection-avatar small">
                          {customer.name.slice(0, 1)}
                        </span>
                        <span>
                          <strong>{customer.name}</strong>
                          <small>شروع: {date(customer.start_date)}</small>
                        </span>
                      </Link>
                    </td>
                    <td>
                      <div className="table-person">
                        <strong>{customer.manager_name}</strong>
                        <span dir="ltr">{customer.phone}</span>
                      </div>
                    </td>
                    <td>
                      <code className="identifier" dir="ltr">
                        {customer.identifier}
                      </code>
                    </td>
                    <td>
                      <span className="table-date">
                        {date(customer.expiration_date)}
                      </span>
                      <small
                        className={`table-days ${customer.days_remaining < 0 ? "expired" : ""}`}
                      >
                        {customer.days_remaining < 0
                          ? `${number(Math.abs(customer.days_remaining))} روز گذشته`
                          : `${number(customer.days_remaining)} روز باقی‌مانده`}
                      </small>
                    </td>
                    <td>
                      <Badge
                        status={customer.status}
                        deleted={!!customer.deleted_at}
                      />
                    </td>
                    <td>
                      <RowActions
                        customer={customer}
                        onAction={setAction}
                        canManage={canManage}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title={
              search || status || from || to || deleted === "deleted"
                ? "نتیجه‌ای پیدا نشد"
                : "اولین مجموعه را به مدار اضافه کنید"
            }
            description={
              search || status || from || to || deleted === "deleted"
                ? "فیلترهای جستجو را تغییر دهید و دوباره بررسی کنید."
                : "ثبت یک مجموعه، آغاز مدیریت ساده و منظم سرویس‌هاست."
            }
            action={
              !search && !status && deleted === "active" ? (
                <button
                  className="button primary"
                  onClick={() => setCreate(true)}
                >
                  <Plus size={16} />
                  ثبت اولین مجموعه
                </button>
              ) : undefined
            }
          />
        )}
        {data && <Pagination count={data.count} page={page} onPage={setPage} />}
      </section>
      {create && (
        <CustomerForm
          onClose={() => setCreate(false)}
          onSaved={() => {
            setCreate(false);
            refresh();
          }}
        />
      )}
      <ActionModal action={action} close={close} saved={refresh} />
    </>
  );
}
export function CustomerDetail({ id }: { id: number }) {
  const { user } = useAuth();
  const toast = useToast();
  const canManage = user?.role !== "operator";
  const { data, error, loading, refresh } = useData<Customer>(
    `customers/${id}/${canManage ? "?deleted=all" : ""}`,
  );
  const history = useData<Paginated<Audit>>(
    canManage
      ? `audit/?entity_type=customer&entity_id=${id}&page_size=20`
      : null,
  );
  const [action, setAction] = useState<Action | null>(null);
  const close = useCallback(() => setAction(null), []);
  if (error) return <ErrorState error={error} retry={refresh} />;
  if (loading && !data) return <Spinner />;
  if (!data) return null;
  const saved = () => {
    refresh();
    history.refresh();
  };
  return (
    <>
      <Link className="back-link" href="/customers">
        <ArrowRight size={16} />
        بازگشت به مجموعه‌ها
      </Link>
      <PageHeading
        eyebrow="پرونده مجموعه"
        title={data.name}
        description={`مدیریت ${data.manager_name}`}
      >
        <Badge status={data.status} deleted={!!data.deleted_at} />
        {data.deleted_at ? (
          canManage && (
            <button
              className="button primary"
              onClick={() => setAction({ type: "delete", customer: data })}
            >
              <RotateCcw size={17} />
              بازیابی مجموعه
            </button>
          )
        ) : (
          <>
            <button
              className="button secondary"
              onClick={() => setAction({ type: "edit", customer: data })}
            >
              <Pencil size={17} />
              ویرایش اطلاعات
            </button>
            <button
              className="button primary"
              onClick={() => setAction({ type: "renew", customer: data })}
            >
              <CalendarClock size={17} />
              تمدید سرویس
            </button>
          </>
        )}
      </PageHeading>
      <div className="detail-grid">
        <Panel title="اطلاعات مجموعه" subtitle="اطلاعات پایه و راه‌های ارتباطی">
          <dl className="detail-info">
            <div>
              <dt>
                <UserRound size={16} />
                مدیر مجموعه
              </dt>
              <dd>{data.manager_name}</dd>
            </div>
            <div>
              <dt>
                <Phone size={16} />
                شماره تماس
              </dt>
              <dd dir="ltr">
                <a href={`tel:${data.phone}`}>{data.phone}</a>
              </dd>
            </div>
            <div>
              <dt>شناسه دائمی</dt>
              <dd>
                <code dir="ltr">{data.identifier}</code>
                <button
                  className="icon-button"
                  aria-label="کپی شناسه"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(data.identifier);
                      toast("شناسه کپی شد.");
                    } catch {
                      toast("امکان کپی در این مرورگر وجود ندارد.", "error");
                    }
                  }}
                >
                  <Copy size={15} />
                </button>
              </dd>
            </div>
            <div>
              <dt>تاریخ ثبت</dt>
              <dd>{date(data.created_at)}</dd>
            </div>
            <div>
              <dt>آخرین به‌روزرسانی</dt>
              <dd>{date(data.updated_at)}</dd>
            </div>
            {data.deleted_at && (
              <div>
                <dt>تاریخ حذف</dt>
                <dd>{date(data.deleted_at)}</dd>
              </div>
            )}
          </dl>
        </Panel>
        <Panel title="مسیر سرویس" subtitle="تاریخ‌های کلیدی همکاری">
          <div className="service-timeline">
            <div>
              <span className="timeline-point" />
              <small>شروع سرویس</small>
              <strong>{date(data.start_date)}</strong>
            </div>
            <span className="timeline-track" />
            <div>
              <span className={`timeline-point end ${data.status}`} />
              <small>پایان سرویس</small>
              <strong>{date(data.expiration_date)}</strong>
            </div>
          </div>
          <div className={`service-remaining ${data.status}`}>
            <CalendarClock size={25} />
            <div>
              <strong>
                {data.days_remaining < 0
                  ? `${number(Math.abs(data.days_remaining))} روز از پایان سرویس گذشته`
                  : `${number(data.days_remaining)} روز تا پایان سرویس`}
              </strong>
              <p>
                {data.status === "scheduled"
                  ? "سرویس این مجموعه هنوز آغاز نشده است."
                  : "انقضا به‌تنهایی دسترسی مجموعه را محدود نمی‌کند."}
              </p>
            </div>
          </div>
          <div className="service-actions">
            {!data.deleted_at && canManage && (
              <button
                className="button subtle danger-text"
                onClick={() => setAction({ type: "delete", customer: data })}
              >
                <Trash2 size={16} />
                حذف و انتقال به بایگانی
              </button>
            )}
          </div>
        </Panel>
      </div>
      {canManage && (
        <Panel
          title="تاریخچه این مجموعه"
          subtitle="تمام تغییرات ثبت شده، همراه با مسئول هر تغییر"
        >
          {history.error ? (
            <ErrorState error={history.error} retry={history.refresh} />
          ) : history.loading ? (
            <Spinner />
          ) : (
            <ActivityList items={history.data?.results || []} />
          )}
          {history.data && history.data.count > 20 && (
            <div className="panel-bottom">
              <Link className="text-link" href={`/activity?entity_id=${id}`}>
                مشاهده تمام فعالیت‌های مجموعه
                <ChevronLeft size={16} />
              </Link>
            </div>
          )}
        </Panel>
      )}
      <ActionModal action={action} close={close} saved={saved} />
    </>
  );
}

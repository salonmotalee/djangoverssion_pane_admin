"use client";
import { useCallback, useEffect, useState } from "react";
import {
  KeyRound,
  Pencil,
  Plus,
  Search,
  ShieldCheck,
  UserRound,
  UserRoundCheck,
  UserRoundX,
  Trash2,
} from "lucide-react";
import { mutate } from "@/lib/api";
import { date, displayName, number, roles, queryString } from "@/lib/format";
import { useData } from "@/lib/use-data";
import type { Paginated, Role, User } from "@/lib/types";
import { useAuth, useToast } from "./providers";
import {
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

function UserForm({
  target,
  onClose,
  onSaved,
}: {
  target?: User;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { user } = useAuth();
  const toast = useToast();
  const [role, setRole] = useState<Role>(target?.role || "operator");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal
      wide
      title={target ? "ویرایش کاربر" : "ایجاد کاربر جدید"}
      description="دسترسی متناسب با مسئولیت هر فرد تنظیم کنید."
      onClose={onClose}
    >
      <form
        data-testid="user-form"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const body: Record<string, unknown> = {
            username: form.get("username"),
            first_name: form.get("first_name"),
            last_name: form.get("last_name"),
            email: form.get("email"),
            role,
            is_active: form.get("is_active") === "on",
          };
          if (!target) body.password = form.get("password");
          setPending(true);
          setError(null);
          try {
            await mutate(
              target ? `users/${target.id}/` : "users/",
              target ? "PATCH" : "POST",
              body,
            );
            toast(target ? "اطلاعات کاربر به‌روز شد." : "کاربر جدید ایجاد شد.");
            onSaved();
          } catch (error) {
            setError((error as Error).message);
          } finally {
            setPending(false);
          }
        }}
      >
        <div className="form-grid">
          <Field label="نام">
            <input
              name="first_name"
              defaultValue={target?.first_name}
              maxLength={150}
              disabled={pending}
            />
          </Field>
          <Field label="نام خانوادگی">
            <input
              name="last_name"
              defaultValue={target?.last_name}
              maxLength={150}
              disabled={pending}
            />
          </Field>
          <Field label="نام کاربری" required>
            <input
              name="username"
              required
              dir="ltr"
              autoComplete="off"
              defaultValue={target?.username}
              maxLength={150}
              disabled={pending}
            />
          </Field>
          <Field label="ایمیل">
            <input
              name="email"
              type="email"
              dir="ltr"
              defaultValue={target?.email}
              disabled={pending}
            />
          </Field>
          <Field label="نقش کاربر" required>
            <select
              value={role}
              onChange={(event) => setRole(event.target.value as Role)}
              disabled={pending}
            >
              {Object.entries(roles)
                .filter(
                  ([value]) =>
                    user?.role === "super_admin" || value === "operator",
                )
                .map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
            </select>
          </Field>
          {!target && (
            <Field
              label="رمز عبور اولیه"
              required
              hint="حداقل ۱۰ نویسه؛ یک رمز قوی و غیرمشابه با نام کاربری"
            >
              <input
                name="password"
                type="password"
                required
                minLength={10}
                autoComplete="new-password"
                dir="ltr"
                disabled={pending}
              />
            </Field>
          )}
        </div>
        <div className="role-description">
          <ShieldCheck size={18} />
          <p>
            {role === "super_admin"
              ? "دسترسی کامل به مجموعه‌ها، کاربران و مدیریت تمام نقش‌ها."
              : role === "admin"
                ? "مدیریت مجموعه‌ها، گزارش‌ها و کاربران با نقش اپراتور."
                : "مشاهده و ثبت مجموعه، ویرایش اطلاعات و تمدید سرویس؛ بدون مدیریت کاربران یا حذف مجموعه."}
          </p>
        </div>
        <label className="checkbox-field">
          <input
            name="is_active"
            type="checkbox"
            defaultChecked={target?.is_active ?? true}
            disabled={pending}
          />
          <span>حساب کاربر فعال باشد</span>
        </label>
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
            {target ? "ذخیره تغییرات" : "ایجاد کاربر"}
          </Submit>
        </div>
      </form>
    </Modal>
  );
}
function ResetPassword({
  target,
  onClose,
  onSaved,
}: {
  target: User;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();
  return (
    <Modal
      title="تعیین رمز عبور جدید"
      description={`حساب ${displayName(target)}`}
      onClose={onClose}
    >
      <form
        data-testid="reset-password-form"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const password = String(form.get("new_password"));
          if (password !== form.get("confirm_password")) {
            setError("تکرار رمز عبور با رمز جدید یکسان نیست.");
            return;
          }
          setPending(true);
          setError(null);
          try {
            await mutate(`users/${target.id}/reset_password/`, "POST", {
              new_password: password,
            });
            toast("رمز عبور کاربر تغییر کرد.");
            onSaved();
          } catch (error) {
            setError((error as Error).message);
          } finally {
            setPending(false);
          }
        }}
      >
        <Field label="رمز عبور جدید" required>
          <input
            name="new_password"
            type="password"
            dir="ltr"
            autoComplete="new-password"
            required
            minLength={10}
            disabled={pending}
          />
        </Field>
        <Field label="تکرار رمز عبور جدید" required>
          <input
            name="confirm_password"
            type="password"
            dir="ltr"
            autoComplete="new-password"
            required
            minLength={10}
            disabled={pending}
          />
        </Field>
        <div className="form-note">
          <KeyRound size={18} />
          <p>رمز جدید را از یک مسیر امن به صاحب حساب تحویل دهید.</p>
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
          <Submit pending={pending}>تغییر رمز عبور</Submit>
        </div>
      </form>
    </Modal>
  );
}
function ToggleUser({
  target,
  onClose,
  onSaved,
  deleting = false,
}: {
  target: User;
  onClose: () => void;
  onSaved: () => void;
  deleting?: boolean;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();
  return (
    <Modal
      title={
        deleting
          ? "حذف حساب کاربری"
          : target.is_active
            ? "غیرفعال کردن حساب"
            : "فعال کردن حساب"
      }
      onClose={onClose}
    >
      <div className="confirm-icon">
        {deleting ? (
          <Trash2 size={28} />
        ) : target.is_active ? (
          <UserRoundX size={28} />
        ) : (
          <UserRoundCheck size={28} />
        )}
      </div>
      <p className="confirm-text">
        حساب <strong>{displayName(target)}</strong>{" "}
        {deleting
          ? "برای همیشه حذف شود؟ این حساب دیگر امکان ورود نخواهد داشت. تاریخچه مدیریتی حفظ می‌شود."
          : target.is_active
            ? "غیرفعال شود؟ کاربر تا فعال شدن مجدد، امکان ورود نخواهد داشت."
            : "دوباره فعال شود؟"}
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
          className={`button ${deleting || target.is_active ? "danger" : "primary"}`}
          disabled={pending}
          onClick={async () => {
            setPending(true);
            setError(null);
            try {
              await mutate(
                `users/${target.id}/`,
                deleting ? "DELETE" : "PATCH",
                deleting ? undefined : { is_active: !target.is_active },
              );
              toast(
                deleting
                  ? "حساب کاربر حذف شد."
                  : target.is_active
                    ? "حساب غیرفعال شد."
                    : "حساب فعال شد.",
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
            : deleting
              ? "بله، حساب حذف شود"
              : target.is_active
                ? "بله، غیرفعال شود"
                : "بله، فعال شود"}
        </button>
      </div>
    </Modal>
  );
}
export function UsersPage() {
  const { user, refresh: refreshSession } = useAuth();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [role, setRole] = useState("");
  const [page, setPage] = useState(1);
  const [create, setCreate] = useState(false);
  const [action, setAction] = useState<{
    type: "edit" | "password" | "toggle" | "delete";
    target: User;
  } | null>(null);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebounced(search);
      setPage(1);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [search]);
  const { data, error, loading, refresh } = useData<Paginated<User>>(
    user?.role !== "operator"
      ? `users/?${queryString({ search: debounced, role, page, page_size: 20, ordering: "-date_joined" })}`
      : null,
  );
  const close = useCallback(() => setAction(null), []);
  const saved = () => {
    close();
    setCreate(false);
    refresh();
    if (action?.target.id === user?.id) void refreshSession();
  };
  if (user?.role === "operator")
    return (
      <ErrorState error="مشاهده و مدیریت کاربران فقط برای مدیران مجاز است." />
    );
  return (
    <>
      <PageHeading
        eyebrow="امنیت در هر سطح"
        title="کاربران و دسترسی"
        description="افراد تیم را همراه با نقش و سطح دسترسی مناسب مدیریت کنید."
      >
        <button className="button primary" onClick={() => setCreate(true)}>
          <Plus size={18} />
          کاربر جدید
        </button>
      </PageHeading>
      <div className="permission-banner">
        <ShieldCheck size={21} />
        <div>
          <strong>
            {user?.role === "super_admin"
              ? "شما مدیر ارشد این فضا هستید"
              : "مدیریت مسئولانه دسترسی‌ها"}
          </strong>
          <p>
            {user?.role === "super_admin"
              ? "حذف یا غیرفعال کردن آخرین مدیر ارشد فعال مجاز نیست."
              : "شما می‌توانید حساب اپراتورها را ایجاد و مدیریت کنید. تغییر حساب سایر مدیران نیازمند مدیر ارشد است."}
          </p>
        </div>
      </div>
      <section className="panel table-panel">
        <div className="table-toolbar">
          <div className="search-box">
            <Search size={18} />
            <input
              aria-label="جستجوی کاربران"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="جستجوی نام، نام کاربری یا ایمیل…"
            />
          </div>
          <select
            aria-label="فیلتر نقش"
            value={role}
            onChange={(event) => {
              setRole(event.target.value);
              setPage(1);
            }}
          >
            <option value="">همه نقش‌ها</option>
            {Object.entries(roles).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="table-description">
          <strong>
            اعضای تیم <span>{data ? number(data.count) : "—"}</span>
          </strong>
          <small>دسترسی مشتریان در این مرحله تعریف نشده است.</small>
        </div>
        {error ? (
          <ErrorState error={error} retry={refresh} />
        ) : !data && loading ? (
          <Spinner />
        ) : data?.results.length ? (
          <div className={`table-scroll ${loading ? "refreshing" : ""}`}>
            <table>
              <thead>
                <tr>
                  <th>نام و حساب کاربری</th>
                  <th>نقش و دسترسی</th>
                  <th>وضعیت</th>
                  <th>آخرین ورود</th>
                  <th>عملیات</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((target) => {
                  const editable =
                    user?.role === "super_admin" || target.role === "operator";
                  return (
                    <tr key={target.id}>
                      <td>
                        <div className="customer-name">
                          <span className="avatar table-avatar">
                            {displayName(target).slice(0, 1)}
                          </span>
                          <span>
                            <strong>
                              {displayName(target)}
                              {target.id === user?.id && (
                                <i className="you-label">شما</i>
                              )}
                            </strong>
                            <small dir="ltr">{target.username}</small>
                            {target.email && (
                              <small dir="ltr">{target.email}</small>
                            )}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className={`role-badge ${target.role}`}>
                          <ShieldCheck size={14} />
                          {roles[target.role]}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`badge ${target.is_active ? "active" : "deleted"}`}
                        >
                          <i />
                          {target.is_active ? "فعال" : "غیرفعال"}
                        </span>
                      </td>
                      <td>
                        <span className="table-date">
                          {date(target.last_login)}
                        </span>
                        <small className="table-days">
                          ثبت: {date(target.date_joined)}
                        </small>
                      </td>
                      <td>
                        {editable ? (
                          <div className="row-actions">
                            <button
                              className="icon-button"
                              aria-label={`ویرایش کاربر ${target.username}`}
                              title="ویرایش کاربر"
                              onClick={() =>
                                setAction({ type: "edit", target })
                              }
                            >
                              <Pencil size={16} />
                            </button>
                            <button
                              className="icon-button indigo"
                              aria-label={`تغییر رمز ${target.username}`}
                              title="تغییر رمز عبور"
                              onClick={() =>
                                setAction({ type: "password", target })
                              }
                            >
                              <KeyRound size={16} />
                            </button>
                            <button
                              className={`icon-button ${target.is_active ? "rose" : "green"}`}
                              aria-label={`${target.is_active ? "غیرفعال کردن" : "فعال کردن"} ${target.username}`}
                              title={
                                target.is_active ? "غیرفعال کردن" : "فعال کردن"
                              }
                              onClick={() =>
                                setAction({ type: "toggle", target })
                              }
                            >
                              {target.is_active ? (
                                <UserRoundX size={17} />
                              ) : (
                                <UserRoundCheck size={17} />
                              )}
                            </button>
                            <button
                              className="icon-button rose"
                              aria-label={`حذف کاربر ${target.username}`}
                              title="حذف حساب کاربری"
                              onClick={() =>
                                setAction({ type: "delete", target })
                              }
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        ) : (
                          <span className="read-only-label">
                            <UserRound size={13} />
                            فقط مشاهده
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="کاربری با این مشخصات پیدا نشد"
            description="فیلتر یا عبارت جستجوی خود را تغییر دهید."
          />
        )}
        {data && <Pagination count={data.count} page={page} onPage={setPage} />}
      </section>
      {create && <UserForm onClose={() => setCreate(false)} onSaved={saved} />}
      {action?.type === "edit" && (
        <UserForm target={action.target} onClose={close} onSaved={saved} />
      )}
      {action?.type === "password" && (
        <ResetPassword target={action.target} onClose={close} onSaved={saved} />
      )}
      {action?.type === "toggle" && (
        <ToggleUser target={action.target} onClose={close} onSaved={saved} />
      )}
      {action?.type === "delete" && (
        <ToggleUser
          deleting
          target={action.target}
          onClose={close}
          onSaved={saved}
        />
      )}
    </>
  );
}

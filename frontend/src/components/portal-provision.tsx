"use client";
import { useState } from "react";
import {
  ExternalLink,
  Copy,
  KeyRound,
  Mountain,
  ShieldCheck,
} from "lucide-react";
import { mutate } from "@/lib/api";
import type { Customer } from "@/lib/types";
import { Field, InlineError, Modal, Panel, Submit } from "./ui";
import { useToast } from "./providers";
import { number } from "@/lib/format";

export function PortalAccess({
  customer,
  canManage,
  onSaved,
}: {
  customer: Customer;
  canManage: boolean;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const toast = useToast();
  return (
    <Panel
      title="پرتال اختصاصی مجموعه"
      subtitle="ورود مستقل؛ داده‌ها و نشست جدا از مدیریت مرکزی"
      className="portal-access-panel"
      action={<Mountain size={22} />}
    >
      <div className="portal-access-content">
        <span
          className={`badge ${customer.portal_is_active ? "active" : "scheduled"}`}
        >
          <i />
          {customer.portal_provisioned
            ? customer.portal_is_active
              ? "ورود مجموعه فعال است"
              : "حساب ورود غیرفعال است"
            : "در انتظار راه‌اندازی امن"}
        </span>
        <dl className="portal-access-meta">
          <div>
            <dt>ظرفیت مجموعه</dt>
            <dd>
              {customer.capacity === null
                ? "هنوز مشخص نشده"
                : `${number(customer.capacity)} نفر`}
            </dd>
          </div>
          {canManage && customer.login_username && (
            <div>
              <dt>نام کاربری ورود</dt>
              <dd dir="ltr">{customer.login_username}</dd>
            </div>
          )}
        </dl>
        <div className="portal-url">
          <code dir="ltr">{customer.portal_url}</code>
          <button
            className="icon-button"
            aria-label="کپی نشانی پرتال"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(customer.portal_url);
                toast("نشانی پرتال کپی شد.");
              } catch {
                toast(
                  "کپی در این مرورگر در دسترس نیست؛ نشانی را انتخاب کنید.",
                  "error",
                );
              }
            }}
          >
            <Copy size={17} />
          </button>
        </div>
        <div className="portal-access-actions">
          {customer.portal_provisioned && !customer.deleted_at && (
            <a
              className="button secondary"
              href={`/${customer.slug}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink size={17} />
              باز کردن ورود مجموعه
            </a>
          )}
          {canManage && !customer.deleted_at && (
            <button className="button primary" onClick={() => setOpen(true)}>
              <KeyRound size={17} />
              {customer.portal_provisioned
                ? "تنظیم دسترسی پرتال"
                : "راه‌اندازی ورود پرتال"}
            </button>
          )}
        </div>
        <p className="portal-access-note">
          <ShieldCheck size={15} />
          رمزهای ورود فقط به‌صورت هش Django نگه‌داری می‌شوند. تاریخ انقضا دسترسی
          را قطع نمی‌کند.
        </p>
      </div>
      {open && (
        <ProvisionForm
          customer={customer}
          onClose={() => setOpen(false)}
          onSaved={() => {
            setOpen(false);
            onSaved();
          }}
        />
      )}
    </Panel>
  );
}

function ProvisionForm({
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
  return (
    <Modal
      title={
        customer.portal_provisioned
          ? "تنظیم دسترسی پرتال"
          : "راه‌اندازی ورود مجموعه"
      }
      description="نام کاربری، ظرفیت و وضعیت ورود را امن تنظیم کنید."
      onClose={onClose}
    >
      <form
        data-testid="portal-provision-form"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const password = String(form.get("login_password") || "");
          if (password !== form.get("confirm_password")) {
            setError("رمز عبور و تکرار آن یکسان نیستند.");
            return;
          }
          setPending(true);
          setError(null);
          try {
            await mutate(`customers/${customer.id}/portal/`, "POST", {
              login_username: form.get("login_username"),
              capacity: Number(form.get("capacity")),
              is_active: form.get("is_active") === "on",
              ...(password ? { login_password: password } : {}),
            });
            toast(
              "دسترسی پرتال به‌روز شد؛ نشست‌های قبلی حساب ورود پایان یافتند.",
            );
            onSaved();
          } catch (error) {
            setError((error as Error).message);
          } finally {
            setPending(false);
          }
        }}
      >
        <Field label="ظرفیت مجموعه" required>
          <input
            name="capacity"
            type="number"
            min={1}
            max={2147483647}
            required
            defaultValue={customer.capacity ?? ""}
            disabled={pending}
            dir="ltr"
          />
        </Field>
        <Field label="نام کاربری پرتال" required>
          <input
            name="login_username"
            required
            minLength={3}
            maxLength={64}
            defaultValue={customer.login_username ?? ""}
            dir="ltr"
            autoComplete="off"
            disabled={pending}
          />
        </Field>
        <div className="form-grid">
          <Field
            label="رمز ورود جدید"
            required={!customer.portal_provisioned}
            hint={
              customer.portal_provisioned
                ? "خالی بگذارید تا رمز قبلی حفظ شود."
                : "حداقل ۱۰ نویسه و یک رمز قوی."
            }
          >
            <input
              name="login_password"
              type="password"
              minLength={10}
              required={!customer.portal_provisioned}
              autoComplete="new-password"
              dir="ltr"
              disabled={pending}
            />
          </Field>
          <Field
            label="تکرار رمز ورود جدید"
            required={!customer.portal_provisioned}
          >
            <input
              name="confirm_password"
              type="password"
              minLength={10}
              required={!customer.portal_provisioned}
              autoComplete="new-password"
              dir="ltr"
              disabled={pending}
            />
          </Field>
        </div>
        <label className="checkbox-field">
          <input
            name="is_active"
            type="checkbox"
            defaultChecked={
              !customer.portal_provisioned || customer.portal_is_active
            }
            disabled={pending}
          />
          <span>ورود مجموعه فعال باشد</span>
        </label>
        <div className="form-note">
          <ShieldCheck size={18} />
          <p>
            این عملیات نشست‌های قبلی این حساب را لغو می‌کند. نشانی مجموعه و
            شناسهٔ اتصال تغییر نمی‌کنند.
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
          <Submit pending={pending}>ذخیره دسترسی پرتال</Submit>
        </div>
      </form>
    </Modal>
  );
}

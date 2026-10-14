"use client";
import { useEffect, useEffectEvent, useId, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Database,
  LoaderCircle,
  X,
} from "lucide-react";
import Link from "next/link";
import DatePicker from "react-multi-date-picker";
import DateObject from "react-date-object";
import persian from "react-date-object/calendars/persian";
import gregorian from "react-date-object/calendars/gregorian";
import persianFa from "react-date-object/locales/persian_fa";
import gregorianEn from "react-date-object/locales/gregorian_en";
import { latinDigits, number, statuses } from "@/lib/format";
import type { ServiceStatus } from "@/lib/types";

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand">
      <span className="brand-symbol" aria-hidden="true">
        <span />
        <span />
        <i />
      </span>
      {!compact && (
        <span className="brand-word">
          مدار<small>مدیریتِ یکپارچه</small>
        </span>
      )}
    </div>
  );
}
export function Spinner({
  label = "در حال دریافت اطلاعات…",
}: {
  label?: string;
}) {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle className="spin" size={26} />
      <span>{label}</span>
    </div>
  );
}
export function Empty({
  title = "هنوز چیزی اینجا نیست",
  description = "با ثبت اولین مجموعه، اطلاعات شما در این بخش نمایش داده می‌شود.",
  action,
}: {
  title?: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Database size={28} strokeWidth={1.5} />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: string;
  retry?: () => void;
}) {
  return (
    <div className="error-state" role="alert">
      <AlertCircle size={24} />
      <h3>دریافت اطلاعات ناموفق بود</h3>
      <p>{error}</p>
      {retry && (
        <button className="button secondary" onClick={retry}>
          تلاش دوباره
        </button>
      )}
    </div>
  );
}
export function Badge({
  status,
  deleted = false,
}: {
  status: ServiceStatus;
  deleted?: boolean;
}) {
  return (
    <span className={`badge ${deleted ? "deleted" : status}`}>
      <i />
      {deleted ? "حذف شده" : statuses[status]}
    </span>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      <div className="heading-actions">{children}</div>
    </header>
  );
}
export function Panel({
  title,
  subtitle,
  children,
  action,
  className = "",
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Field({
  label,
  required,
  children,
  hint,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span>
        {label}
        {required && <b aria-hidden="true"> *</b>}
      </span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function DateField({
  label,
  value,
  onChange,
  required = false,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  disabled?: boolean;
}) {
  const id = useId();
  const [inputError, setInputError] = useState<string | null>(null);
  return (
    <div className="field date-field">
      <label htmlFor={id}>
        {label}
        {required && <b aria-hidden="true"> *</b>}
      </label>
      <div className="date-control">
        <CalendarDays size={17} />
        <DatePicker
          // Focusing an empty field must never insert today's date before typing.
          onOpenPickNewDate={false}
          portal
          zIndex={80}
          className="madar-datepicker"
          required={required}
          renderButton={(direction: string, handleClick: () => void) => (
            <button
              type="button"
              className="icon-button"
              aria-label={direction === "right" ? "ماه بعد" : "ماه قبل"}
              onClick={handleClick}
            >
              {direction === "right" ? (
                <ChevronRight size={16} />
              ) : (
                <ChevronLeft size={16} />
              )}
            </button>
          )}
          mapDays={({ date }) => ({
            "aria-label": date.format("D MMMM YYYY"),
            tabIndex: 0,
          })}
          id={id}
          name={id}
          value={
            value
              ? new DateObject({
                  date: value,
                  format: "YYYY-MM-DD",
                  calendar: gregorian,
                  locale: gregorianEn,
                }).convert(persian, persianFa)
              : ""
          }
          calendar={persian}
          locale={persianFa}
          format="YYYY/MM/DD"
          calendarPosition="bottom-right"
          inputClass="date-input"
          placeholder="انتخاب تاریخ"
          disabled={disabled}
          onChange={(selected, metadata) => {
            const input =
              metadata.input instanceof HTMLInputElement
                ? metadata.input
                : null;
            let chosen = selected;
            if (metadata.isTyping && input) {
              const text = latinDigits(input.value).trim();
              const parts = /^(\d{4})\/(\d{1,2})\/(\d{1,2})$/.exec(text);
              const parsed = parts
                ? new DateObject({
                    date: text,
                    format: "YYYY/MM/DD",
                    calendar: persian,
                    locale: persianFa,
                  })
                : null;
              // DateObject intentionally rolls overflowing months/days forward.
              // Manual entry must instead represent the exact date the user typed.
              if (
                !parts ||
                !parsed?.isValid ||
                parsed.year !== Number(parts[1]) ||
                parsed.month.number !== Number(parts[2]) ||
                parsed.day !== Number(parts[3])
              ) {
                const message = "تاریخ معتبر را به شکل سال/ماه/روز وارد کنید.";
                input.setCustomValidity(text ? message : "");
                setInputError(text ? message : null);
                onChange("");
                return;
              }
              chosen = parsed;
            }
            input?.setCustomValidity("");
            setInputError(null);
            onChange(
              chosen
                ? new DateObject(chosen)
                    .convert(gregorian, gregorianEn)
                    .format("YYYY-MM-DD")
                : "",
            );
          }}
        />
      </div>
      {inputError && (
        <small className="date-validation-error" role="status">
          {inputError}
        </small>
      )}
      {value && (
        <button
          type="button"
          className="clear-date"
          aria-label={`پاک کردن ${label}`}
          onClick={() => onChange("")}
          disabled={disabled}
        >
          <X size={12} />
        </button>
      )}
    </div>
  );
}
export function Modal({
  title,
  description,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const root = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const close = useEffectEvent(onClose);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const timer = window.setTimeout(() => {
      const dialog = root.current;
      // Preserve focus chosen by the user or by a child while the dialog opens.
      if (!dialog || dialog.contains(document.activeElement)) return;
      dialog
        .querySelector<HTMLElement>("input,button,select,textarea")
        ?.focus();
    }, 20);
    const listener = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
      if (event.key !== "Tab") return;
      const selector =
        'button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href],[tabindex="0"]';
      const calendar = document.querySelector(".rmdp-wrapper.madar-datepicker");
      const elements = [
        ...Array.from(
          root.current?.querySelectorAll<HTMLElement>(selector) || [],
        ),
        ...Array.from(calendar?.querySelectorAll<HTMLElement>(selector) || []),
      ].filter((element) => element.getClientRects().length > 0);
      if (!elements?.length) return;
      const first = elements[0];
      const last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", listener);
    return () => {
      window.clearTimeout(timer);
      document.body.style.overflow = overflow;
      window.removeEventListener("keydown", listener);
      previous?.focus();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={root}
        className={`modal ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className="modal-heading">
          <div>
            <h2 id={titleId}>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button
            type="button"
            className="icon-button"
            aria-label="بستن پنجره"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
export function Pagination({
  count,
  page,
  onPage,
  pageSize = 20,
}: {
  count: number;
  page: number;
  onPage: (page: number) => void;
  pageSize?: number;
}) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  return (
    <div className="pagination">
      <span>
        {count
          ? `${number((page - 1) * pageSize + 1)} تا ${number(Math.min(page * pageSize, count))} از ${number(count)} مورد`
          : "هیچ نتیجه‌ای یافت نشد"}
      </span>
      <div>
        <button
          className="icon-button"
          aria-label="صفحه قبل"
          disabled={page === 1}
          onClick={() => onPage(page - 1)}
        >
          <ChevronRight size={18} />
        </button>
        <span>
          صفحه {number(page)} از {number(pages)}
        </span>
        <button
          className="icon-button"
          aria-label="صفحه بعد"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          <ChevronLeft size={18} />
        </button>
      </div>
    </div>
  );
}
export function ViewAll({
  href,
  children = "مشاهده همه",
}: {
  href: string;
  children?: React.ReactNode;
}) {
  return (
    <Link className="text-link" href={href}>
      {children}
      <ArrowLeft size={15} />
    </Link>
  );
}
export function InlineError({ message }: { message: string | null }) {
  return message ? (
    <div className="form-error" role="alert">
      <AlertCircle size={17} />
      <span>{message}</span>
    </div>
  ) : null;
}
export function Submit({
  pending,
  children = "ذخیره تغییرات",
}: {
  pending: boolean;
  children?: React.ReactNode;
}) {
  return (
    <button className="button primary" type="submit" disabled={pending}>
      {pending ? (
        <LoaderCircle size={17} className="spin" />
      ) : (
        <Check size={17} />
      )}
      {pending ? "در حال ذخیره…" : children}
    </button>
  );
}

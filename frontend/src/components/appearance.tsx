"use client";

import { useState, useSyncExternalStore } from "react";
import { Check, Monitor, Moon, RotateCcw, Sun } from "lucide-react";
import {
  DEFAULT_PALETTES,
  isHexColor,
  type Appearance,
  type ThemeMode,
  type ThemePalette,
} from "@/lib/appearance";
import { InlineError, PageHeading } from "./ui";
function subscribeSystem(callback: () => void) {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
}
const systemDark = () =>
  window.matchMedia("(prefers-color-scheme: dark)").matches;

export function useThemeMode(appearance: Appearance): ThemeMode {
  const prefersDark = useSyncExternalStore(
    subscribeSystem,
    systemDark,
    () => false,
  );
  return appearance.mode === "system"
    ? prefersDark
      ? "dark"
      : "light"
    : appearance.mode;
}

const colors: { key: keyof ThemePalette; label: string; hint: string }[] = [
  {
    key: "primary",
    label: "دکمه‌ها و المان‌های اصلی",
    hint: "دکمه‌های اصلی، لینک‌ها و نمودارها",
  },
  {
    key: "background",
    label: "پس‌زمینهٔ پنل",
    hint: "فضای پشت کارت‌ها و جدول‌ها",
  },
  {
    key: "surface",
    label: "کارت‌ها و فرم‌ها",
    hint: "کارت‌ها، جدول‌ها، ورودی‌ها و پنجره‌ها",
  },
  { key: "sidebar", label: "منوی کناری", hint: "پس‌زمینهٔ منوی مجموعه" },
  {
    key: "success",
    label: "وضعیت موفق و فعال",
    hint: "وضعیت فعال و پیام‌های موفقیت",
  },
  { key: "warning", label: "هشدارها", hint: "هشدار ظرفیت و انقضای اشتراک" },
  {
    key: "danger",
    label: "خطاها و وضعیت منقضی",
    hint: "خطاها، حذف و وضعیت منقضی",
  },
];

function ColorField({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: string;
  onChange: (color: string) => void;
}) {
  const [draft, setDraft] = useState(value);
  const invalid = !isHexColor(draft);
  return (
    <div className="appearance-color-field">
      <label className="appearance-color-picker">
        <span>{label}</span>
        <small>{hint}</small>
        <input
          type="color"
          value={value}
          aria-label={`انتخاب رنگ ${label}`}
          onChange={(event) => {
            setDraft(event.target.value);
            onChange(event.target.value);
          }}
        />
      </label>
      <label className="appearance-hex">
        <span className="appearance-sr-only">کد رنگ {label}</span>
        <input
          value={draft}
          dir="ltr"
          maxLength={7}
          spellCheck={false}
          required
          pattern="#[0-9a-fA-F]{6}"
          aria-invalid={invalid}
          aria-label={`کد رنگ ${label}`}
          onChange={(event) => {
            const color = event.target.value;
            setDraft(color);
            if (isHexColor(color)) onChange(color.toLowerCase());
          }}
        />
      </label>
      {invalid && (
        <small className="appearance-color-error" role="status">
          کد معتبر مانند #7860cc وارد کنید.
        </small>
      )}
    </div>
  );
}

export function AppearanceSettings({
  appearance,
  mode,
  onChange,
  onSave,
  onCancel,
  dirty,
}: {
  appearance: Appearance;
  mode: ThemeMode;
  onChange: (next: Appearance) => void;
  onSave: (next: Appearance) => Promise<void>;
  onCancel: () => void;
  dirty: boolean;
}) {
  const [saved, setSaved] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reset, setReset] = useState(0);
  function update(next: Appearance) {
    setSaved(false);
    setError(null);
    onChange(next);
  }
  async function save() {
    setPending(true);
    setError(null);
    setSaved(false);
    try {
      await onSave(appearance);
      setSaved(true);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setPending(false);
    }
  }
  const palette = appearance.palettes[mode];
  return (
    <div className="appearance-page ops-page">
      <PageHeading
        title="تنظیمات ظاهر"
        description="تم و رنگ‌های فضای مطالعه را مطابق سلیقهٔ خودتان تنظیم کنید."
      />
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <fieldset className="appearance-controls" disabled={pending}>
          <section
            className="appearance-section panel"
            aria-labelledby="appearance-mode-title"
          >
            <h2 id="appearance-mode-title">تم پنل</h2>
            <p>
              تغییرات را همین‌جا ببینید و سپس ذخیره کنید. رنگ‌های تم روشن و تیره
              جداگانه قابل تنظیم‌اند.
            </p>
            <div
              className="appearance-modes"
              role="group"
              aria-label="انتخاب تم پنل"
            >
              {(
                [
                  { value: "light", label: "روشن", icon: Sun },
                  { value: "dark", label: "تیره", icon: Moon },
                  { value: "system", label: "هماهنگ با سیستم", icon: Monitor },
                ] as const
              ).map(({ value, label, icon: Icon }) => (
                <button
                  type="button"
                  key={value}
                  aria-pressed={appearance.mode === value}
                  className={`appearance-mode ${appearance.mode === value ? "selected" : ""}`}
                  onClick={() => update({ ...appearance, mode: value })}
                >
                  <Icon size={24} />
                  <strong>{label}</strong>
                  {appearance.mode === value && <Check size={16} />}
                </button>
              ))}
            </div>
          </section>
          <section
            className="appearance-section panel"
            aria-labelledby="appearance-colors-title"
          >
            <div className="appearance-section-heading">
              <div>
                <h2 id="appearance-colors-title">
                  رنگ‌های تم {mode === "dark" ? "تیره" : "روشن"}
                </h2>
                <p>رنگ متن برای خوانایی به‌صورت خودکار تنظیم می‌شود.</p>
              </div>
              <button
                type="button"
                className="button secondary"
                onClick={() => {
                  update({
                    ...appearance,
                    palettes: {
                      ...appearance.palettes,
                      [mode]: { ...DEFAULT_PALETTES[mode] },
                    },
                  });
                  setReset((value) => value + 1);
                }}
              >
                <RotateCcw size={16} />
                بازگردانی رنگ‌های این تم
              </button>
            </div>
            <div className="appearance-colors">
              {colors.map(({ key, label, hint }) => (
                <ColorField
                  key={`${mode}:${key}:${reset}`}
                  label={label}
                  hint={hint}
                  value={palette[key]}
                  onChange={(color) =>
                    update({
                      ...appearance,
                      palettes: {
                        ...appearance.palettes,
                        [mode]: { ...palette, [key]: color },
                      },
                    })
                  }
                />
              ))}
            </div>
          </section>
          <section
            className="appearance-section panel appearance-preview"
            aria-labelledby="appearance-preview-title"
          >
            <h2 id="appearance-preview-title">پیش‌نمایش المان‌ها</h2>
            <div className="appearance-preview-elements">
              <span className="button primary">دکمهٔ اصلی</span>
              <span className="ops-status active">
                <i />
                فعال
              </span>
              <span className="badge expiring">
                <i />
                هشدار
              </span>
              <span className="badge expired">
                <i />
                منقضی
              </span>
              <span className="appearance-preview-link">
                رنگ لینک‌ها و نمودارها
              </span>
            </div>
          </section>
          <div className="appearance-save-bar">
            <p className="appearance-save-status" role="status">
              {saved
                ? "تنظیمات ظاهر برای همهٔ کاربران و دستگاه‌های این مجموعه ذخیره شد."
                : dirty
                  ? "تغییرات هنوز ذخیره نشده‌اند."
                  : "تنظیمات ذخیره‌شده برای همهٔ کاربران و دستگاه‌های این مجموعه مشترک است."}
            </p>
            <div className="appearance-save-actions">
              <button
                type="button"
                className="button secondary"
                disabled={!dirty}
                onClick={() => {
                  onCancel();
                  setSaved(false);
                  setError(null);
                  setReset((value) => value + 1);
                }}
              >
                لغو تغییرات
              </button>
              <button
                type="submit"
                className="button primary"
                disabled={!dirty}
              >
                <Check size={16} />
                {pending ? "در حال ذخیره…" : "ذخیرهٔ تنظیمات ظاهر"}
              </button>
            </div>
          </div>
        </fieldset>
      </form>
      <InlineError message={error} />
    </div>
  );
}

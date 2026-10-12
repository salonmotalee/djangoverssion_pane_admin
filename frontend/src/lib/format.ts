import type { Role, ServiceStatus } from "./types.ts";

export const roles: Record<Role, string> = {
  super_admin: "مدیر ارشد",
  admin: "مدیر",
  operator: "اپراتور",
};
export const statuses: Record<ServiceStatus, string> = {
  scheduled: "شروع در آینده",
  active: "فعال",
  expiring: "نزدیک انقضا",
  expired: "منقضی شده",
};
export const number = (value: number) =>
  new Intl.NumberFormat("fa-IR").format(value);
export const date = (
  value: string | null | undefined,
  options?: Intl.DateTimeFormatOptions,
) =>
  value
    ? new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
        timeZone: "Asia/Tehran",
        year: "numeric",
        month: "long",
        day: "numeric",
        ...options,
      }).format(new Date(value.length === 10 ? `${value}T12:00:00Z` : value))
    : "—";
export const shortDate = (value: string) =>
  date(value, { month: "2-digit", day: "2-digit" });
export const time = (value: string) =>
  date(value, {
    year: undefined,
    month: undefined,
    day: undefined,
    hour: "2-digit",
    minute: "2-digit",
  });
export const displayName = (user: {
  first_name: string;
  last_name: string;
  username: string;
}) =>
  [user.first_name, user.last_name].filter(Boolean).join(" ") || user.username;
export const latinDigits = (value: string) =>
  value
    .replace(/[۰-۹]/g, (char) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(char)))
    .replace(/[٠-٩]/g, (char) => String("٠١٢٣٤٥٦٧٨٩".indexOf(char)));
export const isIranianPhone = (value: string) =>
  /^(?:09\d{9}|\+989\d{9}|00989\d{9})$/.test(
    latinDigits(value).replace(/[\s-]/g, ""),
  );
export const safeExportName = () =>
  `madar-customers-${new Date().toISOString().slice(0, 10)}.csv`;
export function queryString(
  values: Record<string, string | number | undefined>,
) {
  const result = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== "") result.set(key, String(value));
  });
  return result.toString();
}

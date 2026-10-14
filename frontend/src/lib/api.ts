let csrfToken = "";
export class ApiError extends Error {
  status: number;
  fields: Record<string, unknown>;
  constructor(
    message: string,
    status: number,
    fields: Record<string, unknown> = {},
  ) {
    super(message);
    this.status = status;
    this.fields = fields;
  }
}
export async function ensureCsrf() {
  const unavailable = "سرویس ورود در دسترس نیست. کمی بعد دوباره تلاش کنید.";
  let response: Response;
  try {
    response = await fetch("/api/auth/csrf/", {
      credentials: "include",
      cache: "no-store",
    });
  } catch {
    throw new ApiError(unavailable, 0);
  }
  if (!response.ok) throw new ApiError(unavailable, response.status);
  const result = await response.json().catch(() => null);
  if (typeof result?.csrfToken !== "string" || !result.csrfToken)
    throw new ApiError(unavailable, response.status);
  csrfToken = result.csrfToken;
  return csrfToken;
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const method = options.method || "GET";
  const mutating = !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
  // Central and portal logins rotate the shared CSRF cookie independently of
  // their separate sessions. Refresh before writes, including across tabs.
  const token = mutating ? await ensureCsrf() : "";
  const response = await fetch(`/api/${path}`, {
    ...options,
    credentials: "include",
    cache: "no-store",
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(mutating ? { "X-CSRFToken": token } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    if (
      response.status === 401 &&
      path !== "auth/login/" &&
      path !== "auth/me/" &&
      !path.startsWith("organizations/") &&
      typeof window !== "undefined"
    ) {
      resetCsrf();
      window.dispatchEvent(new Event("madar:session-expired"));
    }
    const fields = await response.json().catch(() => ({}));
    const messages = Object.entries(fields).map(([key, value]) =>
      key === "detail" || key === "non_field_errors"
        ? String(value)
        : `${fieldNames[key] || key}: ${Array.isArray(value) ? value.join(" ") : String(value)}`,
    );
    throw new ApiError(
      messages.join(" • ") ||
        (response.status === 403
          ? "مجوز انجام این عملیات را ندارید."
          : response.status === 401
            ? "برای ادامه دوباره وارد شوید."
            : "ارتباط با سرور ناموفق بود. دوباره تلاش کنید."),
      response.status,
      fields,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
const fieldNames: Record<string, string> = {
  name: "نام مجموعه",
  manager_name: "نام مدیر",
  phone: "شماره تماس",
  identifier: "شناسه",
  start_date: "تاریخ شروع",
  expiration_date: "تاریخ پایان",
  username: "نام کاربری",
  password: "رمز عبور",
  new_password: "رمز عبور جدید",
  current_password: "رمز عبور فعلی",
  email: "ایمیل",
  role: "نقش",
  slug: "نشانی اختصاصی",
  capacity: "ظرفیت مجموعه",
  login_username: "نام کاربری پرتال",
  login_password: "رمز ورود پرتال",
  first_name: "نام",
  last_name: "نام خانوادگی",
  primary_phone: "شماره همراه اصلی",
  secondary_phone: "شماره همراه دوم",
  desk_number: "شماره میز",
  grade: "پایهٔ تحصیلی",
  major: "رشتهٔ تحصیلی",
  hall: "سالن",
  start_time: "ساعت شروع",
  end_time: "ساعت پایان",
  is_active: "وضعیت",
  assignments: "تخصیص پارت‌ها",
  halls: "سالن‌ها",
  subject: "موضوع",
  category: "دسته‌بندی",
  priority: "اولویت",
  description: "شرح درخواست",
  body: "متن پیام",
  assigned_to: "مسئول پیگیری",
  date_from: "از تاریخ",
  date_to: "تا تاریخ",
  can_support: "دسترسی پشتیبانی",
};
export const mutate = <T>(path: string, method: string, body?: unknown) =>
  api<T>(path, {
    method,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
export function resetCsrf() {
  csrfToken = "";
}

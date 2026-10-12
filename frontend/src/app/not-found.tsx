import Link from "next/link";
export default function NotFound() {
  return (
    <main className="session-loading">
      <span className="eyebrow">خطای ۴۰۴</span>
      <h1>این مسیر پیدا نشد</h1>
      <p>برای ادامه به فضای مدیریت برگردید.</p>
      <Link className="button primary" href="/dashboard">
        بازگشت به داشبورد
      </Link>
    </main>
  );
}

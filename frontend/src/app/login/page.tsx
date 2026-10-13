"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Eye,
  EyeOff,
  LockKeyhole,
  Orbit,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useAuth } from "@/components/providers";
import { Field, InlineError, Logo } from "@/components/ui";
import { mutate, resetCsrf } from "@/lib/api";
import type { User } from "@/lib/types";
export default function Login() {
  const { user, setUser } = useAuth();
  const router = useRouter();
  const [visible, setVisible] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);
  return (
    <main className="login-page">
      <div className="login-light light-one" />
      <div className="login-light light-two" />
      <div className="login-grid" />
      <header className="login-header">
        <Logo />
        <span>
          <span className="green-dot" />
          فضای امن مدیریت
        </span>
      </header>
      <div className="login-content">
        <section className="login-story">
          <span className="login-eyebrow">
            <Sparkles size={15} />
            یک نگاه. تمامِ تصویر.
          </span>
          <h1>
            همه چیز،
            <br />
            در <span>مدار</span> شما.
          </h1>
          <p>
            فضایی آرام برای مدیریت مجموعه‌ها،
            <br />
            همراه با دیدی روشن به آنچه پیش روست.
          </p>
          <div className="orbital-art" aria-hidden="true">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="orbit orbit-three" />
            <div className="orbit-core">
              <Orbit size={48} strokeWidth={1} />
            </div>
            <span className="orbital-node node-one" />
            <span className="orbital-node node-two" />
            <span className="orbital-node node-three" />
            <div className="orbit-label">
              <span className="green-dot" />
              همه چیز به هم متصل است
            </div>
          </div>
          <div className="login-feature">
            <ShieldCheck size={20} />
            <span>
              دسترسی کنترل‌شده <i /> اطلاعات یکپارچه <i /> مدیریت ساده
            </span>
          </div>
        </section>
        <section className="login-card">
          <div className="login-icon">
            <LockKeyhole size={23} />
          </div>
          <span className="eyebrow">خوش آمدید</span>
          <h2>ورود به فضای مدیریت</h2>
          <p>برای ادامه، اطلاعات حساب خود را وارد کنید.</p>
          <form
            data-testid="login-form"
            onSubmit={async (event) => {
              event.preventDefault();
              setPending(true);
              setError(null);
              const data = new FormData(event.currentTarget);
              try {
                const result = await mutate<User>("auth/login/", "POST", {
                  username: data.get("username"),
                  password: data.get("password"),
                });
                resetCsrf();
                setUser(result);
                router.replace("/dashboard");
              } catch (error) {
                setError((error as Error).message);
              } finally {
                setPending(false);
              }
            }}
          >
            <Field label="نام کاربری" required>
              <div className="input-icon">
                <UserRound size={17} />
                <input
                  name="username"
                  required
                  autoComplete="username"
                  autoCapitalize="none"
                  dir="ltr"
                  placeholder="نام کاربری شما"
                  disabled={pending}
                />
              </div>
            </Field>
            <Field label="رمز عبور" required>
              <div className="input-icon">
                <LockKeyhole size={17} />
                <input
                  name="password"
                  required
                  autoComplete="current-password"
                  type={visible ? "text" : "password"}
                  dir="ltr"
                  placeholder="رمز عبور شما"
                  disabled={pending}
                />
                <button
                  className="password-eye"
                  type="button"
                  aria-label={
                    visible ? "پنهان کردن رمز عبور" : "نمایش رمز عبور"
                  }
                  onClick={() => setVisible(!visible)}
                >
                  {visible ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </Field>
            <InlineError message={error} />
            <button className="button primary login-submit" disabled={pending}>
              {pending ? "در حال ورود…" : "ورود به مدار"}
              <ArrowLeft size={18} />
            </button>
          </form>
          <div className="login-security">
            <ShieldCheck size={15} />
            <span>این پنل ویژه مدیران و اپراتورهای داخلی است.</span>
          </div>
        </section>
      </div>
      <footer className="login-footer">
        <span>مدار؛ مدیریت در مسیر درست.</span>
        <span>
          نسخه ۱.۰ <i /> با توجه به جزئیات ساخته شده
        </span>
      </footer>
    </main>
  );
}

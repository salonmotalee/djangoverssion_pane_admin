import Link from "next/link";
import { DamavandBrand, MountainScene } from "@/components/portal-scene";
export default function NotFound() {
  return (
    <main className="portal-not-found">
      <MountainScene />
      <DamavandBrand />
      <span className="lost-coordinate">۴۰۴</span>
      <h1>این مسیر به قله نمی‌رسد</h1>
      <p>
        مجموعه‌ای در این نشانی پیدا نشد. نشانی اختصاصی مجموعه را بررسی کنید یا
        با مدیریت دماوند تماس بگیرید.
      </p>
      <Link href="/login">ورود به مدیریت مرکزی</Link>
    </main>
  );
}

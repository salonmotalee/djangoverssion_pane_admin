import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import "./globals.css";
import "./portal.css";
import "./operations.css";
export const metadata: Metadata = {
  title: { default: "مدار | فضای مدیریت", template: "%s | مدار" },
  description: "مدار، فضای یکپارچه مدیریت مجموعه‌ها و سرویس‌ها",
  robots: { index: false, follow: false },
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fa" dir="rtl" data-scroll-behavior="smooth">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

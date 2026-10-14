"use client";
import Link from "next/link";
import {
  Building2,
  Clock3,
  GraduationCap,
  ArrowUpLeft,
  Users,
  UserRoundCheck,
} from "lucide-react";
import { number } from "@/lib/format";
import type { OperationsSummary } from "@/lib/operations";
import { HelpTooltip } from "./help-tooltip";
import { SupportIndicators } from "./support";

export function OperationsOverview({
  slug,
  stats,
}: {
  slug: string;
  stats: OperationsSummary;
}) {
  const metrics = [
    {
      label: "مراقب فعال",
      value: stats.active_supervisors,
      href: "supervisors",
      icon: UserRoundCheck,
      color: "purple",
    },
    {
      label: "دانش‌آموز فعال",
      value: stats.active_students,
      href: "students",
      icon: GraduationCap,
      color: "purple",
    },
    {
      label: "ظرفیت باقی‌مانده",
      value: stats.remaining_capacity,
      href: "students",
      icon: Users,
      color: "turquoise",
    },
    {
      label: "سالن فعال",
      value: stats.active_halls,
      href: "halls",
      icon: Building2,
      color: "blue",
    },
    {
      label: "پارت مطالعاتی",
      value: stats.active_sessions,
      href: "study-sessions",
      icon: Clock3,
      color: "orange",
    },
  ];
  return (
    <section className="ops-overview" aria-label="آمار عملیات مجموعه">
      {stats.over_capacity && (
        <div className="ops-warning" role="status">
          <strong>تعداد ثبت‌نام از ظرفیت فعلی بیشتر است.</strong>
          <p>
            دانش‌آموزان فعلی حفظ شده‌اند؛ تا آزادشدن ظرفیت یا افزایش آن، ثبت‌نام
            و بازیابی جدید امکان‌پذیر نیست.
          </p>
        </div>
      )}
      <div className="ops-metrics">
        {metrics.map(({ label, value, href, icon: Icon, color }) => (
          <Link
            key={href + label}
            href={`/${slug}/${href}`}
            className={`ops-metric ${color}`}
          >
            <span className={`tenant-card-icon ${color}`}>
              <Icon size={21} />
            </span>
            <span>
              {label}
              <strong data-testid={`ops-${href}-${color}`}>
                {value === null ? "—" : number(value)}
              </strong>
            </span>
            <ArrowUpLeft size={16} />
          </Link>
        ))}
      </div>
      <SupportIndicators slug={slug} />
      <div className="ops-analytics">
        <div className="tenant-card ops-utilization">
          <div>
            <h2>
              ظرفیت ثبت‌نام
              <HelpTooltip
                label="راهنمای ظرفیت ثبت‌نام"
                content="این درصد از نسبت دانش‌آموزان فعال به ظرفیت مجموعه به دست می‌آید؛ نشان‌دهندهٔ حضور فیزیکی یا اشغال میز نیست."
              />
            </h2>
          </div>
          <strong>
            {stats.utilization_percent === null
              ? "—"
              : number(stats.utilization_percent)}
            <small>٪</small>
          </strong>
          <div
            className="ops-meter"
            role="progressbar"
            aria-label="درصد استفاده از ظرفیت ثبت‌نام"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.min(100, stats.utilization_percent || 0)}
            aria-valuetext={`${number(stats.utilization_percent || 0)} درصد`}
          >
            <span
              style={{
                width: `${Math.min(100, stats.utilization_percent || 0)}%`,
              }}
            />
          </div>
        </div>
        <div className="tenant-card ops-hall-chart">
          <div className="ops-section-title">
            <h2>دانش‌آموزان هر سالن</h2>
            <Link href={`/${slug}/students`}>
              مشاهده و مدیریت <ArrowUpLeft size={15} />
            </Link>
          </div>
          {stats.students_per_hall.length ? (
            stats.students_per_hall.map((hall) => (
              <Link
                href={`/${slug}/students?hall=${hall.id}`}
                key={hall.id}
                className="ops-hall-bar"
              >
                <span>{hall.name}</span>
                <div>
                  <i
                    style={{
                      width: `${stats.active_students ? Math.max(3, (hall.active_students * 100) / stats.active_students) : 0}%`,
                    }}
                  />
                </div>
                <strong>{number(hall.active_students)}</strong>
              </Link>
            ))
          ) : (
            <p className="ops-muted">
              با ساخت اولین سالن، توزیع ثبت‌نام‌ها اینجا نمایش داده می‌شود.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

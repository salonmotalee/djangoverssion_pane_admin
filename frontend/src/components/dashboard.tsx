"use client";
import { useState } from "react";
import Link from "next/link";
import {
  Activity as ActivityIcon,
  ArrowLeft,
  ArrowUpLeft,
  CalendarClock,
  CircleArrowUp,
  CircleCheck,
  Clock3,
  Plus,
  ShieldCheck,
  Users,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useAuth } from "./providers";
import {
  Badge,
  DateField,
  Empty,
  ErrorState,
  PageHeading,
  Panel,
  Spinner,
  ViewAll,
} from "./ui";
import { CustomerForm } from "./customers";
import {
  date,
  displayName,
  number,
  queryString,
  shortDate,
  statuses,
  time,
} from "@/lib/format";
import { useData } from "@/lib/use-data";
import type { Audit, DashboardData } from "@/lib/types";

function monthRange(value: string, short = false) {
  const month = value.slice(0, 7);
  const start = `${month}-01`;
  const [year, part] = month.split("-").map(Number);
  const end = new Date(Date.UTC(year, part, 0, 12)).toISOString().slice(0, 10);
  const options: Intl.DateTimeFormatOptions = short
    ? { year: undefined, month: "2-digit", day: "2-digit" }
    : { year: undefined };
  return `${date(start, options)} ${short ? "–" : "تا"} ${date(end, options)}`;
}
const chartColors: Record<string, string> = {
  active: "#6366f1",
  expiring: "#f2b65e",
  expired: "#ef7a87",
  scheduled: "#b6c3d7",
};
export function ActivityList({ items }: { items: Audit[] }) {
  return items.length ? (
    <div className="activity-list">
      {items.map((item) => (
        <div className="activity-item" key={item.id}>
          <span className={`activity-icon ${item.action}`}>
            <ActivityIcon size={16} />
          </span>
          <div>
            <strong>{item.description || item.action}</strong>
            <p>
              {item.actor ? displayName(item.actor) : "سیستم"}
              <span>·</span>
              {date(item.created_at)}
            </p>
          </div>
          <time>{time(item.created_at)}</time>
        </div>
      ))}
    </div>
  ) : (
    <Empty
      title="تاریخچه از اینجا شروع می‌شود"
      description="فعالیت‌های مدیریتی پس از اولین تغییر نمایش داده می‌شوند."
    />
  );
}
export function Dashboard() {
  const { user } = useAuth();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [filterOpen, setFilterOpen] = useState(false);
  const [create, setCreate] = useState(false);
  const { data, error, loading, refresh } = useData<DashboardData>(
    `dashboard/?${queryString({ date_from: from, date_to: to })}`,
  );
  const canAudit = user?.role !== "operator";
  return (
    <>
      <PageHeading
        eyebrow="مرکز فرماندهی شما"
        title={user ? `سلام، ${displayName(user)} 👋` : "نمای کلی"}
        description="امروز چه خبر؟ نگاهی به وضعیت مجموعه‌ها و سرویس‌های شما."
      >
        <button
          className={`button secondary ${filterOpen ? "selected" : ""}`}
          onClick={() => setFilterOpen(!filterOpen)}
        >
          <CalendarClock size={17} />
          بازه گزارش
        </button>
        <button className="button primary" onClick={() => setCreate(true)}>
          <Plus size={18} />
          مجموعه جدید
        </button>
      </PageHeading>
      {filterOpen && (
        <div className="filter-panel dashboard-filters">
          <DateField label="ثبت از تاریخ" value={from} onChange={setFrom} />
          <DateField label="تا تاریخ" value={to} onChange={setTo} />
          <button
            className="button subtle"
            onClick={() => {
              setFrom("");
              setTo("");
            }}
          >
            پاک کردن بازه
          </button>
          <small>آمار و گزارش بر اساس تاریخ ثبت مجموعه‌ها فیلتر می‌شوند.</small>
        </div>
      )}
      {error ? (
        <ErrorState error={error} retry={refresh} />
      ) : !data ? (
        <Spinner />
      ) : (
        <div className={`dashboard-content ${loading ? "refreshing" : ""}`}>
          <div className="metric-grid">
            {[
              {
                label: "کل مجموعه‌ها",
                value: data.metrics.total_customers,
                icon: Users,
                color: "indigo",
                caption: "مجموعه در فضای شما",
                path: "/customers",
              },
              {
                label: "سرویس‌های فعال",
                value: data.metrics.active_services,
                icon: CircleCheck,
                color: "green",
                caption: "در مسیر خدمت‌رسانی",
                path: "/customers?status=current",
              },
              {
                label: "نزدیک به انقضا",
                value: data.metrics.expiring_services,
                icon: Clock3,
                color: "amber",
                caption: "تا ۳۰ روز آینده",
                path: "/customers?status=expiring",
              },
              {
                label: "سرویس‌های منقضی",
                value: data.metrics.expired_services,
                icon: CalendarClock,
                color: "rose",
                caption: "نیازمند بررسی و تمدید",
                path: "/customers?status=expired",
              },
            ].map(({ label, value, icon: Icon, color, caption, path }) => (
              <Link
                className={`metric-card ${color}`}
                href={`${path}${path.includes("?") ? "&" : "?"}${queryString({ created_date_from: from, created_date_to: to })}`}
                key={label}
              >
                <div>
                  <span className="metric-label">{label}</span>
                  <span className="metric-icon">
                    <Icon size={20} strokeWidth={1.8} />
                  </span>
                </div>
                <strong>{number(value)}</strong>
                <div className="metric-bottom">
                  <span>{caption}</span>
                  <ArrowUpLeft size={15} />
                </div>
                <span className="metric-accent" />
              </Link>
            ))}
          </div>
          <div className="chart-grid">
            <Panel
              title="روند رشد مجموعه‌ها"
              subtitle="ثبت مجموعه‌های جدید در گذر زمان"
              action={
                <span className="chart-legend">
                  <i />
                  مجموعه جدید
                </span>
              }
              className="growth-panel"
            >
              {data.growth.some((item) => item.count > 0) ? (
                <div className="growth-chart" dir="ltr">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={data.growth}
                      margin={{ top: 15, right: 16, left: -18, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient
                          id="growthGradient"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="0%"
                            stopColor="#6366f1"
                            stopOpacity={0.23}
                          />
                          <stop
                            offset="98%"
                            stopColor="#6366f1"
                            stopOpacity={0}
                          />
                        </linearGradient>
                      </defs>
                      <CartesianGrid
                        stroke="#edf0f7"
                        vertical={false}
                        strokeDasharray="3 5"
                      />
                      <XAxis
                        dataKey="month"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: "#8b95a8", fontSize: 11 }}
                        tickFormatter={(value) =>
                          monthRange(String(value), true)
                        }
                        dy={12}
                      />
                      <YAxis
                        allowDecimals={false}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: "#8b95a8", fontSize: 11 }}
                        tickFormatter={number}
                      />
                      <Tooltip
                        contentStyle={{
                          fontFamily: "Vazir FD",
                          borderRadius: 14,
                          border: "1px solid #eaedf4",
                          fontSize: 12,
                          direction: "rtl",
                        }}
                        formatter={(value) => [
                          number(Number(value)),
                          "مجموعه جدید",
                        ]}
                        labelFormatter={(label) => monthRange(String(label))}
                      />
                      <Area
                        type="monotone"
                        dataKey="count"
                        stroke="#6366f1"
                        strokeWidth={3}
                        fill="url(#growthGradient)"
                        activeDot={{ r: 6, stroke: "#fff", strokeWidth: 3 }}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <Empty
                  title="نقطه آغاز یک مسیر تازه"
                  description="با ثبت اولین مجموعه، نمودار رشد شما جان می‌گیرد."
                />
              )}
            </Panel>
            <Panel
              title="وضعیت سرویس‌ها"
              subtitle="تصویر امروزِ مجموعه‌های شما"
              className="distribution-panel"
            >
              {data.metrics.total_customers ? (
                <>
                  <div className="donut-chart" dir="ltr">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={data.distribution}
                          dataKey="count"
                          nameKey="status"
                          cx="50%"
                          cy="50%"
                          innerRadius={68}
                          outerRadius={90}
                          paddingAngle={4}
                          cornerRadius={5}
                          stroke="none"
                        >
                          {data.distribution.map((item) => (
                            <Cell
                              key={item.status}
                              fill={chartColors[item.status]}
                            />
                          ))}
                        </Pie>
                        <Tooltip
                          formatter={(value, name) => [
                            number(Number(value)),
                            statuses[name as keyof typeof statuses],
                          ]}
                          contentStyle={{
                            fontFamily: "Vazir FD",
                            borderRadius: 12,
                            border: "1px solid #eaedf4",
                          }}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="donut-center">
                      <strong>{number(data.metrics.total_customers)}</strong>
                      <span>مجموعه</span>
                    </div>
                  </div>
                  <div className="distribution-legend">
                    {data.distribution.map((item) => (
                      <div key={item.status}>
                        <span>
                          <i style={{ background: chartColors[item.status] }} />
                          {statuses[item.status]}
                        </span>
                        <strong>{number(item.count)}</strong>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <Empty
                  title="در انتظار اولین مجموعه"
                  description="توزیع وضعیت سرویس‌ها اینجا نمایش داده می‌شود."
                />
              )}
            </Panel>
          </div>
          <div className="insight-strip">
            <span className="insight-icon">
              <ShieldCheck size={21} />
            </span>
            <div>
              <strong>
                {number(data.metrics.active_administrators)} مدیر فعال، در کنار
                شما
              </strong>
              <p>
                انقضای سرویس اطلاع‌رسانی است؛ دسترسی مجموعه‌ها به‌صورت خودکار
                قطع نمی‌شود.
              </p>
            </div>
            <Link href={canAudit ? "/users" : "/profile"}>
              مدیریت {canAudit ? "دسترسی‌ها" : "پروفایل"}
              <ArrowLeft size={15} />
            </Link>
          </div>
          <div className="dashboard-lists">
            <Panel
              title="سررسیدهای پیش رو"
              subtitle={`${number(data.metrics.expiring_7_days)} سرویس در ۷ روز آینده`}
              action={<ViewAll href="/alerts" />}
            >
              <div className="compact-customers">
                {data.upcoming_expirations.length ? (
                  data.upcoming_expirations.slice(0, 5).map((item) => (
                    <Link
                      className="compact-customer"
                      href={`/customers/${item.id}`}
                      key={item.id}
                    >
                      <span className="collection-avatar">
                        {item.name.slice(0, 1)}
                      </span>
                      <div>
                        <strong>{item.name}</strong>
                        <small>{item.manager_name}</small>
                      </div>
                      <div className="compact-end">
                        <span
                          className={`remaining ${item.days_remaining <= 7 ? "urgent" : ""}`}
                        >
                          {number(item.days_remaining)} روز باقی‌مانده
                        </span>
                        <small>{shortDate(item.expiration_date)}</small>
                      </div>
                    </Link>
                  ))
                ) : (
                  <Empty
                    title="خیالتان از سررسیدها آسوده"
                    description="هیچ سرویسی در ۳۰ روز آینده منقضی نمی‌شود."
                  />
                )}
              </div>
            </Panel>
            <Panel
              title="جدیدترین مجموعه‌ها"
              subtitle="آخرین همراهان فضای مدیریت"
              action={<ViewAll href="/customers" />}
            >
              <div className="compact-customers">
                {data.recent_customers.length ? (
                  data.recent_customers.slice(0, 5).map((item) => (
                    <Link
                      className="compact-customer"
                      href={`/customers/${item.id}`}
                      key={item.id}
                    >
                      <span className="collection-avatar purple">
                        {item.name.slice(0, 1)}
                      </span>
                      <div>
                        <strong>{item.name}</strong>
                        <small>{date(item.created_at)}</small>
                      </div>
                      <Badge status={item.status} />
                    </Link>
                  ))
                ) : (
                  <Empty
                    title="اولین مجموعه، اولین قدم"
                    description="برای شروع، یک مجموعه به مدار اضافه کنید."
                    action={
                      <button
                        className="button secondary"
                        onClick={() => setCreate(true)}
                      >
                        <Plus size={16} />
                        ثبت اولین مجموعه
                      </button>
                    }
                  />
                )}
              </div>
            </Panel>
          </div>
          {canAudit && (
            <Panel
              title="نبض فعالیت‌ها"
              subtitle="آخرین تغییرات ثبت شده در فضای شما"
              action={<ViewAll href="/activity" />}
            >
              <ActivityList items={data.recent_activities.slice(0, 5)} />
            </Panel>
          )}
          <div className="dashboard-bottom-note">
            <CircleArrowUp size={14} />
            <span>اطلاعات مستقیماً از پایگاه داده شما دریافت می‌شود.</span>
          </div>
        </div>
      )}
      {create && (
        <CustomerForm
          onClose={() => setCreate(false)}
          onSaved={() => {
            setCreate(false);
            refresh();
          }}
        />
      )}
    </>
  );
}

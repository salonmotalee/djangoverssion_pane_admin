import type { Appearance } from "./appearance.ts";
import type { OrganizationSession } from "./types.ts";

export const supervisorPages = [
  "dashboard",
  "halls",
  "students",
  "presence",
  "attendance",
  "schedule",
  "profile",
] as const;
export type SupervisorPage = (typeof supervisorPages)[number];
export const supervisorTitles: Record<SupervisorPage, string> = {
  dashboard: "داشبورد",
  halls: "سالن‌های من",
  students: "دانش‌آموزان",
  presence: "ورود و خروج",
  attendance: "حضور و غیاب",
  schedule: "برنامه شیفت‌ها",
  profile: "پروفایل",
};
export type StaffSession = {
  id: number;
  supervisor_id: number;
  phone: string;
  username: string;
  enabled: boolean;
  first_name: string;
  last_name: string;
  created_at: string;
  halls: { id: number; name: string }[];
  organization: OrganizationSession["organization"] & {
    appearance: Appearance;
  };
};
export type SupervisorAccess = {
  supervisor_id: number;
  phone: string;
  enabled: boolean;
  provisioned: boolean;
  usable: boolean;
  account_id: number | null;
  last_login: string | null;
  halls: { id: number; name: string }[];
};
export type StaffStudySession = {
  id: number;
  title: string;
  start_time: string;
  end_time: string;
};
export type StaffHall = {
  id: number;
  name: string;
  sessions: StaffStudySession[];
  active_students: number;
};
export type StaffStudent = {
  id: number;
  identifier: string;
  first_name: string;
  last_name: string;
  hall: number;
  hall_name: string;
  inside: boolean;
  presence_hall?: number | null;
  last_event_at: string | null;
};
export type PresenceEvent = {
  id: number;
  student: number;
  student_name: string;
  identifier: string;
  hall: number;
  hall_name: string;
  kind: "entry" | "exit";
  occurred_at: string;
  supervisor_name: string;
  sequence: number;
};
export type StaffShift = {
  id: number;
  date: string;
  hall: number;
  hall_name: string;
  shift: number;
  shift_name: string;
  supervisor: number;
  supervisor_name: string;
  start_time: string;
  end_time: string;
  conflict_override: boolean;
};
export type StaffSchedule = {
  week_start: string;
  week_end: string;
  days: { date: string; jalali_date: string; weekday: number }[];
  assignments: StaffShift[];
  halls: { id: number; name: string }[];
};
export type StaffDashboard = {
  halls: StaffHall[];
  student_count: number;
  inside_count: number;
  today_attendance: { completed: number; pending: number };
  today_shifts: StaffShift[];
  upcoming_shifts: StaffShift[];
};
export type AttendanceStatus = "present" | "absent" | "late";
export const attendanceLabels: Record<AttendanceStatus, string> = {
  present: "حاضر",
  absent: "غایب",
  late: "تأخیر",
};
export type AttendanceRecord = {
  id: number;
  status: AttendanceStatus;
  source: "manual" | "automatic";
  revision: number;
  created_at: string;
  updated_at: string;
  recorder: { id: number; name: string };
  early_departure: boolean;
  departed_at: string | null;
  can_edit: boolean;
};
export type AttendanceStudent = {
  id: number;
  identifier: string;
  first_name: string;
  last_name: string;
  record: AttendanceRecord | null;
  calculated_status?: AttendanceStatus;
  early_departure?: boolean;
  departed_at?: string | null;
  selectable?: boolean;
};
export type AttendanceRoster = {
  hall: number;
  date: string;
  session: number | null;
  sessions: StaffStudySession[];
  starts_at: string | null;
  ends_at: string | null;
  provisional: boolean;
  students: AttendanceStudent[];
  preview_token?: string;
};
export type AttendanceChange = {
  student: number;
  status: AttendanceStatus;
  revision?: number;
};

/** Use Tehran's business date even when a supervisor's browser is abroad. */
export function tehranToday(now = new Date()): string {
  const values = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const part = (name: Intl.DateTimeFormatPartTypes) =>
    values.find((value) => value.type === name)?.value;
  return `${part("year")}-${part("month")}-${part("day")}`;
}
export function addCalendarDays(value: string, amount: number): string {
  const point = new Date(`${value}T12:00:00Z`);
  point.setUTCDate(point.getUTCDate() + amount);
  return point.toISOString().slice(0, 10);
}
export function saturdayOfWeek(value: string): string {
  const weekday = new Date(`${value}T12:00:00Z`).getUTCDay();
  return addCalendarDays(value, -((weekday + 1) % 7));
}
export const staffName = (person: { first_name: string; last_name: string }) =>
  `${person.first_name} ${person.last_name}`.trim();

/** Build only deliberate changes, retaining revisions returned by the server. */
export function attendanceChanges(
  rows: AttendanceStudent[],
  draft: Record<number, AttendanceStatus>,
): AttendanceChange[] {
  return rows.flatMap((row) => {
    const status = draft[row.id];
    if (
      !status ||
      row.record?.can_edit === false ||
      row.record?.status === status
    )
      return [];
    return [
      {
        student: row.id,
        status,
        ...(row.record ? { revision: row.record.revision } : {}),
      },
    ];
  });
}
export function automaticSelection(rows: AttendanceStudent[]): number[] {
  // The server remains authoritative; never infer ownership from names or IDs.
  return rows
    .filter((row) => row.selectable === true && row.record?.source !== "manual")
    .sort((first, second) => Number(!!first.record) - Number(!!second.record))
    .map((row) => row.id);
}

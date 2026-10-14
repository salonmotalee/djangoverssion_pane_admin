export const operationPages = [
  "halls",
  "study-sessions",
  "assignments",
  "students",
] as const;
export type OperationPage = (typeof operationPages)[number];
export const operationTitles: Record<OperationPage, string> = {
  halls: "سالن‌ها",
  "study-sessions": "پارت‌های مطالعاتی",
  assignments: "تخصیص پارت‌ها",
  students: "دانش‌آموزان",
};
export const grades: Record<number, string> = {
  7: "هفتم",
  8: "هشتم",
  9: "نهم",
  10: "دهم",
  11: "یازدهم",
  12: "دوازدهم",
  13: "فارغ‌التحصیل",
};
export const majors: Record<string, string> = {
  humanities: "علوم انسانی",
  mathematics: "ریاضی و فیزیک",
  experimental: "علوم تجربی",
  other: "سایر",
};
export type Hall = {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
  active_students: number;
  created_at: string;
  updated_at: string;
};
export type StudySession = {
  id: number;
  title: string;
  start_time: string;
  end_time: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};
export type Student = {
  id: number;
  identifier: string;
  desk_number: string;
  first_name: string;
  last_name: string;
  primary_phone: string;
  secondary_phone: string;
  grade: number;
  major: string;
  hall: number;
  hall_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};
export type AssignmentData = {
  halls: Hall[];
  sessions: StudySession[];
  assignments: { hall: number; session: number }[];
};
export type OperationsSummary = {
  capacity: number | null;
  active_students: number;
  remaining_capacity: number | null;
  utilization_percent: number | null;
  over_capacity: boolean;
  active_halls: number;
  active_sessions: number;
  students_per_hall: { id: number; name: string; active_students: number }[];
};
const seconds = (value: string) => {
  const [hour, minute, second = "0"] = value.split(":");
  return Number(hour) * 3600 + Number(minute) * 60 + Number(second);
};
export const compareSessions = (a: StudySession, b: StudySession) =>
  seconds(a.start_time) - seconds(b.start_time) ||
  seconds(a.end_time) - seconds(b.end_time) ||
  a.id - b.id;
export const clockTime = (value: string) =>
  value.slice(0, 5).replace(/[0-9]/g, (digit) => "۰۱۲۳۴۵۶۷۸۹"[Number(digit)]);
export const sessionLabel = (session: StudySession) =>
  `${session.title || "پارت مطالعاتی"} · ${clockTime(session.start_time)} تا ${clockTime(session.end_time)}`;

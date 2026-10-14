export type WorkShift = {
  id: number;
  name: string;
  start_time: string;
  end_time: string;
  is_active: boolean;
};
export type SchedulingSupervisor = {
  id: number;
  first_name: string;
  last_name: string;
  halls: number[];
};
export type ScheduleAssignment = {
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
export type ScheduleConflict = {
  left: number | string;
  right: number | string;
  supervisor: number;
  supervisor_name?: string;
  date: string;
  start_time: string;
  end_time: string;
  left_hall?: string;
  right_hall?: string;
  left_shift?: string;
  right_shift?: string;
  left_key?: [string, number, number, number];
  right_key?: [string, number, number, number];
  resolved_by_removal?: boolean;
  detail?: string;
};
export type ScheduleWeek = {
  week_start: string;
  week_end: string;
  revision: string;
  days: { date: string; jalali_date: string; weekday: number }[];
  assignments: ScheduleAssignment[];
  shifts: WorkShift[];
  halls: { id: number; name: string }[];
  supervisors: SchedulingSupervisor[];
  conflicts: ScheduleConflict[];
};
export type ProposedAssignment = Pick<
  ScheduleAssignment,
  "date" | "hall" | "shift" | "supervisor"
>;
export type PreviewAction = "add" | "preserve" | "replace" | "skip";
export type PreviewRow = ProposedAssignment & {
  index: number;
  hall_name: string;
  shift_name: string;
  supervisor_name: string;
  start_time: string;
  end_time: string;
  status: "new" | "existing" | "duplicate" | "invalid";
  error?: string;
  existing_assignments?: ScheduleAssignment[];
  source_start_time?: string;
  source_end_time?: string;
  times_changed?: boolean;
  existing_id?: number | null;
  existing_ids: number[];
  default_action: PreviewAction;
  conflicts: ScheduleConflict[];
};
export type SchedulePreview = {
  token: string;
  revision: string;
  rows: PreviewRow[];
  removals: ScheduleAssignment[];
  conflicts: ScheduleConflict[];
  summary: {
    add: number;
    existing: number;
    duplicate: number;
    conflicts: number;
    remove: number;
  };
};
export type PreviewChoice = {
  index: number;
  action: PreviewAction;
  replace_ids?: number[];
};
export const weekDays = [
  "شنبه",
  "یکشنبه",
  "دوشنبه",
  "سه‌شنبه",
  "چهارشنبه",
  "پنجشنبه",
  "جمعه",
];

/** Calendar arithmetic uses UTC dates; clock displays are always Tehran. */
export function moveDate(value: string, days: number) {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}
export function saturdayWeek(value: string) {
  const weekday = new Date(`${value}T12:00:00Z`).getUTCDay();
  return moveDate(value, -((weekday + 1) % 7));
}
export function calendarWeek(value: string) {
  const start = saturdayWeek(value);
  return Array.from({ length: 7 }, (_, day) => moveDate(start, day));
}
export function todayTehran(now = new Date()) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const value = (type: string) =>
    parts.find((part) => part.type === type)?.value;
  return `${value("year")}-${value("month")}-${value("day")}`;
}
export function jalaliMonth(value: string) {
  const parts = new Intl.DateTimeFormat("en-US-u-ca-persian", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).formatToParts(new Date(`${value}T12:00:00Z`));
  const part = (type: string) =>
    Number(parts.find((item) => item.type === type)?.value);
  return { year: part("year"), month: part("month"), day: part("day") };
}
export function initialPreviewChoices(rows: PreviewRow[]): PreviewChoice[] {
  return rows.map((row) => ({
    index: row.index,
    // Preserving is always the safe default, even if a backend proposes replace.
    action:
      row.status === "existing"
        ? "preserve"
        : row.status === "duplicate"
          ? "skip"
          : row.default_action === "add"
            ? "add"
            : "skip",
  }));
}
export function authorizedSupervisors(
  supervisors: SchedulingSupervisor[],
  hall: number,
  search = "",
) {
  const term = search.trim().toLocaleLowerCase("fa");
  return supervisors.filter(
    (supervisor) =>
      supervisor.halls.includes(hall) &&
      `${supervisor.first_name} ${supervisor.last_name}`
        .toLocaleLowerCase("fa")
        .includes(term),
  );
}
export function scheduleKey(row: ProposedAssignment) {
  return `${row.date}:${row.hall}:${row.shift}:${row.supervisor}`;
}
export function uniqueAssignments(rows: ProposedAssignment[]) {
  return [...new Map(rows.map((row) => [scheduleKey(row), row])).values()];
}
export function validateShift(name: string, start: string, end: string) {
  if (!name.trim()) return "نام شیفت را وارد کنید.";
  if (
    !/^\d{2}:\d{2}(:\d{2})?$/.test(start) ||
    !/^\d{2}:\d{2}(:\d{2})?$/.test(end)
  )
    return "ساعت شروع و پایان را وارد کنید.";
  if (
    [start, end].some((value) => {
      const [hour, minute, second = "0"] = value.split(":").map(Number);
      return hour > 23 || minute > 59 || Number(second) > 59;
    })
  )
    return "ساعت معتبر وارد کنید.";
  if (start.slice(0, 5) >= end.slice(0, 5))
    return "ساعت پایان باید بعد از ساعت شروع باشد.";
  return null;
}

/** Only warn about conflicts surviving the manager's explicitly selected actions. */
export function selectedScheduleConflicts(
  preview: SchedulePreview,
  choices: PreviewChoice[],
  removeIds: number[],
) {
  const active = new Set(
    choices
      .filter(
        (choice) => choice.action === "add" || choice.action === "replace",
      )
      .map((choice) => `row-${choice.index}`),
  );
  const removed = new Set([
    ...removeIds,
    ...choices.flatMap((choice) =>
      choice.action === "replace" ? choice.replace_ids || [] : [],
    ),
  ]);
  const survives = (reference: string | number) => {
    const ref = String(reference);
    if (ref.startsWith("row-")) return active.has(ref);
    const id = Number(ref.replace(/^existing-/, ""));
    return !removed.has(id);
  };
  return preview.conflicts.filter(
    (conflict) => survives(conflict.left) && survives(conflict.right),
  );
}
export function assignmentConflictId(reference: string | number) {
  return Number(String(reference).replace(/^existing-/, ""));
}

import assert from "node:assert/strict";
import test from "node:test";
import {
  addCalendarDays,
  attendanceChanges,
  automaticSelection,
  saturdayOfWeek,
  supervisorPages,
  tehranToday,
  type AttendanceStudent,
} from "../src/lib/staff.ts";

function student(
  id: number,
  record?: Partial<NonNullable<AttendanceStudent["record"]>>,
): AttendanceStudent {
  return {
    id,
    identifier: String(id),
    first_name: "آراد",
    last_name: "احمدی",
    record: record
      ? {
          id,
          status: "absent",
          source: "manual",
          revision: 3,
          created_at: "2026-10-14T00:00:00Z",
          updated_at: "2026-10-14T00:00:00Z",
          recorder: { id: 9, name: "مراقب" },
          early_departure: false,
          departed_at: null,
          can_edit: true,
          ...record,
        }
      : null,
  };
}
test("supervisor business date follows Tehran across UTC midnight", () => {
  assert.equal(tehranToday(new Date("2026-10-14T20:29:59Z")), "2026-10-14");
  assert.equal(tehranToday(new Date("2026-10-14T20:30:00Z")), "2026-10-15");
});
test("weekly navigation starts Saturday and crosses Gregorian year safely", () => {
  assert.equal(saturdayOfWeek("2026-10-14"), "2026-10-10");
  assert.equal(saturdayOfWeek("2026-10-10"), "2026-10-10");
  assert.equal(addCalendarDays("2026-12-28", 7), "2027-01-04");
  assert.equal(addCalendarDays("2027-01-04", -7), "2026-12-28");
});
test("manual attendance sends deliberate changes and retains concurrency revisions", () => {
  assert.deepEqual(
    attendanceChanges([student(1), student(2, { revision: 8 })], {
      1: "present",
      2: "late",
    }),
    [
      { student: 1, status: "present" },
      { student: 2, status: "late", revision: 8 },
    ],
  );
});
test("bulk drafts cannot include protected ownership or unchanged records", () => {
  const roster = [
    student(1, { can_edit: false }),
    student(2, { status: "present" }),
    student(3),
  ];
  assert.deepEqual(
    attendanceChanges(roster, { 1: "late", 2: "present", 99: "absent" }),
    [],
  );
});
test("automatic defaults require explicit server eligibility and preserve manual records", () => {
  assert.deepEqual(
    automaticSelection([
      { ...student(1), selectable: true },
      { ...student(2, { source: "automatic" }), selectable: true },
      { ...student(3, { source: "manual" }), selectable: true },
      { ...student(4), selectable: false },
      student(5),
    ]),
    [1, 2],
  );
});
test("portal includes every requested supervisor workflow without manager routes", () => {
  assert.deepEqual(supervisorPages, [
    "dashboard",
    "halls",
    "students",
    "presence",
    "attendance",
    "schedule",
    "profile",
  ]);
});

test("automatic selection prioritizes unrecorded students for successive bounded saves", () => {
  const rows = [
    { ...student(1, { source: "automatic" }), selectable: true },
    { ...student(2), selectable: true },
    { ...student(3, { source: "automatic" }), selectable: true },
    { ...student(4), selectable: true },
  ];
  assert.deepEqual(automaticSelection(rows), [2, 4, 1, 3]);
  assert.deepEqual(
    rows.map((row) => row.id),
    [1, 2, 3, 4],
  );
});
